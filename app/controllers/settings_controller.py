# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Einstellungen im Dashboard.

Verwaltet Kiosk-URL, Hostname und Darstellung (Sprache, Theme).
Die URL wird vor dem Speichern geprueft; nach erfolgreichem
Speichern startet ein laufender Browser automatisch mit der neuen
URL. Nach einer Darstellungsaenderung laedt die Seite neu, damit
Sprache und Theme sofort wirken. Ungueltige Eingaben werden
niemals gespeichert.
"""

from flask import Blueprint, Response, make_response, render_template, request
from flask_login import login_required

from app.controllers import current_services, current_texts
from app.exceptions import NetworkError, PiKioskError, ValidationError
from app.services.browser_service import BrowserStatus
from app.utils.network import check_url_status
from app.utils.validators import URLValidator

settings_blueprint = Blueprint("settings", __name__, url_prefix="/dashboard")


def _render_url_tile(**context: object) -> str:
    """Rendert die URL-Kachel.

    Args:
        context:
            Zusaetzliche Template-Variablen.

    Returns:
        Das gerenderte Kachel-Fragment.
    """
    config = current_services().config_service.load()
    return render_template(
        "dashboard/_url_tile.html",
        texts=current_texts(),
        url=config["url"],
        **context,
    )


def _render_hostname_tile(**context: object) -> str:
    """Rendert die Hostname-Kachel.

    Args:
        context:
            Zusaetzliche Template-Variablen.

    Returns:
        Das gerenderte Kachel-Fragment.
    """
    services = current_services()
    return render_template(
        "dashboard/_hostname_tile.html",
        texts=current_texts(),
        hostname=services.hostname_service.get(),
        **context,
    )


def _check_url(url: str) -> tuple[bool, str]:
    """Validiert eine URL und prueft ihre Erreichbarkeit.

    Args:
        url:
            Zu pruefende URL.

    Returns:
        Tupel aus Gueltigkeit und Meldungstext.
    """
    texts = current_texts()
    try:
        URLValidator().validate(url)
        valid, status = check_url_status(url)
    except ValidationError as error:
        return False, str(error)
    except NetworkError:
        return False, texts["url_unreachable"]
    if not valid:
        return False, f"{texts['url_invalid']} (HTTP {status})"
    return True, f"{texts['url_valid']} ({texts['label_http_status']} {status})"


@settings_blueprint.post("/url/test")
@login_required
def url_test() -> str:
    """Prueft eine URL ohne sie zu speichern.

    Returns:
        Die aktualisierte URL-Kachel.
    """
    url = request.form.get("url", "").strip()
    valid, message = _check_url(url)
    if valid:
        return _render_url_tile(message=message, entered_url=url)
    return _render_url_tile(error=message, entered_url=url)


@settings_blueprint.post("/url/save")
@login_required
def url_save() -> str:
    """Prueft und speichert eine neue Kiosk-URL.

    Nach dem Speichern wird ein laufender Browser automatisch mit
    der neuen URL neu gestartet.

    Returns:
        Die aktualisierte URL-Kachel.
    """
    texts = current_texts()
    services = current_services()
    url = request.form.get("url", "").strip()
    valid, message = _check_url(url)
    if not valid:
        return _render_url_tile(error=message, entered_url=url)
    config = services.config_service.load()
    config["url"] = url
    services.config_service.save(config)
    try:
        if services.browser_service.status() is BrowserStatus.RUNNING:
            services.browser_service.stop()
            services.browser_service.start(url)
    except PiKioskError as error:
        return _render_url_tile(error=str(error), entered_url=url)
    return _render_url_tile(message=texts["url_saved"], entered_url=url)


@settings_blueprint.post("/hostname")
@login_required
def hostname_save() -> str:
    """Prueft und setzt einen neuen Hostnamen.

    Returns:
        Die aktualisierte Hostname-Kachel.
    """
    texts = current_texts()
    services = current_services()
    hostname = request.form.get("hostname", "").strip()
    try:
        services.hostname_service.set(hostname)
        config = services.config_service.load()
        config["hostname"] = hostname
        services.config_service.save(config)
    except PiKioskError as error:
        return _render_hostname_tile(error=str(error), entered_hostname=hostname)
    return _render_hostname_tile(message=texts["hostname_saved_reboot_hint"])


def _render_monitoring_tile(**context: object) -> str:
    """Rendert die Ueberwachungs-Kachel.

    Args:
        context:
            Zusaetzliche Template-Variablen.

    Returns:
        Das gerenderte Kachel-Fragment.
    """
    services = current_services()
    return render_template(
        "dashboard/_monitoring_tile.html",
        texts=current_texts(),
        config=services.config_service.load(),
        watchdog_state=services.dashboard_service.watchdog_state(),
        watchdog_details=services.dashboard_service.watchdog_details(),
        **context,
    )


@settings_blueprint.get("/monitoring")
@login_required
def monitoring_tile() -> str:
    """Zeigt die Ueberwachungs-Kachel.

    Returns:
        Das gerenderte Kachel-Fragment.
    """
    return _render_monitoring_tile()


@settings_blueprint.post("/monitoring")
@login_required
def monitoring_save() -> str:
    """Speichert Watchdog-Schalter und Verbindungspruefung.

    Returns:
        Die aktualisierte Ueberwachungs-Kachel.
    """
    texts = current_texts()
    services = current_services()
    config = services.config_service.load()
    config["watchdog"] = request.form.get("watchdog", "") == "on"
    config["connectivity_check"] = request.form.get(
        "connectivity_check", config["connectivity_check"]
    )
    try:
        services.config_service.save(config)
    except ValidationError as error:
        return _render_monitoring_tile(error=str(error))
    return _render_monitoring_tile(message=texts["monitoring_saved"])


def _render_appearance_tile(**context: object) -> str:
    """Rendert die Darstellungs-Kachel.

    Args:
        context:
            Zusaetzliche Template-Variablen.

    Returns:
        Das gerenderte Kachel-Fragment.
    """
    config = current_services().config_service.load()
    return render_template(
        "dashboard/_appearance_tile.html",
        texts=current_texts(),
        config=config,
        **context,
    )


@settings_blueprint.post("/appearance")
@login_required
def appearance_save() -> str | Response:
    """Speichert Sprache und Theme.

    Nach erfolgreichem Speichern laedt die Seite ueber HTMX neu,
    damit die neue Sprache und das neue Theme sofort wirken.

    Returns:
        Seitenneuladen bei Erfolg, sonst die Kachel mit Fehler.
    """
    services = current_services()
    config = services.config_service.load()
    config["language"] = request.form.get("language", config["language"])
    config["theme"] = request.form.get("theme", config["theme"])
    try:
        services.config_service.save(config)
    except ValidationError as error:
        return _render_appearance_tile(error=str(error))
    response = make_response("", 200)
    response.headers["HX-Refresh"] = "true"
    return response
