# Architektur

PiKiosk Pro ist eine modulare Flask-Anwendung. Module kommunizieren
ausschließlich über definierte Schnittstellen und werden per
Dependency Injection über die `ServiceRegistry` verdrahtet. Es gibt
keine globalen Variablen.

## Schichten

```
                Browser (Chromium)
                       │
                       ▼
                Flask Webserver
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
 Dashboard       Setup Wizard      REST API
        │
        ▼
 Controller Layer
        │
        ▼
 Service Layer
        │
        ▼
 System Layer
        │
        ▼
 Raspberry Pi OS
```

## Module (Version 0.8.0)

| Modul                              | Aufgabe                                        |
| ---------------------------------- | ---------------------------------------------- |
| `app/__init__.py`                  | Anwendungsfabrik, Fehlerbehandlung             |
| `app/app.py`                       | Einstiegspunkt, Bootprozess, Browserstart      |
| `app/constants.py`                 | Zentrale Konstanten (Pfade, Browserparameter)  |
| `app/exceptions.py`                | Eigene Exception-Klassen                       |
| `app/logger.py`                    | KioskLogger mit Rotation                       |
| `app/extensions.py`                | ServiceRegistry (Dependency Injection)         |
| `app/routes.py`                    | Statusseite und Health-Endpunkt                |
| `app/services/config_service.py`   | Konfigurationsverwaltung (JSON)                |
| `app/services/browser_service.py`  | Chromium-Steuerung über subprocess und CDP     |
| `app/controllers/setup_controller.py` | Setup-Wizard (Ersteinrichtung)             |
| `app/controllers/auth_controller.py`  | Anmeldung und Abmeldung (Flask-Login)      |
| `app/controllers/dashboard_controller.py` | Dashboardseite und Datenfragment       |
| `app/controllers/browser_controller.py` | Browsersteuerung im Dashboard            |
| `app/controllers/settings_controller.py` | Kiosk-URL- und Hostname-Verwaltung      |
| `app/controllers/network_controller.py` | WLAN-Kachel im Dashboard                 |
| `app/controllers/system_controller.py` | Neustart, Herunterfahren, Logansicht      |
| `app/services/dashboard_service.py` | Systeminformationen (psutil)                  |
| `app/services/system_service.py`   | Neustart und Herunterfahren ueber systemd      |
| `app/services/watchdog_service.py` | Browser-, Netzwerk- und Systemueberwachung     |
| `app/watchdog.py`                  | Einstiegspunkt des Watchdog-Dienstes           |
| `app/controllers/internal_controller.py` | Tokengeschuetzter Watchdog-Endpunkt     |
| `app/utils/filesystem.py`          | Atomares JSON-Lesen und -Schreiben             |
| `app/services/backup_service.py`   | ZIP-Sicherungen erstellen und verwalten        |
| `app/services/restore_service.py`  | Sicherungen pruefen, wiederherstellen, USB-Scan |
| `app/controllers/backup_controller.py` | Sicherungs-Kachel im Dashboard            |
| `app/controllers/restore_controller.py` | Wiederherstellung und USB-Import         |
| `app/utils/version.py`             | Semantic Versioning, Kompatibilitaetspruefung  |
| `app/services/update_service.py`   | Updates aus GitHub/Paket, Rollback             |
| `app/controllers/update_controller.py` | Update-Kachel im Dashboard                |
| `app/api/`                         | REST API (Token, Status, Browser, Settings, Netzwerk, System, Update, Backup, Logs) |
| `app/utils/crypto.py`              | JWT (HS256) mit Bordmitteln                    |
| `app/services/network_service.py`  | WLAN-Verwaltung über NetworkManager (nmcli)    |
| `app/services/hostname_service.py` | Hostnameverwaltung mit Root-Helferskript       |
| `app/services/auth_service.py`     | Benutzer- und Passwortverwaltung (bcrypt)      |
| `app/models/user_model.py`         | Benutzertabelle in SQLite                      |
| `app/utils/validators.py`          | Hostname-, URL-, Passwort- und Konfigvalidierung |
| `app/utils/network.py`             | DevTools-Client, URL-Statusprüfung             |
| `app/utils/helpers.py`             | Sprachdateien, IP, Gerätemodell, Secret-Key    |
| `scripts/hostname_apply.py`        | Root-Helfer für /etc/hostname und hostnamectl  |

## Bootprozess

1. systemd startet `pikiosk.service` nach dem grafischen Login.
2. `app.app.main()` erzeugt die Anwendung; `ConfigService.load()` legt
   bei Bedarf `config/config.json` aus den Standardwerten an.
3. Ein Hintergrundthread wartet, bis der Webserver erreichbar ist.
4. Der `BrowserService` startet Chromium im Kioskmodus:
   - `first_start=true` oder leere URL → lokale Statusseite
   - sonst → konfigurierte Kiosk-URL

## Konfiguration

Die gesamte Konfiguration liegt in `config/config.json` und wird
ausschließlich über den `ConfigService` gelesen und geschrieben
(atomare Schreibvorgänge, Validierung vor jedem Speichern).
Shell-Skripte verändern niemals Konfigurationsdateien.

## Logging

Jedes Modul besitzt einen eigenen `KioskLogger`. Logdateien rotieren
bei 10 MB mit 10 Generationen. Fehler erscheinen zusätzlich auf der
Konsole (stderr) und damit im systemd-Journal.

