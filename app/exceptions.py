# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Eigene Exception-Klassen.

Alle Module verwenden ausschliesslich diese Exception-Klassen,
damit Fehler gezielt abgefangen und verstaendlich gemeldet werden
koennen. Nackte Exceptions sind im Projekt nicht zulaessig.
"""


class PiKioskError(Exception):
    """Basisklasse fuer alle PiKiosk-Pro-Fehler."""


class ConfigurationError(PiKioskError):
    """Fehler beim Lesen, Schreiben oder Verarbeiten der Konfiguration."""


class ValidationError(PiKioskError):
    """Fehler bei der Validierung von Benutzereingaben oder Daten."""


class BrowserError(PiKioskError):
    """Fehler bei der Steuerung des Chromium-Browsers."""


class NetworkError(PiKioskError):
    """Fehler bei Netzwerkoperationen."""


class AuthenticationError(PiKioskError):
    """Fehler bei Anmeldung oder Benutzerverwaltung."""


class BackupError(PiKioskError):
    """Fehler beim Erstellen oder Verwalten von Sicherungen."""


class RestoreError(PiKioskError):
    """Fehler beim Wiederherstellen einer Sicherung."""


class WifiError(NetworkError):
    """Fehler beim Verbinden mit einem WLAN.

    Attributes:
        reason:
            Maschinenlesbarer Fehlergrund fuer die Uebersetzung in
            der Oberflaeche: wrong_password, not_found, timeout,
            no_ip oder generic.
    """

    def __init__(self, message: str, reason: str = "generic") -> None:
        super().__init__(message)
        self.reason = reason
