# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - RestoreService.

Stellt Sicherungen wieder her: Das ZIP-Archiv wird geprueft
(Integritaet, Manifest, Versionskompatibilitaet), anschliessend
werden Konfiguration und Benutzerdatenbank uebernommen. Ungueltige
Sicherungen werden niemals angewendet. Zusaetzlich werden
eingesteckte USB-Medien nach Sicherungen durchsucht.
"""

import fnmatch
import json
import os
import sqlite3
import tempfile
import zipfile
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any

from app.constants import (
    BACKUP_CONFIG_MEMBER,
    BACKUP_MANIFEST_MEMBER,
    BACKUP_USERS_MEMBER,
    CONFIG_SCHEMA,
    USB_BACKUP_GLOB,
    USB_MOUNT_ROOTS,
    USERS_DB_FILE,
)
from app.exceptions import RestoreError, ValidationError
from app.logger import KioskLogger
from app.services.config_service import ConfigService
from app.utils.version import is_backup_compatible

USB_SCAN_PATTERNS: tuple[str, ...] = (
    f"*/{USB_BACKUP_GLOB}",
    f"*/*/{USB_BACKUP_GLOB}",
)


class RestoreService:
    """Prueft und importiert Konfigurationssicherungen.

    Args:
        logger:
            Logger fuer alle Wiederherstellungsereignisse.

        config_service:
            Dienst fuer die Konfigurationsverwaltung.

        users_db_file:
            Pfad der Benutzerdatenbank.
    """

    def __init__(
        self,
        logger: KioskLogger,
        config_service: ConfigService,
        users_db_file: Path = USERS_DB_FILE,
    ) -> None:
        self._logger = logger
        self._config_service = config_service
        self._users_db_file = users_db_file

    def validate(self, backup_path: Path) -> dict[str, Any]:
        """Prueft eine Sicherung ohne sie anzuwenden.

        Args:
            backup_path:
                Pfad der Sicherungsdatei.

        Returns:
            Das Manifest der Sicherung.

        Raises:
            RestoreError
        """
        if not backup_path.exists():
            raise RestoreError(f"Die Sicherung wurde nicht gefunden: {backup_path}")
        if not zipfile.is_zipfile(backup_path):
            raise RestoreError("Die Datei ist keine gueltige ZIP-Sicherung.")
        try:
            with zipfile.ZipFile(backup_path) as archive:
                if archive.testzip() is not None:
                    raise RestoreError("Die Sicherung ist beschaedigt.")
                manifest = self._read_manifest(archive)
                if BACKUP_CONFIG_MEMBER not in archive.namelist():
                    raise RestoreError(
                        "Die Sicherung enthaelt keine Konfigurationsdatei."
                    )
                self._merged_config(archive)
        except (zipfile.BadZipFile, zlib.error, EOFError, OSError) as error:
            raise RestoreError(f"Die Sicherung ist beschaedigt: {error}") from error
        return manifest

    def restore(self, backup_path: Path) -> dict[str, Any]:
        """Stellt eine gepruefte Sicherung wieder her.

        Args:
            backup_path:
                Pfad der Sicherungsdatei.

        Returns:
            Das Manifest der wiederhergestellten Sicherung.

        Raises:
            RestoreError
        """
        manifest = self.validate(backup_path)
        try:
            with zipfile.ZipFile(backup_path) as archive:
                config = self._merged_config(archive)
                if BACKUP_USERS_MEMBER in archive.namelist():
                    self._restore_users_database(archive)
                self._config_service.save(config)
        except (zipfile.BadZipFile, zlib.error, EOFError) as error:
            raise RestoreError(f"Die Sicherung ist beschaedigt: {error}") from error
        self._logger.info(f"Sicherung wiederhergestellt: {backup_path.name}")
        return manifest

    def scan_usb(self) -> list[dict[str, Any]]:
        """Durchsucht eingehaengte USB-Medien nach Sicherungen.

        Returns:
            Gefundene Sicherungen mit Pfad, Name, Groesse und
            Aenderungszeit, neueste zuerst.
        """
        found: list[dict[str, Any]] = []
        for root in USB_MOUNT_ROOTS:
            if not root.exists():
                continue
            for pattern in USB_SCAN_PATTERNS:
                for path in root.glob(pattern):
                    if not path.is_file():
                        continue
                    info = path.stat()
                    found.append(
                        {
                            "path": str(path),
                            "name": path.name,
                            "size_kb": max(1, info.st_size // 1024),
                            "created": datetime.fromtimestamp(info.st_mtime).strftime(
                                "%d.%m.%Y %H:%M"
                            ),
                        }
                    )
        found.sort(key=lambda entry: str(entry["name"]), reverse=True)
        return found

    def import_from_path(self, path_text: str) -> dict[str, Any]:
        """Importiert eine Sicherung von einem USB-Medium.

        Args:
            path_text:
                Absoluter Pfad der Sicherung auf dem USB-Medium.

        Returns:
            Das Manifest der importierten Sicherung.

        Raises:
            RestoreError
        """
        path = Path(path_text).resolve()
        allowed = any(path.is_relative_to(root) for root in USB_MOUNT_ROOTS)
        if not allowed or not fnmatch.fnmatch(path.name, USB_BACKUP_GLOB):
            raise RestoreError(f"Unzulaessiger Sicherungspfad: {path_text!r}")
        return self.restore(path)

    def _read_manifest(self, archive: zipfile.ZipFile) -> dict[str, Any]:
        """Liest und prueft das Manifest einer Sicherung.

        Args:
            archive:
                Geoeffnetes ZIP-Archiv.

        Returns:
            Das gueltige Manifest.

        Raises:
            RestoreError
        """
        if BACKUP_MANIFEST_MEMBER not in archive.namelist():
            raise RestoreError("Die Sicherung enthaelt kein Manifest.")
        try:
            manifest = json.loads(archive.read(BACKUP_MANIFEST_MEMBER).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as error:
            raise RestoreError(
                f"Das Manifest der Sicherung ist ungueltig: {error}"
            ) from error
        if not isinstance(manifest, dict) or "app_version" not in manifest:
            raise RestoreError("Das Manifest der Sicherung ist unvollstaendig.")
        try:
            compatible = is_backup_compatible(str(manifest["app_version"]))
        except ValidationError as error:
            raise RestoreError(str(error)) from error
        if not compatible:
            raise RestoreError(
                "Die Sicherung stammt aus einer nicht kompatiblen Version "
                f"({manifest['app_version']})."
            )
        return manifest

    def _merged_config(self, archive: zipfile.ZipFile) -> dict[str, Any]:
        """Liest die gesicherte Konfiguration und prueft sie.

        Die gesicherten Werte werden ueber die aktuelle Konfiguration
        gelegt, damit Sicherungen aelterer Versionen ohne neue
        Schluessel wiederhergestellt werden koennen.

        Args:
            archive:
                Geoeffnetes ZIP-Archiv.

        Returns:
            Die validierte, zusammengefuehrte Konfiguration.

        Raises:
            RestoreError
        """
        try:
            backup_config = json.loads(
                archive.read(BACKUP_CONFIG_MEMBER).decode("utf-8")
            )
        except (KeyError, ValueError, UnicodeDecodeError) as error:
            raise RestoreError(
                f"Die gesicherte Konfiguration ist ungueltig: {error}"
            ) from error
        if not isinstance(backup_config, dict):
            raise RestoreError("Die gesicherte Konfiguration ist kein JSON-Objekt.")
        merged = self._config_service.load()
        merged.update(
            {key: value for key, value in backup_config.items() if key in CONFIG_SCHEMA}
        )
        try:
            self._config_service.validate(merged)
        except ValidationError as error:
            raise RestoreError(
                f"Die gesicherte Konfiguration ist ungueltig: {error}"
            ) from error
        return merged

    def _restore_users_database(self, archive: zipfile.ZipFile) -> None:
        """Ersetzt die Benutzerdatenbank durch die gesicherte Fassung.

        Args:
            archive:
                Geoeffnetes ZIP-Archiv.

        Raises:
            RestoreError
        """
        self._users_db_file.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            dir=self._users_db_file.parent, prefix="users", suffix=".db.tmp"
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(archive.read(BACKUP_USERS_MEMBER))
            self._validate_users_database(Path(temp_name))
            os.replace(temp_name, self._users_db_file)
        except OSError as error:
            raise RestoreError(
                f"Die Benutzerdatenbank konnte nicht uebernommen werden: {error}"
            ) from error
        finally:
            Path(temp_name).unlink(missing_ok=True)

    def _validate_users_database(self, path: Path) -> None:
        """Prueft eine gesicherte Benutzerdatenbank.

        Args:
            path:
                Pfad der zu pruefenden Datenbankdatei.

        Raises:
            RestoreError
        """
        try:
            connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                row = connection.execute("SELECT COUNT(*) FROM users").fetchone()
            finally:
                connection.close()
        except sqlite3.Error as error:
            raise RestoreError(
                f"Die gesicherte Benutzerdatenbank ist ungueltig: {error}"
            ) from error
        if int(row[0]) < 1:
            raise RestoreError(
                "Die gesicherte Benutzerdatenbank enthaelt keine Benutzer."
            )
