# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Center - Dienstregistrierung.

Buendelt die Dienste der Zentrale und stellt sie ueber die
Flask-Extension-Schnittstelle bereit (Dependency Injection).
"""

from dataclasses import dataclass

from flask import Flask, current_app

from app.logger import KioskLogger
from app.services.auth_service import AuthService
from center.services.device_client import DeviceClient
from center.services.device_service import DeviceService
from center.services.fleet_service import FleetService

CENTER_EXTENSION_KEY: str = "pikiosk_center"


@dataclass(frozen=True)
class CenterRegistry:
    """Sammlung aller Dienste der Zentrale.

    Attributes:
        logger:
            Logger der Zentrale.

        auth_service:
            Dienst fuer die Anmeldung an der Zentrale.

        device_service:
            Verwaltung der Geraeteliste.

        fleet_service:
            Abfrage und Steuerung der Geraete.

        client:
            Client fuer die Geraete-API.
    """

    logger: KioskLogger
    auth_service: AuthService
    device_service: DeviceService
    fleet_service: FleetService
    client: DeviceClient


def register_center_services(app: Flask, registry: CenterRegistry) -> None:
    """Registriert die Dienste an der Flask-Anwendung.

    Args:
        app:
            Flask-Anwendung der Zentrale.

        registry:
            Zu registrierende Dienste.
    """
    app.extensions[CENTER_EXTENSION_KEY] = registry


def center_services() -> CenterRegistry:
    """Liefert die Dienste der aktuellen Anwendung.

    Returns:
        Die registrierte CenterRegistry.
    """
    registry: CenterRegistry = current_app.extensions[CENTER_EXTENSION_KEY]
    return registry
