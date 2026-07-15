# PiKiosk Pro

Version 1.0

---

# Projektbeschreibung

PiKiosk Pro ist ein professionelles Open-Source-Kiosk-System für Raspberry Pi 4.

Das System soll beliebig oft installiert werden können und ohne Linux-Kenntnisse administrierbar sein.

Nach dem Schreiben einer SD-Karte und dem ersten Start erscheint automatisch ein Setup-Assistent.

Nach Abschluss des Assistenten startet Chromium automatisch im Kioskmodus und zeigt die konfigurierte Webseite an.

Das System ist vollständig webbasiert.

Es werden keine Desktop-Anwendungen (Tkinter o.Ä.) verwendet.

Die Administration erfolgt ausschließlich über eine lokale Weboberfläche.

---

# Zielplattform

Hardware

- Raspberry Pi 4

Empfohlen

- Raspberry Pi 4 4 GB
- Raspberry Pi 4 8 GB

Betriebssystem

- Raspberry Pi OS Desktop 64 Bit

Browser

- Chromium

Python

- Python 3.13

---

# Ziel

Nach dem Booten soll der Raspberry Pi automatisch

- starten
- Benutzer anmelden
- PiKiosk starten
- Chromium starten
- Webseite anzeigen

ohne jegliche Benutzereingriffe.

---

# Philosophie

Das Projekt muss produktionsreif entwickelt werden.

Es handelt sich ausdrücklich nicht um Beispielcode.

Es handelt sich nicht um Demo-Code.

Es handelt sich nicht um Proof of Concept.

Es handelt sich nicht um Schulungsmaterial.

Es handelt sich um eine professionelle Software.

Alle Dateien müssen vollständig implementiert werden.

---

# Anforderungen

Es dürfen niemals verwendet werden

- Platzhalter
- TODO Kommentare
- Dummyfunktionen
- Pseudocode
- Beispielcode
- nicht verwendete Klassen
- nicht verwendete Methoden

Jede Klasse muss vollständig implementiert sein.

Jede Funktion muss vollständig implementiert sein.

---

# Entwicklungsregeln

Arbeite ausschließlich mit

Python

HTML

CSS

JavaScript

Bootstrap

Flask

HTMX

systemd

SQLite (nur falls erforderlich)

JSON

NetworkManager

Chromium

psutil

Werkzeuge dürfen verwendet werden, wenn sie Bestandteil von Raspberry Pi OS sind.

Keine unnötigen Abhängigkeiten installieren.

---

# Projektstruktur

PiKiosk-Pro/

README.md

LICENSE

.gitignore

requirements.txt

install.sh

update.sh

CHANGELOG.md

CONTRIBUTING.md

SECURITY.md

---

app/

---

config/

---

templates/

---

static/

---

scripts/

---

services/

---

docs/

---

tests/

---

logs/

---

backup/

---

# Architektur

Das Projekt besteht aus folgenden Modulen.

config.py

logger.py

browser.py

dashboard.py

setup.py

wifi.py

hostname.py

system.py

watchdog.py

update.py

backup.py

restore.py

authentication.py

users.py

network.py

utils.py

app.py

---

# Programmierrichtlinien

Python

PEP8

Type Hints

Logging

Docstrings

Black kompatibel

Keine globalen Variablen.

Keine doppelten Funktionen.

Keine Copy & Paste Lösungen.

DRY Prinzip.

SOLID Prinzip.

---

# Coding Style

Jede Datei beginnt mit

Copyright

Lizenz

Beschreibung

Imports

Konstanten

Klassen

Funktionen

Main

---

# Logging

Das komplette System schreibt Logdateien.

logs/system.log

logs/browser.log

logs/watchdog.log

logs/install.log

logs/network.log

logs/update.log

Alle Fehler werden zusätzlich auf der Konsole ausgegeben.

---

# Konfiguration

Die komplette Konfiguration wird gespeichert in

config/config.json

Beispiel

{

"hostname":"PiKiosk",

"url":"",

"language":"de",

"theme":"dark",

"fullscreen":true,

"watchdog":true,

"browser":"chromium",

"first_start":true

}

Die Konfiguration wird ausschließlich über Python gelesen und geschrieben.

