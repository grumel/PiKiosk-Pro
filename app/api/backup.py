# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - API: Sicherungen."""

from flask import Response, jsonify, send_file

from app.api import api_auth_required, api_blueprint, api_call, api_error, json_body
from app.controllers import current_services
from app.exceptions import BackupError


@api_blueprint.get("/backup")
@api_auth_required
@api_call
def list_backups() -> Response:
    """Listet alle vorhandenen Sicherungen auf.

    Returns:
        JSON mit den Sicherungen.
    """
    return jsonify(backups=current_services().backup_service.list_backups())


@api_blueprint.post("/backup")
@api_auth_required
@api_call
def create_backup() -> Response:
    """Erstellt eine neue Sicherung.

    Erwartet optional {"include_logs": true}.

    Returns:
        JSON mit dem Namen der erstellten Sicherung.
    """
    include_logs = bool(json_body().get("include_logs", False))
    backup_path = current_services().backup_service.create(include_logs)
    return jsonify(name=backup_path.name, include_logs=include_logs)


@api_blueprint.get("/backup/<name>")
@api_auth_required
@api_call
def download_backup(name: str) -> Response | tuple[Response, int]:
    """Bietet eine Sicherung zum Download an.

    Args:
        name:
            Dateiname der Sicherung.

    Returns:
        Die Sicherungsdatei oder Fehler 404.
    """
    try:
        backup_path = current_services().backup_service.backup_file(name)
    except BackupError:
        return api_error(404, "backup_not_found")
    return send_file(backup_path, as_attachment=True, download_name=name)
