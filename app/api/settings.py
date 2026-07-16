# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - API: Einstellungen."""

from flask import Response, jsonify

from app.api import api_auth_required, api_blueprint, api_call, api_error, json_body
from app.controllers import current_services

UPDATABLE_KEYS: tuple[str, ...] = (
    "url",
    "language",
    "theme",
    "fullscreen",
    "watchdog",
    "hostname",
)


@api_blueprint.get("/settings")
@api_auth_required
@api_call
def get_settings() -> Response:
    """Liefert die aktive Konfiguration.

    Returns:
        JSON mit der vollstaendigen Konfiguration.
    """
    return jsonify(current_services().config_service.load())


@api_blueprint.put("/settings")
@api_auth_required
@api_call
def put_settings() -> Response | tuple[Response, int]:
    """Aktualisiert einzelne Konfigurationsschluessel.

    Zulaessig sind url, language, theme, fullscreen, watchdog und
    hostname. Ungueltige Werte werden niemals gespeichert; eine
    Hostnameaenderung wird sofort auf das System angewendet.

    Returns:
        JSON mit der gespeicherten Konfiguration.
    """
    body = json_body()
    changes = {key: body[key] for key in UPDATABLE_KEYS if key in body}
    if not changes:
        return api_error(400, "no_updatable_keys")
    unknown = sorted(set(body) - set(UPDATABLE_KEYS))
    if unknown:
        return api_error(400, f"unknown_keys: {', '.join(unknown)}")
    services = current_services()
    config = services.config_service.load()
    config.update(changes)
    services.config_service.validate(config)
    if "hostname" in changes and changes["hostname"] != services.hostname_service.get():
        services.hostname_service.set(str(changes["hostname"]))
    services.config_service.save(config)
    return jsonify(config)
