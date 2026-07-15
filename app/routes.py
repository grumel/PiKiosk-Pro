# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Hauptrouten.

Stellt die Statusseite und den Health-Endpunkt bereit. Alle
Oberflaechentexte werden aus den JSON-Sprachdateien geladen.
"""

import socket
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, render_template

from app.constants import APP_NAME, APP_VERSION
from app.extensions import get_services
from app.utils.helpers import load_language, local_ip_address

main_blueprint = Blueprint("main", __name__)


def _collect_status_data(config: dict[str, Any]) -> dict[str, Any]:
    """Sammelt die Anzeigedaten fuer die Statusseite.

    Args:
        config:
            Aktive Konfiguration.

    Returns:
        Anzeigedaten fuer das Template.
    """
    services = get_services(current_app)
    browser_status = services.browser_service.status()
    return {
        "app_name": APP_NAME,
        "version": APP_VERSION,
        "hostname": socket.gethostname(),
        "ip_address": local_ip_address(),
        "browser_status": browser_status.value,
        "kiosk_url": config["url"],
        "first_start": config["first_start"],
    }


@main_blueprint.get("/")
def index() -> str:
    """Rendert die Statusseite des Systems.

    Returns:
        Gerenderte HTML-Seite.
    """
    services = get_services(current_app)
    config = services.config_service.load()
    texts = load_language(config["language"])
    data = _collect_status_data(config)
    return render_template("index.html", texts=texts, data=data, theme=config["theme"])


@main_blueprint.get("/health")
def health() -> Response:
    """Liefert den Systemzustand als JSON.

    Returns:
        JSON-Antwort mit Status, Version und Browserstatus.
    """
    services = get_services(current_app)
    browser_status = services.browser_service.status()
    return jsonify(
        status="ok",
        version=APP_VERSION,
        browser=browser_status.value,
    )
