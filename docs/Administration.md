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
- **Status**: Browserstatus, Internetstatus, Kiosk-URL, letzter
  Neustart, Systemlaufzeit

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

### Logs

Zeigt die letzten 200 Zeilen von Systemlog, Browserlog, Netzwerklog,
Installationslog und Updatelog. Über den Pfeil-Button lässt sich
jede Logdatei herunterladen.

## Abmeldung

Über „Abmelden" oben rechts wird die Sitzung sofort beendet.
