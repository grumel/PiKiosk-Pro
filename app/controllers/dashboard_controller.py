# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Dashboard.

Rendert die Administrationsoberflaeche mit Systeminformationen und
Kacheln fuer Browser, URL, Hostname, WLAN, System und Logs. Die
Systemdaten aktualisieren sich per HTMX automatisch.
"""

from flask import Blueprint, render_template
from flask_login import login_required

from app.controllers import current_services, current_texts, ensure_csrf_token

dashboard_blueprint = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_blueprint.get("/")
@login_required
def index() -> str:
    """Rendert das Dashboard.

    Returns:
        Die vollstaendige Dashboardseite.
    """
    services = current_services()
    config = services.config_service.load()
    ensure_csrf_token()
    return render_template(
        "dashboard.html",
        texts=current_texts(),
        theme=config["theme"],
        config=config,
        data=services.dashboard_service.data(),
        browser_status=services.browser_service.status().value,
    )


@dashboard_blueprint.get("/data")
@login_required
def data() -> str:
    """Liefert die Systeminformationen als HTMX-Fragment.

    Returns:
        Das gerenderte Datenfragment.
    """
    return render_template(
        "dashboard/_data.html",
        texts=current_texts(),
        data=current_services().dashboard_service.data(),
    )
