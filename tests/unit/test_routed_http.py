# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer echte HTTP-Pfade.

Ein konfigurierbarer lokaler HTTP-Server prueft die realen
Netzwerkzugriffe von UpdateService (GitHub-Abfrage, Download) und
WatchdogService (Health-Endpunkt, Neustart-Endpunkt).
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

import pytest

from app.exceptions import UpdateError
from app.extensions import ServiceRegistry
from app.logger import KioskLogger
from app.services import update_service as update_module
from app.services import watchdog_service as watchdog_module
from app.services.update_service import UpdateService
from app.services.watchdog_service import WatchdogService

TEST_REPO = "tester/kiosk"


class _RoutedHandler(BaseHTTPRequestHandler):
    """Handler mit konfigurierbaren Antworten je Pfad."""

    def do_GET(self) -> None:
        self._answer(getattr(self.server, "get_routes", {}))

    def do_POST(self) -> None:
        self._answer(getattr(self.server, "post_routes", {}))

    def _answer(self, routes: dict[str, tuple[int, bytes]]) -> None:
        entry = routes.get(self.path)
        if entry is None:
            self.send_response(404)
            self.end_headers()
            return
        status, body = entry
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def routed_server() -> Iterator[tuple[str, ThreadingHTTPServer]]:
    """Startet einen HTTP-Server mit konfigurierbaren Routen.

    Yields:
        Basis-URL und Serverobjekt mit get_routes/post_routes.
    """
    server = ThreadingHTTPServer(("127.0.0.1", 0), _RoutedHandler)
    server.get_routes = {}  # type: ignore[attr-defined]
    server.post_routes = {}  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", server
    server.shutdown()
    thread.join(timeout=5.0)


@pytest.fixture
def update_service(
    registry: ServiceRegistry, tmp_path: Path, test_logger: KioskLogger
) -> UpdateService:
    """Erzeugt einen UpdateService mit temporaeren Pfaden.

    Args:
        registry:
            ServiceRegistry mit temporaeren Datenpfaden.

        tmp_path:
            Temporaeres Testverzeichnis.

        test_logger:
            Testspezifischer Logger.

    Returns:
        Ein UpdateService fuer HTTP-Tests.
    """
    return UpdateService(
        logger=test_logger,
        config_service=registry.config_service,
        backup_service=registry.backup_service,
        install_dir=tmp_path / "install",
        releases_dir=tmp_path / "releases",
        repo=TEST_REPO,
    )


