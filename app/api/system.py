# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - API: Systemsteuerung und Watchdogstatus."""

from flask import Response, g, jsonify

from app.api import api_auth_required, api_blueprint, api_call, api_error, json_body
from app.constants import WATCHDOG_STATUS_FILE
from app.controllers import current_services
from app.exceptions import ConfigurationError
from app.utils.filesystem import read_json_file

SYSTEM_API_ACTIONS: tuple[str, ...] = ("reboot", "shutdown")


@api_blueprint.get("/system")
@api_auth_required
@api_call
def get_system() -> Response:
    """Liefert den detaillierten Watchdogstatus.

    Returns:
        JSON mit Gesamtzustand und Einzelpruefungen des Watchdogs.
    """
    services = current_services()
    try:
        watchdog = read_json_file(WATCHDOG_STATUS_FILE)
    except ConfigurationError:
        watchdog = {}
    return jsonify(
        watchdog=watchdog,
        watchdog_state=services.dashboard_service.watchdog_state(),
    )


@api_blueprint.post("/system")
@api_auth_required
@api_call
def control_system() -> Response | tuple[Response, int]:
    """Fuehrt eine Systemaktion aus.

    Erwartet {"action": "reboot|shutdown"}.

    Returns:
        JSON mit der eingeleiteten Aktion.
    """
    action = str(json_body().get("action", ""))
    if action not in SYSTEM_API_ACTIONS:
        return api_error(400, "invalid_action")
    services = current_services()
    services.logger.info(
        f"Systemaktion '{action}' ueber die API angefordert von "
        f"{g.api_user.username}."
    )
    if action == "reboot":
        services.system_service.reboot()
    else:
        services.system_service.shutdown()
    return jsonify(action=action, accepted=True)
