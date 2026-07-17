# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - ConfigService.

Zentraler Dienst fuer das Lesen und Schreiben der Konfiguration
in config/config.json. Alle Module greifen ausschliesslich ueber
diesen Dienst auf Einstellungen zu. Schreibvorgaenge erfolgen
atomar, ungueltige Konfigurationen werden niemals gespeichert.
"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from app.constants import BACKUP_DIR, CONFIG_FILE, CONFIG_SCHEMA, DEFAULTS_FILE
from app.exceptions import ConfigurationError
from app.logger import KioskLogger
from app.utils.filesystem import read_json_file, write_json_atomic
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
        self._cache: dict[str, Any] | None = None
        self._cache_mtime_ns: int = -1

    def load(self) -> dict[str, Any]:
        """Laedt die aktive Konfiguration.

        Existiert noch keine Konfigurationsdatei, wird sie aus den
        Standardwerten erzeugt. Eine unveraenderte Datei wird aus
        dem Zwischenspeicher bedient, damit die Konfiguration nicht
        bei jeder Anfrage neu gelesen und validiert werden muss.

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
        mtime_ns = self._config_file.stat().st_mtime_ns
        if self._cache is not None and mtime_ns == self._cache_mtime_ns:
            return dict(self._cache)
        config = self._migrate(read_json_file(self._config_file))
        self.validate(config)
        self._cache = dict(config)
        self._cache_mtime_ns = self._config_file.stat().st_mtime_ns
        return config

    def _migrate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Ergaenzt fehlende Schluessel aus den Standardwerten.

        Nach einem Update kann eine bestehende Konfiguration neue
        Schluessel noch nicht enthalten. Diese werden aus den
        Standardwerten ergaenzt und die Konfiguration wird einmalig
        gespeichert. Vorhandene Werte bleiben unveraendert.

        Args:
            config:
                Gelesene Konfiguration.

        Returns:
            Die vollstaendige Konfiguration.

        Raises:
            ConfigurationError
            ValidationError
        """
        missing = sorted(set(CONFIG_SCHEMA) - set(config))
        if not missing:
            return config
        defaults = read_json_file(self._defaults_file)
        migrated = dict(config)
        for key in missing:
            if key not in defaults:
                raise ConfigurationError(
                    f"Der Standardwert fuer '{key}' fehlt in {self._defaults_file}."
                )
            migrated[key] = defaults[key]
        self.validate(migrated)
        write_json_atomic(self._config_file, migrated)
        self._logger.info(
            "Konfiguration ergaenzt um neue Schluessel: " + ", ".join(missing)
        )
        return migrated

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
        write_json_atomic(self._config_file, config)
        self._cache = dict(config)
        self._cache_mtime_ns = self._config_file.stat().st_mtime_ns
        self._logger.info(f"Konfiguration gespeichert: {self._config_file}")

    def reset(self) -> dict[str, Any]:
        """Setzt die Konfiguration auf die Standardwerte zurueck.

        Returns:
            Die geschriebene Standardkonfiguration.

        Raises:
            ConfigurationError
            ValidationError
        """
        defaults = read_json_file(self._defaults_file)
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
        config = read_json_file(backup_file)
        self.save(config)
        self._logger.info(f"Konfiguration wiederhergestellt aus: {backup_file}")
        return config
