# PiKiosk Center – Zentrale Verwaltung

PiKiosk Center verwaltet beliebig viele PiKiosk-Geräte von einem
Rechner aus: Zustand aller Geräte auf einen Blick, Aktionen für
einzelne Geräte oder für eine ganze Auswahl.

Die Zentrale ist eine eigenständige Anwendung. Sie spricht die
Geräte ausschließlich über deren [REST API](API.md) an – **auf den
Geräten ist keinerlei Änderung nötig**. Jedes Gerät bleibt autark:
Fällt die Zentrale aus, läuft der Kiosk unverändert weiter.

## Installation

Die Zentrale läuft auf einem beliebigen Rechner im Netzwerk
(Debian, Ubuntu, Raspberry Pi OS) – auch auf einem der Kiosk-Pis,
sinnvoller ist aber ein eigener Rechner oder Server.

```bash
git clone https://github.com/grumel/PiKiosk-Pro.git
cd PiKiosk-Pro
sudo ./install_center.sh
```

Danach ist die Zentrale erreichbar unter:

```
http://<adresse-der-zentrale>:8090/
```

Beim ersten Aufruf legen Sie das Administratorkonto der Zentrale an
(gilt nur für die Zentrale, nicht für die Geräte).

## Geräte aufnehmen

Reiter **Geräte** → Name, Adresse (Hostname oder IP), Port
(Standard 8080) sowie Administratorname und -passwort des Geräts
eintragen → „Aufnehmen".

Die Verbindung wird sofort geprüft: Ist das Gerät nicht erreichbar
oder stimmen die Zugangsdaten nicht, wird es **nicht** gespeichert.

**Zu den Zugangsdaten:** Die Zentrale meldet sich bei jedem Gerät
mit dessen Administratorkonto an und braucht das Passwort deshalb
dauerhaft. Es wird verschlüsselt gespeichert (Fernet); der Schlüssel
liegt in `config/center_key` mit Dateirechten 600. Das schützt die
Zugangsdaten in Datenbank und Sicherungen – wer Root-Zugriff auf die
Zentrale hat, kommt an Schlüssel und Daten heran. Die Zentrale
gehört daher auf einen vertrauenswürdigen Rechner.

## Übersicht

Der Reiter **Übersicht** fragt alle Geräte parallel ab (Aktualisierung
alle 15 Sekunden) und zeigt je Gerät:

| Spalte | Bedeutung |
| ------ | --------- |
| Zustand | **Online**, **Offline** (nicht erreichbar), **Anmeldefehler** (Zugangsdaten abgelehnt) oder **Deaktiviert** |
| Browserstatus | Läuft, Nicht gestartet, Fehler, Abgestürzt |
| Watchdog | Online, Warnung, Fehler, Offline, Deaktiviert, Inaktiv |
| Kiosk-URL | Aktuell angezeigte Webseite |
| Temperatur, Version | Aktuelle Werte des Geräts |

Die Zählerreihe oben nennt Gesamtzahl sowie Geräte je Zustand.
Ein nicht erreichbares Gerät bremst die übrigen nicht aus – jedes
Ergebnis steht für sich.

## Aktionen für mehrere Geräte

Geräte links anhaken (oder das Kästchen in der Kopfzeile für alle),
dann eine Aktion wählen:

- **Browser neu starten / starten / stoppen**
- **Neustart / Herunterfahren** (mit Bestätigung)
- **Kiosk-URL für die Auswahl setzen** – dieselbe Webseite auf allen
  ausgewählten Geräten in einem Schritt

Alle Aktionen laufen parallel. Nach der Ausführung listet die
Zentrale je Gerät auf, ob es geklappt hat; Fehler stehen im Klartext
beim jeweiligen Gerät.

## Geräte pflegen

Im Reiter **Geräte** lassen sich Name, Adresse, Port und Benutzer
ändern. Das Passwortfeld bleibt leer, wenn das gespeicherte Passwort
bestehen soll. Der Schalter **Aktiv** nimmt ein Gerät vorübergehend
aus der Abfrage (z. B. während eines Umbaus), ohne es zu entfernen.
„Verbindung testen" prüft ein Gerät sofort, „Entfernen" nimmt es aus
der Verwaltung – das Gerät selbst bleibt davon unberührt.

## Betrieb

```bash
sudo systemctl status pikiosk-center.service    # Status
sudo systemctl restart pikiosk-center.service   # Neu starten
```

Ereignisse stehen in `logs/center.log`: aufgenommene Geräte,
ausgeführte Aktionen und fehlgeschlagene Zugriffe.

## Grenzen und Ausblick

- Die Zentrale fragt die Geräte ab (Pull). Geräte mit wechselnder
  IP-Adresse sollten über einen festen Namen (`<hostname>.local`)
  oder eine feste Adresse eingebunden werden.
- Es gibt keine Verlaufsdaten und keine Benachrichtigungen; die
  Übersicht zeigt den aktuellen Zustand.
- Updates werden nicht über die Zentrale verteilt. Für Geräte ohne
  Internetzugang eignet sich die lokale Updatequelle (siehe
  [Administration.md](Administration.md)); ein Webserver im Netz
  versorgt beliebig viele Geräte.
