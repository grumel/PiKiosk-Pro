# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Kryptografie-Helfer.

Erzeugt und prueft JSON Web Tokens (JWT, HS256) fuer die REST API
ueber die PyJWT-Bibliothek. Abgelaufene, manipulierte oder mit
fremdem Algorithmus signierte Tokens werden abgelehnt.

Zusaetzlich wird die symmetrische Verschluesselung von Geheimnissen
(Fernet) bereitgestellt. Sie schuetzt gespeicherte Zugangsdaten vor
dem Auslesen aus Datenbank oder Sicherung; der Schluessel liegt in
einer eigenen Datei mit Rechten 600.
"""

import time
from pathlib import Path
from typing import Any

import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.exceptions import AuthenticationError, ConfigurationError

JWT_ALGORITHM: str = "HS256"


def create_jwt(claims: dict[str, Any], secret: str, expires_in: int) -> str:
    """Erzeugt ein signiertes JWT mit Ablaufzeit.

    Args:
        claims:
            Nutzdaten des Tokens.

        secret:
            Geheimer Schluessel fuer die Signatur.

        expires_in:
            Gueltigkeitsdauer in Sekunden.

    Returns:
        Das signierte Token.
    """
    now = int(time.time())
    payload = dict(claims)
    payload["iat"] = now
    payload["exp"] = now + expires_in
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def verify_jwt(token: str, secret: str) -> dict[str, Any]:
    """Prueft ein JWT und liefert die Nutzdaten.

    Args:
        token:
            Zu pruefendes Token.

        secret:
            Geheimer Schluessel.

    Returns:
        Die Nutzdaten des Tokens.

    Raises:
        AuthenticationError
    """
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp"]},
        )
    except jwt.ExpiredSignatureError as error:
        raise AuthenticationError("Das Token ist abgelaufen.") from error
    except jwt.MissingRequiredClaimError as error:
        raise AuthenticationError("Ungueltiges Token: Ablaufzeit fehlt.") from error
    except jwt.InvalidTokenError as error:
        raise AuthenticationError(f"Ungueltiges Token: {error}") from error
    return dict(payload)


def load_or_create_fernet_key(key_file: Path) -> bytes:
    """Laedt den Verschluesselungsschluessel oder erzeugt ihn.

    Args:
        key_file:
            Pfad der Schluesseldatei.

    Returns:
        Der Fernet-Schluessel.

    Raises:
        ConfigurationError
    """
    try:
        if key_file.exists():
            key = key_file.read_bytes().strip()
            if key:
                return key
        key = Fernet.generate_key()
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(key + b"\n")
        key_file.chmod(0o600)
        return key
    except OSError as error:
        raise ConfigurationError(
            f"Schluesseldatei nicht verfuegbar: {key_file}: {error}"
        ) from error


def encrypt_secret(plaintext: str, key: bytes) -> str:
    """Verschluesselt ein Geheimnis symmetrisch.

    Args:
        plaintext:
            Zu verschluesselnder Text.

        key:
            Fernet-Schluessel.

    Returns:
        Das verschluesselte Geheimnis als Zeichenkette.

    Raises:
        ConfigurationError
    """
    try:
        return Fernet(key).encrypt(plaintext.encode("utf-8")).decode("ascii")
    except (ValueError, TypeError) as error:
        raise ConfigurationError(
            f"Das Geheimnis konnte nicht verschluesselt werden: {error}"
        ) from error


def decrypt_secret(token: str, key: bytes) -> str:
    """Entschluesselt ein zuvor verschluesseltes Geheimnis.

    Args:
        token:
            Verschluesseltes Geheimnis.

        key:
            Fernet-Schluessel.

    Returns:
        Der entschluesselte Text.

    Raises:
        AuthenticationError
    """
    try:
        return Fernet(key).decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError) as error:
        raise AuthenticationError(
            "Die gespeicherten Zugangsdaten konnten nicht entschluesselt "
            "werden. Wurde die Schluesseldatei ersetzt?"
        ) from error
