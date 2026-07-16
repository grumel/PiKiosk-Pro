# Administration

Diese Anleitung beschreibt die Verwaltung von PiKiosk Pro über die
Weboberfläche. Linux-Kenntnisse sind nicht erforderlich.

## Anmeldung

Die Verwaltungsoberfläche ist im lokalen Netzwerk erreichbar unter:

```
http://<ip-adresse-des-geraets>:8080/login
```

Melden Sie sich mit dem Administratorkonto an, das im Setup-Wizard
angelegt wurde. Nach 30 Minuten ohne Aktivität wird die Sitzung
automatisch beendet. Mit „Angemeldet bleiben" bleibt die Anmeldung
7 Tage erhalten.

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

### System

„Neustart" und „Herunterfahren" beenden zuerst den Browser sauber
und führen die Aktion anschließend über systemd aus. Beide Aktionen
müssen bestätigt werden.

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

„Nach Updates suchen" prüft das GitHub-Repository auf ein neueres
Release. Ist eines verfügbar, kann es mit „Update installieren"
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
