# Entwicklerhandbuch

Dieses Handbuch beschreibt Aufbau, Entwicklungsumgebung und
Arbeitsweise für Beiträge zu PiKiosk Pro.

## Entwicklungsumgebung

```bash
git clone https://github.com/grumel/PiKiosk-Pro.git
cd PiKiosk-Pro
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Anwendung starten (ohne Kioskbrowser):

```bash
python -m app.app --no-browser --host 127.0.0.1
```

Watchdog separat starten:

```bash
python -m app.watchdog
```

## Projektaufbau

| Verzeichnis        | Inhalt                                        |
| ------------------ | --------------------------------------------- |
| `app/`             | Anwendungskern (Factory, Konstanten, Logger)  |
| `app/controllers/` | HTMX-Controller der Weboberfläche             |
| `app/services/`    | Fachlogik (Browser, Netzwerk, Backup, …)      |
| `app/models/`      | Datenbankzugriff (SQLite)                     |
| `app/api/`         | REST API (JWT)                                |
| `app/utils/`       | Validatoren, Dateisystem, Netzwerk, Krypto    |
| `config/`          | defaults.json, Sprachdateien, Laufzeitdaten   |
| `templates/`       | Jinja2-Templates (Bootstrap 5, HTMX)          |
| `services/`        | systemd-Units                                 |
| `scripts/`         | Root-Helferskripte                            |
| `tests/`           | Unit-, Integrations- und Systemtests          |

Details zur Schichtung stehen in [Architecture.md](Architecture.md).

## Grundregeln

- **Dependency Injection**: Alle Dienste werden in der
  `ServiceRegistry` (app/extensions.py) verdrahtet; Module greifen
  nie direkt aufeinander zu. Keine globalen Variablen.
- **Konfiguration** ausschließlich über den `ConfigService`;
  Shell-Skripte verändern niemals Konfigurationsdateien.
- **Texte** ausschließlich in den JSON-Sprachdateien, nie im
  Python-Code.
- **Fehler**: eigene Exception-Klassen (app/exceptions.py), keine
  nackten `except:`; Benutzer sehen verständliche Meldungen, nie
  Tracebacks.
- **Logging** statt `print()`; jedes Modul hat einen eigenen
  `KioskLogger` mit Rotation (10 Dateien à 10 MB).
- **Grenzen**: Dateien ≤ 500 Zeilen, Funktionen ≤ 60 Zeilen,
  Klassen ≤ 400 Zeilen (Ausnahmen: Templates, Sprachdateien).
- Jede Funktion hat Type Hints und einen Google-Style-Docstring.

## Qualitätswerkzeuge

Vor jedem Commit müssen fehlerfrei durchlaufen:

```bash
black app scripts tests
isort --profile black app scripts tests
ruff check app scripts tests
mypy --python-version 3.13 --ignore-missing-imports app scripts
pytest
```

Testabdeckung messen (Ziel: ≥ 90 % in Service- und
Controller-Schicht sowie Validatoren):

```bash
pytest --cov=app --cov-report=term-missing
```

## Teststrategie

- **Unit-Tests** (`tests/unit/`): jede Service-Klasse isoliert;
  externe Prozesse (nmcli, systemctl, Chromium) werden durch
  Fakes/Monkeypatches ersetzt, HTTP-Zugriffe laufen gegen lokale
  Testserver (siehe `test_routed_http.py`, `test_devtools_ws.py`).
- **Integrationstests** (`tests/integration/`): Flask-Testclient
  gegen die echte Anwendung mit temporären Datenpfaden (Fixture
  `registry` in `tests/conftest.py`).
- **Systemtests** (`tests/system/`): manuelle Abnahme auf echter
  Hardware (siehe Troubleshooting/Installation).

## Git-Workflow und Releases

Branches, Commit-Konventionen und die Definition of Done stehen in
[CONTRIBUTING.md](../CONTRIBUTING.md). Releases: Version in
`app/constants.py` erhöhen, CHANGELOG pflegen, `develop` → `main`
mergen, Tag `vX.Y.Z` setzen. Die Versionsnummer in
`app/constants.py` ist die einzige Quelle der Wahrheit; das
Update-System liest sie aus `app/constants.py` des Pakets.

## REST API erweitern

Neue Endpunkte kommen als Modul unter `app/api/` und registrieren
sich am gemeinsamen `api_blueprint`. Jede View trägt die
Dekoratoren `@api_auth_required` (JWT) und `@api_call`
(Fehlerübersetzung). Dokumentation in [API.md](API.md) ergänzen.
