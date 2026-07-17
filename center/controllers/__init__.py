# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Center - Controller-Schicht.

Gemeinsame Helfer der Controller: Oberflaechentexte und das
CSRF-Token der Sitzung.
"""

import secrets

from flask import session

from app.utils.helpers import load_language

CENTER_LANGUAGE: str = "de"
SESSION_CSRF_KEY: str = "csrf_token"


def center_texts() -> dict[str, str]:
    """Laedt die Oberflaechentexte der Zentrale.

    Returns:
        Woerterbuch mit allen Oberflaechentexten.
    """
    return load_language(CENTER_LANGUAGE)


def ensure_csrf_token() -> str:
    """Liefert das CSRF-Token der Sitzung und erzeugt es bei Bedarf.

    Returns:
        Das CSRF-Token.
    """
    if SESSION_CSRF_KEY not in session:
        session[SESSION_CSRF_KEY] = secrets.token_hex(16)
    token: str = session[SESSION_CSRF_KEY]
    return token
