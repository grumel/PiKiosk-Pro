# Changelog

Alle nennenswerten Änderungen an PiKiosk Pro werden in dieser Datei
dokumentiert. Das Format orientiert sich an
[Keep a Changelog](https://keepachangelog.com/de/1.1.0/), die
Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

## [0.1.0] - 2026-07-15

### Hinzugefügt

- Projektstruktur mit Service-, Controller- und Utility-Schichten
- Flask-Webserver mit Statusseite, Fehlerseiten und Health-Endpunkt
- ConfigService: JSON-Konfiguration mit Validierung, atomarem Speichern,
  Zurücksetzen, Sicherung und Wiederherstellung
- BrowserService: Chromium-Steuerung über Python (Start, Stopp, Neustart,
  Reload per Chrome-DevTools-Protokoll, Cache leeren, Statusüberwachung,
  Vollbildprüfung)
- KioskLogger: modulbezogenes Logging mit Rotation (10 Dateien à 10 MB)
  und Konsolenausgabe für Fehler
- Validatoren für Hostname, URL und Gesamtkonfiguration
- Sprachdateien Deutsch und Englisch, alle Oberflächentexte aus JSON
- Bootstrap 5 lokal eingebunden (offlinefähig), Dark/Light-Theme
- install.sh: Installation von Systempaketen, Python-Umgebung,
  systemd-Dienst und Autologin auf Raspberry Pi OS
- update.sh: Aktualisierung über Git mit Neustart des Dienstes
- Unit- und Integrationstests für alle Kernmodule
