# Administration

Diese Anleitung beschreibt die Verwaltung von PiKiosk Pro über die
Weboberfläche. Linux-Kenntnisse sind nicht erforderlich.

## Anmeldung

In allen Passwortfeldern lässt sich die Eingabe über das Auge
rechts im Feld sichtbar machen – hilfreich bei langen Passwörtern
und auf Touchscreens.

Die Verwaltungsoberfläche ist im lokalen Netzwerk erreichbar unter:

```
http://<ip-adresse-des-geraets>:8080/login
```

Melden Sie sich mit dem Administratorkonto an, das im Setup-Wizard
angelegt wurde. Nach 30 Minuten ohne Aktivität wird die Sitzung
automatisch beendet. Mit „Angemeldet bleiben" bleibt die Anmeldung
7 Tage erhalten.

Die Weboberfläche läuft über HTTPS (`https://<ip>:8080/`), sobald
unter `config/tls/` ein Zertifikat liegt – der Installer erzeugt
dort ein selbstsigniertes. Eigene Zertifikate: `cert.pem` und
`key.pem` ersetzen, Dienst neu starten. Nach 5 fehlgeschlagenen
Anmeldeversuchen innerhalb von 15 Minuten wird die Quelle für
5 Minuten gesperrt.

## Dashboard

Nach der Anmeldung zeigt das Dashboard:

- **Gerät**: Hostname, Modell, IP-Adresse, MAC-Adresse, Version
- **Ressourcen**: CPU-Auslastung, Arbeitsspeicher, Temperatur,
  Festplattenbelegung
- **Status**: Browserstatus, Internetstatus, Watchdogstatus,
  Kiosk-URL, letzter Neustart, Systemlaufzeit

Der Watchdogstatus fasst die Überwachung zusammen: **Online** (alles
in Ordnung), **Warnung** (z. B. hohe Temperatur, DNS- oder
URL-Problem), **Fehler** (Browser mehrfach abgestürzt oder kritische
Temperatur), **Offline** (kein Internet), **Deaktiviert** (Watchdog
in der Konfiguration abgeschaltet), **Inaktiv** (Watchdog-Dienst
läuft nicht).

Die Werte aktualisieren sich automatisch alle 10 Sekunden.

## Aus dem Kiosk-Vollbild zur Verwaltung

Der Kioskbrowser läuft im Vollbild und zeigt die konfigurierte
Webseite. Mit der **Ausstiegs-Tastenkombination** (Standard
**Strg+Alt+K**) springt er auf das lokale Dashboard – dort meldet
man sich an und erreicht die komplette Verwaltung. Die Kombination
lässt sich in der Überwachungs-Kachel ändern (leeres Feld schaltet
die Funktion ab); eine Änderung wirkt nach dem nächsten
Geräteneustart. Der zuständige Dienst heißt `pikiosk-keymon` und
liest die Tastatur direkt aus, funktioniert also unter X11 wie
unter Wayland.

## Kacheln

### Browser

Startet, stoppt oder startet den Kioskbrowser neu. Der Status wird
als Badge angezeigt (Läuft, Nicht gestartet, Fehler, Abgestürzt).

### Kiosk-URL

„Testen" prüft die URL, ohne sie zu speichern (gültig bei HTTP 200,
301 oder 302, Timeout 5 Sekunden). „Speichern" übernimmt die URL
nur, wenn die Prüfung erfolgreich ist; ein laufender Browser wird
automatisch mit der neuen URL neu gestartet.

### Hostname

Ändert den Gerätenamen (A-Z, a-z, 0-9, Bindestrich, maximal 63
Zeichen). Nach der Änderung wird ein Neustart empfohlen.

### WLAN

Zeigt die aktive Verbindung mit Signalstärke, IP-Adresse, Gateway
und DNS. „Netzwerke suchen" listet alle verfügbaren WLANs sortiert
nach Signalstärke; die Verbindung erfolgt direkt aus der Liste.
„Trennen" beendet die aktive WLAN-Verbindung.

**Standard-WLAN**: Unten in der Kachel lässt sich eines der bereits
gespeicherten Netzwerke als Standard festlegen. Danach erscheint
oben eine Schaltfläche „Mit „<Name>" verbinden" – ein Klick genügt,
etwa um nach einem Test in einem anderen Netz zurückzuwechseln.
Andere Netzwerke bleiben weiterhin sichtbar und verbindbar.

Hinterlegt wird nur der Name des Netzwerks. Das Passwort bleibt im
Profil von NetworkManager – PiKiosk Pro speichert keine
WLAN-Passwörter. Ein Netzwerk erscheint in der Auswahl, sobald es
einmal erfolgreich verbunden wurde.

