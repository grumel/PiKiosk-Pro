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
git clone https://github.com/grumel/PiKiosk-Pro.git
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

## Mehrere Geräte einrichten (empfohlen: frisch per Imager)

Für weitere Kiosks ist ein **frisch geflashtes System** meist
zuverlässiger als ein Klon: kein beschädigtes Dateisystem, und jedes
Gerät bekommt automatisch eine **eindeutige** Maschinen-ID und eigene
SSH-Host-Keys – Kollisionen wie beim Klonen entstehen gar nicht erst.

Checkliste pro Gerät:

1. **Raspberry Pi Imager** starten, dieselbe Raspberry-Pi-OS-Version
   wie auf dem Master wählen.
2. Vor dem Schreiben die **Voreinstellungen** öffnen (Zahnrad-Symbol
   bzw. `Strg+Umschalt+X`) und setzen:
   - **Hostname** – eindeutig je Gerät (z. B. `kiosk2`)
   - **SSH aktivieren** (Passwort oder öffentlicher Schlüssel)
   - **WLAN**: SSID, Passwort, WLAN-Land
   - Zeitzone und Tastaturlayout
3. Karte schreiben, in den neuen Pi stecken, booten.
4. PiKiosk Pro installieren:
   ```bash
   git clone https://github.com/grumel/PiKiosk-Pro.git ~/PiKiosk-Pro
   cd ~/PiKiosk-Pro && sudo ./install.sh && sudo reboot
   ```
5. Einrichten – eine der beiden Varianten:
   - **Assistent**: im Browser `https://<hostname>.local:8080` öffnen
     und Kiosk-URL, WLAN und Administrator durchklicken.
   - **Sicherung übernehmen** (schneller bei vielen Geräten): auf dem
     Master im Dashboard eine Sicherung erstellen und auf dem neuen
     Gerät wiederherstellen (Kachel „Sicherung"). Das überträgt
     Konfiguration und Admin-Konto, aber **keine** Maschinen-ID oder
     Schlüssel – die bleiben eindeutig. Danach nur noch Hostname und
     WLAN pro Gerät prüfen.
6. **Standard-WLAN mit Passwort** im Dashboard speichern (WLAN-Kachel),
   damit sich das Gerät nach jedem Neustart selbst verbindet. Kontrolle
   ohne Passwortausgabe: `scripts/diagnose.sh`.

Weil jedes Gerät frisch installiert wird, ist das Skript
`reset-device-identity.sh` hier **nicht** nötig – es ist nur für Klone
(nächster Abschnitt) gedacht.

## Geräte klonen (mehrere Kiosks aus einem Master)

Klonen ist möglich, aber fehleranfälliger als der Imager-Weg oben:
Ein Klon der SD-Karte/SSD übernimmt **alle** geräteweiten Kennungen
des Masters.

> **Wichtig:** Niemals mit `dd` von einem **laufenden** System kopieren.
> Das Dateisystem ist dann „unsauber" und der Klon bleibt beim Booten
> an einer `(initramfs)`-Eingabe hängen (Wurzel nicht mountbar).
> Deshalb: Master vorher **herunterfahren** und offline kopieren, oder
> auf dem Master `rpi-clone` verwenden (kopiert das laufende System
> korrekt per rsync). Im selben Netz führt vor allem die doppelte
Maschinen-ID zu IP-/DHCP-Kollisionen; außerdem teilen sich die
Klone SSH-Host-Keys, TLS-Zertifikat und Sitzungs-/API-Schlüssel.
**Nur den Hostnamen zu ändern reicht nicht.**

Empfohlener Ablauf:

1. Master fertig einrichten und **herunterfahren**.
2. Offline klonen (Linux-Laptop):
   ```bash
   lsblk -o NAME,SIZE,MODEL,TRAN            # Quelle/Ziel sicher identifizieren
   sudo dd if=/dev/sdX of=pikiosk-master.img bs=4M status=progress conv=fsync
   # optional verkleinern + auto-expand: PiShrink (pishrink.sh -z)
   sudo dd if=pikiosk-master.img of=/dev/sdY bs=4M status=progress conv=fsync
   ```
   Alternativ auf dem Pi: „SD Card Copier" oder `rpi-clone`.
3. **Immer nur einen Klon ans Netz**, bis er zurückgesetzt ist.
4. Auf jedem Klon einmal die Geräteidentität erneuern:
   ```bash
   sudo /opt/pikiosk-pro/scripts/reset-device-identity.sh kiosk2
   sudo reboot
   ```
   Das Skript erneuert Hostname (System + `/etc/hosts` +
   `config.json`), Maschinen-ID, SSH-Host-Keys, TLS-Zertifikat
   (passend zum neuen Hostnamen) und verwirft Sitzungs-/API-Schlüssel
   (werden beim Start neu erzeugt). Vorher wird alles unter
   `backup/device-identity-<Zeitstempel>/` gesichert. WLAN-Profile
   bleiben erhalten (gemeinsames WLAN funktioniert weiter).

Optional pro Gerät: eigenes Admin-Konto (`config/users.db` löschen →
Assistent startet neu) und feste DHCP-Reservierung pro MAC im Router.

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
4. **Dashboard**: `https://<ip>:8080/login` (Warnung des
   selbstsignierten Zertifikats einmalig bestätigen) – Anmeldung, alle
   Kacheln funktionieren, Dashboard lädt unter 1 Sekunde.
5. **Watchdog**: Badge zeigt „Online";
   `sudo pkill chromium` → der Browser startet automatisch neu.
6. **System-Kachel**: Neustart und Herunterfahren funktionieren.
7. **Sicherung**: Erstellen, Herunterladen und Wiederherstellen
   einer Sicherung; USB-Stick mit `PiKiosk_Backup*.zip` wird
   erkannt.
8. **API**: `curl -k https://<ip>:8080/api/version` mit Token liefert
   die Version (siehe [API.md](API.md)).

## Fehlersuche

- Systemereignisse: `logs/system.log`
- Browserereignisse: `logs/browser.log`
- Watchdog: `logs/watchdog.log`
- Installation: `logs/install.log`
- Aktualisierung: `logs/update.log`
