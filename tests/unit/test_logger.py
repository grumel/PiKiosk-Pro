# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer den KioskLogger."""

import logging
from pathlib import Path

from app.logger import KioskLogger


class TestKioskLogger:
    """Tests fuer die Logger-Klasse."""

    def test_schreibt_in_logdatei(self, tmp_path: Path) -> None:
        log_file = tmp_path / "system.log"
        logger = KioskLogger("test_schreibt", log_file)
        logger.info("Testnachricht")
        content = log_file.read_text(encoding="utf-8")
        assert "Testnachricht" in content
        assert "INFO" in content
        assert "pikiosk.test_schreibt" in content

    def test_alle_loglevel(self, tmp_path: Path) -> None:
        log_file = tmp_path / "level.log"
        logger = KioskLogger("test_level", log_file)
        logger.debug("Debugtext")
        logger.info("Infotext")
        logger.warning("Warntext")
        logger.error("Fehlertext")
        logger.critical("Kritischtext")
        content = log_file.read_text(encoding="utf-8")
        for expected in (
            "Debugtext",
            "Infotext",
            "Warntext",
            "Fehlertext",
            "Kritischtext",
        ):
            assert expected in content

    def test_stacktrace_bei_fehler(self, tmp_path: Path) -> None:
        log_file = tmp_path / "trace.log"
        logger = KioskLogger("test_trace", log_file)
        try:
            raise ValueError("Absichtlicher Testfehler")
        except ValueError:
            logger.error("Fehler mit Stacktrace", exc_info=True)
        content = log_file.read_text(encoding="utf-8")
        assert "Traceback" in content
        assert "Absichtlicher Testfehler" in content

    def test_keine_doppelten_handler(self, tmp_path: Path) -> None:
        log_file = tmp_path / "double.log"
        KioskLogger("test_double", log_file)
        KioskLogger("test_double", log_file)
        internal = logging.getLogger("pikiosk.test_double")
        assert len(internal.handlers) == 2

    def test_erzeugt_logverzeichnis(self, tmp_path: Path) -> None:
        log_file = tmp_path / "unterordner" / "neu.log"
        logger = KioskLogger("test_mkdir", log_file)
        logger.info("Verzeichnistest")
        assert log_file.exists()
