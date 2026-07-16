# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Browsersteuerung im Dashboard.

Stellt Start, Stopp und Neustart des Kioskbrowsers als
HTMX-Endpunkte bereit. Alle Fehler werden als verstaendliche
Meldungen in der Kachel angezeigt.
"""

from flask import Blueprint, abort, render_template
from flask_login import login_required

from app.controllers import current_services, current_texts, kiosk_target_url
from app.exceptions import PiKioskError

browser_blueprint = Blueprint("browser", __name__, url_prefix="/dashboard/browser")

BROWSER_ACTIONS: tuple[str, ...] = ("start", "stop", "restart")


def _render_tile(message: str | None = None, error: str | None = None) -> str:
    """Rendert die Browser-Kachel.

    Args:
        message:
            Optionale Erfolgsmeldung.

        error:
            Optionale Fehlermeldung.

    Returns:
        Das gerenderte Kachel-Fragment.
    """
    services = current_services()
    return render_template(
        "dashboard/_browser_tile.html",
        texts=current_texts(),
        browser_status=services.browser_service.status().value,
        message=message,
        error=error,
    )


@browser_blueprint.post("/<action>")
@login_required
def control(action: str) -> str:
    """Fuehrt eine Browseraktion aus.

    Args:
        action:
            Eine der Aktionen start, stop oder restart.

    Returns:
        Die aktualisierte Browser-Kachel.
    """
    if action not in BROWSER_ACTIONS:
        abort(404)
    texts = current_texts()
    services = current_services()
    try:
        if action == "start":
            services.browser_service.start(kiosk_target_url())
        elif action == "stop":
            services.browser_service.stop()
        else:
            services.browser_service.restart()
    except PiKioskError as error:
        return _render_tile(error=str(error))
    return _render_tile(message=texts[f"browser_{action}_done"])
