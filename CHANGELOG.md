# Changelog

Alle nennenswerten Änderungen an PiKiosk Pro werden in dieser Datei
dokumentiert. Das Format orientiert sich an
[Keep a Changelog](https://keepachangelog.com/de/1.1.0/), die
Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

## [1.8.1] - 2026-07-22

### Behoben

- **Fernsteuerung des Kioskbrowsers reaktiviert (betrifft die
  Ausstiegs-Tastenkombination und den Watchdog-Reload).** Chromium
  weist seit Version 111 Fernsteuerungsverbindungen (DevTools/CDP)
  ohne erlaubten Ursprung ab. Der Kioskbrowser wird jetzt mit
  `--remote-allow-origins=*` gestartet (der Debug-Port ist nur an
  127.0.0.1 gebunden, daher unbedenklich). Ohne diesen Schalter
  konnte die Tastenkombination aus 1.8.0 den Browser nicht auf das
  Dashboard umlenken.

## [1.8.0] - 2026-07-22

### Hinzugefügt

- **Tastenkombination, um aus dem Kiosk-Vollbild zu kommen.** Ein
  neuer Hintergrunddienst (`pikiosk-keymon`) liest die Tastatur
  direkt über `/dev/input` – dadurch unabhängig von X11 oder
  Wayland – und lenkt den Kioskbrowser bei der eingestellten
  Kombination (Standard **Strg+Alt+K**) auf das lokale Dashboard um,
  ohne den Browser neu zu starten. Von dort ist die gesamte
  Verwaltung erreichbar. Die Kombination ist in der
  Überwachungs-Kachel einstellbar (leer = aus); sie wirkt nach dem
  nächsten Geräteneustart. Der neue Dienst wird von
  `sudo ./install.sh` installiert.

## [1.7.0] - 2026-07-18

### Hinzugefügt

- **Direkter Weg von der Statusseite zum Dashboard.** Die
  öffentliche Statusseite (unter `/`, z. B.
  `https://<geraet>:8080/`) hat jetzt einen Knopf „Zum Dashboard" –
  oben in der Leiste und als große Schaltfläche unter den
  Statuswerten. Er führt zur Anmeldung und danach ins Dashboard
  (oder bei bestehender Anmeldung direkt hinein). Bisher gab es von
  der Statusseite keinen sichtbaren Weg in die Verwaltung.
- **Fast volle Festplatte ist jetzt ein Fehler statt einer Warnung.**
  Ab 95 % Belegung meldet der Watchdog „Fehler" (rotes Badge) mit
  der Festplatte als Auslöser – bisher blieb es bei einer gelben
  Warnung ab 90 %. Eine volle SD-Karte legt Sicherungen und Updates
  lahm und lässt den Watchdog seine Statusdatei nicht mehr schreiben
  (die Kachel steht dann auf „Inaktiv"); dieser Zustand darf nicht
  untergehen.

### Geändert

- **Watchdog gibt den Neustart nie dauerhaft auf**
  (`StartLimitIntervalSec=0`). Bisher stellte systemd nach mehreren
  schnellen Fehlversuchen – etwa bei einer beim Booten vorübergehend
  vollen Platte – den automatischen Neustart ein, und der Dienst
  blieb tot. Jetzt versucht er es weiter, bis er wieder läuft. Neue
  Unit-Datei wird von `sudo ./install.sh` installiert.

## [1.6.3] - 2026-07-18

### Hinzugefügt

- **Überwachungs-Kachel zeigt die Einzelprüfungen des Watchdogs.**
  Bisher war nur der Gesamtzustand („Warnung"/„Fehler") sichtbar –
  nicht die Ursache. Die Kachel listet jetzt die letzte Prüfung
  auf: Browser, Gateway, DNS, Internet, Kiosk-URL sowie Temperatur,
  Arbeitsspeicher und Festplatte mit Werten; die auslösende
  Prüfung ist am Warn-Badge direkt erkennbar.

## [1.6.2] - 2026-07-18

### Behoben

- **Watchdog meldete auf TLS-Installationen dauerhaft „Fehler".**
  Der Watchdog fragte den Health-Endpunkt der Hauptanwendung über
  `http://127.0.0.1:8080` ab – mit aktivem TLS läuft dort aber
  HTTPS, die Abfrage scheiterte, und der Watchdog stufte die
  Anwendung unabhängig von der eingestellten Verbindungsprüfung als
  offline ein. Der Health-Check nutzt jetzt (wie der
  Browser-Neustart) den lokalen HTTP-Listener auf 127.0.0.1:8081.
- **Gateway-Prüfung unter der gehärteten Watchdog-Unit.**
  `NoNewPrivileges` blockierte das setuid-/capability-basierte
  `ping`-Binary – die Gateway-Prüfung schlug damit immer fehl. Die
  Watchdog-Unit verzichtet jetzt auf `NoNewPrivileges` und
  `RestrictSUIDSGID` (im Unit-File begründet); die übrige Härtung
  bleibt bestehen. Neue Unit-Dateien werden von `sudo ./install.sh`
  installiert.

## [1.6.1] - 2026-07-18

### Behoben

- **Neuinstallation setzte das Gerät zurück.** `install.sh` und
  `install_center.sh` kopierten mit `rsync --delete` und entfernten
  dabei die Laufzeitdaten einer bestehenden Installation –
  Konfiguration, Benutzerdatenbank, Schlüssel, TLS-Zertifikate und
  Sicherungen. Nach jedem erneuten `sudo ./install.sh` landete das
  Gerät deshalb wieder im Einrichtungsassistenten. Diese Pfade sind
  jetzt vom Abgleich ausgenommen; eine Neuinstallation über eine
  bestehende Installation erhält alle Einstellungen.

## [1.6.0] - 2026-07-18

### Hinzugefügt

- **Versionierte REST-API:** Die API ist jetzt kanonisch unter
  `/api/v1` erreichbar; `/api` bleibt dauerhaft als Alias für
  Bestandsclients bestehen (identische v1-Endpunkte). Künftige
  Vertragsänderungen erscheinen als `/api/v2`, ohne v1 zu brechen.

### Behoben

- **Hostname-Prüfung blockiert nicht mehr.** Die mDNS-Abfrage, ob
  ein Hostname im Netz vergeben ist, lief bisher direkt im
  Webrequest und konnte ihn ohne mDNS-Antwort mehrere Sekunden
  anhalten. Sie läuft jetzt im HostnameService mit einem Zeitlimit
  von 1 Sekunde; ohne rechtzeitige Antwort gilt der Name als frei.

## [1.5.0] - 2026-07-18

### Hinzugefügt

- **Updates mit Integritätsprüfung.** Die CI veröffentlicht zu jedem
  Release eine SHA-256-Prüfsummendatei; das Gerät prüft
  heruntergeladene Update-Archive dagegen und verwirft sie bei
  Abweichung. Lokale Updatequellen benötigen jetzt ein
  `sha256`-Feld im Manifest (Pflicht – siehe Administration.md);
  ältere GitHub-Releases ohne Prüfsummendatei bleiben installierbar
  (nur HTTPS-geschützt, mit Warnung im Log).
- **Ende-zu-Ende-Rauchtests mit echtem Chromium** (Playwright):
  Einrichtungsassistent und Anmeldung werden im echten Browser
  durchgeklickt – genau die Fehlerklasse, die den
  Chromium-Fehler aus 1.3.1 unbemerkt ließ. Eigener CI-Job; lokal
  werden die Tests ohne installiertes Playwright übersprungen.
- **Sichtbare Fehlermeldungen in der gesamten Oberfläche.**
  Fehlgeschlagene Anfragen (Serverfehler, keine Verbindung) zeigen
  jetzt auch im Dashboard und in der Zentrale eine Meldung statt
  eines wirkungslosen Klicks (bisher nur im Assistenten).

### Geändert

- **JWT über PyJWT statt Eigenbau** – gleiche Tokens (HS256),
  aber gepflegte Bibliothek mit Sicherheitsprozess. API-Tokens
  werden jetzt mit einem eigenen Schlüssel signiert
  (`config/api_key`), getrennt vom Sitzungsschlüssel, und sind
  4 Stunden statt 24 Stunden gültig.
- **Reproduzierbare Installationen:** `requirements.lock` schreibt
  alle Abhängigkeitsversionen fest; Installer und update.sh
  verwenden die Datei automatisch.
- **systemd-Härtung:** Zentrale und Watchdog laufen jetzt mit
  NoNewPrivileges, PrivateTmp, ProtectSystem=strict und
  ProtectHome. Der Gerätedienst bleibt bewusst ungehärtet
  (X11-Zugriff für den Kioskbrowser, sudo für Neustart/Hostname) –
  im Unit-File dokumentiert.
- **CI verschärft:** Prüfschwelle für Testabdeckung gilt jetzt auch
  für die Zentrale (`--cov=center`), alle Linter prüfen den
  Center-Code mit, ShellCheck prüft die Shell-Skripte.
- Cache-Busting (`?v=<Version>`) jetzt auch in der Zentrale.

## [1.4.0] - 2026-07-18

### Hinzugefügt

- **TLS-Verschlüsselung (HTTPS) für Gerät und Zentrale.** Der
  Installer erzeugt ein selbstsigniertes Zertifikat unter
  `config/tls/`; sobald `cert.pem` und `key.pem` dort liegen, laufen
  Weboberfläche und REST-API über HTTPS (gleiche Ports wie bisher).
  Eigene Firmenzertifikate ersetzen einfach die beiden Dateien.
  Passwörter, Sitzungscookies und API-Tokens sind damit im Netzwerk
  nicht mehr mitlesbar. Der Kioskbrowser und der Watchdog nutzen
  einen zusätzlichen HTTP-Listener auf 127.0.0.1:8081 und bleiben
  frei von Zertifikatswarnungen; Sitzungscookies erhalten über
  HTTPS automatisch das Secure-Attribut. Die Zentrale erkennt je
  Gerät selbstständig, ob es HTTPS oder (ältere Installationen)
  HTTP spricht – gemischte Flotten funktionieren ohne Umstellung.
- **Schutz vor Passwort-Rateversuchen.** Nach 5 Fehlversuchen
  innerhalb von 15 Minuten wird die Quelle für 5 Minuten gesperrt –
  auf der Anmeldeseite von Gerät und Zentrale (verständliche
  Meldung mit Restzeit) und an der Token-Ausgabe der API
  (HTTP 429 mit Retry-After). Fehlversuche werden mit Quelle
  protokolliert; eine erfolgreiche Anmeldung setzt den Zähler
  zurück.

### Geändert

- **Produktionsreifer Webserver.** Gerät und Zentrale laufen jetzt
  auf dem Cheroot-WSGI-Server (reines Python, feste Thread-Zahl)
  statt auf dem Flask-Entwicklungsserver, der laut Flask nicht für
  den Dauerbetrieb vorgesehen ist.

## [1.3.2] - 2026-07-18

### Behoben

- **Anmeldung stabilisiert.** Nach Ablauf der 30-Minuten-Sitzung
  führte jede Aktion (auch die Anmeldung selbst, wenn die Seite
  länger offen stand) zu einem nackten 400-Fehler. Jetzt leitet die
  Anwendung sauber zur Anmeldeseite um und zeigt den Hinweis „Die
  Sitzung ist abgelaufen"; HTMX-Anfragen lösen dabei einen
  vollständigen Seitenwechsel aus (HX-Redirect), statt die
  Anmeldeseite in eine Kachel einzusetzen. Gilt für Gerät und
  Zentrale.
- **„Angemeldet bleiben" wirkt jetzt tatsächlich.** Der bisherige
  Sitzungsschutz „strong" von Flask-Login löschte bei jeder
  Abweichung der Sitzungskennung (z. B. nach Sitzungsablauf oder
  IP-Wechsel) auch das Anmelde-Cookie – der Administrator wurde
  immer wieder abgemeldet. Der Schutz steht jetzt auf „basic",
  damit das Anmelde-Cookie die Sitzung wie versprochen erneuert.

### Hinzugefügt

- Zentrale: Der Gerätename in der Flottenübersicht ist jetzt ein
  Link, der das Dashboard des jeweiligen Kiosks in einem neuen Tab
  öffnet.

## [1.3.1] - 2026-07-17

### Behoben

- **Einrichtungsassistent: „Prüfen" reagierte in Chromium nicht** (in
  Firefox funktionierte es). Ursache war ein möglicher nativer
  Formular-Absendevorgang: Chromium blockiert das Absenden von
  Passwortfeldern über HTTP, wodurch scheinbar nichts passierte. Die
  Schaltflächen der Wizard-Schritte lösen die Prüfung jetzt
  ausschließlich per HTMX aus (kein nativer Submit mehr); die
  Eingabetaste funktioniert weiterhin.
- **Getrennte Browser-Caches führten zu unterschiedlichem Verhalten.**
  Statische Dateien (CSS/JS) werden nun mit der Programmversion
  ausgeliefert (`?v=<Version>`), sodass nach jedem Update garantiert
  die aktuelle Fassung geladen wird und kein Browser eine veraltete
  JavaScript-Datei aus dem Zwischenspeicher verwendet.

### Hinzugefügt

- Schlägt eine Anfrage im Einrichtungsassistenten fehl (Serverfehler
  oder keine Verbindung), erscheint jetzt eine sichtbare Meldung
  statt eines wirkungslosen Klicks.

## [1.3.0] - 2026-07-17

### Behoben

- **WLAN-Verbindungen scheiterten mit „Not authorized to control
  networking".** NetworkManager verlangt für Verbindungsänderungen
  eine polkit-Bestätigung, die ein systemd-Dienst mangels Sitzung
  nicht beantworten kann; nur der Scan funktionierte. install.sh
  installiert jetzt eine polkit-Regel, die ausschließlich dem
  Kioskbenutzer genau die benötigten NetworkManager-Aktionen
  erlaubt (services/pikiosk-networkmanager.rules). Bestehende
  Installationen: siehe docs/Troubleshooting.md
- Fehlende Berechtigungen werden jetzt als verständliche Meldung
  angezeigt statt als nmcli-Fehlertext

### Hinzugefügt

- Standard-WLAN: Ein gespeichertes Netzwerk lässt sich als Standard
  hinterlegen und per Knopfdruck verbinden; andere Netzwerke bleiben
  sicht- und verbindbar. Gespeichert wird nur der Name – das
  Passwort bleibt bei NetworkManager
- Passwortfelder haben ein Auge zum Ein- und Ausblenden der
  Eingabe (Geräte-Oberfläche, Setup-Wizard und Zentrale)
- API: `wifi_preferred_ssid` über `PUT /api/settings` setzbar

### Geändert

- Die Zentrale trägt dieselbe Versionsnummer wie die Anwendung

## [1.2.0] - 2026-07-17

Zentrale Verwaltung: Mit PiKiosk Center lassen sich beliebig viele
Geräte von einem Rechner aus überwachen und steuern.

### Hinzugefügt

- PiKiosk Center als eigenständige Anwendung (Port 8090) mit
  eigenem Administratorkonto, Ersteinrichtung beim ersten Aufruf,
  Anmeldung, CSRF-Schutz und Session-Timeout
- Flottenübersicht: alle Geräte werden parallel abgefragt
  (Aktualisierung alle 15 Sekunden) und mit Zustand (Online,
  Offline, Anmeldefehler, Deaktiviert), Browserstatus, Watchdog,
  Kiosk-URL, Temperatur und Version angezeigt
- Massenaktionen für eine Auswahl von Geräten: Browser neu starten,
  starten, stoppen, Neustart, Herunterfahren sowie Kiosk-URL für
  alle ausgewählten Geräte setzen; Ergebnisse je Gerät im Klartext
- Geräteverwaltung: aufnehmen (mit sofortiger Verbindungsprüfung),
  ändern, Verbindung testen, deaktivieren und entfernen
- Gerätezugangsdaten werden verschlüsselt gespeichert (Fernet,
  Schlüsseldatei mit Rechten 600); Tokens werden je Gerät bis kurz
  vor Ablauf zwischengespeichert
- install_center.sh und pikiosk-center.service für die Installation
  der Zentrale auf einem beliebigen Rechner im Netzwerk
- Dokumentation der Zentrale (docs/Center.md)

Die Geräte selbst bleiben unverändert: Die Zentrale nutzt
ausschließlich die vorhandene REST API, jedes Gerät läuft autark
weiter, auch wenn die Zentrale ausfällt.

## [1.1.0] - 2026-07-17

Offline-Betrieb: PiKiosk Pro laesst sich jetzt vollstaendig ohne
Internetzugang betreiben – mit lokaler Kiosk-Webseite und lokaler
Updatequelle.

### Hinzugefügt

- Konfigurierbare Updatequelle: GitHub (Internet), lokale Quelle
  oder abgeschaltet. Die lokale Quelle ist ein beliebiger Webserver
  im Netzwerk, der `manifest.json` (version, archive, notes) und das
  Paket ausliefert; Prüfung, automatische Sicherung und Rollback
  sind identisch zum GitHub-Weg
- Konfigurierbare Verbindungsprüfung (`connectivity_check`):
  Internet, Kiosk-URL, Gateway oder keine Prüfung. Ein Kiosk ohne
  Internetzugang gilt damit nicht mehr dauerhaft als „Offline"
- Neue Dashboard-Kachel „Überwachung": Watchdog ein-/ausschalten
  und Verbindungsprüfung wählen
- Update-Kachel mit Auswahl der Updatequelle und Update-URL
- Automatische Migration der Konfiguration: nach einem Update
  fehlende Schlüssel werden aus den Standardwerten ergänzt,
  vorhandene Werte bleiben unverändert
- API: `update_source`, `update_url` und `connectivity_check` über
  `PUT /api/settings` setzbar; `GET /api/update` nennt die Quelle

### Behoben

- Beschädigte Sicherungen und Update-Pakete führten zu einem
  unbehandelten zlib-Fehler statt einer verständlichen Meldung

## [1.0.0] - 2026-07-16

Erstes stabiles Release. PiKiosk Pro verwandelt einen Raspberry
Pi 4 in ein wartungsarmes Kiosksystem: Nach `sudo ./install.sh`
und einem Neustart führt der Setup-Wizard durch Hostname, WLAN,
Administratorkonto und Kiosk-URL – danach startet Chromium
automatisch im Kioskmodus. Die komplette Verwaltung läuft über
das Dashboard, die Fernverwaltung über die REST API.

### Funktionsumfang

- Setup-Wizard mit Sofortprüfung aller Eingaben (v0.2)
- Dashboard mit Login, Systeminformationen und Kacheln für
  Browser, URL, Hostname, WLAN, System, Logs (v0.3)
- Watchdog als eigener systemd-Dienst mit Browser-Neustart,
  Netzwerk- und Systemüberwachung (v0.4)
- Sicherung/Wiederherstellung als ZIP inkl. USB-Import (v0.5)
- Update-System mit GitHub-Releases, Paket-Upload und Rollback (v0.6)
- REST API mit JWT für die Remote-Verwaltung (v0.7)
- Mehrsprachigkeit (de/en) und Themes inkl. Automatik (v0.8)
- Beta-Härtung: 95 % Testabdeckung, vollständige Dokumentation (v0.9)

### Behoben

- SQLite-Verbindungen der Benutzerdatenbank wurden nie geschlossen
  (Ressourcenleck); sie werden jetzt nach jeder Transaktion sicher
  geschlossen

### Hinzugefügt

- GitHub-Actions-CI: Black, isort, ruff, mypy und pytest
  (mit Mindestabdeckung 90 %) bei jedem Push; bei Versions-Tags
  wird automatisch ein Release-Archiv gebaut und veröffentlicht
- Abnahme-Checkliste für den Gerätetest in docs/Installation.md

## [0.9.0] - 2026-07-16

### Behoben

- Setup-Wizard: Das Administratorkonto wird jetzt vor dem Abschluss
  der Einrichtung angelegt. Zuvor konnte ein Fehler bei der
  Kontoanlage das System in einen Zustand ohne Wizard und ohne
  Anmeldung bringen.
- install.sh kopiert das Git-Repository mit, damit update.sh auf
  installierten Systemen funktioniert.

### Geändert (Beta-Härtung)

- Testabdeckung auf 95 % erhöht (396 Tests); Service-Schicht,
  Controller-Schicht und Validatoren liegen über 90 %
- Echte Netzwerkpfade werden gegen lokale Testserver geprüft
  (GitHub-Abfrage, Update-Download, Watchdog-Endpunkte,
  DevTools-WebSocket-Reload)
- Dokumentation vervollständigt: Entwicklerhandbuch
  (docs/DeveloperGuide.md), FAQ (docs/FAQ.md) und
  Troubleshooting (docs/Troubleshooting.md)

## [0.8.0] - 2026-07-16

### Hinzugefügt

- Dashboard-Kachel „Darstellung": Sprache (Deutsch/Englisch) und
  Theme (Dunkel/Hell/Automatisch) direkt über die Oberfläche
  umschaltbar; die Seite lädt nach dem Speichern automatisch neu
- Theme „Automatisch" folgt jetzt der Systemeinstellung
  (prefers-color-scheme) und reagiert auf Änderungen zur Laufzeit
- Sprachwahl auf der Willkommensseite des Setup-Wizards; die
  Zusammenfassung zeigt die gewählte Sprache
- Das lang-Attribut der Seiten folgt der konfigurierten Sprache

### Geändert (Optimierungen)

- Konfiguration wird je Änderungsstand zwischengespeichert
  (mtime-basiert) statt bei jeder Anfrage neu gelesen und validiert
- Sprachdateien werden je Änderungsstand zwischengespeichert

## [0.7.0] - 2026-07-16

### Hinzugefügt

- REST API unter /api mit JWT-Authentifizierung (HS256, mit
  Bordmitteln implementiert, Tokens 24 Stunden gültig)
- Endpunkte: /api/token, /api/status, /api/version, /api/browser,
  /api/settings, /api/network (inkl. Profil-Löschung per DELETE),
  /api/system, /api/update, /api/backup, /api/logs — alle
  authentifiziert, alle Antworten JSON
- Einheitliche JSON-Fehlerbehandlung für alle /api-Pfade
  (401 unauthorized, 400 mit Fehlermeldung, 404 not_found)
- Grundlage für die Remote-Verwaltung mehrerer Geräte; die lokale
  Weboberfläche bleibt unabhängig
- API-Dokumentation (docs/API.md)

### Behoben

- MAC-Adresse über nmcli wurde abgeschnitten, wenn nmcli die
  Doppelpunkte nicht maskiert; der Feldparser setzt Werte jetzt
  korrekt wieder zusammen

## [0.6.0] - 2026-07-16

### Hinzugefügt

- UpdateService: Aktualisierung über lokale Update-Pakete (ZIP oder
  tar.gz) und direkt aus GitHub-Releases
- Automatische Sicherung vor jedem Update über den BackupService
- Rollback-Stand des Programmcodes vor jedem Update; Rollback stellt
  den vorherigen Stand vollständig wieder her (inklusive Entfernen
  neu hinzugefügter Dateien)
- GitHub-Prüfung über die Releases-API mit Versionsvergleich
  (Semantic Versioning); Statusanzeige verfügbar/aktuell/kein Release
- Dashboard-Kachel „Aktualisierung": Nach Updates suchen, aus GitHub
  installieren, Paket hochladen und Rollback mit Bestätigungsabfrage
- Schutz beim Update: Konfiguration, Benutzerdatenbank, Logs und das
  Sicherungsverzeichnis bleiben unangetastet; Pfad-Ausbrüche und
  überdimensionierte Archive werden abgewiesen
- Versionsvergleich `is_newer` in app/utils/version.py

## [0.5.0] - 2026-07-16

### Hinzugefügt

- BackupService: Sicherung als ZIP (PiKiosk_Backup_YYYYMMDD_HHMM.zip)
  mit Konfiguration, Benutzerdatenbank, optional Logdateien und
  Manifest (Version, Zeitpunkt, Hostname); Cache und temporäre
  Dateien werden nicht gesichert
- RestoreService: Wiederherstellung mit vollständiger Prüfung
  (ZIP-Integrität, Manifest, Versionskompatibilität, Konfigurations-
  und Benutzerdatenbank-Validierung); ungültige Sicherungen werden
  niemals angewendet, danach wird ein Neustart empfohlen
- USB-Import: eingehängte USB-Medien (/media, /run/media) werden
  automatisch nach PiKiosk_Backup*.zip durchsucht, Import direkt
  aus der Sicherungs-Kachel
- Dashboard-Kachel „Sicherung": Erstellen (optional mit Logs),
  Auflisten, Herunterladen, Wiederherstellen und Hochladen von
  Sicherungen mit Bestätigungsabfrage
- Versionsverwaltung (app/utils/version.py): Semantic-Versioning-
  Parser und Kompatibilitätsprüfung für Sicherungen
- Upload-Größenlimit (50 MB) für die gesamte Anwendung

## [0.4.0] - 2026-07-16

### Hinzugefügt

- Watchdog als eigenständiger systemd-Dienst (pikiosk-watchdog.service),
  prüft alle 5 Sekunden Browser, Netzwerk und System
- Browser-Watchdog: startet einen abgestürzten Chromium automatisch neu,
  maximal 3 Neustarts innerhalb von 60 Sekunden, danach Fehlerstatus
  mit Administratorbenachrichtigung über das Log
- Netzwerk-Watchdog: Gateway (Ping), DNS, Internet und Kiosk-URL;
  alle Zustände werden in einer Statusdatei gespeichert
- System-Watchdog: Temperatur (Warnung 75 °C, kritisch 80 °C),
  RAM (Warnung 85 %), Festplatte (Warnung 90 %) mit Logeinträgen
  bei Zustandswechseln
- Dashboard zeigt den Watchdog-Gesamtzustand (Online, Warnung, Fehler,
  Offline, Deaktiviert, Inaktiv) und das Watchdoglog
- Interner tokengeschützter Endpunkt /internal/browser/restart für
  den Browser-Neustart durch den Watchdogprozess
- Gemeinsame Helfer: atomares JSON-Schreiben (app/utils/filesystem.py),
  CPU-Temperatur, Internet-/Gateway-/Ping-Prüfungen

### Geändert

- install.sh und update.sh verwalten jetzt beide systemd-Dienste

## [0.3.0] - 2026-07-16

### Hinzugefügt

- Anmeldung mit Flask-Login: bcrypt-Passwortprüfung, Session-Timeout
  30 Minuten, optional „Angemeldet bleiben" (7 Tage), Schutz vor
  offenen Weiterleitungen
- Dashboard mit automatisch aktualisierten Systeminformationen
  (Hostname, Gerätemodell, IP, MAC, CPU, RAM, Temperatur, Festplatte,
  Browserstatus, Internetstatus, URL, Version, letzter Neustart,
  Systemlaufzeit) über den neuen DashboardService (psutil)
- Dashboard-Kacheln: Browser (Start/Stopp/Neustart), Kiosk-URL
  (Testen/Speichern mit automatischem Browserneustart), Hostname,
  WLAN (Status/Scan/Verbinden/Trennen), System
  (Neustart/Herunterfahren mit Bestätigung), Logs (Ansicht der
  letzten 200 Zeilen und Download)
- SystemService: kontrollierter Neustart und Shutdown über systemd,
  der Browser wird vorher sauber beendet
- Globaler CSRF-Schutz für alle Schreibanfragen der Anwendung
- install.sh: sudo-Regeln für systemctl reboot und poweroff
- Dokumentation: Administrationsanleitung (docs/Administration.md)

## [0.2.0] - 2026-07-15

### Hinzugefügt

- Setup-Wizard für die Ersteinrichtung (6 Seiten: Willkommen, Hostname,
  WLAN, Administrator, Kiosk-URL, Zusammenfassung) auf Basis von HTMX
- Erststart-Sperre: bis zum Abschluss der Einrichtung leiten alle
  Anfragen auf den Wizard um, danach ist der Wizard gesperrt
- NetworkService: WLAN-Verwaltung über NetworkManager/nmcli
  (Scan mit Sortierung nach Signalstärke, Verbinden mit verständlichen
  Fehlermeldungen, IP/Gateway/DNS/MAC, gespeicherte Profile)
- HostnameService mit Root-Helferskript `scripts/hostname_apply.py`
  (aktualisiert /etc/hostname, /etc/hosts und ruft hostnamectl auf)
- AuthService und UserModel: Administratorkonto in SQLite,
  Passwörter ausschließlich als bcrypt-Hash
- PasswordValidator (mindestens 12 Zeichen, Groß-/Kleinbuchstaben,
  Zahl, Sonderzeichen) mit Einzelregel-Anzeige im Wizard
- URL-Prüfung mit 5 Sekunden Timeout; gültig bei HTTP 200, 301, 302
- CSRF-Schutz und HttpOnly/SameSite-Session-Cookies
- install.sh installiert eine sudo-Regel für die Hostnameänderung

### Behoben

- nmcli-Ausgaben werden mit neutraler Locale (LC_ALL=C) gelesen,
  damit die Auswertung nicht von der Systemsprache abhängt
- URL-Prüfung sendet einen browserüblichen User-Agent, damit
  Webseiten mit Bot-Filter nicht fälschlich als ungültig gelten

## [0.1.0] - 2026-07-15

### Hinzugefügt

- Projektstruktur mit Service-, Controller- und Utility-Schichten
- Flask-Webserver mit Statusseite, Fehlerseiten und Health-Endpunkt
- ConfigService: JSON-Konfiguration mit Validierung, atomarem Speichern,
  Zurücksetzen, Sicherung und Wiederherstellung
- BrowserService: Chromium-Steuerung über Python (Start, Stopp, Neustart,
  Reload per Chrome-DevTools-Protokoll, Cache leeren, Statusüberwachung,
  Vollbildprüfung)
- KioskLogger: modulbezogenes Logging mit Rotation (10 Dateien à 10 MB)
  und Konsolenausgabe für Fehler
- Validatoren für Hostname, URL und Gesamtkonfiguration
- Sprachdateien Deutsch und Englisch, alle Oberflächentexte aus JSON
- Bootstrap 5 lokal eingebunden (offlinefähig), Dark/Light-Theme
- install.sh: Installation von Systempaketen, Python-Umgebung,
  systemd-Dienst und Autologin auf Raspberry Pi OS
- update.sh: Aktualisierung über Git mit Neustart des Dienstes
- Unit- und Integrationstests für alle Kernmodule
