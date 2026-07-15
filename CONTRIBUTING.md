# Beiträge zu PiKiosk Pro

Vielen Dank für dein Interesse an PiKiosk Pro. Damit das Projekt
langfristig wartbar bleibt, gelten die folgenden Regeln.

## Git-Workflow

- `main` enthält ausschließlich Releases, niemals direkte Commits.
- `develop` ist der Integrationszweig.
- Feature-Branches: `feature/<name>`, Fehlerbehebungen: `bugfix/<name>`,
  Releases: `release/<version>`, Hotfixes: `hotfix/<version>`.
- Jede größere Änderung erfolgt über einen Pull Request mit Beschreibung,
  Änderungen, Tests, Screenshots (bei GUI) und Risiken.

## Commits

Commit-Nachrichten folgen Conventional Commits, jeder Commit enthält
genau eine abgeschlossene Änderung:

```
feat(browser): Browser-Watchdog implementiert
fix(network): WLAN-Scan korrigiert
docs(readme): Installationsanleitung ergänzt
```

## Codequalität

- Python: PEP 8, Black-kompatibel, isort, ruff, mypy
- Alle Funktionen besitzen Type Hints
- Alle öffentlichen Klassen und Funktionen besitzen Google-Style-Docstrings
- Logging statt `print()`, eigene Exception-Klassen statt nackter Exceptions
- Keine Platzhalter, keine TODO-Kommentare, keine Dummyfunktionen
- Keine Datei über 500 Zeilen, keine Funktion über 60 Zeilen

## Tests

- Jede Funktion wird durch Tests abgedeckt (Unit, Integration, System)
- Ziel: mindestens 90 % Testabdeckung in Service- und Controller-Schicht
- Vor jedem Pull Request: `pytest` muss fehlerfrei durchlaufen

## Definition of Done

Eine Änderung gilt erst als fertig, wenn Code, Tests, Dokumentation,
Logging, Fehlerbehandlung und Type Hints vorhanden sind, das Code-Review
bestanden wurde und keine TODOs, Warnungen oder bekannten Fehler existieren.
