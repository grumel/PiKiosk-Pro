# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - DashboardService.

Sammelt alle Systeminformationen fuer das Dashboard in einem
einzigen JSON-faehigen Objekt: Hostname, Netzwerk, CPU, RAM,
Temperatur, Festplatte, Browser- und Internetstatus, Version,
letzter Neustart und Systemlaufzeit.
"""

import socket
from datetime import datetime
from typing import Any

import psutil

from app.constants import (
    APP_VERSION,
    INTERNET_CHECK_HOST,
    INTERNET_CHECK_PORT,
    INTERNET_CHECK_TIMEOUT_SECONDS,
    THERMAL_ZONE_FILE,
)
from app.logger import KioskLogger
from app.services.browser_service import BrowserService
from app.services.config_service import ConfigService
from app.utils.helpers import device_model, local_ip_address


class DashboardService:
    """Liefert die Anzeigedaten des Dashboards.

    Args:
        logger:
            Logger fuer Dashboardereignisse.

        config_service:
            Dienst fuer die Konfigurationsverwaltung.

        browser_service:
            Dienst fuer die Browsersteuerung.
    """

    def __init__(
        self,
        logger: KioskLogger,
        config_service: ConfigService,
        browser_service: BrowserService,
    ) -> None:
        self._logger = logger
        self._config_service = config_service
        self._browser_service = browser_service

    def data(self) -> dict[str, Any]:
        """Sammelt alle Dashboarddaten.

        Returns:
            JSON-faehiges Objekt mit allen Anzeigewerten.
        """
        config = self._config_service.load()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        return {
            "hostname": socket.gethostname(),
            "device": device_model(),
            "ip_address": local_ip_address(),
            "mac_address": self._mac_address(),
            "cpu_percent": psutil.cpu_percent(interval=None),
            "ram_percent": memory.percent,
            "ram_used_mb": int(memory.used / (1024 * 1024)),
            "ram_total_mb": int(memory.total / (1024 * 1024)),
            "temperature": self._cpu_temperature(),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024**3), 1),
            "disk_total_gb": round(disk.total / (1024**3), 1),
            "browser_status": self._browser_service.status().value,
            "internet_online": self.internet_online(),
            "url": config["url"],
            "version": APP_VERSION,
            "last_boot": boot_time.strftime("%d.%m.%Y %H:%M"),
            "uptime": self._format_uptime(boot_time),
        }

    def internet_online(self) -> bool:
        """Prueft die Internetverbindung ueber einen TCP-Verbindungsaufbau.

        Returns:
            True, wenn das Internet erreichbar ist.
        """
        try:
            with socket.create_connection(
                (INTERNET_CHECK_HOST, INTERNET_CHECK_PORT),
                timeout=INTERNET_CHECK_TIMEOUT_SECONDS,
            ):
                return True
        except OSError:
            return False

    def _mac_address(self) -> str:
        """Ermittelt die MAC-Adresse der aktiven Netzwerkschnittstelle.

        Returns:
            MAC-Adresse oder "-", wenn nicht ermittelbar.
        """
        active_ip = local_ip_address()
        interfaces = psutil.net_if_addrs()
        for name, addresses in interfaces.items():
            ips = {a.address for a in addresses if a.family == socket.AF_INET}
            if active_ip not in ips:
                continue
            for address in addresses:
                if address.family == psutil.AF_LINK and address.address:
                    return address.address
        return "-"

    def _cpu_temperature(self) -> float | None:
        """Liest die CPU-Temperatur.

        Returns:
            Temperatur in Grad Celsius oder None, wenn kein
            Sensor verfuegbar ist.
        """
        try:
            sensors = psutil.sensors_temperatures()
        except AttributeError:
            sensors = {}
        for readings in sensors.values():
            for reading in readings:
                if reading.current:
                    return round(float(reading.current), 1)
        try:
            raw = THERMAL_ZONE_FILE.read_text(encoding="ascii").strip()
            return round(int(raw) / 1000.0, 1)
        except (OSError, ValueError):
            return None

    def _format_uptime(self, boot_time: datetime) -> str:
        """Formatiert die Systemlaufzeit seit dem letzten Start.

        Args:
            boot_time:
                Zeitpunkt des letzten Systemstarts.

        Returns:
            Laufzeit im Format "Td HH:MM".
        """
        delta = datetime.now() - boot_time
        total_minutes = max(0, int(delta.total_seconds() // 60))
        days, remainder = divmod(total_minutes, 24 * 60)
        hours, minutes = divmod(remainder, 60)
        return f"{days}d {hours:02d}:{minutes:02d}"
