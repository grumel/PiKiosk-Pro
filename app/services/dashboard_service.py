# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - DashboardService.

Sammelt alle Systeminformationen fuer das Dashboard in einem
einzigen JSON-faehigen Objekt: Hostname, Netzwerk, CPU, RAM,
Temperatur, Festplatte, Browser- und Internetstatus, Version,
letzter Neustart und Systemlaufzeit.
"""

import socket
from datetime import datetime, timedelta
from typing import Any

import psutil

from app.constants import (
    APP_VERSION,
    WATCHDOG_STATUS_FILE,
    WATCHDOG_STATUS_MAX_AGE_SECONDS,
)
from app.exceptions import ConfigurationError
from app.logger import KioskLogger
from app.services.browser_service import BrowserService
from app.services.config_service import ConfigService
from app.utils.filesystem import read_json_file
from app.utils.helpers import cpu_temperature, device_model, local_ip_address
from app.utils.network import connectivity_ok


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
            "temperature": cpu_temperature(),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024**3), 1),
            "disk_total_gb": round(disk.total / (1024**3), 1),
            "browser_status": self._browser_service.status().value,
            "internet_online": connectivity_ok(
                str(config["connectivity_check"]), str(config["url"])
            ),
            "connectivity_check": config["connectivity_check"],
            "watchdog": self.watchdog_state(),
            "url": config["url"],
            "version": APP_VERSION,
            "last_boot": boot_time.strftime("%d.%m.%Y %H:%M"),
            "uptime": self._format_uptime(boot_time),
        }

    def watchdog_state(self) -> str:
        """Liest den Gesamtzustand des Watchdogs aus der Statusdatei.

        Returns:
            Einer der Zustaende online, warning, error, offline,
            disabled oder inactive (Statusdatei fehlt oder ist
            veraltet).
        """
        try:
            status = read_json_file(WATCHDOG_STATUS_FILE)
        except ConfigurationError:
            return "inactive"
        try:
            written = datetime.fromisoformat(str(status["timestamp"]))
        except (KeyError, ValueError):
            return "inactive"
        max_age = timedelta(seconds=WATCHDOG_STATUS_MAX_AGE_SECONDS)
        if datetime.now(written.tzinfo) - written > max_age:
            return "inactive"
        overall = str(status.get("overall", "inactive"))
        allowed = ("online", "warning", "error", "offline", "disabled")
        return overall if overall in allowed else "inactive"

    def watchdog_details(self) -> dict[str, Any] | None:
        """Liest die Einzelpruefungen des Watchdogs aus der Statusdatei.

        Damit kann die Oberflaeche zeigen, welche Pruefung eine
        Warnung oder einen Fehler ausloest, statt nur den
        Gesamtzustand.

        Returns:
            Woerterbuch mit den Bereichen browser, network und
            system oder None, wenn keine aktuelle Statusdatei
            vorliegt oder der Watchdog deaktiviert ist.
        """
        if self.watchdog_state() in ("inactive", "disabled"):
            return None
        try:
            status = read_json_file(WATCHDOG_STATUS_FILE)
        except ConfigurationError:
            return None
        browser = status.get("browser")
        network = status.get("network")
        system = status.get("system")
        if not all(isinstance(part, dict) for part in (browser, network, system)):
            return None
        return {"browser": browser, "network": network, "system": system}

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
