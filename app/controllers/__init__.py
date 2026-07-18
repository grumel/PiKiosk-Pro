# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Controller-Schicht.

Stellt gemeinsame Helfer fuer alle Controller bereit: Zugriff auf
die Dienstregistrierung, Oberflaechentexte und das CSRF-Token der
Sitzung.
"""

import secrets

from flask import current_app, session

from app.extensions import ServiceRegistry, get_services
from app.utils.helpers import load_language, local_base_url

SESSION_CSRF_KEY: str = "csrf_token"


def current_services() -> ServiceRegistry:
    """Liefert die Dienste der aktuellen Anwendung.

    Returns:
        Die registrierte ServiceRegistry.
    """
    return get_services(current_app)


def current_texts() -> dict[str, str]:
    """Laedt die Oberflaechentexte der aktiven Sprache.

    Returns:
        Woerterbuch mit Oberflaechentexten.
    """
    config = current_services().config_service.load()
    return load_language(config["language"])


def ensure_csrf_token() -> str:
    """Liefert das CSRF-Token der Sitzung und erzeugt es bei Bedarf.

    Returns:
        Das CSRF-Token.
    """
    if SESSION_CSRF_KEY not in session:
        session[SESSION_CSRF_KEY] = secrets.token_hex(16)
    token: str = session[SESSION_CSRF_KEY]
    return token


def kiosk_target_url() -> str:
    """Bestimmt die Ziel-URL fuer den Kioskbrowser.

    Returns:
        Konfigurierte Kiosk-URL oder die lokale Statusseite.
    """
    config = current_services().config_service.load()
    return str(config["url"]) if config["url"] else local_base_url()
