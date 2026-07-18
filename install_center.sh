#!/usr/bin/env bash
# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
#
# PiKiosk Center - Installationsskript der Verwaltungszentrale.
# Installiert die Zentrale auf einem beliebigen Rechner im Netzwerk
# (Debian, Raspberry Pi OS). Die Geraete selbst bleiben unveraendert.
# Aufruf: sudo ./install_center.sh
#
# Dieses Skript veraendert keine Konfigurationsdateien der Anwendung.

set -euo pipefail

INSTALL_DIR="/opt/pikiosk-center"
SERVICE_NAME="pikiosk-center.service"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${SOURCE_DIR}/logs/install.log"

log() {
    local message="$1"
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "${timestamp} | CENTER-INSTALL | ${message}" | tee -a "${LOG_FILE}"
}

fail() {
    log "FEHLER: $1"
    exit 1
}

require_root() {
    if [[ "$(id -u)" -ne 0 ]]; then
        fail "Bitte mit sudo ausfuehren: sudo ./install_center.sh"
    fi
}

determine_center_user() {
    if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
        CENTER_USER="${SUDO_USER}"
    else
        fail "Bitte mit sudo als normaler Benutzer ausfuehren."
    fi
    log "Benutzer der Zentrale: ${CENTER_USER}"
}

install_packages() {
    log "Systempakete werden installiert."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y >>"${LOG_FILE}" 2>&1
    apt-get install -y \
        python3 python3-venv python3-pip git rsync >>"${LOG_FILE}" 2>&1
    log "Systempakete installiert."
}

copy_project() {
    if [[ "${SOURCE_DIR}" == "${INSTALL_DIR}" ]]; then
        log "Installation laeuft bereits im Zielverzeichnis."
        return
    fi
    log "Projekt wird nach ${INSTALL_DIR} kopiert."
    mkdir -p "${INSTALL_DIR}"
    rsync -a --delete \
        --exclude ".venv" \
        --exclude "logs/*.log" \
        "${SOURCE_DIR}/" "${INSTALL_DIR}/"
    chown -R "${CENTER_USER}:${CENTER_USER}" "${INSTALL_DIR}"
    log "Projekt kopiert."
}

create_virtualenv() {
    log "Python-Umgebung wird erstellt."
    sudo -u "${CENTER_USER}" python3 -m venv "${INSTALL_DIR}/.venv"
    sudo -u "${CENTER_USER}" "${INSTALL_DIR}/.venv/bin/pip" install \
        --upgrade pip >>"${LOG_FILE}" 2>&1
    sudo -u "${CENTER_USER}" "${INSTALL_DIR}/.venv/bin/pip" install \
        -r "${INSTALL_DIR}/requirements.txt" >>"${LOG_FILE}" 2>&1
    log "Python-Umgebung erstellt."
}

install_service() {
    log "systemd-Dienst wird installiert."
    sed -e "s|__CENTER_USER__|${CENTER_USER}|g" \
        -e "s|__INSTALL_DIR__|${INSTALL_DIR}|g" \
        "${INSTALL_DIR}/services/${SERVICE_NAME}" \
        >"/etc/systemd/system/${SERVICE_NAME}"
    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}" >>"${LOG_FILE}" 2>&1
    log "systemd-Dienst aktiviert."
}

install_tls_certificate() {
    local tls_dir="${INSTALL_DIR}/config/tls"
    if [[ -f "${tls_dir}/cert.pem" && -f "${tls_dir}/key.pem" ]]; then
        log "TLS-Zertifikat vorhanden, wird beibehalten."
        return
    fi
    if ! command -v openssl >/dev/null 2>&1; then
        log "WARNUNG: openssl fehlt, Zentrale laeuft ohne TLS."
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
        chown -R "${CENTER_USER}:${CENTER_USER}" "${tls_dir}"
        log "TLS-Zertifikat erzeugt: ${tls_dir}"
        log "Eigenes Zertifikat: cert.pem und key.pem in ${tls_dir} ersetzen."
    else
        rm -f "${tls_dir}/key.pem" "${tls_dir}/cert.pem"
        log "WARNUNG: Zertifikat konnte nicht erzeugt werden, Zentrale laeuft ohne TLS."
    fi
}

start_service() {
    log "Dienst wird gestartet."
    systemctl restart "${SERVICE_NAME}"
    log "Installation abgeschlossen."
    local scheme="http"
    if [[ -f "${INSTALL_DIR}/config/tls/cert.pem" ]]; then
        scheme="https"
    fi
    log "Die Zentrale ist erreichbar unter: ${scheme}://$(hostname -I | awk '{print $1}'):8090/"
    log "Beim ersten Aufruf wird das Administratorkonto der Zentrale angelegt."
}

main() {
    mkdir -p "${SOURCE_DIR}/logs"
    log "Installation der Zentrale beginnt."
    require_root
    determine_center_user
    install_packages
    copy_project
    create_virtualenv
    install_service
    install_tls_certificate
    start_service
}

main "$@"