Keine Shell-Skripte dürfen Konfigurationsdateien verändern.

---

# Sicherheit

Administratorpasswörter werden niemals im Klartext gespeichert.

Es ist bcrypt zu verwenden.

Beim ersten Login muss das Standardpasswort geändert werden.

HTTPS Unterstützung ist vorzusehen.

CSRF Schutz aktivieren.

Session Timeout implementieren.


# MASTER_PROMPT_PiKiosk_Pro_v1.md

# Teil 2 von 6

---

# Setup Wizard

Der Setup Wizard erscheint ausschließlich beim ersten Start.

Ob der Wizard gestartet wird, entscheidet der Wert

```json
{
    "first_start": true
}
```

Ist first_start=false, startet unmittelbar der Kiosk.

Der Benutzer darf niemals den Linux Desktop sehen.

Der Wizard läuft im Vollbild.

Es existiert keine Möglichkeit, den Wizard ohne Administratorrechte zu verlassen.

---

# Ziel des Wizards

Der Benutzer soll den Raspberry Pi vollständig einrichten können.

Es sind keinerlei Linux-Kenntnisse erforderlich.

Alle Einstellungen werden sofort geprüft.

Ungültige Eingaben dürfen nicht gespeichert werden.

---

# Seite 1

Willkommen

Anzeige

PiKiosk Pro

Version

Lizenz

Geräteinformationen

Weiter

---

# Seite 2

Hostname

Der Hostname darf

nur

A-Z

a-z

0-9

-

enthalten.

Maximal 63 Zeichen.

Prüfen

Hostname bereits vergeben

Hostname gültig

Hostname speichern

---

# Seite 3

WLAN

NetworkManager wird verwendet.

Es werden automatisch alle verfügbaren WLANs gesucht.

Anzeige

SSID

Signalstärke

Sicherheit

Frequenz

Sortierung

beste Signalstärke zuerst.

Passwort

Verbinden

Verbindung testen

IP-Adresse anzeigen

Gateway anzeigen

DNS anzeigen

---

# Seite 4

Administrator

Administratorname

Standard

admin

Administratorpasswort

Passwort wiederholen

Passwortqualität prüfen

Mindestens

12 Zeichen

Großbuchstaben

Kleinbuchstaben

Zahlen

Sonderzeichen

bcrypt Hash erzeugen.

Niemals Klartext speichern.

---

# Seite 5

Kiosk URL

URL

Pflichtfeld

Nur

http

https

zulässig.

Prüfen

HTTP Status

200

301

302

gelten als gültig.

Timeout

5 Sekunden

Falls ungültig

Fehlermeldung anzeigen.

---

# Seite 6

Zusammenfassung

Hostname

WLAN

Administrator

URL

Browser

Sprache

Weiter

Installation starten.

---

# Installation

Hostname setzen

WLAN verbinden

Konfiguration speichern

Benutzer anlegen

Passwort speichern

Browser konfigurieren

Autostart aktivieren

systemd aktivieren

Watchdog aktivieren

Chromium konfigurieren

first_start=false

Browser starten

---

# Dashboard

Nach erfolgreichem Login erscheint

Dashboard

Keine Terminalfenster.

Keine Linux Anwendungen.

Nur Browser.

---

# Dashboard Inhalte

Hostname

Gerätename

Standort

IP-Adresse

MAC-Adresse

CPU

RAM

Temperatur

Festplatte

Browserstatus

Internetstatus

URL

Softwareversion

Letzter Neustart

Systemlaufzeit

---

# Dashboard Kacheln

Browser

Start

Stop

Neustart

---

URL

Ändern

Testen

Speichern

---

Hostname

Ändern

Neustart

---

WLAN

Verbinden

Trennen

Neues Netzwerk

---

System

Neustart

Herunterfahren

Update

Backup

Restore

---

Logs

Systemlog

Browserlog

Watchdoglog

Installationslog

Download

---

# Browser

Chromium wird ausschließlich über Python gestartet.

Keine Shellskripte.

Startparameter

--kiosk

--start-fullscreen

--noerrdialogs

--disable-infobars

--disable-session-crashed-bubble

--disable-translate

--overscroll-history-navigation=0

--disable-pinch

