# Installation

Diese Anleitung beschreibt die Installation von PiKiosk Pro 0.1.0 auf
einem Raspberry Pi 4.

## Voraussetzungen

- Raspberry Pi 4 mit 4 GB oder 8 GB RAM
- SD-Karte mit Raspberry Pi OS Desktop 64 Bit
- Netzwerkverbindung (LAN oder WLAN)
- Ein Benutzerkonto mit sudo-Rechten (Standard: `pi`)

## Schritt 1: Projekt herunterladen

```bash
git clone https://github.com/holgerjohn/PiKiosk-Pro.git
cd PiKiosk-Pro
```

## Schritt 2: Installer ausführen

```bash
sudo ./install.sh
```

Der Installer führt folgende Schritte aus:

1. Installation der Systempakete (Python 3, Chromium, NetworkManager, Git)
2. Kopieren des Projekts nach `/opt/pikiosk-pro`
3. Erstellen der Python-Umgebung und Installation der Abhängigkeiten
4. Installation und Aktivierung des systemd-Dienstes `pikiosk.service`
5. Aktivierung des Desktop-Autologins über `raspi-config`
6. Start des Dienstes

Alle Schritte werden in `logs/install.log` protokolliert.

## Schritt 3: Neustart

```bash
sudo reboot
```

Nach dem Neustart startet PiKiosk Pro automatisch. Solange die
Ersteinrichtung nicht abgeschlossen ist, zeigt der Browser die lokale
Statusseite unter `http://127.0.0.1:8080/` an.

## Dienststeuerung

```bash
sudo systemctl status pikiosk.service    # Status anzeigen
sudo systemctl restart pikiosk.service   # Neu starten
sudo systemctl stop pikiosk.service      # Stoppen
```

## Aktualisierung

```bash
sudo ./update.sh
```

## Fehlersuche

- Systemereignisse: `logs/system.log`
- Browserereignisse: `logs/browser.log`
- Installation: `logs/install.log`
- Aktualisierung: `logs/update.log`
