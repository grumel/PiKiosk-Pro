# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - API: Aktualisierung und Rollback."""

from flask import Response, jsonify

from app.api import api_auth_required, api_blueprint, api_call, api_error, json_body
from app.controllers import current_services

UPDATE_API_ACTIONS: tuple[str, ...] = ("check", "install", "rollback")


@api_blueprint.get("/update")
@api_auth_required
@api_call
def get_update() -> Response:
    """Liefert Version und Rollback-Zustand.

    Returns:
        JSON mit Version, Updatequelle und Rollback-Informationen.
    """
    update = current_services().update_service
    return jsonify(
        current=update.current_version(),
        source=update.source(),
        can_rollback=update.can_rollback(),
        rollback=update.rollback_info(),
    )


@api_blueprint.post("/update")
@api_auth_required
@api_call
def control_update() -> Response | tuple[Response, int]:
    """Fuehrt eine Updateaktion aus.

    Erwartet {"action": "check|install|rollback"}.

    Returns:
        JSON mit dem Ergebnis der Aktion.
    """
    action = str(json_body().get("action", ""))
    if action not in UPDATE_API_ACTIONS:
        return api_error(400, "invalid_action")
    update = current_services().update_service
    if action == "check":
        return jsonify(update.check())
    if action == "install":
        return jsonify(update.apply())
    return jsonify(update.rollback())
