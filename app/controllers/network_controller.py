# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - WLAN-Verwaltung im Dashboard.

Stellt Scan, Verbinden, Trennen und das Standard-WLAN als
HTMX-Endpunkte fuer die WLAN-Kachel bereit. Alle nmcli-Fehler
werden als verstaendliche Meldungen angezeigt.
"""

from typing import Any

from flask import Blueprint, render_template, request
from flask_login import login_required

from app.constants import PREFERRED_WIFI_PRIORITY
from app.controllers import current_services, current_texts
from app.exceptions import NetworkError, PiKioskError, WifiError

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


def _saved_profiles() -> list[str]:
    """Liefert die gespeicherten WLAN-Profile.

    Returns:
        Namen der gespeicherten Profile, leer bei Fehlern.
    """
    try:
        return current_services().network_service.saved()
    except NetworkError:
        return []


def _render_tile(**context: Any) -> str:
    """Rendert die WLAN-Kachel.

    Args:
        context:
            Zusaetzliche Template-Variablen.

    Returns:
        Das gerenderte Kachel-Fragment.
    """
    config = current_services().config_service.load()
    return render_template(
        "dashboard/_wifi_tile.html",
        texts=current_texts(),
        connection=_connection_info(),
        preferred_ssid=config["wifi_preferred_ssid"],
        saved_profiles=_saved_profiles(),
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


@network_blueprint.post("/preferred")
@login_required
def save_preferred() -> str:
    """Legt das Standard-WLAN fest.

    Wird ein Passwort mitgegeben, speichert NetworkManager es
    dauerhaft im Verbindungsprofil (systemweit, automatische
    Verbindung mit hoher Prioritaet) - das Geraet verbindet sich
    dann nach jedem Neustart von selbst. Ohne Passwort wird bei
    einem vorhandenen Profil nur die automatische Verbindung
    aktiviert. Der Kiosk selbst speichert keine Passwoerter.

    Returns:
        Die aktualisierte WLAN-Kachel.
    """
    texts = current_texts()
    services = current_services()
    ssid = request.form.get("preferred_ssid", "").strip()
    password = request.form.get("preferred_password", "")
    if ssid:
        try:
            if password:
                services.network_service.save_profile(
                    ssid, password, priority=PREFERRED_WIFI_PRIORITY
                )
            else:
                services.network_service.set_autoconnect(ssid, PREFERRED_WIFI_PRIORITY)
        except WifiError as error:
            message = texts.get(f"wifi_error_{error.reason}", str(error))
            return _render_tile(error=message)
        except PiKioskError as error:
            return _render_tile(error=str(error))
    config = services.config_service.load()
    config["wifi_preferred_ssid"] = ssid
    try:
        services.config_service.save(config)
    except PiKioskError as error:
        return _render_tile(error=str(error))
    if not ssid:
        return _render_tile(message=texts["wifi_preferred_cleared"])
    return _render_tile(message=texts["wifi_preferred_saved"].format(ssid=ssid))


@network_blueprint.post("/preferred/connect")
@login_required
def connect_preferred() -> str:
    """Verbindet mit dem hinterlegten Standard-WLAN.

    Returns:
        Die aktualisierte WLAN-Kachel.
    """
    texts = current_texts()
    services = current_services()
    ssid = str(services.config_service.load()["wifi_preferred_ssid"])
    try:
        services.network_service.connect_saved(ssid)
    except WifiError as error:
        message = texts.get(f"wifi_error_{error.reason}", str(error))
        return _render_tile(error=f"{message} ({error})")
    except PiKioskError as error:
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
