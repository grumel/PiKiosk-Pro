# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - ConfigService.

Zentraler Dienst fuer das Lesen und Schreiben der Konfiguration
in config/config.json. Alle Module greifen ausschliesslich ueber
diesen Dienst auf Einstellungen zu. Schreibvorgaenge erfolgen
atomar, ungueltige Konfigurationen werden niemals gespeichert.
"""

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from app.constants import BACKUP_DIR, CONFIG_FILE, DEFAULTS_FILE
from app.exceptions import ConfigurationError
from app.logger import KioskLogger
from app.utils.validators import ConfigValidator


class ConfigService:
    """Verwaltet die JSON-Konfiguration von PiKiosk Pro.

    Args:
        logger:
            Logger fuer alle Konfigurationsereignisse.

        config_file:
            Pfad zur aktiven Konfigurationsdatei.

        defaults_file:
            Pfad zur Datei mit den Standardwerten.

        backup_dir:
            Verzeichnis fuer Konfigurationssicherungen.
    """

    def __init__(
        self,
        logger: KioskLogger,
        config_file: Path = CONFIG_FILE,
        defaults_file: Path = DEFAULTS_FILE,
        backup_dir: Path = BACKUP_DIR,
    ) -> None:
        self._logger = logger
        self._config_file = config_file
        self._defaults_file = defaults_file
        self._backup_dir = backup_dir
        self._validator = ConfigValidator()

    def load(self) -> dict[str, Any]:
        """Laedt die aktive Konfiguration.

        Existiert noch keine Konfigurationsdatei, wird sie aus den
        Standardwerten erzeugt.

        Returns:
            Die validierte Konfiguration.

        Raises:
            ConfigurationError
        """
        if not self._config_file.exists():
            self._logger.info(
                "Keine Konfiguration gefunden, Standardwerte werden gesetzt."
            )
            return self.reset()
        config = self._read_json(self._config_file)
        self.validate(config)
        return config

    def save(self, config: dict[str, Any]) -> None:
        """Validiert und speichert eine Konfiguration atomar.

        Args:
            config:
                Zu speichernde Konfiguration.

        Raises:
            ConfigurationError
            ValidationError
        """
        self.validate(config)
        self._write_json_atomic(self._config_file, config)
        self._logger.info(f"Konfiguration gespeichert: {self._config_file}")

    def reset(self) -> dict[str, Any]:
        """Setzt die Konfiguration auf die Standardwerte zurueck.

        Returns:
            Die geschriebene Standardkonfiguration.

        Raises:
            ConfigurationError
            ValidationError
        """
        defaults = self._read_json(self._defaults_file)
        self.save(defaults)
        self._logger.info("Konfiguration auf Standardwerte zurueckgesetzt.")
        return defaults

    def validate(self, config: dict[str, Any]) -> None:
        """Validiert eine Konfiguration ohne sie zu speichern.

        Args:
            config:
                Zu pruefende Konfiguration.

        Raises:
            ValidationError
        """
        self._validator.validate(config)

    def backup(self) -> Path:
        """Erstellt eine Sicherungskopie der aktiven Konfiguration.

        Returns:
            Pfad der erzeugten Sicherungsdatei.

        Raises:
            ConfigurationError
        """
        self.load()
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self._backup_dir / f"config_{timestamp}.json"
        try:
            shutil.copy2(self._config_file, backup_file)
        except OSError as error:
            raise ConfigurationError(
                f"Sicherung konnte nicht erstellt werden: {error}"
            ) from error
        self._logger.info(f"Konfigurationssicherung erstellt: {backup_file}")
        return backup_file

    def restore(self, backup_file: Path) -> dict[str, Any]:
        """Stellt eine Konfiguration aus einer Sicherung wieder her.

        Args:
            backup_file:
                Pfad der Sicherungsdatei.

        Returns:
            Die wiederhergestellte Konfiguration.

        Raises:
            ConfigurationError
            ValidationError
        """
        config = self._read_json(backup_file)
        self.save(config)
        self._logger.info(f"Konfiguration wiederhergestellt aus: {backup_file}")
        return config

    def _read_json(self, path: Path) -> dict[str, Any]:
        """Liest eine JSON-Datei ein.

        Args:
            path:
                Pfad der JSON-Datei.

        Returns:
            Inhalt der Datei als Woerterbuch.

        Raises:
            ConfigurationError
        """
        try:
            with path.open("r", encoding="utf-8") as handle:
                content = json.load(handle)
        except FileNotFoundError as error:
            raise ConfigurationError(f"Datei nicht gefunden: {path}") from error
        except json.JSONDecodeError as error:
            raise ConfigurationError(f"Ungueltiges JSON in {path}: {error}") from error
        except OSError as error:
            raise ConfigurationError(
                f"Datei konnte nicht gelesen werden: {path}: {error}"
            ) from error
        if not isinstance(content, dict):
            raise ConfigurationError(f"Die Datei {path} enthaelt kein JSON-Objekt.")
        return content

    def _write_json_atomic(self, path: Path, data: dict[str, Any]) -> None:
        """Schreibt ein Woerterbuch atomar als JSON-Datei.

        Args:
            path:
                Zielpfad.

            data:
                Zu schreibende Daten.

        Raises:
            ConfigurationError
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor, temp_name = tempfile.mkstemp(
                dir=path.parent, prefix=path.name, suffix=".tmp"
            )
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=4)
                handle.write("\n")
            os.replace(temp_name, path)
        except OSError as error:
            raise ConfigurationError(
                f"Datei konnte nicht geschrieben werden: {path}: {error}"
            ) from error
