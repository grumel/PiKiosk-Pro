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

## WLAN verbindet nicht

- Fehlermeldung in der WLAN-Kachel beachten (falsches Passwort,
  SSID nicht gefunden, DHCP-Fehler, Zeitüberschreitung).
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
- Passwort vergessen → siehe [FAQ](FAQ.md).

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
