# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Allgemeine Hilfsfunktionen.

Enthaelt die Sprachdatei-Verwaltung und kleine Systemhelfer.
Alle Oberflaechentexte werden ausschliesslich ueber die
JSON-Sprachdateien geladen, es stehen keine Texte im Python-Code.
"""

import json
import socket
from pathlib import Path

from app.constants import CONFIG_DIR, SUPPORTED_LANGUAGES
from app.exceptions import ConfigurationError, ValidationError


def load_language(language: str, config_dir: Path = CONFIG_DIR) -> dict[str, str]:
    """Laedt die Oberflaechentexte einer Sprache.

    Args:
        language:
            Sprachcode, zum Beispiel "de" oder "en".

        config_dir:
            Verzeichnis mit den Sprachdateien.

    Returns:
        Woerterbuch mit allen Oberflaechentexten.

    Raises:
        ValidationError
        ConfigurationError
    """
    if language not in SUPPORTED_LANGUAGES:
        raise ValidationError(
            "Unterstuetzte Sprachen: " + ", ".join(SUPPORTED_LANGUAGES)
        )
    language_file = config_dir / f"language_{language}.json"
    try:
        with language_file.open("r", encoding="utf-8") as handle:
            texts = json.load(handle)
    except FileNotFoundError as error:
        raise ConfigurationError(
            f"Sprachdatei nicht gefunden: {language_file}"
        ) from error
    except (json.JSONDecodeError, OSError) as error:
        raise ConfigurationError(
            f"Sprachdatei konnte nicht gelesen werden: {language_file}: {error}"
        ) from error
    if not isinstance(texts, dict):
        raise ConfigurationError(
            f"Die Sprachdatei {language_file} enthaelt kein JSON-Objekt."
        )
    return texts


def local_ip_address() -> str:
    """Ermittelt die lokale IPv4-Adresse des Geraets.

    Es wird keine echte Verbindung aufgebaut, die Zieladresse dient
    nur der Routenbestimmung.

    Returns:
        Die lokale IPv4-Adresse oder "0.0.0.0", falls keine
        Netzwerkverbindung besteht.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        address = str(probe.getsockname()[0])
    except OSError:
        address = "0.0.0.0"
    finally:
        probe.close()
    return address
