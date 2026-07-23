#!/usr/bin/env bash
# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
#
# PiKiosk Pro - Geraeteidentitaet nach dem Klonen zuruecksetzen.
#
# Nach dem Klonen einer SSD/SD-Karte teilen sich alle Kopien die
# gleiche Maschinen-ID, dieselben SSH-Host-Keys, dasselbe
# TLS-Zertifikat und dieselben Sitzungs-/API-Schluessel. Im selben
# Netz fuehrt vor allem die doppelte Maschinen-ID zu IP-/DHCP-
# Kollisionen. Dieses Skript stellt pro Geraet eine frische,
# eindeutige Identitaet her:
#
#   1. Optionaler neuer Hostname (System + /etc/hosts + config.json)
#   2. Neue Maschinen-ID (/etc/machine-id, D-Bus)
#   3. Neue SSH-Host-Keys
#   4. Neues TLS-Zertifikat passend zum Hostnamen
#   5. Verwerfen von Sitzungs- und API-Schluessel (werden neu erzeugt)
#
# WLAN-Profile werden bewusst NICHT angetastet: Ein geklontes
# Standard-WLAN (inkl. Passwort) soll weiter funktionieren.
#
# Vor jeder Aenderung wird eine Sicherung angelegt. Das Skript ist
# idempotent und kann gefahrlos erneut ausgefuehrt werden.
#
# Aufruf (als root):
#   sudo /opt/pikiosk-pro/scripts/reset-device-identity.sh [neuer-hostname]
#
# Ohne Hostname-Argument bleibt der aktuelle Hostname erhalten und es
# werden nur Maschinen-ID, SSH-Keys, Zertifikat und Schluessel erneuert.

set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
INSTALL_DIR="$(dirname -- "${SCRIPT_DIR}")"
TLS_DIR="${INSTALL_DIR}/config/tls"
CONFIG_FILE="${INSTALL_DIR}/config/config.json"
SECRET_KEY_FILE="${INSTALL_DIR}/config/secret_key"
API_KEY_FILE="${INSTALL_DIR}/config/api_key"
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
BACKUP_DIR="${INSTALL_DIR}/backup/device-identity-${TIMESTAMP}"

log() {
    printf '[reset] %s\n' "$1"
}

die() {
    printf '[reset] FEHLER: %s\n' "$1" >&2
    exit 1
}

require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        die "Bitte mit sudo ausfuehren."
    fi
}

# Ermittelt den Kioskbenutzer (Eigentuemer des Installationsverzeichnisses,
# ersatzweise der sudo-Aufrufer, sonst 'pi').
kiosk_user() {
    local owner
    owner="$(stat -c '%U' "${INSTALL_DIR}" 2>/dev/null || true)"
    if [[ -n "${owner}" && "${owner}" != "root" && "${owner}" != "UNKNOWN" ]]; then
        printf '%s' "${owner}"
    else
        printf '%s' "${SUDO_USER:-pi}"
    fi
}

