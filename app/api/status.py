# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - API: Gesamtstatus und Version."""

from flask import Response, jsonify

from app.api import api_auth_required, api_blueprint, api_call
from app.constants import APP_NAME, APP_VERSION
from app.controllers import current_services


@api_blueprint.get("/status")
@api_auth_required
@api_call
def get_status() -> Response:
    """Liefert den vollstaendigen Geraetestatus.

    Returns:
        JSON mit allen Dashboard-Systeminformationen.
    """
    return jsonify(current_services().dashboard_service.data())


@api_blueprint.get("/version")
@api_auth_required
@api_call
def get_version() -> Response:
    """Liefert Name und Version der Anwendung.

    Returns:
        JSON mit Anwendungsname und Version.
    """
    return jsonify(name=APP_NAME, version=APP_VERSION)
