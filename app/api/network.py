# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - API: Netzwerkverwaltung."""

from flask import Response, jsonify

from app.api import api_auth_required, api_blueprint, api_call, api_error, json_body
from app.controllers import current_services

NETWORK_API_ACTIONS: tuple[str, ...] = ("connect", "disconnect", "scan")


@api_blueprint.get("/network")
@api_auth_required
@api_call
def get_network() -> Response:
    """Liefert den aktuellen Netzwerkzustand.

    Returns:
        JSON mit aktiver Verbindung, Adressen und Profilen.
    """
    network = current_services().network_service
    return jsonify(
        connected=network.current(),
        ip=network.ip(),
        gateway=network.gateway(),
        dns=network.dns(),
        mac=network.mac(),
        signal=network.signal(),
        saved=network.saved(),
    )


@api_blueprint.post("/network")
@api_auth_required
@api_call
def control_network() -> Response | tuple[Response, int]:
    """Fuehrt eine Netzwerkaktion aus.

    Erwartet {"action": "connect|disconnect|scan"}; connect
    benoetigt zusaetzlich ssid und optional password.

    Returns:
        JSON mit dem Ergebnis der Aktion.
    """
    body = json_body()
    action = str(body.get("action", ""))
    if action not in NETWORK_API_ACTIONS:
        return api_error(400, "invalid_action")
    network = current_services().network_service
    if action == "scan":
        return jsonify(networks=network.scan())
    if action == "connect":
        network.connect(str(body.get("ssid", "")), str(body.get("password", "")))
    else:
        network.disconnect()
    return jsonify(action=action, connected=network.current())


@api_blueprint.delete("/network/profiles/<name>")
@api_auth_required
@api_call
def delete_profile(name: str) -> Response | tuple[Response, int]:
    """Loescht ein gespeichertes WLAN-Profil.

    Args:
        name:
            Name des Verbindungsprofils.

    Returns:
        JSON mit den verbleibenden Profilen.
    """
    network = current_services().network_service
    if name not in network.saved():
        return api_error(404, "profile_not_found")
    network.delete(name)
    return jsonify(deleted=name, saved=network.saved())
