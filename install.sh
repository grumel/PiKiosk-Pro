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
SERVICE_NAME="pikiosk.service"
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
    rsync -a --delete \
        --exclude ".git" \
        --exclude ".venv" \
        --exclude "logs/*.log" \
        "${SOURCE_DIR}/" "${INSTALL_DIR}/"
    chown -R "${KIOSK_USER}:${KIOSK_USER}" "${INSTALL_DIR}"
    log "Projekt kopiert."
}

create_virtualenv() {
    log "Python-Umgebung wird erstellt."
    sudo -u "${KIOSK_USER}" python3 -m venv "${INSTALL_DIR}/.venv"
    sudo -u "${KIOSK_USER}" "${INSTALL_DIR}/.venv/bin/pip" install \
        --upgrade pip >>"${LOG_FILE}" 2>&1
    sudo -u "${KIOSK_USER}" "${INSTALL_DIR}/.venv/bin/pip" install \
        -r "${INSTALL_DIR}/requirements.txt" >>"${LOG_FILE}" 2>&1
    log "Python-Umgebung erstellt."
}

install_service() {
    log "systemd-Dienst wird installiert."
    sed -e "s|__KIOSK_USER__|${KIOSK_USER}|g" \
        -e "s|__INSTALL_DIR__|${INSTALL_DIR}|g" \
        "${INSTALL_DIR}/services/${SERVICE_NAME}" \
        >"/etc/systemd/system/${SERVICE_NAME}"
    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}" >>"${LOG_FILE}" 2>&1
    log "systemd-Dienst aktiviert."
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
    log "Dienst wird gestartet."
    systemctl restart "${SERVICE_NAME}"
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
    enable_autologin
    start_service
}

main "$@"
