# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - BackupService.

Erstellt und verwaltet Sicherungen als ZIP-Archiv. Eine Sicherung
enthaelt die Konfiguration, die Benutzerdatenbank und optional die
Logdateien sowie ein Manifest mit Version und Erstellungszeitpunkt.
Cache und temporaere Dateien werden nicht gesichert.
"""

import json
import re
import socket
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.constants import (
    APP_VERSION,
    BACKUP_CONFIG_MEMBER,
    BACKUP_DIR,
    BACKUP_MANIFEST_MEMBER,
    BACKUP_NAME_REGEX,
    BACKUP_PREFIX,
    BACKUP_TIMESTAMP_FORMAT,
    BACKUP_USERS_MEMBER,
    CONFIG_FILE,
    LOG_DIR,
    USERS_DB_FILE,
)
from app.exceptions import BackupError
from app.logger import KioskLogger
from app.services.config_service import ConfigService

BACKUP_NAME_PATTERN: re.Pattern[str] = re.compile(BACKUP_NAME_REGEX)


class BackupService:
    """Erstellt und verwaltet Konfigurationssicherungen.

    Args:
        logger:
            Logger fuer alle Sicherungsereignisse.

        config_service:
            Dienst fuer die Konfigurationsverwaltung.

        config_file:
            Pfad der aktiven Konfigurationsdatei.

        users_db_file:
            Pfad der Benutzerdatenbank.

        backup_dir:
            Verzeichnis fuer Sicherungsdateien.

        log_dir:
            Verzeichnis der Logdateien.
    """

    def __init__(
        self,
        logger: KioskLogger,
        config_service: ConfigService,
        config_file: Path = CONFIG_FILE,
        users_db_file: Path = USERS_DB_FILE,
        backup_dir: Path = BACKUP_DIR,
        log_dir: Path = LOG_DIR,
    ) -> None:
        self._logger = logger
        self._config_service = config_service
        self._config_file = config_file
        self._users_db_file = users_db_file
        self._backup_dir = backup_dir
        self._log_dir = log_dir

    def create(self, include_logs: bool = False) -> Path:
        """Erstellt eine neue Sicherung als ZIP-Archiv.

        Args:
            include_logs:
                True, um die Logdateien mitzusichern.

        Returns:
            Pfad der erstellten Sicherungsdatei.

        Raises:
            BackupError
        """
        self._config_service.load()
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime(BACKUP_TIMESTAMP_FORMAT)
        backup_path = self._backup_dir / f"{BACKUP_PREFIX}{timestamp}.zip"
        manifest = {
            "app_version": APP_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "hostname": socket.gethostname(),
            "include_logs": include_logs,
        }
        try:
            with zipfile.ZipFile(
                backup_path, "w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                archive.writestr(
                    BACKUP_MANIFEST_MEMBER,
                    json.dumps(manifest, ensure_ascii=False, indent=4),
                )
                archive.write(self._config_file, BACKUP_CONFIG_MEMBER)
                if self._users_db_file.exists():
                    archive.write(self._users_db_file, BACKUP_USERS_MEMBER)
                if include_logs:
                    for log_file in sorted(self._log_dir.glob("*.log")):
                        archive.write(log_file, f"logs/{log_file.name}")
        except OSError as error:
            raise BackupError(
                f"Die Sicherung konnte nicht erstellt werden: {error}"
            ) from error
        self._logger.info(f"Sicherung erstellt: {backup_path.name}")
        return backup_path

    def list_backups(self) -> list[dict[str, Any]]:
        """Listet alle vorhandenen Sicherungen auf.

        Returns:
            Sicherungen mit Name, Groesse und Erstellungszeit,
            neueste zuerst.
        """
        backups: list[dict[str, Any]] = []
        if not self._backup_dir.exists():
            return backups
        for path in sorted(self._backup_dir.glob("*.zip"), reverse=True):
            if not BACKUP_NAME_PATTERN.match(path.name):
                continue
            info = path.stat()
            backups.append(
                {
                    "name": path.name,
                    "size_kb": max(1, info.st_size // 1024),
                    "created": datetime.fromtimestamp(info.st_mtime).strftime(
                        "%d.%m.%Y %H:%M"
                    ),
                }
            )
        return backups

    def backup_file(self, name: str) -> Path:
        """Liefert den Pfad einer vorhandenen Sicherung.

        Args:
            name:
                Dateiname der Sicherung.

        Returns:
            Pfad der Sicherungsdatei.

        Raises:
            BackupError
        """
        if not BACKUP_NAME_PATTERN.match(name):
            raise BackupError(f"Ungueltiger Sicherungsname: {name!r}")
        path = self._backup_dir / name
        if not path.exists():
            raise BackupError(f"Die Sicherung wurde nicht gefunden: {name}")
        return path
