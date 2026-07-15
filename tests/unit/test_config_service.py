# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer den ConfigService."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.exceptions import ConfigurationError, ValidationError
from app.logger import KioskLogger
from app.services.config_service import ConfigService

DEFAULTS: dict[str, Any] = {
    "hostname": "PiKiosk",
    "url": "",
    "language": "de",
    "theme": "dark",
    "fullscreen": True,
    "watchdog": True,
    "browser": "chromium",
    "first_start": True,
}


@pytest.fixture
def service(tmp_path: Path, test_logger: KioskLogger) -> ConfigService:
    """Erzeugt einen ConfigService mit temporaeren Pfaden.

    Args:
        tmp_path:
            Temporaeres Testverzeichnis.

        test_logger:
            Testspezifischer Logger.

    Returns:
        Ein einsatzbereiter ConfigService.
    """
    defaults_file = tmp_path / "defaults.json"
    defaults_file.write_text(
        json.dumps(DEFAULTS, ensure_ascii=False, indent=4), encoding="utf-8"
    )
    return ConfigService(
        logger=test_logger,
        config_file=tmp_path / "config.json",
        defaults_file=defaults_file,
        backup_dir=tmp_path / "backup",
    )


class TestConfigService:
    """Tests fuer den Konfigurationsdienst."""

    def test_load_erzeugt_konfiguration_aus_standardwerten(
        self, service: ConfigService, tmp_path: Path
    ) -> None:
        config = service.load()
        assert config == DEFAULTS
        assert (tmp_path / "config.json").exists()

    def test_save_und_load_roundtrip(self, service: ConfigService) -> None:
        config = service.load()
        config["url"] = "https://example.org/"
        config["first_start"] = False
        service.save(config)
        assert service.load() == config

    def test_save_lehnt_ungueltige_konfiguration_ab(
        self, service: ConfigService, tmp_path: Path
    ) -> None:
        config = service.load()
        config["theme"] = "neon"
        with pytest.raises(ValidationError):
            service.save(config)
        saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        assert saved["theme"] == "dark"

    def test_reset_stellt_standardwerte_wieder_her(
        self, service: ConfigService
    ) -> None:
        config = service.load()
        config["hostname"] = "Geaendert"
        service.save(config)
        assert service.reset() == DEFAULTS
        assert service.load() == DEFAULTS

    def test_backup_erzeugt_sicherungsdatei(self, service: ConfigService) -> None:
        service.load()
        backup_file = service.backup()
        assert backup_file.exists()
        assert json.loads(backup_file.read_text(encoding="utf-8")) == DEFAULTS

    def test_restore_uebernimmt_sicherung(self, service: ConfigService) -> None:
        config = service.load()
        config["url"] = "https://example.org/"
        service.save(config)
        backup_file = service.backup()
        service.reset()
        restored = service.restore(backup_file)
        assert restored["url"] == "https://example.org/"
        assert service.load() == restored

    def test_restore_lehnt_ungueltige_sicherung_ab(
        self, service: ConfigService, tmp_path: Path
    ) -> None:
        bad_backup = tmp_path / "kaputt.json"
        bad_backup.write_text('{"hostname": "x"}', encoding="utf-8")
        with pytest.raises(ValidationError):
            service.restore(bad_backup)

    def test_defektes_json_meldet_konfigurationsfehler(
        self, service: ConfigService, tmp_path: Path
    ) -> None:
        (tmp_path / "config.json").write_text("{kaputt", encoding="utf-8")
        with pytest.raises(ConfigurationError):
            service.load()

    def test_fehlende_standardwerte_melden_fehler(
        self, tmp_path: Path, test_logger: KioskLogger
    ) -> None:
        service = ConfigService(
            logger=test_logger,
            config_file=tmp_path / "config.json",
            defaults_file=tmp_path / "fehlt.json",
            backup_dir=tmp_path / "backup",
        )
        with pytest.raises(ConfigurationError):
            service.load()
