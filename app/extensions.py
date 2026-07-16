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
from app.services.auth_service import AuthService
from app.services.backup_service import BackupService
from app.services.browser_service import BrowserService
from app.services.config_service import ConfigService
from app.services.dashboard_service import DashboardService
from app.services.hostname_service import HostnameService
from app.services.network_service import NetworkService
from app.services.restore_service import RestoreService
from app.services.system_service import SystemService

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

        network_service:
            Dienst fuer die WLAN-Verwaltung ueber NetworkManager.

        hostname_service:
            Dienst fuer die Hostnameverwaltung.

        auth_service:
            Dienst fuer Benutzer- und Passwortverwaltung.

        dashboard_service:
            Dienst fuer die Dashboard-Systeminformationen.

        system_service:
            Dienst fuer Neustart und Herunterfahren.

        backup_service:
            Dienst fuer das Erstellen von Sicherungen.

        restore_service:
            Dienst fuer das Wiederherstellen von Sicherungen.
    """

    logger: KioskLogger
    config_service: ConfigService
    browser_service: BrowserService
    network_service: NetworkService
    hostname_service: HostnameService
    auth_service: AuthService
    dashboard_service: DashboardService
    system_service: SystemService
    backup_service: BackupService
    restore_service: RestoreService


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
