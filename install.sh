#!/usr/bin/env bash
# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
#
# PiKiosk Pro - Installationsskript.
# Installiert alle Systempakete, die Python-Umgebung und den
# systemd-Dienst und aktiviert Autologin sowie Autostart.
# Aufruf: sudo ./install.sh
#
# Dieses Skript veraendert keine Konfigurationsdateien der
# Anwendung. Die Konfiguration wird ausschliesslich von der
# Python-Anwendung selbst erzeugt und verwaltet.

set -euo pipefail

INSTALL_DIR="/opt/pikiosk-pro"
SERVICE_NAMES=("pikiosk.service" "pikiosk-watchdog.service")
POLKIT_RULE_FILE="/etc/polkit-1/rules.d/50-pikiosk-networkmanager.rules"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${SOURCE_DIR}/logs/install.log"

log() {
    local message="$1"
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "${timestamp} | INSTALL | ${message}" | tee -a "${LOG_FILE}"
}

fail() {
    log "FEHLER: $1"
    exit 1
}

require_root() {
    if [[ "$(id -u)" -ne 0 ]]; then
        fail "Bitte mit sudo ausfuehren: sudo ./install.sh"
    fi
}

determine_kiosk_user() {
    if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
        KIOSK_USER="${SUDO_USER}"
    elif id pi >/dev/null 2>&1; then
        KIOSK_USER="pi"
    else
        fail "Kein Kioskbenutzer gefunden. Bitte mit sudo als normaler Benutzer ausfuehren."
    fi
    log "Kioskbenutzer: ${KIOSK_USER}"
}

install_packages() {
    log "Systempakete werden installiert."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y >>"${LOG_FILE}" 2>&1
    apt-get install -y \
        python3 python3-venv python3-pip \
        network-manager git rsync >>"${LOG_FILE}" 2>&1
    if ! apt-get install -y chromium-browser >>"${LOG_FILE}" 2>&1; then
        apt-get install -y chromium >>"${LOG_FILE}" 2>&1 \
            || fail "Chromium konnte nicht installiert werden."
    fi
    log "Systempakete installiert."
}

copy_project() {
    if [[ "${SOURCE_DIR}" == "${INSTALL_DIR}" ]]; then
        log "Installation laeuft bereits im Zielverzeichnis."
        return
    fi
    log "Projekt wird nach ${INSTALL_DIR} kopiert."
    mkdir -p "${INSTALL_DIR}"
    # Laufzeitdaten einer bestehenden Installation bleiben erhalten:
    # Konfiguration, Benutzer, Schluessel, TLS-Zertifikate und
    # Sicherungen liegen nicht im Repository und duerfen von
    # --delete niemals entfernt werden.
    rsync -a --delete \
        --exclude ".venv" \
        --exclude "logs/*.log" \
        --exclude "config/config.json" \
        --exclude "config/users.db" \
        --exclude "config/secret_key" \
        --exclude "config/api_key" \
        --exclude "config/tls" \
        --exclude "config/center_devices.db" \
        --exclude "config/center_users.db" \
        --exclude "config/center_key" \
        --exclude "backup" \
        "${SOURCE_DIR}/" "${INSTALL_DIR}/"
    chown -R "${KIOSK_USER}:${KIOSK_USER}" "${INSTALL_DIR}"
    log "Projekt kopiert (Konfiguration und Schluessel bleiben erhalten)."
}

create_virtualenv() {
    log "Python-Umgebung wird erstellt."
    sudo -u "${KIOSK_USER}" python3 -m venv "${INSTALL_DIR}/.venv"
    # shellcheck disable=SC2024  # Skript laeuft als root, Logdatei gehoert root.
    sudo -u "${KIOSK_USER}" "${INSTALL_DIR}/.venv/bin/pip" install \
        --upgrade pip >>"${LOG_FILE}" 2>&1
    local requirements="${INSTALL_DIR}/requirements.txt"
    if [[ -f "${INSTALL_DIR}/requirements.lock" ]]; then
        requirements="${INSTALL_DIR}/requirements.lock"
    fi
    # shellcheck disable=SC2024  # Skript laeuft als root, Logdatei gehoert root.
    sudo -u "${KIOSK_USER}" "${INSTALL_DIR}/.venv/bin/pip" install \
        -r "${requirements}" >>"${LOG_FILE}" 2>&1
    log "Python-Umgebung erstellt."
}

