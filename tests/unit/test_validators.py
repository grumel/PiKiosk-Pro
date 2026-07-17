# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer die Validatoren."""

from typing import Any

import pytest

from app.exceptions import ValidationError
from app.utils.validators import (
    ConfigValidator,
    HostnameValidator,
    PasswordValidator,
    URLValidator,
)
from tests.conftest import project_defaults


def valid_config() -> dict[str, Any]:
    """Liefert eine gueltige Beispielkonfiguration.

    Returns:
        Gueltige Konfiguration.
    """
    return project_defaults(url="https://example.org/", first_start=False)


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

    def test_ungueltige_updatequelle(self) -> None:
        config = valid_config()
        config["update_source"] = "ftp"
        with pytest.raises(ValidationError):
            ConfigValidator().validate(config)

    def test_lokale_quelle_ohne_url(self) -> None:
        config = valid_config()
        config["update_source"] = "local"
        config["update_url"] = ""
        with pytest.raises(ValidationError):
            ConfigValidator().validate(config)

    def test_lokale_quelle_mit_url(self) -> None:
        config = valid_config()
        config["update_source"] = "local"
        config["update_url"] = "http://server.local/pikiosk"
        ConfigValidator().validate(config)

    def test_ungueltige_update_url(self) -> None:
        config = valid_config()
        config["update_source"] = "local"
        config["update_url"] = "ftp://server.local/pikiosk"
        with pytest.raises(ValidationError):
            ConfigValidator().validate(config)

    def test_ungueltige_verbindungspruefung(self) -> None:
        config = valid_config()
        config["connectivity_check"] = "telepathie"
        with pytest.raises(ValidationError):
            ConfigValidator().validate(config)

    def test_url_pruefung_ohne_kiosk_url(self) -> None:
        config = valid_config()
        config["connectivity_check"] = "url"
        config["url"] = ""
        with pytest.raises(ValidationError):
            ConfigValidator().validate(config)

    def test_url_pruefung_mit_kiosk_url(self) -> None:
        config = valid_config()
        config["connectivity_check"] = "url"
        ConfigValidator().validate(config)

    def test_zu_langer_wlan_name(self) -> None:
        config = valid_config()
        config["wifi_preferred_ssid"] = "x" * 33
        with pytest.raises(ValidationError):
            ConfigValidator().validate(config)

    def test_gueltiger_wlan_name(self) -> None:
        config = valid_config()
        config["wifi_preferred_ssid"] = "Zuhause"
        ConfigValidator().validate(config)

    def test_updatequelle_aus(self) -> None:
        config = valid_config()
        config["update_source"] = "off"
        ConfigValidator().validate(config)


class TestPasswordValidator:
    """Tests fuer PasswordValidator."""

    @pytest.mark.parametrize(
        "password",
        ["Sicher-2026-Kiosk", "Aa1!Aa1!Aa1!", "XyZ9#kLm2$Qw7"],
    )
    def test_gueltige_passwoerter(self, password: str) -> None:
        PasswordValidator().validate(password)

    @pytest.mark.parametrize(
        ("password", "failed_rule"),
        [
            ("Aa1!short", "min_length"),
            ("nur-kleinbuchstaben-123", "uppercase"),
            ("NUR-GROSSBUCHSTABEN-123", "lowercase"),
            ("KeineZahlenHier!", "digit"),
            ("KeineSonderzeichen123", "special"),
        ],
    )
    def test_ungueltige_passwoerter(self, password: str, failed_rule: str) -> None:
        validator = PasswordValidator()
        with pytest.raises(ValidationError):
            validator.validate(password)
        assert validator.check_rules(password)[failed_rule] is False

    def test_alle_regeln_erfuellt(self) -> None:
        rules = PasswordValidator().check_rules("Sicher-2026-Kiosk")
        assert all(rules.values())
