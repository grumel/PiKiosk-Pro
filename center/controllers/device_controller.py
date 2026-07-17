# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Center - Geraeteverwaltung.

Geraete aufnehmen, aendern, testen und entfernen. Beim Aufnehmen
wird die Verbindung sofort geprueft, damit falsche Adressen oder
Zugangsdaten nicht unbemerkt gespeichert werden.
"""

from flask import Blueprint, render_template, request
from flask_login import login_required

from app.exceptions import PiKioskError
from center.constants import DEVICE_DEFAULT_PORT
from center.controllers import center_texts
from center.extensions import center_services

device_blueprint = Blueprint("devices", __name__, url_prefix="/devices")


def _render_list(message: str | None = None, error: str | None = None) -> str:
    """Rendert die Geraeteliste als Fragment.

    Args:
        message:
            Optionale Erfolgsmeldung.

        error:
            Optionale Fehlermeldung.

    Returns:
        Das gerenderte Fragment.
    """
    return render_template(
        "fleet/_devices.html",
        texts=center_texts(),
        devices=center_services().device_service.all(),
        default_port=DEVICE_DEFAULT_PORT,
        message=message,
        error=error,
    )


@device_blueprint.get("/")
@login_required
def index() -> str:
    """Zeigt die Geraeteliste.

    Returns:
        Das gerenderte Fragment.
    """
    return _render_list()


@device_blueprint.post("/")
@login_required
def add() -> str:
    """Nimmt ein Geraet in die Verwaltung auf.

    Die Verbindung wird sofort geprueft; schlaegt sie fehl, wird das
    Geraet wieder entfernt und der Fehler angezeigt.

    Returns:
        Die aktualisierte Geraeteliste.
    """
    texts = center_texts()
    services = center_services()
    try:
        device = services.device_service.add(
            name=request.form.get("name", ""),
            address=request.form.get("address", ""),
            port=request.form.get("port", DEVICE_DEFAULT_PORT),
            username=request.form.get("username", ""),
            password=request.form.get("password", ""),
        )
    except PiKioskError as error:
        return _render_list(error=str(error))
    try:
        services.client.status(device)
    except PiKioskError as error:
        services.device_service.delete(device.id)
        return _render_list(
            error=texts["center_device_unreachable"].format(error=str(error))
        )
    return _render_list(message=texts["center_device_added"].format(name=device.name))


@device_blueprint.post("/<int:device_id>")
@login_required
def update(device_id: int) -> str:
    """Aendert ein vorhandenes Geraet.

    Returns:
        Die aktualisierte Geraeteliste.
    """
    texts = center_texts()
    services = center_services()
    try:
        device = services.device_service.update(
            device_id=device_id,
            name=request.form.get("name", ""),
            address=request.form.get("address", ""),
            port=request.form.get("port", DEVICE_DEFAULT_PORT),
            username=request.form.get("username", ""),
            password=request.form.get("password", ""),
            enabled=request.form.get("enabled", "") == "on",
        )
    except PiKioskError as error:
        return _render_list(error=str(error))
    services.client.forget_token(device_id)
    return _render_list(message=texts["center_device_updated"].format(name=device.name))


@device_blueprint.post("/<int:device_id>/test")
@login_required
def test(device_id: int) -> str:
    """Prueft die Verbindung zu einem Geraet.

    Returns:
        Die Geraeteliste mit dem Pruefergebnis.
    """
    texts = center_texts()
    services = center_services()
    device = services.device_service.find(device_id)
    if device is None:
        return _render_list(error=texts["center_device_not_found"])
    services.client.forget_token(device_id)
    try:
        status = services.client.status(device)
    except PiKioskError as error:
        return _render_list(
            error=texts["center_device_unreachable"].format(error=str(error))
        )
    return _render_list(
        message=texts["center_device_ok"].format(
            name=device.name, version=status.get("version", "?")
        )
    )


@device_blueprint.post("/<int:device_id>/delete")
@login_required
def delete(device_id: int) -> str:
    """Entfernt ein Geraet aus der Verwaltung.

    Returns:
        Die aktualisierte Geraeteliste.
    """
    texts = center_texts()
    services = center_services()
    try:
        services.device_service.delete(device_id)
    except PiKioskError as error:
        return _render_list(error=str(error))
    services.client.forget_token(device_id)
    return _render_list(message=texts["center_device_deleted"])
