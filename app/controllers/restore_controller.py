# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Wiederherstellung im Dashboard.

Stellt die Wiederherstellung von Sicherungen bereit: aus dem
Sicherungsverzeichnis, per Dateiupload oder von einem USB-Medium.
Jede Sicherung wird vor dem Anwenden vollstaendig geprueft.
"""

import tempfile
from pathlib import Path

from flask import Blueprint, request
from flask_login import login_required

from app.controllers import current_services, current_texts
from app.controllers.backup_controller import render_backup_tile
from app.exceptions import PiKioskError

restore_blueprint = Blueprint("restore", __name__, url_prefix="/dashboard/restore")


@restore_blueprint.post("/file/<name>")
@login_required
def restore_file(name: str) -> str:
    """Stellt eine Sicherung aus dem Sicherungsverzeichnis wieder her.

    Args:
        name:
            Dateiname der Sicherung.

    Returns:
        Die aktualisierte Sicherungs-Kachel.
    """
    texts = current_texts()
    services = current_services()
    try:
        backup_path = services.backup_service.backup_file(name)
        services.restore_service.restore(backup_path)
    except PiKioskError as error:
        return render_backup_tile(error=str(error))
    return render_backup_tile(message=texts["restore_done_reboot"])


@restore_blueprint.post("/upload")
@login_required
def upload() -> str:
    """Stellt eine hochgeladene Sicherung wieder her.

    Returns:
        Die aktualisierte Sicherungs-Kachel.
    """
    texts = current_texts()
    services = current_services()
    uploaded = request.files.get("backup_file")
    if uploaded is None or not uploaded.filename:
        return render_backup_tile(error=texts["restore_no_file"])
    descriptor = tempfile.NamedTemporaryFile(
        suffix=".zip", prefix="pikiosk_upload_", delete=False
    )
    temp_path = Path(descriptor.name)
    try:
        uploaded.save(descriptor)
        descriptor.close()
        services.restore_service.restore(temp_path)
    except PiKioskError as error:
        return render_backup_tile(error=str(error))
    finally:
        temp_path.unlink(missing_ok=True)
    return render_backup_tile(message=texts["restore_done_reboot"])


@restore_blueprint.post("/usb")
@login_required
def restore_usb() -> str:
    """Importiert eine Sicherung von einem USB-Medium.

    Returns:
        Die aktualisierte Sicherungs-Kachel.
    """
    texts = current_texts()
    services = current_services()
    path_text = request.form.get("path", "")
    try:
        services.restore_service.import_from_path(path_text)
    except PiKioskError as error:
        return render_backup_tile(error=str(error))
    return render_backup_tile(message=texts["restore_done_reboot"])
