# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer die Dateisystem-Helfer."""

from pathlib import Path

import pytest

from app.exceptions import ConfigurationError
from app.utils.filesystem import read_json_file, write_json_atomic


class TestReadJsonFile:
    """Tests fuer das Lesen von JSON-Dateien."""

    def test_liest_objekt(self, tmp_path: Path) -> None:
        path = tmp_path / "daten.json"
        path.write_text('{"a": 1}', encoding="utf-8")
        assert read_json_file(path) == {"a": 1}

    def test_fehlende_datei(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError):
            read_json_file(tmp_path / "fehlt.json")

    def test_kaputtes_json(self, tmp_path: Path) -> None:
        path = tmp_path / "kaputt.json"
        path.write_text("{kaputt", encoding="utf-8")
        with pytest.raises(ConfigurationError):
            read_json_file(path)

    def test_kein_objekt(self, tmp_path: Path) -> None:
        path = tmp_path / "liste.json"
        path.write_text("[1, 2]", encoding="utf-8")
        with pytest.raises(ConfigurationError):
            read_json_file(path)

    def test_lesefehler(self, tmp_path: Path) -> None:
        path = tmp_path / "gesperrt.json"
        path.write_text("{}", encoding="utf-8")
        path.chmod(0o000)
        try:
            with pytest.raises(ConfigurationError):
                read_json_file(path)
        finally:
            path.chmod(0o600)


class TestWriteJsonAtomic:
    """Tests fuer das atomare Schreiben von JSON-Dateien."""

    def test_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "unterordner" / "daten.json"
        write_json_atomic(path, {"a": 1})
        assert read_json_file(path) == {"a": 1}

    def test_schreibfehler(self, tmp_path: Path) -> None:
        target = tmp_path / "gesperrt"
        target.mkdir()
        target.chmod(0o500)
        try:
            with pytest.raises(ConfigurationError):
                write_json_atomic(target / "daten.json", {"a": 1})
        finally:
            target.chmod(0o700)
