# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - API: Logdateien."""

from flask import Response, jsonify

from app.api import api_auth_required, api_blueprint, api_call, api_error
from app.constants import LOG_FILES, LOG_VIEW_LINES
from app.utils.helpers import read_log_tail


@api_blueprint.get("/logs")
@api_auth_required
@api_call
def list_logs() -> Response:
    """Listet die verfuegbaren Logdateien auf.

    Returns:
        JSON mit den Lognamen und deren Verfuegbarkeit.
    """
    return jsonify(
        logs=[
            {"name": name, "exists": path.exists()} for name, path in LOG_FILES.items()
        ]
    )


@api_blueprint.get("/logs/<name>")
@api_auth_required
@api_call
def get_log(name: str) -> Response | tuple[Response, int]:
    """Liefert die letzten Zeilen einer Logdatei.

    Args:
        name:
            Logname aus LOG_FILES.

    Returns:
        JSON mit den letzten Logzeilen oder Fehler 404.
    """
    log_file = LOG_FILES.get(name)
    if log_file is None:
        return api_error(404, "log_not_found")
    content = read_log_tail(log_file, LOG_VIEW_LINES)
    return jsonify(name=name, lines=content.splitlines())
