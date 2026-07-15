# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Dienstregistrierung.

Buendelt alle Dienste der Anwendung in einer ServiceRegistry und
stellt sie ueber die Flask-Extension-Schnittstelle bereit. Module
kommunizieren ausschliesslich ueber diese Registry miteinander
(Dependency Injection), es gibt keine globalen Variablen.
"""

from dataclasses import dataclass

from flask import Flask

from app.logger import KioskLogger
from app.services.browser_service import BrowserService
from app.services.config_service import ConfigService

EXTENSION_KEY: str = "pikiosk"


@dataclass(frozen=True)
class ServiceRegistry:
    """Sammlung aller Anwendungsdienste.

    Attributes:
        logger:
            Systemlogger der Anwendung.

        config_service:
            Dienst fuer die Konfigurationsverwaltung.

        browser_service:
            Dienst fuer die Browsersteuerung.
    """

    logger: KioskLogger
    config_service: ConfigService
    browser_service: BrowserService


def register_services(app: Flask, registry: ServiceRegistry) -> None:
    """Registriert die Dienste an der Flask-Anwendung.

    Args:
        app:
            Flask-Anwendung.

        registry:
            Zu registrierende Dienste.
    """
    app.extensions[EXTENSION_KEY] = registry


def get_services(app: Flask) -> ServiceRegistry:
    """Liefert die registrierten Dienste einer Flask-Anwendung.

    Args:
        app:
            Flask-Anwendung.

    Returns:
        Die registrierte ServiceRegistry.
    """
    registry: ServiceRegistry = app.extensions[EXTENSION_KEY]
    return registry
