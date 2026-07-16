# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer die Einstiegspunkte."""

import socket
from typing import Any

import pytest

from app.app import determine_kiosk_url, parse_arguments, wait_for_server
from app.constants import DEFAULT_HOST, DEFAULT_PORT, LOCAL_URL
from app.exceptions import ConfigurationError


class TestParseArguments:
    """Tests fuer die Kommandozeilenauswertung."""

    def test_standardwerte(self) -> None:
        arguments = parse_arguments([])
        assert arguments.host == DEFAULT_HOST
        assert arguments.port == DEFAULT_PORT
        assert arguments.no_browser is False

    def test_eigene_werte(self) -> None:
        arguments = parse_arguments(
            ["--host", "127.0.0.1", "--port", "9000", "--no-browser"]
        )
        assert arguments.host == "127.0.0.1"
        assert arguments.port == 9000
        assert arguments.no_browser is True


class TestDetermineKioskUrl:
    """Tests fuer die Ziel-URL des Kioskbrowsers."""

    def test_erststart_zeigt_lokale_seite(self) -> None:
        config = {"first_start": True, "url": "https://example.org/"}
        assert determine_kiosk_url(config) == LOCAL_URL

    def test_ohne_url_zeigt_lokale_seite(self) -> None:
        config = {"first_start": False, "url": ""}
        assert determine_kiosk_url(config) == LOCAL_URL

    def test_konfigurierte_url(self) -> None:
        config = {"first_start": False, "url": "https://example.org/"}
        assert determine_kiosk_url(config) == "https://example.org/"


class TestWaitForServer:
    """Tests fuer das Warten auf den Webserver."""

    def test_erreichbarer_server(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        try:
            assert wait_for_server("127.0.0.1", port, timeout=2.0) is True
            assert wait_for_server("0.0.0.0", port, timeout=2.0) is True
        finally:
            listener.close()

    def test_nicht_erreichbarer_server(self) -> None:
        assert wait_for_server("127.0.0.1", 59994, timeout=0.6) is False


class TestBrowserStartThread:
    """Tests fuer den Browserstart nach Serverstart."""

    def test_browser_startet_nach_serverstart(
        self, registry: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app import app as app_module

        started: list[str] = []
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        monkeypatch.setattr(
            registry.browser_service, "start", lambda url: started.append(url)
        )
        try:
            app_module._start_browser_when_ready(registry, "127.0.0.1", port)
        finally:
            listener.close()
        assert started == [LOCAL_URL]

    def test_abbruch_ohne_server(
        self, registry: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app import app as app_module

        def fail_start(url: str) -> None:
            raise AssertionError("Browser darf nicht starten")

        monkeypatch.setattr(registry.browser_service, "start", fail_start)
        monkeypatch.setattr(
            app_module, "SERVER_START_TIMEOUT_SECONDS", 0.6, raising=True
        )
        app_module._start_browser_when_ready(registry, "127.0.0.1", 59993)

    def test_browserfehler_wird_geloggt(
        self, registry: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app import app as app_module
        from app.exceptions import BrowserError

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]

        def fail_start(url: str) -> None:
            raise BrowserError("kein Chromium")

        monkeypatch.setattr(registry.browser_service, "start", fail_start)
        try:
            app_module._start_browser_when_ready(registry, "127.0.0.1", port)
        finally:
            listener.close()


class TestWatchdogEntry:
    """Tests fuer den Watchdog-Einstiegspunkt."""

    def test_main_beendet_sich_bei_tastaturabbruch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app import watchdog as watchdog_entry

        def stop_loop(self: object) -> None:
            raise KeyboardInterrupt

        monkeypatch.setattr(watchdog_entry.WatchdogService, "run_forever", stop_loop)
        assert watchdog_entry.main() == 0

    def test_main_bricht_ohne_schluessel_ab(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app import watchdog as watchdog_entry

        def fail_key() -> str:
            raise ConfigurationError("kein Schluessel")

        monkeypatch.setattr(watchdog_entry, "load_or_create_secret_key", fail_key)
        assert watchdog_entry.main() == 1
