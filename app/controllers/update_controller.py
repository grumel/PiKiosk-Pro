# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Aktualisierung im Dashboard.

Stellt die Wahl der Updatequelle (GitHub, lokale Quelle oder aus),
die Suche nach Updates, die Installation aus der Quelle oder einem
hochgeladenen Paket sowie den Rollback bereit. Vor jeder
Installation wird automatisch eine Sicherung erstellt.
"""

import tempfile
from pathlib import Path
from typing import Any

from flask import Blueprint, render_template, request
from flask_login import login_required

from app.controllers import current_services, current_texts
from app.exceptions import PiKioskError

update_blueprint = Blueprint("update", __name__, url_prefix="/dashboard/update")


def render_update_tile(
    message: str | None = None,
    error: str | None = None,
    info: dict[str, Any] | None = None,
) -> str:
    """Rendert die Update-Kachel.

    Args:
        message:
            Optionale Erfolgsmeldung.

        error:
            Optionale Fehlermeldung.

        info:
            Optionales Ergebnis der Updatepruefung.

    Returns:
        Das gerenderte Kachel-Fragment.
    """
    services = current_services()
    service = services.update_service
    config = services.config_service.load()
    return render_template(
        "dashboard/_update_tile.html",
        texts=current_texts(),
        current_version=service.current_version(),
        can_rollback=service.can_rollback(),
        rollback_info=service.rollback_info(),
        config=config,
        info=info,
        message=message,
        error=error,
    )


@update_blueprint.get("/")
@login_required
def tile() -> str:
    """Zeigt die Update-Kachel.

    Returns:
        Das gerenderte Kachel-Fragment.
    """
    return render_update_tile()


@update_blueprint.post("/source")
@login_required
def save_source() -> str:
    """Speichert Updatequelle und Update-URL.

    Returns:
        Die aktualisierte Update-Kachel.
    """
    texts = current_texts()
    services = current_services()
    config = services.config_service.load()
    config["update_source"] = request.form.get("update_source", config["update_source"])
    config["update_url"] = request.form.get("update_url", "").strip()
    try:
        services.config_service.save(config)
    except PiKioskError as error:
        return render_update_tile(error=str(error))
    return render_update_tile(message=texts["update_source_saved"])


@update_blueprint.post("/check")
@login_required
def check() -> str:
    """Sucht in der konfigurierten Quelle nach einem Update.

    Returns:
        Die aktualisierte Update-Kachel.
    """
    try:
        info = current_services().update_service.check()
    except PiKioskError as error:
        return render_update_tile(error=str(error))
    return render_update_tile(info=info)


@update_blueprint.post("/install")
@login_required
def install_source() -> str:
    """Installiert das Update aus der konfigurierten Quelle.

    Returns:
        Die aktualisierte Update-Kachel.
    """
    texts = current_texts()
    services = current_services()
    try:
        result = services.update_service.apply()
    except PiKioskError as error:
        return render_update_tile(error=str(error))
    return render_update_tile(
        message=texts["update_installed_reboot"].format(version=result["version"])
    )


@update_blueprint.post("/upload")
@login_required
def upload() -> str:
    """Installiert ein hochgeladenes Update-Paket.

    Returns:
        Die aktualisierte Update-Kachel.
    """
    texts = current_texts()
    services = current_services()
    uploaded = request.files.get("update_file")
    if uploaded is None or not uploaded.filename:
        return render_update_tile(error=texts["update_no_file"])
    descriptor = tempfile.NamedTemporaryFile(
        suffix=".pkg", prefix="pikiosk_update_", delete=False
    )
    temp_path = Path(descriptor.name)
    try:
        uploaded.save(descriptor)
        descriptor.close()
        result = services.update_service.apply_package(temp_path)
    except PiKioskError as error:
        return render_update_tile(error=str(error))
    finally:
        temp_path.unlink(missing_ok=True)
    return render_update_tile(
        message=texts["update_installed_reboot"].format(version=result["version"])
    )


@update_blueprint.post("/rollback")
@login_required
def rollback() -> str:
    """Setzt die Anwendung auf den vorherigen Stand zurueck.

    Returns:
        Die aktualisierte Update-Kachel.
    """
    texts = current_texts()
    services = current_services()
    try:
        result = services.update_service.rollback()
    except PiKioskError as error:
        return render_update_tile(error=str(error))
    return render_update_tile(
        message=texts["update_rolled_back_reboot"].format(version=result["version"])
    )
