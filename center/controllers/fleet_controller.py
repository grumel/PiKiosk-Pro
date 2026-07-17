# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Center - Flottenuebersicht.

Zeigt alle verwalteten Geraete mit ihrem Zustand und fuehrt
Aktionen auf einzelnen Geraeten oder einer Auswahl aus.
"""

from typing import Any

from flask import Blueprint, render_template, request
from flask_login import login_required

from app.exceptions import PiKioskError
from center.constants import CENTER_NAME, CENTER_VERSION, DEVICE_ACTIONS
from center.controllers import center_texts, ensure_csrf_token
from center.extensions import center_services
from center.services.fleet_service import FleetService

fleet_blueprint = Blueprint("fleet", __name__)


def _render_overview(
    message: str | None = None,
    error: str | None = None,
    results: list[dict[str, Any]] | None = None,
) -> str:
    """Rendert die Flottenuebersicht als Fragment.

    Args:
        message:
            Optionale Erfolgsmeldung.

        error:
            Optionale Fehlermeldung.

        results:
            Optionale Ergebnisse einer Massenaktion.

    Returns:
        Das gerenderte Fragment.
    """
    service: FleetService = center_services().fleet_service
    entries = service.overview()
    return render_template(
        "fleet/_overview.html",
        texts=center_texts(),
        devices=entries,
        summary=service.summary(entries),
        results=results,
        message=message,
        error=error,
    )


def _selected_ids() -> list[int]:
    """Liest die ausgewaehlten Geraetekennungen der Anfrage.

    Returns:
        Die ausgewaehlten Kennungen.
    """
    ids: list[int] = []
    for raw in request.form.getlist("device_ids"):
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    return ids


@fleet_blueprint.get("/")
@login_required
def index() -> str:
    """Rendert die Seite der Flottenuebersicht.

    Returns:
        Die vollstaendige Uebersichtsseite.
    """
    ensure_csrf_token()
    return render_template(
        "center_fleet.html",
        texts=center_texts(),
        center_name=CENTER_NAME,
        center_version=CENTER_VERSION,
    )


@fleet_blueprint.get("/overview")
@login_required
def overview() -> str:
    """Liefert die Uebersicht als HTMX-Fragment.

    Returns:
        Das gerenderte Fragment.
    """
    return _render_overview()


@fleet_blueprint.post("/action")
@login_required
def action() -> str:
    """Fuehrt eine Aktion auf den ausgewaehlten Geraeten aus.

    Returns:
        Die aktualisierte Uebersicht mit den Ergebnissen.
    """
    texts = center_texts()
    requested = request.form.get("action", "")
    if requested not in DEVICE_ACTIONS:
        return _render_overview(error=texts["center_invalid_action"])
    device_ids = _selected_ids()
    if not device_ids:
        return _render_overview(error=texts["center_no_selection"])
    try:
        results = center_services().fleet_service.run_action(device_ids, requested)
    except PiKioskError as error:
        return _render_overview(error=str(error))
    return _render_overview(
        message=texts["center_action_done"].format(count=len(results)),
        results=results,
    )


@fleet_blueprint.post("/url")
@login_required
def set_url() -> str:
    """Setzt die Kiosk-URL auf den ausgewaehlten Geraeten.

    Returns:
        Die aktualisierte Uebersicht mit den Ergebnissen.
    """
    texts = center_texts()
    url = request.form.get("url", "").strip()
    device_ids = _selected_ids()
    if not device_ids:
        return _render_overview(error=texts["center_no_selection"])
    if not url:
        return _render_overview(error=texts["center_url_required"])
    try:
        results = center_services().fleet_service.set_url(device_ids, url)
    except PiKioskError as error:
        return _render_overview(error=str(error))
    return _render_overview(
        message=texts["center_action_done"].format(count=len(results)),
        results=results,
    )
