#!/usr/bin/env bash
# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
#
# PiKiosk Pro - Diagnoseskript.
#
# Gibt einen kompakten Statusbericht ueber Kiosk-Dienste, Desktop-
# bzw. Display-Umgebung, NetworkManager, das hinterlegte Standard-
# WLAN und die aktive Verbindung aus. Es werden ausschliesslich
# nicht-vertrauliche Informationen ausgegeben; WLAN-Passwoerter
# werden nie angezeigt oder abgefragt.
#
# Aufruf:
#   scripts/diagnose.sh
#
# Das Skript veraendert nichts am System und benoetigt keine
# Root-Rechte; einzelne Detailangaben sind ohne Root ggf. leer.

set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
INSTALL_DIR="$(dirname -- "${SCRIPT_DIR}")"
CONFIG_FILE="${INSTALL_DIR}/config/config.json"
LOG_DIR="${INSTALL_DIR}/logs"

heading() {
    printf '\n=== %s ===\n' "$1"
}

field() {
    printf '  %-22s %s\n' "$1" "$2"
}

# Liest einen Stringwert aus der config.json, ohne zusaetzliche
# Werkzeuge vorauszusetzen (Python gehoert zur Laufzeit dazu).
read_config() {
    local key="$1"
    if [[ ! -f "${CONFIG_FILE}" ]]; then
        printf ''
        return
    fi
    python3 - "${CONFIG_FILE}" "${key}" <<'PY' 2>/dev/null || printf ''
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        data = json.load(handle)
except (OSError, ValueError):
    sys.exit(1)
value = data.get(sys.argv[2], "")
print(value if isinstance(value, str) else "")
PY
}

service_state() {
    local unit="$1"
    if ! command -v systemctl >/dev/null 2>&1; then
        printf 'systemctl nicht verfuegbar'
        return
    fi
    local active enabled
    active="$(systemctl is-active "${unit}" 2>/dev/null || true)"
    enabled="$(systemctl is-enabled "${unit}" 2>/dev/null || true)"
    printf '%s (%s)' "${active:-unbekannt}" "${enabled:-unbekannt}"
}

printf 'PiKiosk Pro - Diagnosebericht\n'
field "Installationsverzeichnis" "${INSTALL_DIR}"
field "Zeitpunkt" "$(date '+%Y-%m-%d %H:%M:%S')"

heading "Kiosk-Dienste"
field "pikiosk.service" "$(service_state pikiosk.service)"
field "pikiosk-keymon" "$(service_state pikiosk-keymon.service)"
field "pikiosk-watchdog" "$(service_state pikiosk-watchdog.service)"

heading "Desktop- / Display-Umgebung"
field "Session-Typ" "${XDG_SESSION_TYPE:-unbekannt}"
field "Wayland-Display" "${WAYLAND_DISPLAY:-(keiner)}"
field "X11-Display" "${DISPLAY:-(keiner)}"
compositor="(nicht erkannt)"
for candidate in labwc wayfire wlroots lxsession openbox mutter; do
    if pgrep -x "${candidate}" >/dev/null 2>&1; then
        compositor="${candidate}"
        break
    fi
done
field "Compositor/Session" "${compositor}"

heading "NetworkManager"
field "Dienst" "$(service_state NetworkManager.service)"
if command -v nmcli >/dev/null 2>&1; then
    field "Networking" "$(nmcli networking 2>/dev/null || echo unbekannt)"
    active_ssid="$(nmcli -t -f ACTIVE,SSID device wifi 2>/dev/null \
        | awk -F: '$1=="yes"{print $2; exit}')"
    field "Aktives WLAN" "${active_ssid:-(keins)}"
else
    field "nmcli" "nicht installiert"
fi

heading "Standard-WLAN (hinterlegt)"
preferred="$(read_config wifi_preferred_ssid)"
field "Konfigurierte SSID" "${preferred:-(keine)}"
if [[ -n "${preferred}" ]] && command -v nmcli >/dev/null 2>&1; then
    if nmcli -t -f NAME,TYPE connection show 2>/dev/null \
        | awk -F: '{print $1}' | grep -Fxq "${preferred}"; then
        field "NM-Profil vorhanden" "ja"
        autoconnect="$(nmcli -t -f connection.autoconnect connection show \
            "${preferred}" 2>/dev/null | awk -F: '{print $2}')"
        priority="$(nmcli -t -f connection.autoconnect-priority connection show \
            "${preferred}" 2>/dev/null | awk -F: '{print $2}')"
        field "Automatische Verbindung" "${autoconnect:-unbekannt}"
        field "Prioritaet" "${priority:-unbekannt}"
    else
        field "NM-Profil vorhanden" "NEIN - Passwort im Dashboard hinterlegen"
    fi
fi

heading "Kiosk-Tastenkombination"
field "Kombination" "$(read_config escape_hotkey || echo unbekannt)"
if [[ -x "${INSTALL_DIR}/.venv/bin/python" ]]; then
    # Exit-Code 1 bedeutet "nicht bereit" und ist kein Skriptfehler.
    ( cd "${INSTALL_DIR}" && .venv/bin/python -m app.keymon --check ) 2>/dev/null
else
    field "Selbsttest" ".venv nicht gefunden - im Installationsverzeichnis pruefen"
fi

heading "Logdateien"
if [[ -d "${LOG_DIR}" ]]; then
    for logfile in system browser watchdog network install update; do
        path="${LOG_DIR}/${logfile}.log"
        if [[ -f "${path}" ]]; then
            field "${logfile}.log" "${path}"
        fi
    done
else
    field "Verzeichnis" "${LOG_DIR} nicht vorhanden"
fi

printf '\nHinweis: WLAN-Passwoerter werden bewusst nicht ausgegeben.\n'
