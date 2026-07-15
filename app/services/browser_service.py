# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - BrowserService.

Steuert den Chromium-Browser ausschliesslich ueber Python.
Der Browserprozess wird per subprocess verwaltet, der Seiten-
Reload erfolgt ueber das Chrome-DevTools-Protokoll. Es werden
keine Shellskripte verwendet.
"""

import os
import shutil
import subprocess
from enum import Enum
from pathlib import Path

from app.constants import (
    BROWSER_ARGS,
    BROWSER_STOP_TIMEOUT_SECONDS,
    BROWSER_USER_DATA_DIR,
    CDP_HOST,
    CDP_PORT,
    CHROMIUM_BINARIES,
)
from app.exceptions import BrowserError, NetworkError
from app.logger import KioskLogger
from app.utils.network import DevToolsClient
from app.utils.validators import URLValidator


class BrowserStatus(Enum):
    """Moegliche Zustaende des Kioskbrowsers."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    RESTARTING = "restarting"
    ERROR = "error"
    CRASHED = "crashed"


class BrowserService:
    """Verwaltet den Chromium-Prozess des Kiosksystems.

    Args:
        logger:
            Logger fuer alle Browserereignisse.

        user_data_dir:
            Chromium-Profilverzeichnis des Kiosks.
    """

    def __init__(
        self,
        logger: KioskLogger,
        user_data_dir: Path = BROWSER_USER_DATA_DIR,
    ) -> None:
        self._logger = logger
        self._user_data_dir = user_data_dir
        self._url_validator = URLValidator()
        self._process: subprocess.Popen[bytes] | None = None
        self._status = BrowserStatus.NOT_STARTED
        self._command: list[str] = []
        self._current_url: str | None = None

    def start(self, url: str) -> None:
        """Startet Chromium im Kioskmodus mit der angegebenen URL.

        Args:
            url:
                Anzuzeigende URL.

        Raises:
            BrowserError
            ValidationError
        """
        self._url_validator.validate(url)
        if self.status() is BrowserStatus.RUNNING:
            raise BrowserError("Der Browser laeuft bereits.")
        binary = self._find_binary()
        self._user_data_dir.mkdir(parents=True, exist_ok=True)
        self._command = self._build_command(binary, url)
        environment = os.environ.copy()
        environment.setdefault("DISPLAY", ":0")
        try:
            self._process = subprocess.Popen(
                self._command,
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as error:
            self._status = BrowserStatus.ERROR
            raise BrowserError(
                f"Chromium konnte nicht gestartet werden: {error}"
            ) from error
        self._current_url = url
        self._status = BrowserStatus.RUNNING
        self._logger.info(f"Browser gestartet mit URL: {url}")

    def stop(self) -> None:
        """Beendet den Browserprozess kontrolliert."""
        if self._process is None:
            self._logger.warning("Stoppanforderung ignoriert, es laeuft kein Browser.")
            self._status = BrowserStatus.NOT_STARTED
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=BROWSER_STOP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            self._logger.warning("Browser reagiert nicht, Prozess wird beendet.")
            self._process.kill()
            self._process.wait()
        self._process = None
        self._status = BrowserStatus.NOT_STARTED
        self._logger.info("Browser gestoppt.")

    def restart(self) -> None:
        """Startet den Browser mit der zuletzt verwendeten URL neu.

        Raises:
            BrowserError
        """
        if self._current_url is None:
            raise BrowserError(
                "Neustart nicht moeglich, der Browser wurde noch nie gestartet."
            )
        self._logger.info("Browser wird neu gestartet.")
        self._status = BrowserStatus.RESTARTING
        if self._process is not None:
            self.stop()
        self.start(self._current_url)

    def reload(self) -> None:
        """Laedt die aktive Seite ueber das DevTools-Protokoll neu.

        Raises:
            BrowserError
        """
        if self.status() is not BrowserStatus.RUNNING:
            raise BrowserError("Neuladen nicht moeglich, der Browser laeuft nicht.")
        client = DevToolsClient(CDP_HOST, CDP_PORT)
        try:
            client.reload_page()
        except NetworkError as error:
            self._logger.error(f"Seiten-Reload fehlgeschlagen: {error}")
            raise BrowserError(
                f"Die Seite konnte nicht neu geladen werden: {error}"
            ) from error
        self._logger.info("Seite neu geladen.")

    def clear_cache(self) -> None:
        """Loescht das Chromium-Profil des Kiosks vollstaendig.

        Ein laufender Browser wird dazu gestoppt und anschliessend
        automatisch wieder gestartet.

        Raises:
            BrowserError
        """
        was_running = self.status() is BrowserStatus.RUNNING
        if was_running:
            self.stop()
        try:
            if self._user_data_dir.exists():
                shutil.rmtree(self._user_data_dir)
        except OSError as error:
            self._status = BrowserStatus.ERROR
            raise BrowserError(
                f"Der Browsercache konnte nicht geloescht werden: {error}"
            ) from error
        self._logger.info("Browsercache geloescht.")
        if was_running and self._current_url is not None:
            self.start(self._current_url)

    def status(self) -> BrowserStatus:
        """Ermittelt den aktuellen Browserstatus.

        Returns:
            Der aktuelle Status des Browserprozesses.
        """
        if self._process is None:
            return self._status
        if self._process.poll() is None:
            return BrowserStatus.RUNNING
        exit_code = self._process.returncode
        self._process = None
        self._status = BrowserStatus.CRASHED
        self._logger.error(f"Browserprozess unerwartet beendet, Exit-Code {exit_code}.")
        return self._status

    def fullscreen(self) -> bool:
        """Prueft, ob der Browser im Vollbild-Kioskmodus laeuft.

        Returns:
            True, wenn der Browser laeuft und mit Kiosk-Parametern
            gestartet wurde.
        """
        return self.status() is BrowserStatus.RUNNING and "--kiosk" in self._command

    def _find_binary(self) -> str:
        """Sucht die installierte Chromium-Programmdatei.

        Returns:
            Absoluter Pfad zur Chromium-Programmdatei.

        Raises:
            BrowserError
        """
        for name in CHROMIUM_BINARIES:
            binary = shutil.which(name)
            if binary:
                return binary
        raise BrowserError("Chromium ist nicht installiert oder nicht im Suchpfad.")

    def _build_command(self, binary: str, url: str) -> list[str]:
        """Baut die Chromium-Kommandozeile zusammen.

        Args:
            binary:
                Pfad zur Chromium-Programmdatei.

            url:
                Anzuzeigende URL.

        Returns:
            Vollstaendige Kommandozeile als Liste.
        """
        return [
            binary,
            *BROWSER_ARGS,
            f"--user-data-dir={self._user_data_dir}",
            f"--remote-debugging-port={CDP_PORT}",
            url,
        ]
