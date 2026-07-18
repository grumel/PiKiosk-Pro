# PiKiosk Pro

Professionelles Open-Source-Kiosk-System für Raspberry Pi 4.

PiKiosk Pro verwandelt einen Raspberry Pi 4 in ein wartungsarmes Kiosksystem:
Nach dem Booten meldet sich das Gerät automatisch an, startet Chromium im
Kioskmodus und zeigt die konfigurierte Webseite an. Die komplette
Administration erfolgt über eine lokale Weboberfläche – ohne Linux-Kenntnisse.

## Funktionen

- **PiKiosk Center**: zentrale Verwaltung beliebig vieler Geräte –
  Zustand auf einen Blick, Massenaktionen für eine Auswahl
  ([docs/Center.md](docs/Center.md))
- Offlinefähig: lokale Kiosk-Webseite, lokale Updatequelle und
  konfigurierbare Verbindungsprüfung – kein Internetzugang nötig
- Sprache (Deutsch/Englisch) und Theme (Dunkel/Hell/Automatisch)
  direkt im Dashboard umschaltbar; „Automatisch" folgt der
  Systemeinstellung
- REST API mit JWT-Authentifizierung für die Remote-Verwaltung:
  Status, Browser, Einstellungen, Netzwerk, System, Updates,
  Sicherungen und Logs ([docs/API.md](docs/API.md))
- Update-System: Aktualisierung aus GitHub-Releases oder per
  hochgeladenem Paket, automatische Sicherung vor dem Update und
  vollständiger Rollback
- Backup und Restore: ZIP-Sicherungen von Konfiguration und
  Benutzern mit Versionsprüfung, Download, Upload und
  automatischem USB-Import
- Watchdog als eigener systemd-Dienst: überwacht Browser, Netzwerk
  (Gateway, DNS, Internet, URL) und System (Temperatur, RAM,
  Festplatte) alle 5 Sekunden und startet einen abgestürzten
  Browser automatisch neu (maximal 3-mal pro Minute)
- Dashboard mit Login: Systeminformationen (CPU, RAM, Temperatur,
  Festplatte, Netzwerk, Browserstatus, Watchdogstatus, Laufzeit)
  und Kacheln für Browser, Kiosk-URL, Hostname, WLAN, System und Logs
- Anmeldung über Flask-Login mit Session-Timeout und CSRF-Schutz
- Setup-Wizard für die Ersteinrichtung ohne Linux-Kenntnisse:
  Hostname, WLAN, Administratorkonto und Kiosk-URL mit Sofortprüfung
- WLAN-Verwaltung über NetworkManager (Scan, Verbinden, IP/Gateway/DNS)
- Administratorkonto in SQLite, Passwörter ausschließlich als bcrypt-Hash
- Flask-Webserver mit Statusseite und Health-Endpunkt
- Vollständige Chromium-Steuerung über Python (Start, Stopp, Neustart,
  Seiten-Reload per DevTools-Protokoll, Cache leeren, Statusüberwachung)
- Zentrale JSON-Konfiguration mit Validierung, Sicherung und Wiederherstellung
- Logging mit Rotation (10 Dateien à 10 MB) für alle Module
- Mehrsprachige Oberflächentexte (Deutsch, Englisch) aus JSON-Sprachdateien
- Installer für Raspberry Pi OS mit systemd-Autostart und Autologin

## Zielplattform

| Komponente     | Anforderung                       |
| -------------- | --------------------------------- |
| Hardware       | Raspberry Pi 4 (4 GB oder 8 GB)   |
| Betriebssystem | Raspberry Pi OS Desktop 64 Bit    |
| Browser        | Chromium                          |
| Python         | Python 3.13                       |

## Installation

```bash
git clone https://github.com/grumel/PiKiosk-Pro.git
cd PiKiosk-Pro
sudo ./install.sh
```

Der Installer richtet alle Systempakete, die Python-Umgebung, den
systemd-Dienst, den Autologin und ein selbstsigniertes
TLS-Zertifikat ein. Die Weboberfläche ist danach über
`https://<adresse>:8080/` erreichbar (Browserwarnung beim
selbstsignierten Zertifikat einmalig bestätigen; eigene Zertifikate:
`config/tls/` ersetzen). Details stehen in
[docs/Installation.md](docs/Installation.md).

## Aktualisierung

```bash
sudo ./update.sh
```

## Zentrale Verwaltung (optional)

Zur Verwaltung mehrerer Geräte lässt sich auf einem beliebigen
Rechner im Netzwerk die Zentrale installieren:

```bash
sudo ./install_center.sh
```

Danach erreichbar unter `https://<adresse>:8090/` – Details in
[docs/Center.md](docs/Center.md).

## Entwicklung

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m app.app --no-browser   # Webserver ohne Kioskbrowser starten
pytest                            # Tests ausführen
```

Die Architektur ist in [docs/Architecture.md](docs/Architecture.md)
beschrieben, das Entwicklerhandbuch in
[docs/DeveloperGuide.md](docs/DeveloperGuide.md). Hinweise für
Beiträge stehen in [CONTRIBUTING.md](CONTRIBUTING.md).

## Dokumentation

- [Installation](docs/Installation.md)
- [Administration](docs/Administration.md)
- [REST API](docs/API.md)
- [Zentrale Verwaltung](docs/Center.md)
- [Architektur](docs/Architecture.md)
- [Entwicklerhandbuch](docs/DeveloperGuide.md)
- [FAQ](docs/FAQ.md)
- [Troubleshooting](docs/Troubleshooting.md)
- [Changelog](CHANGELOG.md)

## Lizenz

MIT License – siehe [LICENSE](LICENSE).

Copyright (c) 2026 Holger John
