# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Systemsteuerung und Logs im Dashboard.

Stellt Neustart und Herunterfahren sowie die Anzeige und den
Download der Logdateien bereit. Es sind ausschliesslich die in
LOG_FILES definierten Dateien zugreifbar.
"""

from collections import deque

from flask import Blueprint, abort, render_template, send_file
from flask_login import login_required
from werkzeug.wrappers import Response

from app.constants import LOG_FILES, LOG_VIEW_LINES
from app.controllers import current_services, current_texts
from app.exceptions import PiKioskError

system_blueprint = Blueprint("system", __name__, url_prefix="/dashboard/system")

SYSTEM_ACTIONS: tuple[str, ...] = ("reboot", "shutdown")


def _render_tile(message: str | None = None, error: str | None = None) -> str:
    """Rendert die System-Kachel.

    Args:
        message:
            Optionale Erfolgsmeldung.

        error:
            Optionale Fehlermeldung.

    Returns:
        Das gerenderte Kachel-Fragment.
    """
    return render_template(
        "dashboard/_system_tile.html",
        texts=current_texts(),
        message=message,
        error=error,
    )


@system_blueprint.post("/<action>")
@login_required
def control(action: str) -> str:
    """Fuehrt eine Systemaktion aus.

    Args:
        action:
            Eine der Aktionen reboot oder shutdown.

    Returns:
        Die aktualisierte System-Kachel.
    """
    if action not in SYSTEM_ACTIONS:
        abort(404)
    texts = current_texts()
    services = current_services()
    try:
        if action == "reboot":
            services.system_service.reboot()
        else:
            services.system_service.shutdown()
    except PiKioskError as error:
        return _render_tile(error=str(error))
    return _render_tile(message=texts[f"system_{action}_done"])


@system_blueprint.get("/logs/<name>")
@login_required
def view_log(name: str) -> str:
    """Zeigt die letzten Zeilen einer Logdatei an.

    Args:
        name:
            Logname aus LOG_FILES.

    Returns:
        Das gerenderte Log-Fragment.
    """
    log_file = LOG_FILES.get(name)
    if log_file is None:
        abort(404)
    texts = current_texts()
    try:
        with log_file.open("r", encoding="utf-8", errors="replace") as handle:
            lines = deque(handle, maxlen=LOG_VIEW_LINES)
        content = "".join(lines)
    except OSError:
        content = ""
    return render_template(
        "dashboard/_log_viewer.html",
        texts=texts,
        name=name,
        content=content,
    )


@system_blueprint.get("/logs/<name>/download")
@login_required
def download_log(name: str) -> Response:
    """Bietet eine Logdatei zum Download an.

    Args:
        name:
            Logname aus LOG_FILES.

    Returns:
        Die Logdatei als Download.
    """
    log_file = LOG_FILES.get(name)
    if log_file is None or not log_file.exists():
        abort(404)
    current_services().logger.info(f"Logdatei heruntergeladen: {name}")
    return send_file(log_file, as_attachment=True, download_name=f"pikiosk_{name}.log")
