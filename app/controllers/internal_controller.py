# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Interne Endpunkte.

Stellt den Browser-Neustart fuer den Watchdogprozess bereit. Die
Authentifizierung erfolgt ueber ein gemeinsames Token aus der
Schluesseldatei, der Vergleich ist zeitkonstant.
"""

import hmac

from flask import Blueprint, Response, abort, current_app, jsonify, request

from app.constants import WATCHDOG_TOKEN_HEADER
from app.controllers import current_services, kiosk_target_url
from app.exceptions import PiKioskError
from app.services.browser_service import BrowserStatus

internal_blueprint = Blueprint("internal", __name__, url_prefix="/internal")


@internal_blueprint.post("/browser/restart")
def browser_restart() -> Response | tuple[Response, int]:
    """Startet den Kioskbrowser im Auftrag des Watchdogs neu.

    Returns:
        JSON-Antwort mit dem Ergebnis des Neustarts.
    """
    token = request.headers.get(WATCHDOG_TOKEN_HEADER, "")
    expected = str(current_app.config["SECRET_KEY"])
    if not token or not hmac.compare_digest(token, expected):
        abort(403)
    services = current_services()
    if services.browser_service.status() is BrowserStatus.RUNNING:
        return jsonify(restarted=False, status="running")
    try:
        services.browser_service.start(kiosk_target_url())
    except PiKioskError as error:
        services.logger.error(f"Watchdog-Neustart fehlgeschlagen: {error}")
        return jsonify(restarted=False, error=str(error)), 500
    services.logger.info("Watchdog hat den Browser neu gestartet.")
    return jsonify(restarted=True, status="running")
