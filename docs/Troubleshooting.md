# Troubleshooting

Leitfaden zur Fehlersuche. Die Logdateien sind im Dashboard
(Kachel „Logs") einsehbar und herunterladbar; auf dem Gerät liegen
sie unter `/opt/pikiosk-pro/logs/`.

## Der Bildschirm bleibt schwarz / kein Browser

1. Dienststatus prüfen:
   ```bash
   sudo systemctl status pikiosk.service
   ```
2. `logs/system.log` und `logs/browser.log` prüfen.
3. Häufigste Ursachen:
   - Chromium nicht installiert → `sudo ./install.sh` erneut ausführen.
   - Kein grafischer Autologin → `sudo raspi-config` →
     System Options → Boot / Auto Login → Desktop Autologin.
   - `DISPLAY` nicht verfügbar → Gerät neu starten.

## Browserstatus „Abgestürzt" oder Watchdog „Fehler"

Der Watchdog hat den Browser mehrfach neu gestartet und aufgegeben
(mehr als 3 Abstürze in 60 Sekunden). `logs/watchdog.log` und
`logs/browser.log` prüfen. Häufig ist die Kiosk-URL die Ursache
(z. B. Seite mit sehr hohem Speicherbedarf). Browser über das
Dashboard manuell starten – läuft er wieder, setzt der Watchdog
seinen Fehlerstatus automatisch zurück.

## Watchdog-Badge zeigt „Inaktiv"

Der Watchdog-Dienst läuft nicht oder schreibt keine Statusdatei:

```bash
sudo systemctl status pikiosk-watchdog.service
sudo systemctl restart pikiosk-watchdog.service
```

Zeigt das Badge „Deaktiviert", ist der Watchdog in der
Konfiguration abgeschaltet (`watchdog: false`).

Häufigste Ursache in der Praxis ist eine **volle SD-Karte**: Ist
kein Platz mehr frei, kann der Watchdog seine Statusdatei nicht
schreiben, und das Dashboard zeigt „Inaktiv". Freien Platz prüfen
und größte Verzeichnisse finden:

```bash
df -h /
sudo du -xh /home/pi --max-depth=2 2>/dev/null | sort -rh | head -15
```

Ein häufiger, gefahrlos zu leerender Speicherfresser ist der
Papierkorb der Desktop-Oberfläche:

```bash
rm -rf ~/.local/share/Trash/files ~/.local/share/Trash/info
```

Ist die Platte zu **95 % oder mehr** belegt, meldet die
Überwachungs-Kachel dies ab Version 1.6.4 als roten **Fehler** mit
der Festplatte als Auslöser.

## „Not authorized to control networking" / keine Berechtigung

Der WLAN-Scan funktioniert, aber jede Verbindung scheitert mit
„Not authorized to control networking" bzw. „Keine Berechtigung,
das Netzwerk zu ändern".

**Ursache:** NetworkManager verlangt für Verbindungsänderungen eine
interaktive Bestätigung durch einen Administrator (polkit,
`auth_admin_keep`). Ein systemd-Dienst hat keine Sitzung, die diese
Rückfrage beantworten könnte. Lesen (Scannen) ist davon nicht
betroffen – deshalb funktioniert nur der Scan.

**Lösung:** Die polkit-Regel installieren, die `install.sh` seit
Version 1.3.0 mitbringt. Bei einer bestehenden Installation genügt:

```bash
sudo sed "s/__KIOSK_USER__/$USER/" \
  /opt/pikiosk-pro/services/pikiosk-networkmanager.rules \
  | sudo tee /etc/polkit-1/rules.d/50-pikiosk-networkmanager.rules
sudo systemctl restart polkit
sudo systemctl restart pikiosk.service
```

Die Regel erlaubt ausschließlich dem Kioskbenutzer genau die
NetworkManager-Aktionen, die PiKiosk Pro benötigt (Verbindungen
anlegen, aktivieren, trennen). Alle übrigen Berechtigungen bleiben
unverändert. Prüfen lässt sich das mit:

```bash
ls -l /etc/polkit-1/rules.d/50-pikiosk-networkmanager.rules
sudo journalctl -u polkit -n 20
```

## WLAN verbindet nicht

- Fehlermeldung in der WLAN-Kachel beachten (falsches Passwort,
  SSID nicht gefunden, DHCP-Fehler, Zeitüberschreitung, fehlende
  Berechtigung – siehe oben).
- `logs/network.log` prüfen.
- NetworkManager-Status: `systemctl status NetworkManager`.
- 5-GHz-Netze erfordern das korrekte WLAN-Land:
  `sudo raspi-config` → Localisation → WLAN Country.

## Hostnameänderung schlägt fehl

Die Änderung läuft über `sudo` und das Helferskript
`scripts/hostname_apply.py`. Prüfen, ob `/etc/sudoers.d/pikiosk`
existiert (wird von `install.sh` angelegt). Fehlerdetails stehen in
`logs/system.log`.

## Neustart/Herunterfahren über das Dashboard wirkt nicht

Ebenfalls eine sudo-Regel aus `/etc/sudoers.d/pikiosk`
(`systemctl reboot` / `systemctl poweroff`). Nach einer manuellen
Installation ohne `install.sh` fehlt diese Datei.

## Anmeldung nicht möglich

- „Anmeldename oder Passwort ist falsch": Groß-/Kleinschreibung
  prüfen; Fehlversuche stehen in `logs/system.log`.
- „Zu viele Fehlversuche": Nach 5 Fehlversuchen innerhalb von
  15 Minuten sperrt das Gerät die Quelle für 5 Minuten. Die
  Meldung nennt die Restzeit; danach einfach erneut anmelden.
- Passwort vergessen → siehe [FAQ](FAQ.md).

## Browser warnt vor dem Zertifikat

Der Installer erzeugt ein selbstsigniertes TLS-Zertifikat. Beim
ersten Aufruf von `https://<ip>:8080/` zeigt der Browser deshalb
eine Warnung („Verbindung ist nicht privat"). Das ist erwartet:
Die Verbindung ist verschlüsselt, nur der Aussteller ist dem
Browser unbekannt. Warnung über „Erweitert" → „Trotzdem fortfahren"
einmalig bestätigen – oder ein Firmenzertifikat verwenden: dazu
`cert.pem` und `key.pem` unter `config/tls/` ersetzen und den
Dienst neu starten (`sudo systemctl restart pikiosk`).

## Update schlägt fehl

- `logs/update.log` bzw. Meldung in der Update-Kachel prüfen.
- Vor jedem Update wird eine Sicherung erstellt; „Rollback" stellt
  den vorherigen Stand wieder her.
- Bei GitHub-Updates: Internetverbindung und Erreichbarkeit von
  api.github.com prüfen.

## Wiederherstellung wird abgelehnt

Die Sicherung wird vor dem Anwenden geprüft. Typische Meldungen:

- „keine gültige ZIP-Sicherung" / „beschädigt": Datei unvollständig
  übertragen – Sicherung erneut herunterladen/kopieren.
- „nicht kompatible Version": Die Sicherung stammt von einer
  neueren PiKiosk-Version als der installierten – erst das System
  aktualisieren, dann wiederherstellen.

## Weboberfläche nicht erreichbar

1. Läuft der Dienst? `sudo systemctl status pikiosk.service`
2. Richtige IP? Auf dem Gerät: `hostname -I`
3. Port 8080 im Netzwerk erreichbar? `curl http://<ip>:8080/health`
   (liefert JSON, auch während der Ersteinrichtung).

## Diagnose per API

```bash
TOKEN=$(curl -s -X POST http://<ip>:8080/api/token \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<passwort>"}' | jq -r .token)
curl -s http://<ip>:8080/api/status -H "Authorization: Bearer $TOKEN"
curl -s http://<ip>:8080/api/system -H "Authorization: Bearer $TOKEN"
curl -s http://<ip>:8080/api/logs/watchdog -H "Authorization: Bearer $TOKEN"
```
