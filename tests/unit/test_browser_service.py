# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer den BrowserService.

Der Chromium-Prozess wird durch einen Fake-Prozess ersetzt, damit
die Tests ohne installierten Browser und ohne Display laufen.
"""

from pathlib import Path
from typing import Any

import pytest

from app.exceptions import BrowserError, ValidationError
from app.logger import KioskLogger
from app.services import browser_service as browser_module
from app.services.browser_service import BrowserService, BrowserStatus

TEST_URL = "https://example.org/"
FAKE_BINARY = "/usr/bin/chromium-browser"


class FakeProcess:
    """Ersatz fuer subprocess.Popen in den Tests."""

    def __init__(self, command: list[str], **_: Any) -> None:
        self.command = command
        self.returncode: int | None = None
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        if self.returncode is None:
            raise browser_module.subprocess.TimeoutExpired(
                cmd=self.command, timeout=timeout or 0.0
            )
        return self.returncode


@pytest.fixture
def service(
    tmp_path: Path,
    test_logger: KioskLogger,
    monkeypatch: pytest.MonkeyPatch,
) -> BrowserService:
    """Erzeugt einen BrowserService mit Fake-Prozess.

    Args:
        tmp_path:
            Temporaeres Testverzeichnis.

        test_logger:
            Testspezifischer Logger.

        monkeypatch:
            Pytest-Patchwerkzeug.

    Returns:
        Ein testbarer BrowserService.
    """
    monkeypatch.setattr(browser_module.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(browser_module.shutil, "which", lambda name: FAKE_BINARY)
    return BrowserService(logger=test_logger, user_data_dir=tmp_path / "chromium")


class TestBrowserService:
    """Tests fuer die Browsersteuerung."""

    def test_initialer_status(self, service: BrowserService) -> None:
        assert service.status() is BrowserStatus.NOT_STARTED

    def test_start_setzt_status_und_kommando(
        self, service: BrowserService, tmp_path: Path
    ) -> None:
        service.start(TEST_URL)
        assert service.status() is BrowserStatus.RUNNING
        command = service._command
        assert command[0] == FAKE_BINARY
        assert "--kiosk" in command
        assert "--incognito" in command
        assert command[-1] == TEST_URL
        assert (tmp_path / "chromium").exists()

    def test_start_mit_ungueltiger_url(self, service: BrowserService) -> None:
        with pytest.raises(ValidationError):
            service.start("ftp://example.org")

    def test_doppelter_start_wird_abgelehnt(self, service: BrowserService) -> None:
        service.start(TEST_URL)
        with pytest.raises(BrowserError):
            service.start(TEST_URL)

    def test_stop_beendet_prozess(self, service: BrowserService) -> None:
        service.start(TEST_URL)
        service.stop()
        assert service.status() is BrowserStatus.NOT_STARTED

    def test_stop_ohne_laufenden_browser(self, service: BrowserService) -> None:
        service.stop()
        assert service.status() is BrowserStatus.NOT_STARTED

    def test_absturz_wird_erkannt(self, service: BrowserService) -> None:
        service.start(TEST_URL)
        service._process.returncode = 139  # type: ignore[union-attr]
        assert service.status() is BrowserStatus.CRASHED

    def test_restart_verwendet_letzte_url(self, service: BrowserService) -> None:
        service.start(TEST_URL)
        service.restart()
        assert service.status() is BrowserStatus.RUNNING
        assert service._command[-1] == TEST_URL

    def test_restart_ohne_vorherigen_start(self, service: BrowserService) -> None:
        with pytest.raises(BrowserError):
            service.restart()

    def test_reload_ohne_laufenden_browser(self, service: BrowserService) -> None:
        with pytest.raises(BrowserError):
            service.reload()

    def test_clear_cache_loescht_profil(
        self, service: BrowserService, tmp_path: Path
    ) -> None:
        profile = tmp_path / "chromium"
        profile.mkdir()
        (profile / "Cache").mkdir()
        service.clear_cache()
        assert not profile.exists()

    def test_clear_cache_startet_browser_neu(
        self, service: BrowserService, tmp_path: Path
    ) -> None:
        service.start(TEST_URL)
        service.clear_cache()
        assert service.status() is BrowserStatus.RUNNING
        assert (tmp_path / "chromium").exists()

    def test_fullscreen_nur_bei_laufendem_browser(
        self, service: BrowserService
    ) -> None:
        assert service.fullscreen() is False
        service.start(TEST_URL)
        assert service.fullscreen() is True

    def test_fehlendes_chromium_meldet_fehler(
        self,
        service: BrowserService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(browser_module.shutil, "which", lambda name: None)
        with pytest.raises(BrowserError):
            service.start(TEST_URL)


class TestBrowserServiceFehlerpfade:
    """Tests fuer Fehler- und Sonderpfade der Browsersteuerung."""

    def test_startfehler_setzt_fehlerstatus(
        self, service: BrowserService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def broken_popen(*args: Any, **kwargs: Any) -> None:
            raise OSError("kein Display")

        monkeypatch.setattr(browser_module.subprocess, "Popen", broken_popen)
        with pytest.raises(BrowserError):
            service.start(TEST_URL)
        assert service.status() is BrowserStatus.ERROR

    def test_stop_erzwingt_kill_bei_haengendem_prozess(
        self, service: BrowserService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service.start(TEST_URL)
        process = service._process
        monkeypatch.setattr(process, "terminate", lambda: None)
        service.stop()
        assert process.killed is True
        assert service.status() is BrowserStatus.NOT_STARTED

    def test_reload_bei_laufendem_browser(
        self, service: BrowserService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        reloads: list[bool] = []

        class FakeClient:
            def __init__(self, host: str, port: int) -> None:
                pass

            def reload_page(self) -> None:
                reloads.append(True)

        monkeypatch.setattr(browser_module, "DevToolsClient", FakeClient)
        service.start(TEST_URL)
        service.reload()
        assert reloads == [True]

    def test_reload_fehler_wird_uebersetzt(
        self, service: BrowserService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.exceptions import NetworkError

        class BrokenClient:
            def __init__(self, host: str, port: int) -> None:
                pass

            def reload_page(self) -> None:
                raise NetworkError("keine Seite")

        monkeypatch.setattr(browser_module, "DevToolsClient", BrokenClient)
        service.start(TEST_URL)
        with pytest.raises(BrowserError):
            service.reload()

    def test_clear_cache_fehler(
        self, service: BrowserService, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "chromium").mkdir()

        def broken_rmtree(path: object) -> None:
            raise OSError("keine Rechte")

        monkeypatch.setattr(browser_module.shutil, "rmtree", broken_rmtree)
        with pytest.raises(BrowserError):
            service.clear_cache()
        assert service.status() is BrowserStatus.ERROR
