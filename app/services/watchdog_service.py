# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - WatchdogService.

Ueberwacht Browser, Netzwerk und System im 5-Sekunden-Takt und
schreibt den Zustand atomar in eine Statusdatei, die das Dashboard
anzeigt. Ein abgestuerzter Browser wird ueber den internen
HTTP-Endpunkt der Hauptanwendung neu gestartet, maximal 3 Mal
innerhalb von 60 Sekunden. Danach wechselt der Watchdog in den
Fehlerstatus und informiert den Administrator ueber das Log.
"""

import json
import socket
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

import psutil

from app.constants import (
    BROWSER_RESTART_LIMIT,
    BROWSER_RESTART_URL,
    BROWSER_RESTART_WINDOW_SECONDS,
    DISK_WARNING_PERCENT,
    HEALTH_CHECK_URL,
    RAM_WARNING_PERCENT,
    TEMPERATURE_CRITICAL_CELSIUS,
    TEMPERATURE_WARNING_CELSIUS,
    URL_CHECK_TIMEOUT_SECONDS,
    WATCHDOG_HTTP_TIMEOUT_SECONDS,
    WATCHDOG_INTERVAL_SECONDS,
    WATCHDOG_STATUS_FILE,
    WATCHDOG_TOKEN_HEADER,
)
from app.exceptions import ConfigurationError, NetworkError
from app.logger import KioskLogger
from app.services.config_service import ConfigService
from app.utils.filesystem import write_json_atomic
from app.utils.helpers import cpu_temperature
from app.utils.network import (
    check_url_status,
    default_gateway,
    internet_reachable,
    ping_host,
)

APP_OFFLINE_STATUS: str = "app_offline"


class WatchdogService:
    """Ueberwacht Browser, Netzwerk und System des Kiosks.

    Args:
        logger:
            Logger fuer alle Watchdogereignisse.

        config_service:
            Dienst fuer die Konfigurationsverwaltung.

        token:
            Token fuer den internen Browser-Neustart-Endpunkt.
    """

    def __init__(
        self,
        logger: KioskLogger,
        config_service: ConfigService,
        token: str,
    ) -> None:
        self._logger = logger
        self._config_service = config_service
        self._token = token
        self._restart_times: deque[float] = deque()
        self._browser_failed = False
        self._last_warnings: set[str] = set()

    def run_forever(self) -> None:
        """Fuehrt die Ueberwachung dauerhaft im Intervall aus."""
        while True:
            started = time.monotonic()
            try:
                self.check_once()
            except Exception as error:  # noqa: BLE001 - Watchdog darf nie sterben.
                self._logger.error(
                    f"Pruefzyklus fehlgeschlagen: {error}", exc_info=True
                )
            elapsed = time.monotonic() - started
            time.sleep(max(0.0, WATCHDOG_INTERVAL_SECONDS - elapsed))

    def check_once(self) -> dict[str, Any]:
        """Fuehrt einen einzelnen Pruefzyklus aus.

        Returns:
            Der geschriebene Watchdogstatus.
        """
        config = self._safe_config()
        if config is None or not config["watchdog"]:
            status = self._build_status("disabled", {}, {}, {})
            self._write_status(status)
            return status
        browser = self._check_browser()
        network = self._check_network(str(config["url"]))
        system = self._check_system()
        overall = self._overall(browser, network, system)
        status = self._build_status(overall, browser, network, system)
        self._write_status(status)
        return status

    def _safe_config(self) -> dict[str, Any] | None:
        """Laedt die Konfiguration ohne den Watchdog zu beenden.

        Returns:
            Die Konfiguration oder None bei Fehlern.
        """
        try:
            return self._config_service.load()
        except Exception:  # noqa: BLE001 - Watchdog darf nie sterben.
            self._logger.error("Konfiguration nicht lesbar.", exc_info=True)
            return None

    def _check_browser(self) -> dict[str, Any]:
        """Prueft den Browserzustand ueber die Hauptanwendung.

        Returns:
            Browserstatus mit Neustartzaehler und Fehlerkennzeichen.
        """
        health = self._fetch_health()
        if health is None:
            self._logger.error("Hauptanwendung nicht erreichbar.")
            browser_status = APP_OFFLINE_STATUS
        else:
            browser_status = str(health.get("browser", "unknown"))
        if browser_status == "running":
            self._browser_failed = False
            self._restart_times.clear()
        elif browser_status == "crashed":
            self._handle_crashed_browser()
        self._prune_restart_times()
        return {
            "status": browser_status,
            "failed": self._browser_failed,
            "restarts_in_window": len(self._restart_times),
        }

    def _handle_crashed_browser(self) -> None:
        """Startet einen abgestuerzten Browser neu (mit Limit)."""
        if self._browser_failed:
            return
        self._prune_restart_times()
        if len(self._restart_times) >= BROWSER_RESTART_LIMIT:
            self._browser_failed = True
            self._logger.critical(
                f"Browser {BROWSER_RESTART_LIMIT} Mal innerhalb von "
                f"{int(BROWSER_RESTART_WINDOW_SECONDS)} Sekunden neu "
                "gestartet. Fehlerstatus gesetzt, Administrator "
                "informieren."
            )
            return
        if self._request_restart():
            self._restart_times.append(self._now())
            self._logger.warning(
                "Browser abgestuerzt, Neustart ausgeloest "
                f"({len(self._restart_times)}/{BROWSER_RESTART_LIMIT})."
            )
        else:
            self._logger.error("Browser-Neustart konnte nicht ausgeloest werden.")

    def _check_network(self, url: str) -> dict[str, Any]:
        """Prueft Gateway, DNS, Internet und Kiosk-URL.

        Args:
            url:
                Konfigurierte Kiosk-URL, leer wenn nicht gesetzt.

        Returns:
            Ergebnis der Netzwerkpruefungen.
        """
        gateway = default_gateway()
        url_reachable: bool | None = None
        if url:
            try:
                url_reachable, _ = check_url_status(
                    url, timeout=URL_CHECK_TIMEOUT_SECONDS
                )
            except NetworkError:
                url_reachable = False
        return {
            "gateway": ping_host(gateway) if gateway else False,
            "dns": self._dns_ok(url),
            "internet": internet_reachable(),
            "url": url_reachable,
        }

    def _dns_ok(self, url: str) -> bool:
        """Prueft die Namensaufloesung des Kiosk-URL-Hosts.

        Args:
            url:
                Konfigurierte Kiosk-URL.

        Returns:
            True, wenn die Aufloesung gelingt oder nicht noetig ist.
        """
        host = urlsplit(url).hostname if url else None
        if not host:
            return True
        try:
            socket.inet_aton(host)
            return True
        except OSError:
            pass
        try:
            socket.gethostbyname(host)
            return True
        except OSError:
            return False

    def _check_system(self) -> dict[str, Any]:
        """Prueft CPU, Speicher, Festplatte und Temperatur.

        Returns:
            Systemwerte mit Warnungsliste.
        """
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        temperature = cpu_temperature()
        warnings: list[str] = []
        if temperature is not None:
            if temperature >= TEMPERATURE_CRITICAL_CELSIUS:
                warnings.append("temperature_critical")
            elif temperature >= TEMPERATURE_WARNING_CELSIUS:
                warnings.append("temperature_warning")
        if memory.percent >= RAM_WARNING_PERCENT:
            warnings.append("ram_warning")
        if disk.percent >= DISK_WARNING_PERCENT:
            warnings.append("disk_warning")
        self._log_warning_changes(set(warnings))
        return {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "ram_percent": memory.percent,
            "disk_percent": disk.percent,
            "temperature": temperature,
            "warnings": warnings,
        }

    def _log_warning_changes(self, warnings: set[str]) -> None:
        """Protokolliert neue und aufgehobene Systemwarnungen.

        Args:
            warnings:
                Aktuelle Warnungen dieses Pruefzyklus.
        """
        for warning in sorted(warnings - self._last_warnings):
            if warning == "temperature_critical":
                self._logger.critical(f"Systemwarnung: {warning}")
            else:
                self._logger.warning(f"Systemwarnung: {warning}")
        for cleared in sorted(self._last_warnings - warnings):
            self._logger.info(f"Systemwarnung aufgehoben: {cleared}")
        self._last_warnings = warnings

    def _overall(
        self,
        browser: dict[str, Any],
        network: dict[str, Any],
        system: dict[str, Any],
    ) -> str:
        """Bestimmt den Gesamtzustand aus allen Einzelpruefungen.

        Args:
            browser:
                Ergebnis der Browserpruefung.

            network:
                Ergebnis der Netzwerkpruefung.

            system:
                Ergebnis der Systempruefung.

        Returns:
            online, warning, error oder offline.
        """
        if browser["failed"] or browser["status"] == APP_OFFLINE_STATUS:
            return "error"
        if "temperature_critical" in system["warnings"]:
            return "error"
        if not network["internet"]:
            return "offline"
        if (
            system["warnings"]
            or browser["status"] == "crashed"
            or not network["gateway"]
            or not network["dns"]
            or network["url"] is False
        ):
            return "warning"
        return "online"

    def _build_status(
        self,
        overall: str,
        browser: dict[str, Any],
        network: dict[str, Any],
        system: dict[str, Any],
    ) -> dict[str, Any]:
        """Baut das Statusobjekt fuer die Statusdatei zusammen.

        Args:
            overall:
                Gesamtzustand.

            browser:
                Ergebnis der Browserpruefung.

            network:
                Ergebnis der Netzwerkpruefung.

            system:
                Ergebnis der Systempruefung.

        Returns:
            Das vollstaendige Statusobjekt.
        """
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall": overall,
            "browser": browser,
            "network": network,
            "system": system,
        }

    def _write_status(self, status: dict[str, Any]) -> None:
        """Schreibt den Status atomar in die Statusdatei.

        Args:
            status:
                Zu schreibender Status.
        """
        try:
            write_json_atomic(WATCHDOG_STATUS_FILE, status)
        except ConfigurationError as error:
            self._logger.error(f"Statusdatei nicht schreibbar: {error}")

    def _fetch_health(self) -> dict[str, Any] | None:
        """Fragt den Health-Endpunkt der Hauptanwendung ab.

        Returns:
            Health-Daten oder None bei Fehlern.
        """
        try:
            with urllib.request.urlopen(
                HEALTH_CHECK_URL, timeout=WATCHDOG_HTTP_TIMEOUT_SECONDS
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None

    def _request_restart(self) -> bool:
        """Loest den Browser-Neustart in der Hauptanwendung aus.

        Returns:
            True, wenn der Neustart angenommen wurde.
        """
        request = urllib.request.Request(
            BROWSER_RESTART_URL,
            method="POST",
            headers={WATCHDOG_TOKEN_HEADER: self._token},
        )
        try:
            with urllib.request.urlopen(
                request, timeout=WATCHDOG_HTTP_TIMEOUT_SECONDS
            ) as response:
                return int(response.status) == 200
        except (urllib.error.URLError, OSError):
            return False

    def _prune_restart_times(self) -> None:
        """Entfernt Neustarts ausserhalb des Zeitfensters."""
        cutoff = self._now() - BROWSER_RESTART_WINDOW_SECONDS
        while self._restart_times and self._restart_times[0] < cutoff:
            self._restart_times.popleft()

    def _now(self) -> float:
        """Liefert die monotone Zeit fuer die Neustartverwaltung.

        Returns:
            Monotone Zeit in Sekunden.
        """
        return time.monotonic()
