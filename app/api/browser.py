# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - API: Browsersteuerung."""

from flask import Response, jsonify

from app.api import api_auth_required, api_blueprint, api_call, api_error, json_body
from app.controllers import current_services, kiosk_target_url

BROWSER_API_ACTIONS: tuple[str, ...] = (
    "start",
    "stop",
    "restart",
    "reload",
    "clear_cache",
)


@api_blueprint.get("/browser")
@api_auth_required
@api_call
def get_browser() -> Response:
    """Liefert den aktuellen Browserstatus.

    Returns:
        JSON mit dem Browserstatus.
    """
    services = current_services()
    return jsonify(status=services.browser_service.status().value)


@api_blueprint.post("/browser")
@api_auth_required
@api_call
def control_browser() -> Response | tuple[Response, int]:
    """Fuehrt eine Browseraktion aus.

    Erwartet {"action": "start|stop|restart|reload|clear_cache"}.

    Returns:
        JSON mit dem Browserstatus nach der Aktion.
    """
    action = str(json_body().get("action", ""))
    if action not in BROWSER_API_ACTIONS:
        return api_error(400, "invalid_action")
    services = current_services()
    browser = services.browser_service
    if action == "start":
        browser.start(kiosk_target_url())
    elif action == "stop":
        browser.stop()
    elif action == "restart":
        browser.restart()
    elif action == "reload":
        browser.reload()
    else:
        browser.clear_cache()
    return jsonify(status=browser.status().value, action=action)