class TestGithubFetch:
    """Tests fuer die echte GitHub-Abfrage."""

    def test_release_wird_gelesen(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        update_service: UpdateService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        base, server = routed_server
        release = {"tag_name": "v99.0.0", "body": "Notizen", "tarball_url": ""}
        server.get_routes[f"/repos/{TEST_REPO}/releases/latest"] = (
            200,
            json.dumps(release).encode("utf-8"),
        )
        monkeypatch.setattr(update_module, "GITHUB_API_BASE", base)
        data = update_service._github_latest()
        assert data is not None
        assert data["tag_name"] == "v99.0.0"

    def test_kein_release_liefert_none(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        update_service: UpdateService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        base, _ = routed_server
        monkeypatch.setattr(update_module, "GITHUB_API_BASE", base)
        assert update_service._github_latest() is None

    def test_serverfehler_meldet_updatefehler(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        update_service: UpdateService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        base, server = routed_server
        server.get_routes[f"/repos/{TEST_REPO}/releases/latest"] = (500, b"kaputt")
        monkeypatch.setattr(update_module, "GITHUB_API_BASE", base)
        with pytest.raises(UpdateError):
            update_service._github_latest()

    def test_ungueltiges_json_meldet_updatefehler(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        update_service: UpdateService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        base, server = routed_server
        server.get_routes[f"/repos/{TEST_REPO}/releases/latest"] = (200, b"kaputt")
        monkeypatch.setattr(update_module, "GITHUB_API_BASE", base)
        with pytest.raises(UpdateError):
            update_service._github_latest()

    def test_nicht_erreichbar(
        self, update_service: UpdateService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(update_module, "GITHUB_API_BASE", "http://127.0.0.1:59997")
        with pytest.raises(UpdateError):
            update_service._github_latest()


class TestDownload:
    """Tests fuer den echten Archiv-Download."""

    def test_download_speichert_datei(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        update_service: UpdateService,
    ) -> None:
        base, server = routed_server
        server.get_routes["/blob"] = (200, b"x" * 4096)
        path = update_service._download(f"{base}/blob")
        try:
            assert path.read_bytes() == b"x" * 4096
        finally:
            path.unlink(missing_ok=True)

    def test_zu_grosses_archiv_wird_abgelehnt(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        update_service: UpdateService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        base, server = routed_server
        server.get_routes["/big"] = (200, b"y" * 4096)
        monkeypatch.setattr(update_module, "UPDATE_PACKAGE_MAX_BYTES", 1024)
        with pytest.raises(UpdateError):
            update_service._download(f"{base}/big")

    def test_fehlgeschlagener_download(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        update_service: UpdateService,
    ) -> None:
        base, _ = routed_server
        with pytest.raises(UpdateError):
            update_service._download(f"{base}/fehlt")


@pytest.fixture
def watchdog(registry: ServiceRegistry, test_logger: KioskLogger) -> WatchdogService:
    """Erzeugt einen WatchdogService fuer HTTP-Tests.

    Args:
        registry:
            ServiceRegistry mit temporaeren Datenpfaden.

        test_logger:
            Testspezifischer Logger.

    Returns:
        Ein einsatzbereiter WatchdogService.
    """
    return WatchdogService(
        logger=test_logger,
        config_service=registry.config_service,
        token="test-token",
    )


class TestWatchdogHttp:
    """Tests fuer die echten HTTP-Zugriffe des Watchdogs."""

    def test_fetch_health_liest_json(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        watchdog: WatchdogService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        base, server = routed_server
        server.get_routes["/health"] = (200, b'{"browser": "running"}')
        monkeypatch.setattr(watchdog_module, "HEALTH_CHECK_URL", f"{base}/health")
        health = watchdog._fetch_health()
        assert health == {"browser": "running"}

    def test_fetch_health_bei_kaputtem_json(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        watchdog: WatchdogService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        base, server = routed_server
        server.get_routes["/health"] = (200, b"kaputt")
        monkeypatch.setattr(watchdog_module, "HEALTH_CHECK_URL", f"{base}/health")
        assert watchdog._fetch_health() is None

    def test_fetch_health_nicht_erreichbar(
        self, watchdog: WatchdogService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            watchdog_module, "HEALTH_CHECK_URL", "http://127.0.0.1:59996/health"
        )
        assert watchdog._fetch_health() is None

    def test_request_restart_erfolgreich(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        watchdog: WatchdogService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        base, server = routed_server
        server.post_routes["/restart"] = (200, b'{"restarted": true}')
        monkeypatch.setattr(watchdog_module, "BROWSER_RESTART_URL", f"{base}/restart")
        assert watchdog._request_restart() is True

    def test_request_restart_abgelehnt(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        watchdog: WatchdogService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        base, _ = routed_server
        monkeypatch.setattr(watchdog_module, "BROWSER_RESTART_URL", f"{base}/fehlt")
        assert watchdog._request_restart() is False


class TestLocalUpdateSource:
    """Tests fuer die lokale Updatequelle mit echtem Webserver."""

    def use_local_source(self, update_service: UpdateService, base_url: str) -> None:
        """Stellt die Konfiguration auf die lokale Quelle um.

        Args:
            update_service:
                Der zu konfigurierende Dienst.

            base_url:
                Basis-URL der lokalen Quelle.
        """
        config = update_service._config_service.load()
        config["update_source"] = "local"
        config["update_url"] = base_url
        update_service._config_service.save(config)

    def test_update_verfuegbar(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        update_service: UpdateService,
    ) -> None:
        base, server = routed_server
        manifest = {
            "version": "99.0.0",
            "archive": "PiKiosk-Pro-99.0.0.zip",
            "notes": "Lokale Notizen",
        }
        server.get_routes["/manifest.json"] = (
            200,
            json.dumps(manifest).encode("utf-8"),
        )
        self.use_local_source(update_service, base)
        info = update_service.check()
        assert info["available"] is True
        assert info["source"] == "local"
        assert info["latest"] == "99.0.0"
        assert info["notes"] == "Lokale Notizen"
        assert info["archive_url"] == f"{base}/PiKiosk-Pro-99.0.0.zip"

    def test_bereits_aktuell(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        update_service: UpdateService,
    ) -> None:
        base, server = routed_server
        manifest = {"version": "0.0.1", "archive": "alt.zip"}
        server.get_routes["/manifest.json"] = (
            200,
            json.dumps(manifest).encode("utf-8"),
        )
        self.use_local_source(update_service, base)
        info = update_service.check()
        assert info["available"] is False
        assert info["status"] == "up_to_date"

    def test_absolute_archiv_url_bleibt_erhalten(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        update_service: UpdateService,
    ) -> None:
        base, server = routed_server
        manifest = {
            "version": "99.0.0",
            "archive": "http://anderer.server/paket.zip",
        }
        server.get_routes["/manifest.json"] = (
            200,
            json.dumps(manifest).encode("utf-8"),
        )
        self.use_local_source(update_service, base)
        info = update_service.check()
        assert info["archive_url"] == "http://anderer.server/paket.zip"

    def test_unvollstaendiges_manifest(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        update_service: UpdateService,
    ) -> None:
        base, server = routed_server
        server.get_routes["/manifest.json"] = (200, b'{"version": "9.9.9"}')
        self.use_local_source(update_service, base)
        with pytest.raises(UpdateError):
            update_service.check()

    def test_ungueltige_version_im_manifest(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        update_service: UpdateService,
    ) -> None:
        base, server = routed_server
        server.get_routes["/manifest.json"] = (
            200,
            b'{"version": "keine-version", "archive": "x.zip"}',
        )
        self.use_local_source(update_service, base)
        info = update_service.check()
        assert info["status"] == "invalid_version"
        assert info["available"] is False

    def test_quelle_nicht_erreichbar(self, update_service: UpdateService) -> None:
        self.use_local_source(update_service, "http://127.0.0.1:59991")
        with pytest.raises(UpdateError):
            update_service.check()

    def test_manifest_fehlt(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        update_service: UpdateService,
    ) -> None:
        base, _ = routed_server
        self.use_local_source(update_service, base)
        with pytest.raises(UpdateError):
            update_service.check()

    def test_kaputtes_manifest(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        update_service: UpdateService,
    ) -> None:
        base, server = routed_server
        server.get_routes["/manifest.json"] = (200, b"kein json")
        self.use_local_source(update_service, base)
        with pytest.raises(UpdateError):
            update_service.check()

    def test_manifest_kein_objekt(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        update_service: UpdateService,
    ) -> None:
        base, server = routed_server
        server.get_routes["/manifest.json"] = (200, b"[1, 2]")
        self.use_local_source(update_service, base)
        with pytest.raises(UpdateError):
            update_service.check()

    def test_quelle_aus(self, update_service: UpdateService) -> None:
        config = update_service._config_service.load()
        config["update_source"] = "off"
        update_service._config_service.save(config)
        info = update_service.check()
        assert info["status"] == "disabled"
        assert info["available"] is False
        assert update_service.source() == "off"
        with pytest.raises(UpdateError):
            update_service.apply()

    def test_installation_aus_lokaler_quelle(
        self,
        routed_server: tuple[str, ThreadingHTTPServer],
        update_service: UpdateService,
        tmp_path: Path,
    ) -> None:
        from tests.unit.test_update_service import build_zip

        base, server = routed_server
        package = build_zip(tmp_path / "paket.zip", "99.0.0")
        server.get_routes["/manifest.json"] = (
            200,
            json.dumps({"version": "99.0.0", "archive": "paket.zip"}).encode("utf-8"),
        )
        server.get_routes["/paket.zip"] = (200, package.read_bytes())
        self.use_local_source(update_service, base)
        result = update_service.apply()
        assert result["version"] == "99.0.0"
        assert (update_service._install_dir / "app" / "constants.py").read_text(
            encoding="utf-8"
        ).count("99.0.0") == 1