--incognito

Die Startparameter werden zentral verwaltet.

Keine doppelten Definitionen.

---

# Browsersteuerung

Funktionen

start()

stop()

restart()

reload()

clear_cache()

status()

fullscreen()

---

# Browserstatus

Nicht gestartet

Läuft

Neustart

Fehler

Abgestürzt

Alle Status werden im Dashboard angezeigt.

---

# URL Verwaltung

Administrator kann URL ändern.

Nach Speichern

URL prüfen.

Falls gültig

Browser automatisch neu starten.

Falls ungültig

Fehlermeldung anzeigen.

Konfiguration nicht speichern.

---

# Kioskmodus

Benutzer sieht ausschließlich

Chromium.

Keine Taskleiste.

Kein Desktop.

Keine Icons.

Keine Kontextmenüs.

Keine Dialoge.

Keine Fehlermeldungen.

---

# Touchscreen

Alle Buttons mindestens

48 x 48 Pixel.

Bootstrap responsive.

Bedienbar mit Finger.

Keine Hover Funktionen erforderlich.

---

# Sprache

Deutsch

Englisch

Sprachdateien

JSON

Keine Texte im Python Code.

Alle Texte werden über Sprachdateien geladen.

---

# Theme

Dark

Light

Automatisch

Theme wird gespeichert.

# MASTER_PROMPT_PiKiosk_Pro_v1.md

# Teil 3 von 6

---

# Benutzerverwaltung

PiKiosk Pro kennt zwei Rollen.

## Benutzer

Der normale Benutzer besitzt keinerlei Administrationsrechte.

Er sieht ausschließlich die konfigurierte Webseite.

Er kann

- nichts schließen
- keine URL ändern
- keine Einstellungen ändern
- den Browser nicht verlassen
- keine Shell öffnen
- keinen Desktop verwenden

Der Benutzer bemerkt nicht, dass Linux im Hintergrund läuft.

---

## Administrator

Der Administrator erhält Zugriff auf

Dashboard

Browsersteuerung

URL

Hostname

WLAN

Netzwerk

SSH

VNC

Updates

Backup

Restore

Logs

Systeminformationen

Neustart

Herunterfahren

Administratorverwaltung

---

# Authentifizierung

Flask-Login verwenden.

Passwortprüfung ausschließlich über bcrypt.

Keine Passwörter im Klartext.

Session Timeout

30 Minuten

CSRF Schutz aktiv.

Session Cookies

HttpOnly

Secure

SameSite=Lax

---

# Benutzerdaten

Die Benutzer werden in SQLite gespeichert.

Tabelle

users

Felder

id

username

password_hash

role

created_at

last_login

enabled

Es wird mindestens ein Benutzer erzeugt.

admin

Beim ersten Start muss dessen Passwort geändert werden.

---

# WLAN Manager

Es wird ausschließlich

NetworkManager

verwendet.

Keine Bearbeitung von

/etc/wpa_supplicant.conf

Der WLAN Manager verwendet ausschließlich

nmcli

---

# Funktionen

scan()

connect()

disconnect()

delete_profile()

current_connection()

list_saved_networks()

signal_strength()

ip_address()

gateway()

dns()

---

# WLAN Dashboard

Anzeige

SSID

Signal

Sicherheit

IPv4

Gateway

DNS

Status

Verbunden

Nicht verbunden

Verbinden

Trennen

---

# WLAN Fehler

Passwort falsch

SSID nicht gefunden

Keine IP erhalten

DHCP Fehler

DNS Fehler

Zeitüberschreitung

Alle Fehler verständlich anzeigen.

Keine Linux Fehlermeldungen.

---

# Hostname Manager

Hostname ändern.

Hostname prüfen.

Hostname speichern.

System aktualisieren.

Neustart anbieten.

Verwendete Dateien

/etc/hostname

/etc/hosts

Nach Änderung

hostnamectl

verwenden.

---

# Watchdog

Eigenständiger systemd Dienst.

Startet automatisch.

Läuft dauerhaft.

Prüft alle 5 Sekunden

Browser läuft

Browserprozess

Internet erreichbar

Gateway erreichbar

URL erreichbar

Speicher

CPU

Temperatur

---

