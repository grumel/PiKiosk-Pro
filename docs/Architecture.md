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

## Module (Version 0.1.0)

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
| `app/utils/validators.py`          | Hostname-, URL- und Konfigurationsvalidierung  |
| `app/utils/network.py`             | DevTools-Client für den Seiten-Reload          |
| `app/utils/helpers.py`             | Sprachdateien, lokale IP-Ermittlung            |

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

## Ausblick

Die Struktur ist auf die kommenden Versionen vorbereitet: Setup-Wizard
(v0.2), Dashboard (v0.3), Watchdog (v0.4), Backup/Restore (v0.5),
Updatesystem (v0.6), REST API (v0.7) sowie Mehrsprachigkeit und
Themes (v0.8).
