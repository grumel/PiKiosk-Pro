# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - HostnameService.

Verwaltet den Hostnamen des Geraets. Die Aenderung der
Systemdateien /etc/hostname und /etc/hosts sowie der Aufruf von
hostnamectl erfolgen ueber das Helferskript
scripts/hostname_apply.py, das mit Root-Rechten laeuft.
"""

import os
import socket
import subprocess
import sys
import threading

from app.constants import ETC_HOSTNAME_FILE, HOSTNAME_APPLY_SCRIPT
from app.exceptions import NetworkError
from app.logger import KioskLogger
from app.utils.helpers import local_ip_address
from app.utils.validators import HostnameValidator

APPLY_TIMEOUT_SECONDS: float = 30.0
LOOKUP_TIMEOUT_SECONDS: float = 1.0


class HostnameService:
    """Liest, prueft und setzt den Hostnamen des Systems.

    Args:
        logger:
            Logger fuer alle Hostnameereignisse.
    """

    def __init__(self, logger: KioskLogger) -> None:
        self._logger = logger
        self._validator = HostnameValidator()

    def get(self) -> str:
        """Liefert den aktuellen Hostnamen.

        Returns:
            Der aktuelle Hostname des Systems.
        """
        return socket.gethostname()

    def validate(self, hostname: str) -> None:
        """Prueft einen Hostnamen gegen die Projektregeln.

        Args:
            hostname:
                Zu pruefender Hostname.

        Raises:
            ValidationError
        """
        self._validator.validate(hostname)

    def is_taken(self, hostname: str) -> bool:
        """Prueft per mDNS-Aufloesung, ob der Hostname vergeben ist.

        Die Aufloesung laeuft in einem Hintergrund-Thread mit
        kurzem Zeitlimit, damit die Oberflaeche nicht bis zum
        DNS-Timeout blockiert. Antwortet niemand rechtzeitig, gilt
        der Name als frei.

        Args:
            hostname:
                Zu pruefender Hostname.

        Returns:
            True, wenn ein anderes Geraet den Namen bereits nutzt.
        """
        if hostname.lower() == socket.gethostname().lower():
            return False
        resolved: list[str] = []

        def resolve() -> None:
            try:
                resolved.append(socket.gethostbyname(f"{hostname}.local"))
            except OSError:
                pass

        worker = threading.Thread(target=resolve, daemon=True)
        worker.start()
        worker.join(LOOKUP_TIMEOUT_SECONDS)
        if not resolved:
            return False
        return resolved[0] != local_ip_address()

    def set(self, hostname: str) -> None:
        """Validiert und setzt einen neuen Hostnamen.

        Args:
            hostname:
                Neuer Hostname.

        Raises:
            ValidationError
            NetworkError
        """
        self.validate(hostname)
        if hostname == self.get():
            self._logger.info(f"Hostname unveraendert: {hostname}")
            return
        self.apply(hostname)

    def apply(self, hostname: str) -> None:
        """Wendet einen Hostnamen ueber das Root-Helferskript an.

        Args:
            hostname:
                Neuer Hostname.

        Raises:
            NetworkError
        """
        command = self._build_apply_command(hostname)
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=APPLY_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise NetworkError(
                f"Der Hostname konnte nicht gesetzt werden: {error}"
            ) from error
        if result.returncode != 0:
            details = result.stderr.strip() or result.stdout.strip()
            self._logger.error(f"Hostname-Aenderung fehlgeschlagen: {details}")
            raise NetworkError(f"Der Hostname konnte nicht gesetzt werden: {details}")
        self._logger.info(f"Hostname gesetzt: {hostname}")

    def reboot_required(self) -> bool:
        """Prueft, ob ein Neustart fuer den Hostnamen erforderlich ist.

        Returns:
            True, wenn der konfigurierte Hostname in /etc/hostname
            vom laufenden Hostnamen abweicht.
        """
        try:
            configured = ETC_HOSTNAME_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            return False
        return bool(configured) and configured != self.get()

    def _build_apply_command(self, hostname: str) -> list[str]:
        """Baut den Aufruf des Helferskripts zusammen.

        Args:
            hostname:
                Neuer Hostname.

        Returns:
            Kommandozeile fuer das Helferskript, bei fehlenden
            Root-Rechten mit vorangestelltem sudo.
        """
        command = [sys.executable, str(HOSTNAME_APPLY_SCRIPT), hostname]
        if os.geteuid() != 0:
            command = ["sudo", "-n", *command]
        return command
