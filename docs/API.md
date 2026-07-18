# REST API

PiKiosk Pro stellt unter `/api/v1` eine versionierte REST API
bereit. Sie ist die Grundlage für die Remote-Verwaltung mehrerer
Geräte; die lokale Weboberfläche bleibt davon unberührt. Alle
Antworten sind JSON, alle Endpunkte (außer der Token-Ausgabe) sind
authentifiziert.

Der unversionierte Pfad `/api` bleibt dauerhaft als Alias für
Bestandsclients erhalten und bedient dieselben v1-Endpunkte; neue
Integrationen verwenden `/api/v1`. Bei einer künftigen API-Version
v2 bleibt `/api/v1` unverändert gültig.

## Authentifizierung

Die API verwendet JSON Web Tokens (JWT, HS256). Ein Token wird mit
den Anmeldedaten des Administrators ausgestellt und ist 4 Stunden
gültig.

```bash
curl -k -X POST https://<geraet>:8080/api/v1/token \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "<passwort>"}'
```

Antwort:

```json
{"token": "<jwt>", "token_type": "Bearer", "expires_in": 14400}
```

Läuft das Gerät noch ohne TLS-Zertifikat, gilt `http://` statt
`https://`; `-k` akzeptiert das selbstsignierte Zertifikat des
Installers. Nach 5 fehlgeschlagenen Anmeldeversuchen innerhalb von
15 Minuten antwortet die Token-Ausgabe mit `429 too_many_attempts`
und einer `Retry-After`-Kopfzeile (Sekunden bis zum nächsten
Versuch).

Alle weiteren Anfragen tragen das Token im Header:

```
Authorization: Bearer <jwt>
```

Fehlende oder ungültige Tokens ergeben `401 {"error": "unauthorized"}`.
Fachliche Fehler ergeben `400 {"error": "<meldung>"}`, unbekannte
Pfade `404 {"error": "not_found"}`.

## Endpunkte

### Status und Version

| Methode | Pfad           | Beschreibung                          |
| ------- | -------------- | ------------------------------------- |
| GET     | `/api/status`  | Vollständiger Gerätestatus (Hostname, IP, MAC, CPU, RAM, Temperatur, Festplatte, Browser-, Internet- und Watchdogstatus, URL, Version, Laufzeit) |
| GET     | `/api/version` | Anwendungsname und Version            |

### Browser

| Methode | Pfad           | Beschreibung                          |
| ------- | -------------- | ------------------------------------- |
| GET     | `/api/browser` | Browserstatus                         |
| POST    | `/api/browser` | Aktion ausführen: `{"action": "start\|stop\|restart\|reload\|clear_cache"}` |

### Einstellungen

| Methode | Pfad            | Beschreibung                         |
| ------- | --------------- | ------------------------------------ |
| GET     | `/api/settings` | Aktive Konfiguration                 |
| PUT     | `/api/settings` | Schlüssel ändern: `url`, `language`, `theme`, `fullscreen`, `watchdog`, `hostname`, `update_source` (`github`/`local`/`off`), `update_url`, `connectivity_check` (`internet`/`url`/`gateway`/`off`). Ungültige Werte werden nie gespeichert; eine Hostnameänderung wird sofort angewendet. |

### Netzwerk

| Methode | Pfad                          | Beschreibung           |
| ------- | ----------------------------- | ---------------------- |
| GET     | `/api/network`                | Aktive Verbindung, IP, Gateway, DNS, MAC, Signal, gespeicherte Profile |
| POST    | `/api/network`                | `{"action": "scan"}` (Netzwerkliste), `{"action": "connect", "ssid": "...", "password": "..."}`, `{"action": "disconnect"}` |
| DELETE  | `/api/network/profiles/<name>`| Gespeichertes WLAN-Profil löschen |

### System

| Methode | Pfad          | Beschreibung                           |
| ------- | ------------- | -------------------------------------- |
| GET     | `/api/system` | Detaillierter Watchdogstatus           |
| POST    | `/api/system` | `{"action": "reboot\|shutdown"}` (Browser wird vorher sauber beendet) |

### Aktualisierung

| Methode | Pfad          | Beschreibung                           |
| ------- | ------------- | -------------------------------------- |
| GET     | `/api/update` | Version, Updatequelle und Rollback-Zustand |
| POST    | `/api/update` | `{"action": "check"}` (konfigurierte Quelle prüfen), `{"action": "install"}` (installieren, mit automatischer Sicherung), `{"action": "rollback"}` |

### Sicherung

| Methode | Pfad                 | Beschreibung                    |
| ------- | -------------------- | ------------------------------- |
| GET     | `/api/backup`        | Sicherungen auflisten           |
| POST    | `/api/backup`        | Sicherung erstellen, optional `{"include_logs": true}` |
| GET     | `/api/backup/<name>` | Sicherung herunterladen (ZIP)   |

### Logs

| Methode | Pfad               | Beschreibung                      |
| ------- | ------------------ | --------------------------------- |
| GET     | `/api/logs`        | Verfügbare Logdateien             |
| GET     | `/api/logs/<name>` | Letzte 200 Zeilen einer Logdatei  |

## Beispiel: Gerät per API verwalten

```bash
BASE=http://<geraet>:8080
TOKEN=$(curl -s -X POST $BASE/api/token \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<passwort>"}' | jq -r .token)

curl -s $BASE/api/status  -H "Authorization: Bearer $TOKEN"
curl -s -X PUT $BASE/api/settings \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"url": "https://beispiel.de/anzeige"}'
curl -s -X POST $BASE/api/browser \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"action": "restart"}'
```

## Offline-Betrieb einrichten

```bash
curl -s -X PUT $BASE/api/settings \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"url": "http://server.local/anzeige",
       "connectivity_check": "url",
       "update_source": "local",
       "update_url": "http://server.local/pikiosk"}'
```

Danach benötigt das Gerät keinen Internetzugang mehr: Die
Kiosk-Webseite und die Updatequelle liegen im lokalen Netz, und die
Verbindungsprüfung misst die Erreichbarkeit der Kiosk-URL statt des
Internets.

## Mehrgerätefähigkeit

Eine zentrale Verwaltung spricht jedes Gerät über diese API an:
Statusabfrage, Konfiguration, Browsersteuerung, Updates, Sicherungen
und Neustarts sind vollständig entfernt steuerbar. Die Geräte bleiben
dabei autark – die lokale Weboberfläche und der Kioskbetrieb sind von
der API unabhängig.
