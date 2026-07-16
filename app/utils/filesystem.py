# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Dateisystem-Helfer.

Zentrale Funktionen fuer das Lesen und atomare Schreiben von
JSON-Dateien. Alle Module verwenden ausschliesslich diese
Funktionen, damit Schreibvorgaenge niemals halbfertige Dateien
hinterlassen.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from app.exceptions import ConfigurationError


def read_json_file(path: Path) -> dict[str, Any]:
    """Liest eine JSON-Datei mit einem Objekt auf oberster Ebene.

    Args:
        path:
            Pfad der JSON-Datei.

    Returns:
        Inhalt der Datei als Woerterbuch.

    Raises:
        ConfigurationError
    """
    try:
        with path.open("r", encoding="utf-8") as handle:
            content = json.load(handle)
    except FileNotFoundError as error:
        raise ConfigurationError(f"Datei nicht gefunden: {path}") from error
    except json.JSONDecodeError as error:
        raise ConfigurationError(f"Ungueltiges JSON in {path}: {error}") from error
    except OSError as error:
        raise ConfigurationError(
            f"Datei konnte nicht gelesen werden: {path}: {error}"
        ) from error
    if not isinstance(content, dict):
        raise ConfigurationError(f"Die Datei {path} enthaelt kein JSON-Objekt.")
    return content


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    """Schreibt ein Woerterbuch atomar als JSON-Datei.

    Args:
        path:
            Zielpfad.

        data:
            Zu schreibende Daten.

    Raises:
        ConfigurationError
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor, temp_name = tempfile.mkstemp(
            dir=path.parent, prefix=path.name, suffix=".tmp"
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=4)
            handle.write("\n")
        os.replace(temp_name, path)
    except OSError as error:
        raise ConfigurationError(
            f"Datei konnte nicht geschrieben werden: {path}: {error}"
        ) from error
