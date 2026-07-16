# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Sicherungen im Dashboard.

Stellt das Erstellen, Auflisten und Herunterladen von Sicherungen
sowie die Anzeige gefundener USB-Sicherungen bereit.
"""

from flask import Blueprint, abort, render_template, request, send_file
from flask_login import login_required
from werkzeug.wrappers import Response

from app.controllers import current_services, current_texts
from app.exceptions import BackupError
from app.services.restore_service import RestoreService

backup_blueprint = Blueprint("backup", __name__, url_prefix="/dashboard/backup")


def render_backup_tile(message: str | None = None, error: str | None = None) -> str:
    """Rendert die Sicherungs-Kachel.

    Args:
        message:
            Optionale Erfolgsmeldung.

        error:
            Optionale Fehlermeldung.

    Returns:
        Das gerenderte Kachel-Fragment.
    """
    return render_template(
        "dashboard/_backup_tile.html",
        texts=current_texts(),
        backups=current_services().backup_service.list_backups(),
        message=message,
        error=error,
    )


@backup_blueprint.get("/")
@login_required
def tile() -> str:
    """Zeigt die Sicherungs-Kachel.

    Returns:
        Das gerenderte Kachel-Fragment.
    """
    return render_backup_tile()


@backup_blueprint.post("/create")
@login_required
def create() -> str:
    """Erstellt eine neue Sicherung.

    Returns:
        Die aktualisierte Sicherungs-Kachel.
    """
    texts = current_texts()
    include_logs = request.form.get("include_logs", "") == "on"
    try:
        backup_path = current_services().backup_service.create(include_logs)
    except BackupError as error:
        return render_backup_tile(error=str(error))
    return render_backup_tile(message=f"{texts['backup_created']} {backup_path.name}")


@backup_blueprint.get("/download/<name>")
@login_required
def download(name: str) -> Response:
    """Bietet eine Sicherung zum Download an.

    Args:
        name:
            Dateiname der Sicherung.

    Returns:
        Die Sicherungsdatei als Download.
    """
    services = current_services()
    try:
        backup_path = services.backup_service.backup_file(name)
    except BackupError:
        abort(404)
    services.logger.info(f"Sicherung heruntergeladen: {name}")
    return send_file(backup_path, as_attachment=True, download_name=name)


@backup_blueprint.get("/usb")
@login_required
def usb() -> str:
    """Listet auf USB-Medien gefundene Sicherungen auf.

    Returns:
        Das USB-Fragment der Sicherungs-Kachel.
    """
    restore_service: RestoreService = current_services().restore_service
    return render_template(
        "dashboard/_usb_backups.html",
        texts=current_texts(),
        usb_backups=restore_service.scan_usb(),
    )