validate_hostname() {
    local name="$1"
    if [[ ${#name} -gt 63 ]]; then
        die "Hostname zu lang (max. 63 Zeichen)."
    fi
    if [[ ! "${name}" =~ ^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$ ]]; then
        die "Ungueltiger Hostname. Erlaubt: A-Z, a-z, 0-9, Bindestrich (nicht am Rand)."
    fi
}

backup_path() {
    # Sichert eine Datei/ein Verzeichnis unter Beibehaltung der Struktur.
    local source="$1"
    if [[ -e "${source}" ]]; then
        local target="${BACKUP_DIR}${source}"
        mkdir -p "$(dirname -- "${target}")"
        cp -a "${source}" "${target}" 2>/dev/null \
            && log "Gesichert: ${source}" || true
    fi
}

set_hostname() {
    local new_name="$1"
    local old_name
    old_name="$(hostname)"
    if [[ "${new_name}" == "${old_name}" ]]; then
        log "Hostname bereits '${new_name}', keine Aenderung."
        return
    fi
    backup_path /etc/hostname
    backup_path /etc/hosts
    if command -v hostnamectl >/dev/null 2>&1; then
        hostnamectl set-hostname "${new_name}" \
            || die "hostnamectl set-hostname fehlgeschlagen."
    else
        printf '%s\n' "${new_name}" >/etc/hostname
        hostname "${new_name}" || true
    fi
    # /etc/hosts: 127.0.1.1-Zeile setzen oder anlegen (behebt fehlenden
    # Eintrag, der sonst zu "Hostname nicht aufloesbar" fuehrt).
    if grep -qE '^127\.0\.1\.1[[:space:]]' /etc/hosts; then
        sed -i -E "s/^127\.0\.1\.1[[:space:]].*/127.0.1.1\t${new_name}/" /etc/hosts
    else
        printf '127.0.1.1\t%s\n' "${new_name}" >>/etc/hosts
    fi
    log "Hostname gesetzt: ${old_name} -> ${new_name}"
}

update_config_hostname() {
    local new_name="$1"
    [[ -f "${CONFIG_FILE}" ]] || return 0
    backup_path "${CONFIG_FILE}"
    local owner
    owner="$(kiosk_user)"
    if python3 - "${CONFIG_FILE}" "${new_name}" <<'PY'
import json
import sys

path, hostname = sys.argv[1], sys.argv[2]
try:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
except (OSError, ValueError):
    sys.exit(1)
data["hostname"] = hostname
with open(path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, ensure_ascii=False, indent=4)
    handle.write("\n")
PY
    then
        chown "${owner}:${owner}" "${CONFIG_FILE}" 2>/dev/null || true
        log "config.json: hostname aktualisiert."
    else
        log "WARNUNG: config.json konnte nicht aktualisiert werden."
    fi
}

reset_machine_id() {
    backup_path /etc/machine-id
    backup_path /var/lib/dbus/machine-id
    rm -f /etc/machine-id
    if command -v systemd-machine-id-setup >/dev/null 2>&1; then
        systemd-machine-id-setup >/dev/null 2>&1 \
            || die "systemd-machine-id-setup fehlgeschlagen."
    else
        die "systemd-machine-id-setup nicht gefunden."
    fi
    if command -v dbus-uuidgen >/dev/null 2>&1; then
        rm -f /var/lib/dbus/machine-id
        dbus-uuidgen --ensure=/var/lib/dbus/machine-id 2>/dev/null || true
    fi
    log "Maschinen-ID neu erzeugt (behebt DHCP-/IP-Kollisionen)."
}

reset_ssh_host_keys() {
    [[ -d /etc/ssh ]] || return 0
    if ! command -v ssh-keygen >/dev/null 2>&1; then
        log "WARNUNG: ssh-keygen fehlt, SSH-Host-Keys nicht erneuert."
        return 0
    fi
    local existing=(/etc/ssh/ssh_host_*)
    if [[ -e "${existing[0]}" ]]; then
        mkdir -p "${BACKUP_DIR}/etc/ssh"
        cp -a /etc/ssh/ssh_host_* "${BACKUP_DIR}/etc/ssh/" 2>/dev/null || true
        rm -f /etc/ssh/ssh_host_*
    fi
    ssh-keygen -A >/dev/null 2>&1 || die "ssh-keygen -A fehlgeschlagen."
    log "SSH-Host-Keys neu erzeugt."
}

reset_tls_certificate() {
    local owner host_name
    owner="$(kiosk_user)"
    host_name="$(hostname)"
    if ! command -v openssl >/dev/null 2>&1; then
        log "WARNUNG: openssl fehlt, TLS-Zertifikat nicht erneuert."
        return 0
    fi
    if [[ -d "${TLS_DIR}" ]]; then
        backup_path "${TLS_DIR}"
    fi
    mkdir -p "${TLS_DIR}"
    # Parameter identisch zu install.sh (install_tls_certificate).
    if openssl req -x509 -newkey ec \
        -pkeyopt ec_paramgen_curve:prime256v1 \
        -keyout "${TLS_DIR}/key.pem" \
        -out "${TLS_DIR}/cert.pem" \
        -days 3650 -nodes \
        -subj "/CN=${host_name}" \
        -addext "subjectAltName=DNS:${host_name},DNS:${host_name}.local,DNS:localhost,IP:127.0.0.1" \
        >/dev/null 2>&1; then
        chmod 600 "${TLS_DIR}/key.pem"
        chmod 644 "${TLS_DIR}/cert.pem"
        chown -R "${owner}:${owner}" "${TLS_DIR}"
        log "TLS-Zertifikat neu erzeugt (CN=${host_name})."
    else
        rm -f "${TLS_DIR}/key.pem" "${TLS_DIR}/cert.pem"
        log "WARNUNG: TLS-Zertifikat konnte nicht erzeugt werden."
    fi
}

reset_app_secrets() {
    for secret in "${SECRET_KEY_FILE}" "${API_KEY_FILE}"; do
        if [[ -f "${secret}" ]]; then
            backup_path "${secret}"
            rm -f "${secret}"
            log "Verworfen (wird beim Start neu erzeugt): $(basename -- "${secret}")"
        fi
    done
}

main() {
    local new_hostname=""
    if [[ $# -gt 1 ]]; then
        die "Zu viele Argumente. Aufruf: $0 [neuer-hostname]"
    fi
    if [[ $# -eq 1 ]]; then
        case "$1" in
            -h|--help)
                grep -E '^# ' "${BASH_SOURCE[0]}" | sed 's/^# //'
                return 0
                ;;
            *)
                new_hostname="$1"
                ;;
        esac
    fi
    require_root
    if [[ -n "${new_hostname}" ]]; then
        validate_hostname "${new_hostname}"
    fi

    log "Geraeteidentitaet wird zurueckgesetzt. Sicherung: ${BACKUP_DIR}"
    mkdir -p "${BACKUP_DIR}"

    if [[ -n "${new_hostname}" ]]; then
        set_hostname "${new_hostname}"
        update_config_hostname "${new_hostname}"
    else
        log "Kein Hostname angegeben - aktueller Hostname bleibt: $(hostname)"
    fi

    reset_machine_id
    reset_ssh_host_keys
    reset_tls_certificate
    reset_app_secrets

    log "Fertig. WLAN-Profile wurden bewusst nicht veraendert."
    log "Sicherung liegt unter: ${BACKUP_DIR}"
    log "Jetzt neu starten:  sudo reboot"
}

main "$@"
