# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer die Validatoren."""

from typing import Any

import pytest

from app.exceptions import ValidationError
from app.utils.validators import (
    ConfigValidator,
    HostnameValidator,
    URLValidator,
)


def valid_config() -> dict[str, Any]:
    """Liefert eine gueltige Beispielkonfiguration.

    Returns:
        Gueltige Konfiguration.
    """
    return {
        "hostname": "PiKiosk",
        "url": "https://example.org/",
        "language": "de",
        "theme": "dark",
        "fullscreen": True,
        "watchdog": True,
        "browser": "chromium",
        "first_start": False,
    }


class TestHostnameValidator:
    """Tests fuer HostnameValidator."""

    @pytest.mark.parametrize(
        "hostname", ["PiKiosk", "kiosk-01", "A", "a1-b2-C3", "x" * 63]
    )
    def test_gueltige_hostnamen(self, hostname: str) -> None:
        HostnameValidator().validate(hostname)

    @pytest.mark.parametrize(
        "hostname",
        ["", "x" * 64, "kiosk_01", "kiosk 01", "kiösk", "kiosk.local"],
    )
    def test_ungueltige_hostnamen(self, hostname: str) -> None:
        with pytest.raises(ValidationError):
            HostnameValidator().validate(hostname)


class TestURLValidator:
    """Tests fuer URLValidator."""

    @pytest.mark.parametrize(
        "url",
        [
            "http://example.org",
            "https://example.org/pfad?x=1",
            "http://192.168.1.10:8080/",
        ],
    )
    def test_gueltige_urls(self, url: str) -> None:
        URLValidator().validate(url)

    @pytest.mark.parametrize(
        "url",
        ["", "ftp://example.org", "example.org", "http://", "https://"],
    )
    def test_ungueltige_urls(self, url: str) -> None:
        with pytest.raises(ValidationError):
            URLValidator().validate(url)


class TestConfigValidator:
    """Tests fuer ConfigValidator."""

    def test_gueltige_konfiguration(self) -> None:
        ConfigValidator().validate(valid_config())

    def test_leere_url_ist_zulaessig(self) -> None:
        config = valid_config()
        config["url"] = ""
        ConfigValidator().validate(config)

    def test_fehlender_schluessel(self) -> None:
        config = valid_config()
        del config["theme"]
        with pytest.raises(ValidationError):
            ConfigValidator().validate(config)

    def test_unbekannter_schluessel(self) -> None:
        config = valid_config()
        config["unbekannt"] = 1
        with pytest.raises(ValidationError):
            ConfigValidator().validate(config)

    def test_falscher_typ(self) -> None:
        config = valid_config()
        config["fullscreen"] = "ja"
        with pytest.raises(ValidationError):
            ConfigValidator().validate(config)

    def test_bool_statt_string_wird_abgelehnt(self) -> None:
        config = valid_config()
        config["url"] = True
        with pytest.raises(ValidationError):
            ConfigValidator().validate(config)

    def test_ungueltige_sprache(self) -> None:
        config = valid_config()
        config["language"] = "fr"
        with pytest.raises(ValidationError):
            ConfigValidator().validate(config)

    def test_ungueltiges_theme(self) -> None:
        config = valid_config()
        config["theme"] = "neon"
        with pytest.raises(ValidationError):
            ConfigValidator().validate(config)

    def test_ungueltiger_browser(self) -> None:
        config = valid_config()
        config["browser"] = "firefox"
        with pytest.raises(ValidationError):
            ConfigValidator().validate(config)

    def test_ungueltige_url(self) -> None:
        config = valid_config()
        config["url"] = "ftp://example.org"
        with pytest.raises(ValidationError):
            ConfigValidator().validate(config)

    def test_kein_woerterbuch(self) -> None:
        with pytest.raises(ValidationError):
            ConfigValidator().validate([])  # type: ignore[arg-type]
