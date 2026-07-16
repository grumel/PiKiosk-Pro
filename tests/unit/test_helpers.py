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


class TestSystemHelpers:
    """Tests fuer Geraete- und Temperaturhelfer."""

    def test_cpu_temperatur_aus_sensoren(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.utils import helpers as helpers_module

        class Reading:
            current = 55.4

        monkeypatch.setattr(
            helpers_module.psutil,
            "sensors_temperatures",
            lambda: {"cpu_thermal": [Reading()]},
        )
        assert helpers_module.cpu_temperature() == 55.4

    def test_cpu_temperatur_aus_thermalzone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.utils import helpers as helpers_module

        zone = tmp_path / "temp"
        zone.write_text("47500\n", encoding="ascii")
        monkeypatch.setattr(helpers_module.psutil, "sensors_temperatures", lambda: {})
        monkeypatch.setattr(helpers_module, "THERMAL_ZONE_FILE", zone)
        assert helpers_module.cpu_temperature() == 47.5

    def test_cpu_temperatur_ohne_sensor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.utils import helpers as helpers_module

        monkeypatch.setattr(helpers_module.psutil, "sensors_temperatures", lambda: {})
        monkeypatch.setattr(helpers_module, "THERMAL_ZONE_FILE", tmp_path / "fehlt")
        assert helpers_module.cpu_temperature() is None

    def test_geraetemodell(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.utils import helpers as helpers_module

        model_file = tmp_path / "model"
        model_file.write_text("Raspberry Pi 4 Model B\x00", encoding="utf-8")
        monkeypatch.setattr(helpers_module, "DEVICE_MODEL_FILE", model_file)
        assert helpers_module.device_model() == "Raspberry Pi 4 Model B"
        monkeypatch.setattr(helpers_module, "DEVICE_MODEL_FILE", tmp_path / "fehlt")
        assert helpers_module.device_model() == ""

    def test_lokale_ip_ohne_netz(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.utils import helpers as helpers_module

        class FakeSocket:
            def connect(self, target: tuple[str, int]) -> None:
                raise OSError("kein Netz")

            def close(self) -> None:
                pass

        monkeypatch.setattr(
            helpers_module.socket, "socket", lambda *a, **k: FakeSocket()
        )
        assert helpers_module.local_ip_address() == "0.0.0.0"


class TestSecretKey:
    """Tests fuer die Schluesseldatei."""

    def test_erzeugt_und_liest_schluessel(self, tmp_path: Path) -> None:
        from app.utils.helpers import load_or_create_secret_key

        key_file = tmp_path / "secret_key"
        key = load_or_create_secret_key(key_file)
        assert len(key) == 64
        assert load_or_create_secret_key(key_file) == key

    def test_schreibfehler_meldet_konfigurationsfehler(self, tmp_path: Path) -> None:
        from app.utils.helpers import load_or_create_secret_key

        target = tmp_path / "gesperrt"
        target.mkdir()
        target.chmod(0o500)
        try:
            with pytest.raises(ConfigurationError):
                load_or_create_secret_key(target / "secret_key")
        finally:
            target.chmod(0o700)


class TestLanguageFileErrors:
    """Tests fuer defekte Sprachdateien."""

    def test_kaputtes_json(self, tmp_path: Path) -> None:
        (tmp_path / "language_de.json").write_text("{kaputt", encoding="utf-8")
        with pytest.raises(ConfigurationError):
            load_language("de", config_dir=tmp_path)

    def test_kein_objekt(self, tmp_path: Path) -> None:
        (tmp_path / "language_de.json").write_text("[1, 2]", encoding="utf-8")
        with pytest.raises(ConfigurationError):
            load_language("de", config_dir=tmp_path)
