# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer die JWT-Implementierung."""

import base64
import json
import time

import pytest

from app.exceptions import AuthenticationError
from app.utils.crypto import create_jwt, verify_jwt

SECRET = "test-geheimnis"


class TestJwt:
    """Tests fuer Erzeugung und Pruefung von JWTs."""

    def test_roundtrip(self) -> None:
        token = create_jwt({"sub": "1", "username": "admin"}, SECRET, 60)
        claims = verify_jwt(token, SECRET)
        assert claims["sub"] == "1"
        assert claims["username"] == "admin"
        assert claims["exp"] > claims["iat"]

    def test_abgelaufenes_token(self) -> None:
        token = create_jwt({"sub": "1"}, SECRET, -10)
        with pytest.raises(AuthenticationError):
            verify_jwt(token, SECRET)

    def test_falsches_geheimnis(self) -> None:
        token = create_jwt({"sub": "1"}, SECRET, 60)
        with pytest.raises(AuthenticationError):
            verify_jwt(token, "anderes-geheimnis")

    def test_manipulierte_nutzdaten(self) -> None:
        token = create_jwt({"sub": "1"}, SECRET, 60)
        header, payload, signature = token.split(".")
        forged = json.dumps({"sub": "2", "exp": int(time.time()) + 600})
        forged_part = base64.urlsafe_b64encode(forged.encode()).rstrip(b"=").decode()
        with pytest.raises(AuthenticationError):
            verify_jwt(f"{header}.{forged_part}.{signature}", SECRET)

    def test_unzulaessiger_algorithmus(self) -> None:
        header = (
            base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
            .rstrip(b"=")
            .decode()
        )
        token = create_jwt({"sub": "1"}, SECRET, 60)
        _, payload, _ = token.split(".")
        with pytest.raises(AuthenticationError):
            verify_jwt(f"{header}.{payload}.", SECRET)

    @pytest.mark.parametrize("bad", ["", "abc", "a.b", "a.b.c.d", "..", "?.!.#"])
    def test_kaputte_tokens(self, bad: str) -> None:
        with pytest.raises(AuthenticationError):
            verify_jwt(bad, SECRET)

    def test_token_ohne_ablauf(self) -> None:
        token = create_jwt({"sub": "1"}, SECRET, 60)
        header, _, _ = token.split(".")
        payload = (
            base64.urlsafe_b64encode(json.dumps({"sub": "1"}).encode())
            .rstrip(b"=")
            .decode()
        )
        with pytest.raises(AuthenticationError):
            verify_jwt(f"{header}.{payload}.x", SECRET)
