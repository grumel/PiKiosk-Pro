# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Validatoren.

Stellt Validator-Klassen fuer Hostname, URL und Konfiguration
bereit. Alle Validatoren werfen bei ungueltigen Eingaben eine
ValidationError mit einer verstaendlichen Meldung. Ungueltige
Eingaben werden niemals gespeichert.
"""

import re
from typing import Any
from urllib.parse import urlparse

from app.constants import (
    ALLOWED_URL_SCHEMES,
    CONFIG_SCHEMA,
    HOSTNAME_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    SUPPORTED_BROWSERS,
    SUPPORTED_CONNECTIVITY_CHECKS,
    SUPPORTED_LANGUAGES,
    SUPPORTED_THEMES,
    SUPPORTED_UPDATE_SOURCES,
    WIFI_SSID_MAX_LENGTH,
)
from app.exceptions import ValidationError

HOSTNAME_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z0-9-]+$")
PASSWORD_UPPER_PATTERN: re.Pattern[str] = re.compile(r"[A-Z]")
PASSWORD_LOWER_PATTERN: re.Pattern[str] = re.compile(r"[a-z]")
PASSWORD_DIGIT_PATTERN: re.Pattern[str] = re.compile(r"[0-9]")
PASSWORD_SPECIAL_PATTERN: re.Pattern[str] = re.compile(r"[^A-Za-z0-9]")


class HostnameValidator:
    """Validiert Hostnamen nach den Projektregeln.

    Erlaubt sind ausschliesslich A-Z, a-z, 0-9 und Bindestrich
    bei einer Maximallaenge von 63 Zeichen.
    """

    def validate(self, hostname: str) -> None:
        """Prueft einen Hostnamen.

        Args:
            hostname:
                Zu pruefender Hostname.

        Raises:
            ValidationError
        """
        if not isinstance(hostname, str) or not hostname:
            raise ValidationError("Der Hostname darf nicht leer sein.")
        if len(hostname) > HOSTNAME_MAX_LENGTH:
            raise ValidationError(
                f"Der Hostname darf maximal {HOSTNAME_MAX_LENGTH} " "Zeichen lang sein."
            )
        if not HOSTNAME_PATTERN.match(hostname):
            raise ValidationError(
                "Der Hostname darf nur A-Z, a-z, 0-9 und " "Bindestriche enthalten."
            )


class URLValidator:
    """Validiert URLs fuer den Kioskbetrieb.

    Zulaessig sind ausschliesslich vollstaendige http- und
    https-URLs mit Hostangabe.
    """

    def validate(self, url: str) -> None:
        """Prueft eine URL.

        Args:
            url:
                Zu pruefende URL.

        Raises:
            ValidationError
        """
        if not isinstance(url, str) or not url:
            raise ValidationError("Die URL darf nicht leer sein.")
        parsed = urlparse(url)
        if parsed.scheme not in ALLOWED_URL_SCHEMES:
            raise ValidationError("Es sind nur http- und https-URLs zulaessig.")
        if not parsed.netloc:
            raise ValidationError("Die URL muss einen gueltigen Host enthalten.")


class ConfigValidator:
    """Validiert die komplette PiKiosk-Konfiguration.

    Prueft Vollstaendigkeit, Datentypen und Wertebereiche aller
    Konfigurationsschluessel gemaess CONFIG_SCHEMA.
    """

    def __init__(self) -> None:
        self._hostname_validator = HostnameValidator()
        self._url_validator = URLValidator()

    def validate(self, config: dict[str, Any]) -> None:
        """Prueft eine Konfiguration vollstaendig.

        Args:
            config:
                Konfigurations-Woerterbuch.

        Raises:
            ValidationError
        """
        if not isinstance(config, dict):
            raise ValidationError("Die Konfiguration muss ein JSON-Objekt sein.")
        self._validate_keys(config)
        self._validate_types(config)
        self._validate_values(config)

    def _validate_keys(self, config: dict[str, Any]) -> None:
        """Prueft auf fehlende und unbekannte Schluessel.

        Args:
            config:
                Konfigurations-Woerterbuch.

        Raises:
            ValidationError
        """
        missing = sorted(set(CONFIG_SCHEMA) - set(config))
        if missing:
            raise ValidationError(
                "Fehlende Konfigurationsschluessel: " + ", ".join(missing)
            )
        unknown = sorted(set(config) - set(CONFIG_SCHEMA))
        if unknown:
            raise ValidationError(
                "Unbekannte Konfigurationsschluessel: " + ", ".join(unknown)
            )

    def _validate_types(self, config: dict[str, Any]) -> None:
        """Prueft die Datentypen aller Schluessel.

        Args:
            config:
                Konfigurations-Woerterbuch.

        Raises:
            ValidationError
        """
        for key, expected_type in CONFIG_SCHEMA.items():
            value = config[key]
            if not isinstance(value, expected_type) or isinstance(value, bool) is not (
                expected_type is bool
            ):
                raise ValidationError(
                    f"Der Schluessel '{key}' muss vom Typ "
                    f"{expected_type.__name__} sein."
                )

    def _validate_values(self, config: dict[str, Any]) -> None:
        """Prueft die Wertebereiche einzelner Schluessel.

        Args:
            config:
                Konfigurations-Woerterbuch.

        Raises:
            ValidationError
        """
        self._hostname_validator.validate(config["hostname"])
        if config["url"]:
            self._url_validator.validate(config["url"])
        if config["language"] not in SUPPORTED_LANGUAGES:
            raise ValidationError(
                "Unterstuetzte Sprachen: " + ", ".join(SUPPORTED_LANGUAGES)
            )
        if config["theme"] not in SUPPORTED_THEMES:
            raise ValidationError(
                "Unterstuetzte Themes: " + ", ".join(SUPPORTED_THEMES)
            )
        if config["browser"] not in SUPPORTED_BROWSERS:
            raise ValidationError(
                "Unterstuetzte Browser: " + ", ".join(SUPPORTED_BROWSERS)
            )
        self._validate_update_and_connectivity(config)

    def _validate_update_and_connectivity(self, config: dict[str, Any]) -> None:
        """Prueft Updatequelle und Verbindungspruefung.

        Args:
            config:
                Konfigurations-Woerterbuch.

        Raises:
            ValidationError
        """
        if config["update_source"] not in SUPPORTED_UPDATE_SOURCES:
            raise ValidationError(
                "Unterstuetzte Updatequellen: " + ", ".join(SUPPORTED_UPDATE_SOURCES)
            )
        if config["update_source"] == "local":
            if not config["update_url"]:
                raise ValidationError(
                    "Fuer die lokale Updatequelle wird eine Update-URL benoetigt."
                )
            self._url_validator.validate(config["update_url"])
        elif config["update_url"]:
            self._url_validator.validate(config["update_url"])
        if config["connectivity_check"] not in SUPPORTED_CONNECTIVITY_CHECKS:
            raise ValidationError(
                "Unterstuetzte Verbindungspruefungen: "
                + ", ".join(SUPPORTED_CONNECTIVITY_CHECKS)
            )
        if config["connectivity_check"] == "url" and not config["url"]:
            raise ValidationError(
                "Die Verbindungspruefung 'url' benoetigt eine konfigurierte Kiosk-URL."
            )
        if len(config["wifi_preferred_ssid"]) > WIFI_SSID_MAX_LENGTH:
            raise ValidationError(
                f"Der WLAN-Name darf maximal {WIFI_SSID_MAX_LENGTH} Zeichen "
                "lang sein."
            )


class PasswordValidator:
    """Validiert Administratorpasswoerter.

    Ein Passwort muss mindestens 12 Zeichen lang sein und
    Grossbuchstaben, Kleinbuchstaben, Zahlen und Sonderzeichen
    enthalten.
    """

    def validate(self, password: str) -> None:
        """Prueft die Passwortqualitaet.

        Args:
            password:
                Zu pruefendes Passwort.

        Raises:
            ValidationError
        """
        failed = [
            rule for rule, passed in self.check_rules(password).items() if not passed
        ]
        if failed:
            raise ValidationError(
                "Das Passwort erfuellt folgende Regeln nicht: " + ", ".join(failed)
            )

    def check_rules(self, password: str) -> dict[str, bool]:
        """Prueft jede Passwortregel einzeln.

        Args:
            password:
                Zu pruefendes Passwort.

        Returns:
            Regelname und Ergebnis jeder Einzelpruefung.
        """
        value = password if isinstance(password, str) else ""
        return {
            "min_length": len(value) >= PASSWORD_MIN_LENGTH,
            "uppercase": bool(PASSWORD_UPPER_PATTERN.search(value)),
            "lowercase": bool(PASSWORD_LOWER_PATTERN.search(value)),
            "digit": bool(PASSWORD_DIGIT_PATTERN.search(value)),
            "special": bool(PASSWORD_SPECIAL_PATTERN.search(value)),
        }