# Browser Watchdog

Falls Chromium beendet wurde

Browser neu starten.

Maximal

3 Neustarts

innerhalb

60 Sekunden.

Danach

Fehlerstatus.

Administrator informieren.

---

# Netzwerk Watchdog

Gateway nicht erreichbar

DNS nicht erreichbar

Internet nicht erreichbar

URL nicht erreichbar

Alle Zustände werden gespeichert.

Dashboard zeigt

Online

Offline

Warnung

Fehler

---

# System Watchdog

CPU Temperatur

Warnung

75°C

Kritisch

80°C

RAM Nutzung

Warnung

85%

Festplatte

Warnung

90%

Logdatei schreiben.

---

# Backup

Komplette Konfiguration sichern.

Zu sichern

config/

SQLite Datenbank

Logs optional

Assets optional

Backup als ZIP.

Dateiname

PiKiosk_Backup_YYYYMMDD_HHMM.zip

---

# Restore

ZIP auswählen.

Backup prüfen.

Version prüfen.

Konfiguration wiederherstellen.

Neustart anbieten.

---

# USB Import

USB Geräte automatisch erkennen.

Nach Einstecken

Suche

PiKiosk_Backup.zip

Falls gefunden

Import anbieten.

Konfiguration prüfen.

Version prüfen.

Importieren.

---

# Update System

Lokale Updates.

GitHub Updates.

Version prüfen.

Neue Version herunterladen.

Backup erstellen.

Update installieren.

Neustart anbieten.

Rollback ermöglichen.

---

# GitHub

Repository

PiKiosk-Pro

Branches

main

develop

