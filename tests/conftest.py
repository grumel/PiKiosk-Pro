# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Gemeinsame Testkonfiguration.

Macht das Projektpaket importierbar und stellt wiederverwendbare
Fixtures fuer alle Testebenen bereit.
"""

import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.extensions import ServiceRegistry  # noqa: E402
from app.logger import KioskLogger  # noqa: E402
from app.models.user_model import UserModel  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from app.services.backup_service import BackupService  # noqa: E402
from app.services.browser_service import BrowserService  # noqa: E402
from app.services.config_service import ConfigService  # noqa: E402
from app.services.dashboard_service import DashboardService  # noqa: E402
from app.services.hostname_service import HostnameService  # noqa: E402
from app.services.network_service import NetworkService  # noqa: E402
from app.services.restore_service import RestoreService  # noqa: E402
from app.services.system_service import SystemService  # noqa: E402


@pytest.fixture
def test_logger(tmp_path: Path, request: pytest.FixtureRequest) -> KioskLogger:
    """Erzeugt einen isolierten Logger fuer einen Testfall.

    Args:
        tmp_path:
            Temporaeres Testverzeichnis.

        request:
            Pytest-Anfrageobjekt fuer eindeutige Loggernamen.

    Returns:
        Ein testspezifischer KioskLogger.
    """
    return KioskLogger(f"test_{request.node.name}", tmp_path / "test.log")


@pytest.fixture
def registry(tmp_path: Path, test_logger: KioskLogger) -> ServiceRegistry:
    """Erzeugt eine ServiceRegistry mit temporaeren Datenpfaden.

    Die Standardwerte und Sprachdateien des Projekts werden
    weiterverwendet, alle Laufzeitdaten liegen im Testverzeichnis.

    Args:
        tmp_path:
            Temporaeres Testverzeichnis.

        test_logger:
            Testspezifischer Logger.

    Returns:
        Eine vollstaendig befuellte ServiceRegistry.
    """
    config_service = ConfigService(
        logger=test_logger,
        config_file=tmp_path / "config.json",
        defaults_file=PROJECT_ROOT / "config" / "defaults.json",
        backup_dir=tmp_path / "backup",
    )
    browser_service = BrowserService(
        logger=test_logger, user_data_dir=tmp_path / "chromium"
    )
    return ServiceRegistry(
        logger=test_logger,
        config_service=config_service,
        browser_service=browser_service,
        network_service=NetworkService(logger=test_logger),
        hostname_service=HostnameService(logger=test_logger),
        auth_service=AuthService(
            logger=test_logger, user_model=UserModel(tmp_path / "users.db")
        ),
        dashboard_service=DashboardService(
            logger=test_logger,
            config_service=config_service,
            browser_service=browser_service,
        ),
        system_service=SystemService(
            logger=test_logger, browser_service=browser_service
        ),
        backup_service=BackupService(
            logger=test_logger,
            config_service=config_service,
            config_file=tmp_path / "config.json",
            users_db_file=tmp_path / "users.db",
            backup_dir=tmp_path / "backup",
            log_dir=tmp_path / "logs",
        ),
        restore_service=RestoreService(
            logger=test_logger,
            config_service=config_service,
            users_db_file=tmp_path / "users.db",
        ),
    )


class _StatusHandler(BaseHTTPRequestHandler):
    """Testserver-Handler mit festen Statusantworten."""

    def do_GET(self) -> None:
        if self.path == "/ok":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/ok")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def http_status_server() -> Iterator[str]:
    """Startet einen lokalen HTTP-Testserver.

    Yields:
        Basis-URL des Testservers.
    """
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StatusHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=5.0)
