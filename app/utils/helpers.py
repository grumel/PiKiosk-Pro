# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Allgemeine Hilfsfunktionen.

Enthaelt die Sprachdatei-Verwaltung und kleine Systemhelfer.
Alle Oberflaechentexte werden ausschliesslich ueber die
JSON-Sprachdateien geladen, es stehen keine Texte im Python-Code.
"""

import json
import secrets
import socket
from collections import deque
from pathlib import Path

import psutil

from app.constants import (
    CONFIG_DIR,
    SECRET_KEY_FILE,
    SUPPORTED_LANGUAGES,
    THERMAL_ZONE_FILE,
)
from app.exceptions import ConfigurationError, ValidationError

DEVICE_MODEL_FILE: Path = Path("/proc/device-tree/model")


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


def device_model() -> str:
    """Liest die Geraetebezeichnung des Raspberry Pi.

    Returns:
        Modellbezeichnung oder leer, wenn nicht verfuegbar.
    """
    try:
        return DEVICE_MODEL_FILE.read_text(encoding="utf-8").strip("\x00\n ")
    except OSError:
        return ""


def cpu_temperature() -> float | None:
    """Liest die CPU-Temperatur des Geraets.

    Es werden zuerst die psutil-Sensoren gelesen, danach die
    Thermalzone des Kernels.

    Returns:
        Temperatur in Grad Celsius oder None, wenn kein Sensor
        verfuegbar ist.
    """
    try:
        sensors = psutil.sensors_temperatures()
    except AttributeError:
        sensors = {}
    for readings in sensors.values():
        for reading in readings:
            if reading.current:
                return round(float(reading.current), 1)
    try:
        raw = THERMAL_ZONE_FILE.read_text(encoding="ascii").strip()
        return round(int(raw) / 1000.0, 1)
    except (OSError, ValueError):
        return None


def read_log_tail(log_file: Path, max_lines: int) -> str:
    """Liest die letzten Zeilen einer Logdatei.

    Args:
        log_file:
            Pfad der Logdatei.

        max_lines:
            Maximale Anzahl der Zeilen.

    Returns:
        Die letzten Zeilen oder leer, wenn die Datei fehlt.
    """
    try:
        with log_file.open("r", encoding="utf-8", errors="replace") as handle:
            lines = deque(handle, maxlen=max_lines)
    except OSError:
        return ""
    return "".join(lines)


def load_or_create_secret_key(key_file: Path = SECRET_KEY_FILE) -> str:
    """Laedt den Flask-Sitzungsschluessel oder erzeugt ihn neu.

    Args:
        key_file:
            Pfad der Schluesseldatei.

    Returns:
        Der Sitzungsschluessel als Hexadezimal-Zeichenkette.

    Raises:
        ConfigurationError
    """
    try:
        if key_file.exists():
            key = key_file.read_text(encoding="utf-8").strip()
            if key:
                return key
        key = secrets.token_hex(32)
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text(key + "\n", encoding="utf-8")
        key_file.chmod(0o600)
        return key
    except OSError as error:
        raise ConfigurationError(
            f"Sitzungsschluessel konnte nicht erzeugt werden: {error}"
        ) from error