feature/*

release/*

hotfix/*

---

# Versionierung

Semantic Versioning

Major

Minor

Patch

Beispiel

1.0.0

1.1.0

1.1.1

---

# Logging

Jedes Modul besitzt einen eigenen Logger.

Browser

Dashboard

Installer

Update

Watchdog

Network

Authentication

Backup

Restore

Alle Logs besitzen

Zeit

Level

Modul

Nachricht

Stacktrace bei Fehlern.

---

# Fehlerbehandlung

Keine Python Tracebacks im Browser.

Alle Fehler werden abgefangen.

Benutzer erhält verständliche Meldungen.

Administrator erhält Detailinformationen.

---

# REST API

Vorbereiten.

Noch nicht vollständig implementieren.

Basis

/api

GET

POST

PUT

DELETE

JSON

JWT vorbereitet.

---

# API Endpunkte

/api/status

/api/browser

/api/settings

/api/network

/api/system

/api/version

/api/update

/api/backup

/api/logs

Alle Endpunkte authentifizieren.

---

# Mehrgerätefähigkeit

Architektur muss später ermöglichen

10

100

1000

PiKiosk Systeme zentral zu verwalten.

Lokale Software darf dadurch nicht beeinflusst werden.

# MASTER_PROMPT_PiKiosk_Pro_v1.md

# Teil 4 von 6

---

# Softwarearchitektur

PiKiosk Pro wird als modulare Anwendung entwickelt.

Alle Module müssen unabhängig voneinander funktionieren.

Zwischen den Modulen darf ausschließlich über klar definierte Schnittstellen kommuniziert werden.

Keine direkten Zugriffe zwischen Modulen.

Keine globalen Variablen.

Alle Module verwenden Dependency Injection.

---

# Architektur

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

---

# Projektstruktur

PiKiosk-Pro/

README.md

LICENSE

CHANGELOG.md

CONTRIBUTING.md

SECURITY.md

requirements.txt

install.sh

update.sh

.env.example

.gitignore

---

app/

__init__.py

app.py

extensions.py

routes.py

config.py

constants.py

exceptions.py

logger.py

---

app/controllers/

dashboard_controller.py

browser_controller.py

network_controller.py

setup_controller.py

settings_controller.py

system_controller.py

update_controller.py

backup_controller.py

restore_controller.py

auth_controller.py

---

app/services/

browser_service.py

network_service.py

hostname_service.py

config_service.py

watchdog_service.py

update_service.py

backup_service.py

restore_service.py

system_service.py

auth_service.py

dashboard_service.py

---

app/models/

config_model.py

user_model.py

system_model.py

---

app/api/

status.py

browser.py

network.py

settings.py

update.py

system.py

backup.py

logs.py

---

app/utils/

validators.py

helpers.py

filesystem.py

network.py

crypto.py

version.py

---

config/

config.json

defaults.json

language_de.json

language_en.json

---

templates/

base.html

setup.html

login.html

dashboard.html

browser.html

network.html

settings.html

logs.html

backup.html

update.html

---

static/

css/

js/

img/

fonts/

---

services/

pikiosk.service

pikiosk-watchdog.service

---

scripts/

start_browser.py

stop_browser.py

restart_browser.py

install_browser.py

network_scan.py

hostname_apply.py

---

logs/

---

backup/

---

tests/

unit/

integration/

system/

---

docs/

Installation.md

Administration.md

DeveloperGuide.md

API.md

Architecture.md

---

# Flask

Blueprints verwenden.

Keine einzige große app.py.

Blueprints

dashboard

setup

browser

network

settings

auth

system

api

---

# Template System

Jede Seite erweitert

base.html

Keine doppelten Header.

Keine doppelten Menüs.

Navigation zentral.

---

# Frontend

Bootstrap 5

HTMX

Vanilla JavaScript

Keine React Installation.

Keine Angular Installation.

Keine Vue Installation.

---

# Design

Dark Theme

Light Theme

Automatik

Responsive

Touchscreen geeignet

Buttons mindestens

48x48 Pixel.

---

# Browsersteuerung

Nur Python.

Keine Shellskripte.

Browserprozess über subprocess verwalten.

Klasse

BrowserService

Methoden

start()

stop()

restart()

reload()

clear_cache()

status()

fullscreen()

---

# Konfiguration

ConfigService

Methoden

load()

save()

reset()

validate()

backup()

restore()

Alle Module greifen ausschließlich über ConfigService auf Einstellungen zu.

Direkte Dateizugriffe verboten.

---

# Netzwerk

NetworkService

Methoden

scan()

connect()

disconnect()

current()

saved()

delete()

ip()

gateway()

dns()

mac()

signal()

Es wird ausschließlich nmcli verwendet.

---

# Hostname

HostnameService

Methoden

get()

set()

validate()

apply()

reboot_required()

---

# Dashboard

DashboardService

Liefert

Hostname

IP

CPU

RAM

Temperatur

Browserstatus

Internetstatus

Version

Uptime

Speicher

Festplatte

JSON Objekt.

Dashboard rendert ausschließlich dieses Objekt.

---

# Authentifizierung

Flask Login

bcrypt

Session

Remember Me

Logout

Session Timeout

CSRF

---

# Logging

Logger Klasse.

Methoden

debug()

info()

warning()

error()

critical()

Rotation

10 Dateien

10 MB

---

# Exception Handling

Eigene Exception Klassen

ConfigurationError

BrowserError

NetworkError

UpdateError

BackupError

RestoreError

AuthenticationError

ValidationError

Keine nackten Exceptions.

---

# Validierung

Validator Klassen

HostnameValidator

URLValidator

PasswordValidator

NetworkValidator

ConfigValidator

Alle Eingaben validieren.

---

# Datenmodell

Konfiguration

JSON

Benutzer

SQLite

Logs

Dateien

Backups

ZIP

---

# Installer

Installiert

Python

pip

Flask

Chromium

NetworkManager

Git

systemd

Aktiviert

Autologin

PiKiosk

Watchdog

Browser

---

# Bootprozess

System bootet

↓

Autologin

↓

systemd startet PiKiosk

↓

Config laden

↓

first_start?

Ja

↓

Setup Wizard

Nein

↓

Browser starten

↓

Dashboard initialisieren

↓

Watchdog starten

↓

Kiosk aktiv

---

# Shutdown

Vor dem Herunterfahren

Konfiguration speichern

Logs schließen

Browser sauber beenden

Services stoppen

Erst danach Shutdown.

---

# Neustart

Browser stoppen

Konfiguration speichern

Services beenden

Reboot

Automatischer Neustart

PiKiosk wieder aktiv.

# MASTER_PROMPT_PiKiosk_Pro_v1.md

# Teil 5 von 6

---

# Entwicklungsrichtlinien

PiKiosk Pro wird wie ein professionelles Open-Source-Projekt entwickelt.

Jede Änderung muss

- nachvollziehbar
- dokumentiert
- getestet
- versioniert

sein.

Keine Änderungen direkt auf dem main Branch.

---

# Git Workflow

Branches

main

develop

feature/<feature-name>

bugfix/<bug-name>

release/<version>

hotfix/<version>

---

# Commit Regeln

Jeder Commit enthält genau eine abgeschlossene Änderung.

Beispiele

feat(browser): Browser Watchdog implementiert

fix(network): WLAN Scan korrigiert

docs(readme): Installationsanleitung ergänzt

refactor(config): ConfigService vereinfacht

test(browser): Unit Tests ergänzt

---

# Pull Requests

Jede größere Änderung erfolgt über Pull Requests.

Pull Request muss enthalten

Beschreibung

Änderungen

Tests

Screenshots (bei GUI)

Risiken

---

# Code Reviews

Vor Merge prüfen

PEP8

Black

Type Hints

Docstrings

Logging

Fehlerbehandlung

Tests

---

# Coding Standards

Python

PEP8

Black

isort

mypy

ruff

Alle Funktionen besitzen Type Hints.

Alle öffentlichen Klassen besitzen Docstrings.

---

# Docstrings

Google Style

Beispiel

def connect(ssid: str, password: str) -> bool:
    """
    Verbindet den Raspberry Pi mit einem WLAN.

    Args:
        ssid:
            Name des WLANs.

        password:
            WLAN Passwort.

    Returns:
        True wenn Verbindung erfolgreich.

    Raises:
        NetworkError
    """

---

# Logging

Kein print()

Ausschließlich Logging.

DEBUG

INFO

WARNING

ERROR

CRITICAL

Log Rotation

10 Dateien

10 MB

---

# Fehlerbehandlung

Keine nackten

except:

verwenden.

Immer

except Exception as e

oder

eigene Exceptions.

---

# Tests

Es werden erstellt

Unit Tests

Integration Tests

System Tests

---

# Unit Tests

Für

ConfigService

BrowserService

HostnameService

NetworkService

BackupService

RestoreService

WatchdogService

UpdateService

AuthenticationService

Validators

---

# Integration Tests

Browser startet

Browser stoppt

Browser Neustart

WLAN Verbindung

Hostname ändern

Backup

Restore

Installer

---

# System Tests

Erster Boot

Setup Wizard

Browser startet

Autostart

Update

Backup

Restore

Watchdog

---

# Testabdeckung

Mindestens

90%

für

Service Layer

Controller Layer

Validatoren

---

# Performance

Bootzeit

unter

30 Sekunden.

Browserstart

unter

5 Sekunden.

Dashboard

unter

1 Sekunde.

API Antwort

unter

200 ms.

---

# Speicherverbrauch

RAM

unter

300 MB

ohne Chromium.

CPU

Leerlauf

unter

5%.

---

# Sicherheit

OWASP Top 10 berücksichtigen.

Keine SQL Injection.

Keine Command Injection.

Keine Klartextpasswörter.

bcrypt verwenden.

CSRF aktivieren.

Session Timeout.

HttpOnly Cookies.

SameSite Cookies.

---

# Datenschutz

Keine Telemetrie.

Keine Cloud Pflicht.

Alle Daten bleiben lokal.

Keine personenbezogenen Daten senden.

---

# Update Strategie

Vor jedem Update

Backup erstellen.

Update herunterladen.

Validieren.

Installieren.

Neustart.

Rollback ermöglichen.

---

# Backup Strategie

Backup enthält

Konfiguration

Benutzer

Sprache

Themes

Browser Einstellungen

Optional

Logs

Nicht sichern

Cache

Temporäre Dateien

---

# Release Prozess

Version erhöhen.

Tests ausführen.

Dokumentation aktualisieren.

Release Notes erstellen.

Git Tag erzeugen.

GitHub Release erstellen.

---

# Versionsschema

Semantic Versioning

MAJOR.MINOR.PATCH

Beispiele

0.1.0

0.2.0

0.5.3

1.0.0

---

# Dokumentation

README

Installation

Administration

Entwicklerhandbuch

API Dokumentation

Architektur

Changelog

FAQ

Troubleshooting

---

# Lizenz

MIT License

Copyright

Holger John

PiKiosk Pro

---

# GitHub Actions

Automatisch ausführen

Lint

Black

isort

mypy

pytest

Build

Release

---

# CI Pipeline

Push

↓

Lint

↓

Tests

↓

Build

↓

Release

---

# Wartbarkeit

Keine Datei größer als

500 Zeilen

Ausnahmen

Templates

Sprachdateien

Keine Funktion größer als

60 Zeilen

Keine Klasse größer als

400 Zeilen

---

# Modularität

Ein Modul

Eine Aufgabe.

Keine gegenseitigen Abhängigkeiten.

Services kommunizieren ausschließlich über definierte Schnittstellen.

---

# Definition of Done

Eine Funktion gilt erst als fertig wenn

Code geschrieben

Tests vorhanden

Dokumentation vorhanden

Logging vorhanden

Fehlerbehandlung vorhanden

Type Hints vorhanden

Code Review bestanden

Keine TODOs

Keine Warnungen

Keine bekannten Fehler

---

# Entwicklungsregel für KI

Der KI-Assistent darf niemals

Platzhalter erzeugen.

TODO Kommentare erzeugen.

Pseudo Code schreiben.

Beispielcode erzeugen.

Nur Ausschnitte liefern.

Diffs liefern.

Patches liefern.

Immer komplette Dateien liefern.

Immer lauffähigen Code liefern.

Immer produktionsreifen Code liefern.

# MASTER_PROMPT_PiKiosk_Pro_v1.md

# Teil 6 von 6

---

# MASTER PROMPT

Du bist Lead Software Architect, Senior Python Developer,
Senior Linux Administrator,
Senior UI Designer,
Senior DevOps Engineer und Raspberry Pi Spezialist.

Du entwickelst eine professionelle Software.

Projektname

PiKiosk Pro

Version

1.0

---

# Ziel

Entwickle PiKiosk Pro vollständig.

Es handelt sich ausdrücklich NICHT um ein Beispielprojekt.

Es handelt sich NICHT um Demo-Code.

Es handelt sich NICHT um Lerncode.

Es handelt sich um produktionsreife Software.

Alle Funktionen müssen vollständig implementiert werden.

---

# Entwicklungsstrategie

Arbeite wie in einem professionellen Softwareunternehmen.

Plane zuerst.

Programmiere anschließend.

Teste jede Funktion.

Dokumentiere jede Änderung.

---

# Arbeitsweise

Arbeite Version für Version.

0.1

0.2

0.3

...

1.0

Jede Version muss vollständig lauffähig sein.

Keine unfertigen Zwischenstände.

---

# Dateien

Wenn eine Datei geändert wird

liefere IMMER

die komplette Datei.

Niemals

Diffs.

Patches.

Ausschnitte.

Ellipsen.

Pseudo Code.

---

# Antworten

Bei Änderungen

immer

Dateiname

kompletter Inhalt

kurze Erklärung

---

# Codequalität

Python

PEP8

Type Hints

Docstrings

Logging

Black kompatibel

Keine Warnungen.

Keine Fehler.

---

# Architektur

Halte dich exakt an die definierte Architektur.

Keine spontanen Änderungen.

Neue Module nur wenn erforderlich.

---

# Verzeichnisstruktur

Die Projektstruktur darf nur erweitert werden.

Bestehende Module dürfen nicht beliebig verschoben werden.

---

# Benutzeroberfläche

Bootstrap 5

HTMX

Responsive

Touchscreen geeignet.

Dark Mode

Light Mode

Barrierearm.

---

# Browser

Chromium.

Keine Alternative.

Keine Shellskripte.

Browsersteuerung ausschließlich über Python.

---

# Netzwerk

NetworkManager.

nmcli.

Keine Manipulation von

wpa_supplicant.

---

# Betriebssystem

Raspberry Pi OS Desktop

64 Bit

Raspberry Pi 4

---

# Services

systemd

Autostart

Watchdog

Logging

---

# Installer

Ein einziger Befehl

sudo ./install.sh

installiert

alle Pakete

alle Python Module

alle Services

Autologin

Chromium

PiKiosk

---

# Konfiguration

JSON

Keine INI Dateien.

Keine YAML Dateien.

Keine XML Dateien.

Konfiguration ausschließlich über ConfigService.

---

# Logging

Alle Module verwenden Logger.

Kein print()

Keine Debug-Ausgaben.

---

# Fehler

Alle Fehler werden behandelt.

Keine Python Tracebacks im Browser.

Benutzer erhält verständliche Meldungen.

Administrator erhält technische Details.

---

# Dokumentation

README

Installation

Administration

API

Developer Guide

Architecture

Troubleshooting

Changelog

immer aktuell halten.

---

# Git

Arbeite commitweise.

Jede Funktion

eigener Commit.

Committexte nach Conventional Commits.

---

# Tests

Nach jeder Funktion

Tests schreiben.

Tests müssen erfolgreich laufen.

Keine Funktion ohne Tests.

---

# Performance

Browserstart

unter 5 Sekunden.

Bootzeit

unter 30 Sekunden.

Dashboard

unter 1 Sekunde.

---

# Sicherheit

bcrypt

CSRF

Session Timeout

HttpOnly

Secure Cookies

Keine Klartextpasswörter.

---

# Benutzer

Benutzer

Administrator

Rollenkonzept strikt einhalten.

---

# Dashboard

Modern.

Übersichtlich.

Touchscreen geeignet.

Bootstrap.

Keine Tabellen wenn Karten besser geeignet sind.

---

# Zukunftssicherheit

Architektur vorbereiten für

REST API

Remote Management

Mehrere Raspberry Pi

OTA Updates

Docker Entwicklungsumgebung

Plugin System

Mehrsprachigkeit

Theme System

---

# KI Regeln

Die KI darf niemals

vereinfachen.

abkürzen.

Pseudo Code erzeugen.

Dummyfunktionen erzeugen.

TODO Kommentare erzeugen.

Platzhalter erzeugen.

---

# Die KI MUSS

immer komplette Dateien liefern.

immer lauffähigen Code liefern.

immer dokumentieren.

immer testen.

immer Logging einbauen.

immer Type Hints verwenden.

immer Docstrings schreiben.

immer Fehler behandeln.

---

# Definition eines Releases

Ein Release gilt nur dann als abgeschlossen wenn

alle Dateien vollständig sind.

alle Tests erfolgreich sind.

keine bekannten Fehler existieren.

keine TODOs vorhanden sind.

die Dokumentation vollständig ist.

der Installer funktioniert.

PiKiosk auf einem Raspberry Pi 4 installiert werden kann.

der Browser automatisch startet.

der Setup Wizard funktioniert.

der Administrator arbeiten kann.

---

# Releaseplan

v0.1

Projektstruktur

Installer

Flask

Browser

Logging

ConfigService

---

v0.2

Setup Wizard

Hostname

WLAN

Administrator

URL

---

v0.3

Dashboard

Browsersteuerung

Systeminformationen

---

v0.4

Watchdog

Browser Monitor

Netzwerk Monitor

---

v0.5

Backup

Restore

USB Import

---

v0.6

Update

Rollback

Versionierung

---

v0.7

REST API

Remote Verwaltung

---

v0.8

Mehrsprachigkeit

Themes

Optimierungen

---

v0.9

Beta

Fehlerbehebung

Tests

Dokumentation

---

v1.0

Release

---

# Projektziel

PiKiosk Pro soll eine professionelle Raspberry-Pi-Kiosk-Lösung werden.

Das System muss robust, wartbar, modular und langfristig erweiterbar sein.

Es soll ohne Linux-Kenntnisse bedienbar sein und nach dem ersten Einschalten selbstständig durch einen Einrichtungsassistenten konfiguriert werden.

Nach der Einrichtung startet der Raspberry Pi automatisch in den Kioskmodus und zeigt ausschließlich die konfigurierte Webseite an.

Alle administrativen Aufgaben müssen über eine moderne Weboberfläche möglich sein.

Die Software soll produktionsreif, quelloffen und beliebig oft auf Raspberry Pi 4 installiert werden können.

# Ende des Dokuments
