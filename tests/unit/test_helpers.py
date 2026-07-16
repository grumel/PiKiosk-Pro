# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer die Hilfsfunktionen."""

import json
import os
from pathlib import Path

import pytest

from app.exceptions import ConfigurationError, ValidationError
from app.utils.helpers import load_language, read_log_tail


class TestLoadLanguage:
    """Tests fuer das Laden der Sprachdateien."""

    def test_laedt_projektsprachen(self) -> None:
        for language in ("de", "en"):
            texts = load_language(language)
            assert texts["app_title"] == "PiKiosk Pro"
            assert texts["html_lang"] == language

    def test_unbekannte_sprache(self) -> None:
        with pytest.raises(ValidationError):
            load_language("fr")

    def test_fehlende_datei(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError):
            load_language("de", config_dir=tmp_path)

    def test_cache_liefert_kopien(self) -> None:
        first = load_language("de")
        first["app_title"] = "manipuliert"
        assert load_language("de")["app_title"] == "PiKiosk Pro"

    def test_geaenderte_datei_wird_neu_gelesen(self, tmp_path: Path) -> None:
        language_file = tmp_path / "language_de.json"
        language_file.write_text(json.dumps({"app_title": "Alt"}), encoding="utf-8")
        os.utime(language_file, ns=(1, 1))
        assert load_language("de", config_dir=tmp_path)["app_title"] == "Alt"
        language_file.write_text(json.dumps({"app_title": "Neu"}), encoding="utf-8")
        os.utime(language_file, ns=(2, 2))
        assert load_language("de", config_dir=tmp_path)["app_title"] == "Neu"


class TestReadLogTail:
    """Tests fuer das Lesen der letzten Logzeilen."""

    def test_letzte_zeilen(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        log_file.write_text(
            "".join(f"Zeile {i}\n" for i in range(10)), encoding="utf-8"
        )
        content = read_log_tail(log_file, 3)
        assert content == "Zeile 7\nZeile 8\nZeile 9\n"

    def test_fehlende_datei(self, tmp_path: Path) -> None:
        assert read_log_tail(tmp_path / "fehlt.log", 3) == ""
