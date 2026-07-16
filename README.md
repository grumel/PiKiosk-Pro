# PiKiosk Pro

Professionelles Open-Source-Kiosk-System für Raspberry Pi 4.

PiKiosk Pro verwandelt einen Raspberry Pi 4 in ein wartungsarmes Kiosksystem:
Nach dem Booten meldet sich das Gerät automatisch an, startet Chromium im
Kioskmodus und zeigt die konfigurierte Webseite an. Die komplette
Administration erfolgt über eine lokale Weboberfläche – ohne Linux-Kenntnisse.

## Funktionen (Version 0.3.0)

- Dashboard mit Login: Systeminformationen (CPU, RAM, Temperatur,
  Festplatte, Netzwerk, Browserstatus, Laufzeit) und Kacheln für
  Browser, Kiosk-URL, Hostname, WLAN, System und Logs
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
git clone https://github.com/holgerjohn/PiKiosk-Pro.git
cd PiKiosk-Pro
sudo ./install.sh
```

Der Installer richtet alle Systempakete, die Python-Umgebung, den
systemd-Dienst und den Autologin ein. Details stehen in
[docs/Installation.md](docs/Installation.md).

## Aktualisierung

```bash
sudo ./update.sh
```

## Entwicklung

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m app.app --no-browser   # Webserver ohne Kioskbrowser starten
pytest                            # Tests ausführen
```

Die Architektur ist in [docs/Architecture.md](docs/Architecture.md)
beschrieben. Hinweise für Beiträge stehen in
[CONTRIBUTING.md](CONTRIBUTING.md).

## Lizenz

MIT License – siehe [LICENSE](LICENSE).

Copyright (c) 2026 Holger John
