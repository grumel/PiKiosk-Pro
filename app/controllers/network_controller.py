# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - WLAN-Verwaltung im Dashboard.

Stellt Scan, Verbinden und Trennen als HTMX-Endpunkte fuer die
WLAN-Kachel bereit. Alle nmcli-Fehler werden als verstaendliche
Meldungen angezeigt.
"""

from typing import Any

from flask import Blueprint, render_template, request
from flask_login import login_required

from app.controllers import current_services, current_texts
from app.exceptions import NetworkError, WifiError

network_blueprint = Blueprint("network", __name__, url_prefix="/dashboard/wifi")


def _connection_info() -> dict[str, Any] | None:
    """Ermittelt die Daten der aktiven WLAN-Verbindung.

    Returns:
        Verbindungsdaten oder None ohne aktive Verbindung.
    """
    services = current_services()
    try:
        active = services.network_service.current()
        if active is None:
            return None
        return {
            "ssid": active["ssid"],
            "signal": active["signal"],
            "security": active["security"],
            "ip": services.network_service.ip(),
            "gateway": services.network_service.gateway(),
            "dns": ", ".join(services.network_service.dns()),
        }
    except NetworkError:
        return None


def _render_tile(**context: Any) -> str:
    """Rendert die WLAN-Kachel.

    Args:
        context:
            Zusaetzliche Template-Variablen.

    Returns:
        Das gerenderte Kachel-Fragment.
    """
    return render_template(
        "dashboard/_wifi_tile.html",
        texts=current_texts(),
        connection=_connection_info(),
        **context,
    )


@network_blueprint.get("/")
@login_required
def status() -> str:
    """Zeigt den aktuellen WLAN-Status der Kachel.

    Returns:
        Die WLAN-Kachel mit der aktiven Verbindung.
    """
    return _render_tile()


@network_blueprint.post("/scan")
@login_required
def scan() -> str:
    """Sucht verfuegbare WLAN-Netzwerke.

    Returns:
        Die WLAN-Kachel mit Netzwerkliste.
    """
    try:
        networks = current_services().network_service.scan()
    except NetworkError as error:
        return _render_tile(error=str(error))
    return _render_tile(networks=networks)


@network_blueprint.post("/connect")
@login_required
def connect() -> str:
    """Verbindet das Geraet mit dem gewaehlten WLAN.

    Returns:
        Die aktualisierte WLAN-Kachel.
    """
    texts = current_texts()
    ssid = request.form.get("ssid", "").strip()
    password = request.form.get("password", "")
    try:
        current_services().network_service.connect(ssid, password)
    except WifiError as error:
        message = texts.get(f"wifi_error_{error.reason}", str(error))
        return _render_tile(error=message)
    except NetworkError as error:
        return _render_tile(error=str(error))
    return _render_tile(message=texts["wifi_connected"])


@network_blueprint.post("/disconnect")
@login_required
def disconnect() -> str:
    """Trennt die aktive WLAN-Verbindung.

    Returns:
        Die aktualisierte WLAN-Kachel.
    """
    texts = current_texts()
    try:
        current_services().network_service.disconnect()
    except NetworkError as error:
        return _render_tile(error=str(error))
    return _render_tile(message=texts["wifi_disconnected"])
