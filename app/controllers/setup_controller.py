# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Setup-Wizard.

Fuehrt die Ersteinrichtung des Kiosksystems durch: Hostname, WLAN,
Administratorkonto und Kiosk-URL. Der Wizard laeuft ausschliesslich
beim ersten Start, alle Eingaben werden sofort geprueft und
ungueltige Eingaben niemals gespeichert. Passwoerter werden nur als
bcrypt-Hash in der Sitzung gehalten.
"""

import socket
from typing import Any

from flask import Blueprint, abort, render_template, request, session

from app.constants import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_ADMIN_USERNAME,
    SETUP_STEPS,
)
from app.controllers import current_services as _services
from app.controllers import current_texts as _texts
from app.controllers import ensure_csrf_token
from app.exceptions import (
    NetworkError,
    PiKioskError,
    ValidationError,
    WifiError,
)
from app.utils.helpers import device_model
from app.utils.network import check_url_status
from app.utils.validators import URLValidator

setup_blueprint = Blueprint("setup", __name__, url_prefix="/setup")

SESSION_STATE_KEY: str = "setup_state"
REQUIRED_STATE_KEYS: tuple[str, ...] = (
    "hostname",
    "admin_username",
    "admin_password_hash",
    "url",
)


def _state() -> dict[str, Any]:
    """Liefert den Wizard-Zustand aus der Sitzung.

    Returns:
        Der aktuelle Wizard-Zustand.
    """
    state: dict[str, Any] = session.setdefault(SESSION_STATE_KEY, {})
    return state


def _update_state(**values: Any) -> None:
    """Schreibt Werte in den Wizard-Zustand.

    Args:
        values:
            Zu speichernde Schluessel und Werte.
    """
    state = _state()
    state.update(values)
    session[SESSION_STATE_KEY] = state
    session.modified = True


def _render_step(name: str, **context: Any) -> str:
    """Rendert ein Schritt-Fragment des Wizards.

    Args:
        name:
            Name des Wizard-Schritts.

        context:
            Zusaetzliche Template-Variablen.

    Returns:
        Das gerenderte HTML-Fragment.
    """
    return render_template(
        f"setup/_{name}.html",
        texts=_texts(),
        state=_state(),
        app_name=APP_NAME,
        app_version=APP_VERSION,
        current_language=_services().config_service.load()["language"],
        **context,
    )


def _connection_info() -> dict[str, Any] | None:
    """Ermittelt die Daten der aktiven WLAN-Verbindung.

    Returns:
        Verbindungsdaten oder None ohne aktive Verbindung.
    """
    services = _services()
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


@setup_blueprint.get("/")
def wizard() -> str:
    """Rendert die Wizard-Seite mit dem Willkommensschritt.

    Returns:
        Die vollstaendige Wizard-Seite.
    """
    ensure_csrf_token()
    config = _services().config_service.load()
    return render_template(
        "setup.html",
        texts=_texts(),
        theme=config["theme"],
        state=_state(),
        app_name=APP_NAME,
        app_version=APP_VERSION,
        device=device_model(),
        current_hostname=socket.gethostname(),
    )


@setup_blueprint.get("/step/<name>")
def step(name: str) -> str:
    """Rendert einen einzelnen Wizard-Schritt.

    Args:
        name:
            Name des Schritts.

    Returns:
        Das gerenderte Schritt-Fragment.
    """
    if name not in SETUP_STEPS:
        abort(404)
    context: dict[str, Any] = {}
    if name == "welcome":
        context["device"] = device_model()
    if name == "hostname":
        context["current_hostname"] = socket.gethostname()
    if name == "wifi":
        context["connection"] = _connection_info()
    return _render_step(name, **context)


@setup_blueprint.post("/language")
def save_language() -> str:
    """Stellt die Sprache des Wizards um.

    Returns:
        Das Willkommens-Fragment in der neuen Sprache.
    """
    services = _services()
    config = services.config_service.load()
    config["language"] = request.form.get("language", config["language"])
    try:
        services.config_service.save(config)
    except ValidationError as error:
        return _render_step("welcome", error=str(error), device=device_model())
    return _render_step("welcome", device=device_model())


@setup_blueprint.post("/hostname")
def save_hostname() -> str:
    """Prueft und uebernimmt den gewuenschten Hostnamen.

    Returns:
        Das aktualisierte Hostname-Fragment.
    """
    texts = _texts()
    hostname = request.form.get("hostname", "").strip()
    try:
        _services().hostname_service.validate(hostname)
    except ValidationError as error:
        return _render_step(
            "hostname", error=str(error), current_hostname=socket.gethostname()
        )
    if _services().hostname_service.is_taken(hostname):
        return _render_step(
            "hostname",
            error=texts["hostname_taken"],
            current_hostname=socket.gethostname(),
        )
    _update_state(hostname=hostname)
    return _render_step("hostname", success=True, current_hostname=socket.gethostname())


@setup_blueprint.post("/wifi/scan")
def wifi_scan() -> str:
    """Sucht verfuegbare WLAN-Netzwerke.

    Returns:
        Das Fragment mit der Netzwerkliste.
    """
    try:
        networks = _services().network_service.scan()
    except NetworkError as error:
        return render_template(
            "setup/_wifi_networks.html",
            texts=_texts(),
            networks=[],
            error=str(error),
        )
    return render_template(
        "setup/_wifi_networks.html", texts=_texts(), networks=networks, error=None
    )


@setup_blueprint.post("/wifi/connect")
def wifi_connect() -> str:
    """Verbindet das Geraet mit dem gewaehlten WLAN.

    Returns:
        Das aktualisierte WLAN-Fragment.
    """
    texts = _texts()
    ssid = request.form.get("ssid", "").strip()
    password = request.form.get("password", "")
    try:
        _services().network_service.connect(ssid, password)
    except WifiError as error:
        message = texts.get(f"wifi_error_{error.reason}", str(error))
        return _render_step("wifi", error=message, connection=_connection_info())
    except NetworkError as error:
        return _render_step("wifi", error=str(error), connection=_connection_info())
    _update_state(wifi_ssid=ssid)
    return _render_step("wifi", success=True, connection=_connection_info())


@setup_blueprint.post("/admin")
def save_admin() -> str:
    """Prueft und uebernimmt das Administratorkonto.

    Returns:
        Das aktualisierte Administrator-Fragment.
    """
    texts = _texts()
    services = _services()
    username = request.form.get("username", "").strip() or DEFAULT_ADMIN_USERNAME
    password = request.form.get("password", "")
    password_repeat = request.form.get("password_repeat", "")
    rules = services.auth_service.check_password_rules(password)
    if password != password_repeat:
        return _render_step(
            "admin", error=texts["password_mismatch"], rules=rules, username=username
        )
    if not all(rules.values()):
        return _render_step(
            "admin", error=texts["password_weak"], rules=rules, username=username
        )
    password_hash = services.auth_service.hash_password(password)
    _update_state(admin_username=username, admin_password_hash=password_hash)
    return _render_step("admin", success=True, rules=rules, username=username)


@setup_blueprint.post("/url")
def save_url() -> str:
    """Prueft und uebernimmt die Kiosk-URL.

    Returns:
        Das aktualisierte URL-Fragment.
    """
    texts = _texts()
    url = request.form.get("url", "").strip()
    try:
        URLValidator().validate(url)
        valid, status = check_url_status(url)
    except ValidationError as error:
        return _render_step("url", error=str(error))
    except NetworkError:
        return _render_step("url", error=texts["url_unreachable"])
    if not valid:
        return _render_step("url", error=f"{texts['url_invalid']} (HTTP {status})")
    _update_state(url=url)
    return _render_step("url", success=True, status=status)


@setup_blueprint.post("/install")
def install() -> str:
    """Fuehrt die Installation mit allen gesammelten Daten durch.

    Returns:
        Das Ergebnis-Fragment der Installation.
    """
    texts = _texts()
    services = _services()
    state = _state()
    if any(not state.get(key) for key in REQUIRED_STATE_KEYS):
        return _render_step("summary", error=texts["setup_incomplete"])
    try:
        services.hostname_service.set(str(state["hostname"]))
        if not services.auth_service.administrator_exists():
            services.auth_service.create_administrator(
                str(state["admin_username"]), str(state["admin_password_hash"])
            )
        config = services.config_service.load()
        config["hostname"] = state["hostname"]
        config["url"] = state["url"]
        config["first_start"] = False
        services.config_service.save(config)
        session.pop(SESSION_STATE_KEY, None)
        services.logger.info("Ersteinrichtung abgeschlossen.")
        return _render_step("install", success=True, redirect_url=config["url"])
    except PiKioskError as error:
        services.logger.error(f"Installation fehlgeschlagen: {error}", exc_info=True)
        return _render_step("install", success=False, error=str(error))
