# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Versionsverwaltung.

Hilfsfunktionen fuer Semantic Versioning: Versionsnummern parsen
und die Kompatibilitaet von Sicherungen mit der laufenden
Anwendung pruefen.
"""

import re

from app.constants import APP_VERSION
from app.exceptions import ValidationError

VERSION_PATTERN: re.Pattern[str] = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def parse_version(text: str) -> tuple[int, int, int]:
    """Zerlegt eine Versionsnummer nach Semantic Versioning.

    Args:
        text:
            Versionsnummer im Format MAJOR.MINOR.PATCH.

    Returns:
        Tupel aus Major-, Minor- und Patch-Version.

    Raises:
        ValidationError
    """
    match = VERSION_PATTERN.match(text.strip() if isinstance(text, str) else "")
    if match is None:
        raise ValidationError(f"Ungueltige Versionsnummer: {text!r}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def is_backup_compatible(
    backup_version: str, current_version: str = APP_VERSION
) -> bool:
    """Prueft, ob eine Sicherung zur laufenden Version passt.

    Eine Sicherung ist kompatibel, wenn die Major-Version
    uebereinstimmt und die Sicherung nicht von einer neueren
    Version stammt.

    Args:
        backup_version:
            Version, mit der die Sicherung erstellt wurde.

        current_version:
            Version der laufenden Anwendung.

    Returns:
        True, wenn die Sicherung wiederhergestellt werden darf.

    Raises:
        ValidationError
    """
    backup = parse_version(backup_version)
    current = parse_version(current_version)
    return backup[0] == current[0] and backup[1:] <= current[1:]
