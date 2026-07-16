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
5. Installation der sudo-Regel für die Hostnameänderung
   (`/etc/sudoers.d/pikiosk`, erlaubt ausschließlich das Helferskript
   `scripts/hostname_apply.py`)
6. Aktivierung des Desktop-Autologins über `raspi-config`
7. Start des Dienstes

Alle Schritte werden in `logs/install.log` protokolliert.

## Schritt 3: Neustart

```bash
sudo reboot
```

Nach dem Neustart startet PiKiosk Pro automatisch. Beim ersten Start
zeigt der Browser den Setup-Wizard an, der Hostname, WLAN,
Administratorkonto und Kiosk-URL einrichtet. Nach Abschluss der
Einrichtung startet der Kiosk direkt mit der konfigurierten Webseite.

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

## Abnahme auf dem Gerät (Release-Checkliste)

Nach der Installation auf einem Raspberry Pi 4 sollten folgende
Punkte geprüft werden:

1. **Erster Boot**: Nach `sudo reboot` erscheint ohne Eingriff der
   Setup-Wizard im Vollbild (kein Desktop, keine Taskleiste).
2. **Wizard**: Hostname, WLAN (Scan findet Netzwerke, Verbindung
   klappt), Administrator (Passwortregeln werden angezeigt) und
   URL (Prüfung liefert HTTP-Status) lassen sich abschließen.
3. **Kioskstart**: Nach Abschluss lädt der Browser die konfigurierte
   Webseite; nach einem weiteren Neustart startet der Kiosk
   automatisch (Bootzeit bis zur Anzeige unter 30 Sekunden,
   Browserstart unter 5 Sekunden).
4. **Dashboard**: `http://<ip>:8080/login` – Anmeldung, alle
   Kacheln funktionieren, Dashboard lädt unter 1 Sekunde.
5. **Watchdog**: Badge zeigt „Online";
   `sudo pkill chromium` → der Browser startet automatisch neu.
6. **System-Kachel**: Neustart und Herunterfahren funktionieren.
7. **Sicherung**: Erstellen, Herunterladen und Wiederherstellen
   einer Sicherung; USB-Stick mit `PiKiosk_Backup*.zip` wird
   erkannt.
8. **API**: `curl http://<ip>:8080/api/version` mit Token liefert
   die Version (siehe [API.md](API.md)).

## Fehlersuche

- Systemereignisse: `logs/system.log`
- Browserereignisse: `logs/browser.log`
- Watchdog: `logs/watchdog.log`
- Installation: `logs/install.log`
- Aktualisierung: `logs/update.log`
