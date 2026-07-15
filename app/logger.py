# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Logging.

Stellt die Klasse KioskLogger bereit. Jedes Modul erzeugt einen
eigenen Logger mit Logrotation (10 Dateien zu je 10 MB). Fehler
werden zusaetzlich auf der Konsole (stderr) ausgegeben.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.constants import LOG_BACKUP_COUNT, LOG_FORMAT, LOG_MAX_BYTES


class KioskLogger:
    """Modulbezogener Logger mit Dateirotation und Konsolenausgabe.

    Args:
        module:
            Name des Moduls, erscheint in jeder Logzeile.

        log_file:
            Pfad der Logdatei, in die geschrieben wird.

        level:
            Minimales Loglevel fuer die Dateiausgabe.
    """

    def __init__(self, module: str, log_file: Path, level: int = logging.DEBUG) -> None:
        self._logger = logging.getLogger(f"pikiosk.{module}")
        self._logger.setLevel(level)
        self._logger.propagate = False
        if not self._logger.handlers:
            self._attach_handlers(log_file)

    def _attach_handlers(self, log_file: Path) -> None:
        """Haengt Datei- und Konsolen-Handler an den Logger an.

        Args:
            log_file:
                Pfad der Logdatei.
        """
        log_file.parent.mkdir(parents=True, exist_ok=True)
        formatter = logging.Formatter(LOG_FORMAT)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.ERROR)
        console_handler.setFormatter(formatter)
        self._logger.addHandler(file_handler)
        self._logger.addHandler(console_handler)

    def debug(self, message: str) -> None:
        """Schreibt eine DEBUG-Meldung.

        Args:
            message:
                Logtext.
        """
        self._logger.debug(message)

    def info(self, message: str) -> None:
        """Schreibt eine INFO-Meldung.

        Args:
            message:
                Logtext.
        """
        self._logger.info(message)

    def warning(self, message: str) -> None:
        """Schreibt eine WARNING-Meldung.

        Args:
            message:
                Logtext.
        """
        self._logger.warning(message)

    def error(self, message: str, exc_info: bool = False) -> None:
        """Schreibt eine ERROR-Meldung, optional mit Stacktrace.

        Args:
            message:
                Logtext.

            exc_info:
                True, um den aktuellen Stacktrace mitzuloggen.
        """
        self._logger.error(message, exc_info=exc_info)

    def critical(self, message: str, exc_info: bool = False) -> None:
        """Schreibt eine CRITICAL-Meldung, optional mit Stacktrace.

        Args:
            message:
                Logtext.

            exc_info:
                True, um den aktuellen Stacktrace mitzuloggen.
        """
        self._logger.critical(message, exc_info=exc_info)