| Datei              | Inhalt                          |
| ------------------ | ------------------------------- |
| `logs/system.log`  | Anwendung und Konfiguration     |
| `logs/browser.log` | Browsersteuerung                |
| `logs/install.log` | Installationsskript             |
| `logs/update.log`  | Aktualisierungsskript           |

## Setup-Wizard

Der Wizard läuft ausschließlich beim ersten Start (`first_start=true`).
Ein zentraler Before-Request-Hook leitet bis zum Abschluss der
Einrichtung alle Anfragen auf `/setup` um; danach ist der Wizard
gesperrt. Die Schritte werden als HTMX-Fragmente nachgeladen, alle
Eingaben werden serverseitig validiert (Hostname, Passwortregeln,
URL-Erreichbarkeit). Der Wizard-Zustand liegt in der Flask-Session,
Passwörter dort nur als bcrypt-Hash. Alle POST-Anfragen sind per
CSRF-Token geschützt.

## Datenhaltung

| Daten          | Ablage                       |
| -------------- | ---------------------------- |
| Konfiguration  | `config/config.json` (JSON)  |
| Benutzer       | `config/users.db` (SQLite)   |
| Sitzungsschlüssel | `config/secret_key`       |
| Logs           | `logs/*.log` (Dateien)       |

## Anmeldung und Sicherheit

Das Dashboard ist nur nach Anmeldung erreichbar (Flask-Login,
`login_view = auth.login`). Passwoerter werden ausschliesslich mit
bcrypt geprueft. Die Sitzung laeuft nach 30 Minuten ab, Cookies
sind HttpOnly und SameSite=Lax. Ein globaler Before-Request-Hook
erzwingt fuer alle Schreibanfragen (POST/PUT/PATCH/DELETE) ein
CSRF-Token aus der Sitzung.

## Watchdog

Der Watchdog laeuft als eigenstaendiger systemd-Dienst
(`pikiosk-watchdog.service`) in einem eigenen Prozess und prueft
alle 5 Sekunden:

- **Browser**: Zustand ueber den Health-Endpunkt der Hauptanwendung.
  Ein abgestuerzter Browser wird ueber den tokengeschuetzten
  Endpunkt `/internal/browser/restart` neu gestartet, maximal 3 Mal
  innerhalb von 60 Sekunden; danach Fehlerstatus. Ein vom
  Administrator gestoppter Browser wird nicht angefasst.
- **Netzwerk**: Gateway (Ping auf die Standardroute), DNS
  (Aufloesung des Kiosk-URL-Hosts), Internet (TCP-Verbindung),
  Kiosk-URL (HTTP-Statuspruefung).
- **System**: Temperatur (Warnung 75 °C, kritisch 80 °C), RAM
  (85 %), Festplatte (90 %).

Der Gesamtzustand (online, warning, error, offline, disabled) wird
atomar in `logs/watchdog_status.json` geschrieben; das Dashboard
liest die Datei und zeigt den Zustand an. Ist die Datei aelter als
20 Sekunden, gilt der Watchdog als inaktiv.

## Aktualisierung

Der `UpdateService` unterstuetzt zwei Quellen: ein hochgeladenes
Update-Paket (ZIP oder tar.gz) und das neueste GitHub-Release. Vor
jeder Installation wird automatisch eine Sicherung erstellt und ein
Rollback-Stand des aktuellen Programmcodes unter
`backup/releases/rollback_<zeit>` angelegt. Das Paket wird geprueft
(gueltiges Archiv, Pflichtdateien, auswertbare Version, keine
Pfad-Ausbrueche) und muss echt neuer als die laufende Version sein.
Beim Entpacken bleiben Konfiguration, Benutzerdatenbank, Logs und das
Sicherungsverzeichnis unangetastet. Ein Manifest
(`backup/releases/update_manifest.json`) haelt Von-/Zielversion,
Rollback-Stand und die installierten Dateien fest, sodass der
Rollback den vorherigen Stand vollstaendig wiederherstellt und neu
hinzugefuegte Dateien wieder entfernt. Nach Update oder Rollback wird
ein Neustart empfohlen.

## REST API und Remote-Verwaltung

Die REST API unter `/api` liefert ausschliesslich JSON und ist
vollstaendig authentifiziert: `POST /api/token` stellt gegen die
Administrator-Anmeldedaten ein JWT (HS256, 24 h gueltig) aus, alle
weiteren Endpunkte erwarten es als Bearer-Token. Die API ist von
CSRF-Schutz und Setup-Umleitung ausgenommen (Token statt Sitzung)
und besitzt eigene JSON-Fehlerantworten. Eine zentrale Verwaltung
kann darueber beliebig viele Geraete steuern (Status, Konfiguration,
Browser, Netzwerk, Updates, Sicherungen, Neustart), ohne dass die
lokale Weboberflaeche davon abhaengt. Details: [API.md](API.md).

## Mehrsprachigkeit und Themes

Alle Oberflaechentexte kommen aus den JSON-Sprachdateien
(`config/language_de.json`, `config/language_en.json`); im
Python-Code stehen keine Texte. Sprache und Theme werden in der
Konfiguration gespeichert und lassen sich im Dashboard (Kachel
„Darstellung") sowie im Setup-Wizard umschalten. Das Theme
„Automatisch" folgt ueber `static/js/theme.js` der
Systemeinstellung. Konfiguration und Sprachdateien werden je
Aenderungsstand (mtime) zwischengespeichert, damit sie nicht bei
jeder Anfrage neu gelesen werden.

## Ausblick

Es folgen die Stabilisierungsversionen v0.9 (Beta: Fehlerbehebung,
Tests, Dokumentation) und v1.0 (Release).
