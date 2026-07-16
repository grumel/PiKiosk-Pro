# Changelog

Alle nennenswerten Änderungen an PiKiosk Pro werden in dieser Datei
dokumentiert. Das Format orientiert sich an
[Keep a Changelog](https://keepachangelog.com/de/1.1.0/), die
Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

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
