# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - SystemService.

Fuehrt Neustart und Herunterfahren des Geraets kontrolliert durch:
Der Browser wird sauber beendet, bevor systemctl aufgerufen wird.
Ohne Root-Rechte wird sudo -n verwendet; der Installer richtet die
dafuer noetige sudo-Regel ein.
"""

import os
import subprocess

from app.constants import SYSTEM_COMMAND_TIMEOUT_SECONDS, SYSTEMCTL_BINARY
from app.exceptions import PiKioskError
from app.logger import KioskLogger
from app.services.browser_service import BrowserService


class SystemService:
    """Steuert Neustart und Herunterfahren des Systems.

    Args:
        logger:
            Logger fuer Systemereignisse.

        browser_service:
            Dienst fuer die Browsersteuerung.
    """

    def __init__(self, logger: KioskLogger, browser_service: BrowserService) -> None:
        self._logger = logger
        self._browser_service = browser_service

    def reboot(self) -> None:
        """Startet das Geraet neu.

        Raises:
            PiKioskError
        """
        self._logger.info("Systemneustart angefordert.")
        self._browser_service.stop()
        self._run_systemctl("reboot")

    def shutdown(self) -> None:
        """Faehrt das Geraet herunter.

        Raises:
            PiKioskError
        """
        self._logger.info("Herunterfahren angefordert.")
        self._browser_service.stop()
        self._run_systemctl("poweroff")

    def _run_systemctl(self, action: str) -> None:
        """Fuehrt eine systemctl-Aktion aus.

        Args:
            action:
                systemctl-Unterbefehl, zum Beispiel "reboot".

        Raises:
            PiKioskError
        """
        command = [SYSTEMCTL_BINARY, action]
        if os.geteuid() != 0:
            command = ["sudo", "-n", *command]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=SYSTEM_COMMAND_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise PiKioskError(f"Systemkommando fehlgeschlagen: {error}") from error
        if result.returncode != 0:
            details = result.stderr.strip() or result.stdout.strip()
            self._logger.error(f"systemctl {action} fehlgeschlagen: {details}")
            raise PiKioskError(f"Systemkommando fehlgeschlagen: {details}")