### System

„Neustart" und „Herunterfahren" beenden zuerst den Browser sauber
und führen die Aktion anschließend über systemd aus. Beide Aktionen
müssen bestätigt werden.

### Überwachung

Hier lässt sich der Watchdog ein- und ausschalten und festlegen,
was als „Online" gilt (Verbindungsprüfung):

| Einstellung | Bedeutung |
| ----------- | --------- |
| Internet erreichbar | Standard: prüft eine Verbindung ins Internet (1.1.1.1) |
| Kiosk-URL erreichbar | Für Geräte **ohne Internetzugang**: prüft den Host der konfigurierten Kiosk-URL |
| Gateway erreichbar | Prüft das Standardgateway per Ping |
| Keine Prüfung | Verbindung gilt immer als in Ordnung |

Ohne Umstellung meldet ein Kiosk ohne Internetzugang dauerhaft
„Offline" – für lokale Installationen daher „Kiosk-URL erreichbar"
wählen.

### Darstellung

Sprache (Deutsch/Englisch) und Theme (Dunkel/Hell/Automatisch)
lassen sich hier umschalten. „Automatisch" folgt der
Systemeinstellung des anzeigenden Geräts. Nach dem Speichern lädt
die Seite neu und wendet die Auswahl sofort an.

### Sicherung

„Sicherung erstellen" erzeugt eine ZIP-Datei
(`PiKiosk_Backup_JJJJMMTT_HHMM.zip`) mit Konfiguration und
Benutzerkonten, optional mit Logdateien. Vorhandene Sicherungen
lassen sich herunterladen oder wiederherstellen. Zusätzlich kann
eine Sicherungsdatei hochgeladen und direkt wiederhergestellt
werden.

Vor jeder Wiederherstellung wird die Sicherung vollständig geprüft
(ZIP-Integrität, Manifest, Versionskompatibilität, Konfiguration);
ungültige Sicherungen werden nicht angewendet. Nach der
Wiederherstellung wird ein Neustart empfohlen.

**USB-Import**: Eingesteckte USB-Sticks werden automatisch nach
`PiKiosk_Backup*.zip` durchsucht; gefundene Sicherungen erscheinen
in der Kachel und können mit einem Klick importiert werden.

### Aktualisierung

**Updatequelle** wählen:

- **GitHub (Internet)**: Standard; holt das neueste Release aus dem
  Projekt-Repository.
- **Lokale Quelle**: Für Geräte ohne Internetzugang. Unter
  „Update-URL" die Basisadresse eines Webservers im Netzwerk
  eintragen, z. B. `http://server.local/pikiosk`. Dort werden
  erwartet:
  - `manifest.json` mit den Feldern `version` (z. B. `1.2.0`),
    `archive` (Dateiname des Pakets), `sha256` (Prüfsumme des
    Pakets, `sha256sum <paket>`) und optional `notes`
  - das Paket selbst (ZIP oder tar.gz)

  Die Prüfsumme ist Pflicht: Ein Paket, dessen Prüfsumme nicht zum
  Manifest passt, wird verworfen und niemals installiert.
- **Aus**: Es wird nicht nach Updates gesucht.

Beispiel für ein Manifest:

```json
{
    "version": "1.2.0",
    "archive": "PiKiosk-Pro-1.2.0.zip",
    "sha256": "d94d3f0e6c8a…(64 Hexadezimalzeichen)…b1c2",
    "notes": "Neue Funktionen …"
}
```

Prüfung, automatische Sicherung und Rollback laufen bei allen
Quellen identisch ab.

„Nach Updates suchen" prüft die gewählte Quelle auf eine neuere
Version. Ist eine verfügbar, kann sie mit „Update installieren"
eingespielt werden. Alternativ lässt sich ein Update-Paket (ZIP oder
tar.gz) hochladen und installieren.

Vor jeder Installation wird automatisch eine Sicherung erstellt und
ein Rollback-Stand angelegt. Über „Rollback durchführen" kann der
zuletzt installierte Stand wieder zurückgenommen werden. Nach Update
oder Rollback wird ein Neustart empfohlen (System-Kachel).

### Logs

Zeigt die letzten 200 Zeilen von Systemlog, Browserlog, Watchdoglog,
Netzwerklog, Installationslog und Updatelog. Über den Pfeil-Button
lässt sich jede Logdatei herunterladen.

## Abmeldung

Über „Abmelden" oben rechts wird die Sitzung sofort beendet.