install_service() {
    log "systemd-Dienste werden installiert."
    local service_name
    for service_name in "${SERVICE_NAMES[@]}"; do
        sed -e "s|__KIOSK_USER__|${KIOSK_USER}|g" \
            -e "s|__INSTALL_DIR__|${INSTALL_DIR}|g" \
            "${INSTALL_DIR}/services/${service_name}" \
            >"/etc/systemd/system/${service_name}"
    done
    systemctl daemon-reload
    for service_name in "${SERVICE_NAMES[@]}"; do
        systemctl enable "${service_name}" >>"${LOG_FILE}" 2>&1
    done
    log "systemd-Dienste aktiviert."
}

install_sudoers() {
    log "sudo-Regeln fuer Hostname, Neustart und Herunterfahren werden installiert."
    cat >/etc/sudoers.d/pikiosk <<EOF
${KIOSK_USER} ALL=(root) NOPASSWD: ${INSTALL_DIR}/.venv/bin/python ${INSTALL_DIR}/scripts/hostname_apply.py *
${KIOSK_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl reboot
${KIOSK_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl poweroff
EOF
    chmod 440 /etc/sudoers.d/pikiosk
    log "sudo-Regeln installiert."
}

install_tls_certificate() {
    local tls_dir="${INSTALL_DIR}/config/tls"
    if [[ -f "${tls_dir}/cert.pem" && -f "${tls_dir}/key.pem" ]]; then
        log "TLS-Zertifikat vorhanden, wird beibehalten."
        return
    fi
    if ! command -v openssl >/dev/null 2>&1; then
        log "WARNUNG: openssl fehlt, Weboberflaeche laeuft ohne TLS."
        return
    fi
    log "Selbstsigniertes TLS-Zertifikat wird erzeugt."
    local host_name
    host_name="$(hostname)"
    mkdir -p "${tls_dir}"
    if openssl req -x509 -newkey ec \
        -pkeyopt ec_paramgen_curve:prime256v1 \
        -keyout "${tls_dir}/key.pem" \
        -out "${tls_dir}/cert.pem" \
        -days 3650 -nodes \
        -subj "/CN=${host_name}" \
        -addext "subjectAltName=DNS:${host_name},DNS:${host_name}.local,DNS:localhost,IP:127.0.0.1" \
        >>"${LOG_FILE}" 2>&1; then
        chmod 600 "${tls_dir}/key.pem"
        chmod 644 "${tls_dir}/cert.pem"
        chown -R "${KIOSK_USER}:${KIOSK_USER}" "${tls_dir}"
        log "TLS-Zertifikat erzeugt: ${tls_dir} (Weboberflaeche: https://<adresse>:8080)"
        log "Eigenes Zertifikat: cert.pem und key.pem in ${tls_dir} ersetzen."
    else
        rm -f "${tls_dir}/key.pem" "${tls_dir}/cert.pem"
        log "WARNUNG: Zertifikat konnte nicht erzeugt werden, Weboberflaeche laeuft ohne TLS."
    fi
}

install_polkit_rule() {
    log "polkit-Regel fuer NetworkManager wird installiert."
    if [[ ! -d /etc/polkit-1/rules.d ]]; then
        log "WARNUNG: /etc/polkit-1/rules.d fehlt, WLAN-Aenderungen koennten scheitern."
        return
    fi
    sed "s|__KIOSK_USER__|${KIOSK_USER}|g" \
        "${INSTALL_DIR}/services/pikiosk-networkmanager.rules" \
        >"${POLKIT_RULE_FILE}"
    chmod 644 "${POLKIT_RULE_FILE}"
    systemctl restart polkit >>"${LOG_FILE}" 2>&1 \
        || log "WARNUNG: polkit konnte nicht neu gestartet werden."
    log "polkit-Regel installiert: ${POLKIT_RULE_FILE}"
}

enable_autologin() {
    if command -v raspi-config >/dev/null 2>&1; then
        log "Autologin (Desktop) wird aktiviert."
        raspi-config nonint do_boot_behaviour B4 >>"${LOG_FILE}" 2>&1 \
            || log "WARNUNG: Autologin konnte nicht aktiviert werden."
    else
        log "WARNUNG: raspi-config nicht gefunden, Autologin bitte manuell aktivieren."
    fi
}

start_service() {
    log "Dienste werden gestartet."
    local service_name
    for service_name in "${SERVICE_NAMES[@]}"; do
        systemctl restart "${service_name}"
    done
    log "Installation abgeschlossen. PiKiosk Pro laeuft nach dem naechsten Neustart automatisch."
}

main() {
    mkdir -p "${SOURCE_DIR}/logs"
    log "Installation von PiKiosk Pro beginnt."
    require_root
    determine_kiosk_user
    install_packages
    copy_project
    create_virtualenv
    install_service
    install_sudoers
    install_tls_certificate
    install_polkit_rule
    enable_autologin
    start_service
}

main "$@"
