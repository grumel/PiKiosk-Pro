# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer den Produktions-Webserver."""

import datetime
import socket
import ssl
import threading
import time
import urllib.request
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from flask import Flask

from app.server import build_server
from app.utils.helpers import local_base_url, tls_files


def _free_port() -> int:
    """Reserviert einen freien TCP-Port.

    Returns:
        Ein aktuell freier Port.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _tiny_app() -> Flask:
    """Erzeugt eine minimale WSGI-Anwendung fuer Servertests.

    Returns:
        Eine Flask-Anwendung mit einer Route.
    """
    app = Flask("pikiosk-servertest")

    @app.get("/")
    def index() -> str:
        return "pikiosk-ok"

    return app


@pytest.fixture
def tls_pair(tmp_path: Path) -> tuple[Path, Path]:
    """Erzeugt ein selbstsigniertes Zertifikat fuer die Tests.

    Args:
        tmp_path:
            Temporaeres Testverzeichnis.

    Returns:
        Pfadpaar (Zertifikat, Schluessel).
    """
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False
        )
        .sign(key, hashes.SHA256())
    )
    cert_file = tmp_path / "cert.pem"
    key_file = tmp_path / "key.pem"
    cert_file.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return cert_file, key_file


def _run_until_ready(server: object, port: int) -> threading.Thread:
    """Startet einen Server im Hintergrund und wartet auf den Port.

    Args:
        server:
            Der Cheroot-Server.

        port:
            Erwarteter Port.

    Returns:
        Der Serverthread.
    """
    thread = threading.Thread(target=server.safe_start, daemon=True)  # type: ignore[attr-defined]
    thread.start()
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return thread
        except OSError:
            time.sleep(0.1)
    raise AssertionError("Server wurde nicht bereit.")


class TestBuildServer:
    """Tests fuer den Cheroot-Server."""

    def test_http_antwortet(self) -> None:
        port = _free_port()
        server = build_server(_tiny_app(), "127.0.0.1", port)
        thread = _run_until_ready(server, port)
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/", timeout=5.0
            ) as response:
                assert response.read() == b"pikiosk-ok"
        finally:
            server.stop()
            thread.join(timeout=5.0)

    def test_https_antwortet_mit_tls(self, tls_pair: tuple[Path, Path]) -> None:
        port = _free_port()
        server = build_server(_tiny_app(), "127.0.0.1", port, tls=tls_pair)
        thread = _run_until_ready(server, port)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        try:
            with urllib.request.urlopen(
                f"https://127.0.0.1:{port}/", timeout=5.0, context=context
            ) as response:
                assert response.read() == b"pikiosk-ok"
        finally:
            server.stop()
            thread.join(timeout=5.0)


class TestTlsHelpers:
    """Tests fuer die TLS-Hilfsfunktionen."""

    def test_ohne_dateien_kein_tls(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.utils import helpers as helpers_module

        monkeypatch.setattr(helpers_module, "TLS_CERT_FILE", tmp_path / "cert.pem")
        monkeypatch.setattr(helpers_module, "TLS_KEY_FILE", tmp_path / "key.pem")
        assert tls_files() is None
        assert local_base_url().startswith("http://127.0.0.1:8080")

    def test_mit_dateien_tls_und_loopback(
        self,
        tmp_path: Path,
        tls_pair: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.utils import helpers as helpers_module

        certificate, key = tls_pair
        monkeypatch.setattr(helpers_module, "TLS_CERT_FILE", certificate)
        monkeypatch.setattr(helpers_module, "TLS_KEY_FILE", key)
        assert tls_files() == (certificate, key)
        assert local_base_url() == "http://127.0.0.1:8081/"
