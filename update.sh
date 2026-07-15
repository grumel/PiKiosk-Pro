#!/usr/bin/env bash
# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
#
# PiKiosk Pro - Aktualisierungsskript.
# Holt die neueste Version aus dem Git-Repository, aktualisiert
# die Python-Abhaengigkeiten und startet den Dienst neu.
# Aufruf: sudo ./update.sh
#
# Dieses Skript veraendert keine Konfigurationsdateien der
# Anwendung.

set -euo pipefail

INSTALL_DIR="/opt/pikiosk-pro"
SERVICE_NAME="pikiosk.service"
LOG_FILE="${INSTALL_DIR}/logs/update.log"

log() {
    local message="$1"
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "${timestamp} | UPDATE | ${message}" | tee -a "${LOG_FILE}"
}

fail() {
    log "FEHLER: $1"
    exit 1
}

require_root() {
    if [[ "$(id -u)" -ne 0 ]]; then
        fail "Bitte mit sudo ausfuehren: sudo ./update.sh"
    fi
}

main() {
    mkdir -p "${INSTALL_DIR}/logs"
    log "Aktualisierung beginnt."
    require_root
    if [[ ! -d "${INSTALL_DIR}/.git" ]]; then
        fail "Kein Git-Repository unter ${INSTALL_DIR} gefunden."
    fi
    systemctl stop "${SERVICE_NAME}" || true
    log "Dienst gestoppt."
    git -C "${INSTALL_DIR}" pull --ff-only >>"${LOG_FILE}" 2>&1 \
        || fail "Git-Aktualisierung fehlgeschlagen."
    log "Quellcode aktualisiert."
    "${INSTALL_DIR}/.venv/bin/pip" install \
        -r "${INSTALL_DIR}/requirements.txt" >>"${LOG_FILE}" 2>&1 \
        || fail "Python-Abhaengigkeiten konnten nicht aktualisiert werden."
    log "Abhaengigkeiten aktualisiert."
    systemctl start "${SERVICE_NAME}"
    log "Dienst gestartet. Aktualisierung abgeschlossen."
}

main "$@"
