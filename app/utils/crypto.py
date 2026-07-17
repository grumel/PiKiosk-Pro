# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Kryptografie-Helfer.

Implementiert JSON Web Tokens (JWT, HS256) fuer die REST API mit
Bordmitteln der Standardbibliothek. Signaturen werden zeitkonstant
verglichen, abgelaufene oder manipulierte Tokens werden abgelehnt.

Zusaetzlich wird die symmetrische Verschluesselung von Geheimnissen
(Fernet) bereitgestellt. Sie schuetzt gespeicherte Zugangsdaten vor
dem Auslesen aus Datenbank oder Sicherung; der Schluessel liegt in
einer eigenen Datei mit Rechten 600.
"""

import base64
import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.exceptions import AuthenticationError, ConfigurationError

JWT_HEADER: dict[str, str] = {"alg": "HS256", "typ": "JWT"}


def _b64url_encode(data: bytes) -> str:
    """Kodiert Bytes als Base64-URL ohne Auffuellzeichen.

    Args:
        data:
            Zu kodierende Bytes.

    Returns:
        Die Base64-URL-Zeichenkette.
    """
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    """Dekodiert eine Base64-URL-Zeichenkette.

    Args:
        text:
            Zu dekodierende Zeichenkette.

    Returns:
        Die dekodierten Bytes.

    Raises:
        AuthenticationError
    """
    padding = "=" * (-len(text) % 4)
    try:
        return base64.urlsafe_b64decode(text + padding)
    except (ValueError, UnicodeEncodeError) as error:
        raise AuthenticationError(f"Ungueltiges Token: {error}") from error


def _sign(message: bytes, secret: str) -> bytes:
    """Signiert eine Nachricht mit HMAC-SHA256.

    Args:
        message:
            Zu signierende Bytes.

        secret:
            Geheimer Schluessel.

    Returns:
        Die Signatur.
    """
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()


def create_jwt(claims: dict[str, Any], secret: str, expires_in: int) -> str:
    """Erzeugt ein signiertes JWT.

    Args:
        claims:
            Nutzdaten des Tokens.

        secret:
            Geheimer Schluessel.

        expires_in:
            Gueltigkeitsdauer in Sekunden.

    Returns:
        Das signierte Token.
    """
    now = int(time.time())
    payload = dict(claims)
    payload["iat"] = now
    payload["exp"] = now + int(expires_in)
    header_part = _b64url_encode(
        json.dumps(JWT_HEADER, separators=(",", ":")).encode("utf-8")
    )
    payload_part = _b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    message = f"{header_part}.{payload_part}".encode("ascii")
    signature_part = _b64url_encode(_sign(message, secret))
    return f"{header_part}.{payload_part}.{signature_part}"


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
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthenticationError("Ungueltiges Token: falsches Format.")
    header_part, payload_part, signature_part = parts
    message = f"{header_part}.{payload_part}".encode("ascii")
    expected = _sign(message, secret)
    if not hmac.compare_digest(expected, _b64url_decode(signature_part)):
        raise AuthenticationError("Ungueltiges Token: Signatur falsch.")
    header = _decode_json(header_part)
    if header.get("alg") != JWT_HEADER["alg"]:
        raise AuthenticationError("Ungueltiges Token: Algorithmus unzulaessig.")
    payload = _decode_json(payload_part)
    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or expires_at < int(time.time()):
        raise AuthenticationError("Das Token ist abgelaufen.")
    return payload


def _decode_json(part: str) -> dict[str, Any]:
    """Dekodiert einen Base64-URL-JSON-Abschnitt eines Tokens.

    Args:
        part:
            Base64-URL-kodierter JSON-Abschnitt.

    Returns:
        Der dekodierte JSON-Inhalt.

    Raises:
        AuthenticationError
    """
    try:
        content = json.loads(_b64url_decode(part).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as error:
        raise AuthenticationError(f"Ungueltiges Token: {error}") from error
    if not isinstance(content, dict):
        raise AuthenticationError("Ungueltiges Token: kein JSON-Objekt.")
    return content


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
