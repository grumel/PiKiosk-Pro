# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer die Kiosk-Tastenueberwachung."""

import struct
from typing import Any

import pytest

from app import keymon


def _event(event_type: int, code: int, value: int) -> bytes:
    """Baut eine rohe input_event-Struktur fuer Tests.

    Args:
        event_type:
            Ereignistyp.

        code:
            Tastencode.

        value:
            Ereigniswert.

    Returns:
        Die Bytes eines Ereignisses.
    """
    padding = keymon.EVENT_SIZE - struct.calcsize("HHi")
    return b"\x00" * padding + struct.pack("HHi", event_type, code, value)


class _FakeDevice:
    """Ersetzt eine Eingabegeraetedatei mit festen Ereignissen."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.closed = False

    def read(self, size: int) -> bytes:
        data = self._payload
        self._payload = b""
        return data

    def close(self) -> None:
        self.closed = True


class TestReadEvents:
    """Tests fuer das Zerlegen roher Ereignisse."""

    def test_mehrere_ereignisse(self) -> None:
        payload = _event(1, 29, 1) + _event(1, 56, 1) + _event(1, 37, 1)
        device: Any = _FakeDevice(payload)
        assert keymon.read_events(device) == [(1, 29, 1), (1, 56, 1), (1, 37, 1)]

    def test_leerer_read(self) -> None:
        device: Any = _FakeDevice(b"")
        assert keymon.read_events(device) == []


class TestDashboardUrl:
    """Tests fuer die Ziel-URL der Umleitung."""

    def test_ohne_tls_lokaler_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(keymon, "local_base_url", lambda: "http://127.0.0.1:8080/")
        assert keymon.dashboard_url() == "http://127.0.0.1:8080/dashboard/"

    def test_mit_tls_loopback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(keymon, "local_base_url", lambda: "http://127.0.0.1:8081/")
        assert keymon.dashboard_url() == "http://127.0.0.1:8081/dashboard/"


class _FakeConfigService:
    """Liefert eine feste Konfiguration fuer die main-Tests."""

    def __init__(self, hotkey: str) -> None:
        self._hotkey = hotkey

    def load(self) -> dict[str, Any]:
        return {"escape_hotkey": self._hotkey}


class TestMain:
    """Tests fuer den Einstiegspunkt."""

    def test_leere_kombination_beendet_sauber(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            keymon, "ConfigService", lambda **kwargs: _FakeConfigService("")
        )
        assert keymon.main() == 0

    def test_ungueltige_kombination_meldet_fehler(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            keymon,
            "ConfigService",
            lambda **kwargs: _FakeConfigService("ctrl+alt+gibtsnicht"),
        )
        assert keymon.main() == 1

    def test_gueltige_kombination_startet_ueberwachung(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            keymon, "ConfigService", lambda **kwargs: _FakeConfigService("ctrl+alt+k")
        )
        aufgerufen: list[bool] = []

        def fake_monitor(
            logger: object, matcher: object, client: object, url: str
        ) -> None:
            aufgerufen.append(True)
            raise KeyboardInterrupt

        monkeypatch.setattr(keymon, "monitor", fake_monitor)
        assert keymon.main() == 0
        assert aufgerufen == [True]


class _FakeSelector:
    """Minimaler Selector fuer die Geraeteverwaltung im Test."""

    def __init__(self) -> None:
        self.registered: dict[Any, Any] = {}

    def register(self, fileobj: Any, events: int, data: Any = None) -> None:
        self.registered[fileobj] = data

    def unregister(self, fileobj: Any) -> None:
        self.registered.pop(fileobj, None)


class TestReopenDevices:
    """Tests fuer das frische Neu-Oeffnen der Eingabegeraete."""

    def test_geraete_werden_frisch_geoeffnet(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            keymon.glob,
            "glob",
            lambda pattern: ["/dev/input/event0", "/dev/input/event1"],
        )
        monkeypatch.setattr(
            keymon, "open", lambda *a, **k: _FakeDevice(b""), raising=False
        )
        selector: Any = _FakeSelector()
        registered: dict[str, Any] = {}
        keymon.reopen_devices(selector, registered)
        assert set(registered) == {"/dev/input/event0", "/dev/input/event1"}

    def test_alte_geraete_werden_zuvor_geschlossen(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        altes = _FakeDevice(b"")
        selector: Any = _FakeSelector()
        registered: dict[str, Any] = {"/dev/input/event9": altes}
        selector.registered[altes] = "/dev/input/event9"
        monkeypatch.setattr(
            keymon, "open", lambda *a, **k: _FakeDevice(b""), raising=False
        )
        monkeypatch.setattr(keymon.glob, "glob", lambda pattern: ["/dev/input/event0"])
        keymon.reopen_devices(selector, registered)
        assert altes.closed is True
        assert set(registered) == {"/dev/input/event0"}

    def test_verschwundene_geraete_bleiben_zu(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        altes = _FakeDevice(b"")
        selector: Any = _FakeSelector()
        registered: dict[str, Any] = {"/dev/input/event9": altes}
        selector.registered[altes] = "/dev/input/event9"
        monkeypatch.setattr(keymon.glob, "glob", lambda pattern: [])
        keymon.reopen_devices(selector, registered)
        assert registered == {}
        assert altes.closed is True


class _FakeResponse:
    """Minimale HTTP-Antwort fuer den Selbsttest."""

    status = 200

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class TestCheck:
    """Tests fuer den Selbsttest (--check)."""

    def _patch_common(
        self, monkeypatch: pytest.MonkeyPatch, hotkey: str = "ctrl+alt+k"
    ) -> None:
        monkeypatch.setattr(
            keymon, "ConfigService", lambda **kwargs: _FakeConfigService(hotkey)
        )
        monkeypatch.setattr(keymon, "open_keyboards", lambda logger: [_FakeDevice(b"")])
        monkeypatch.setattr(
            keymon.urllib.request, "urlopen", lambda url, timeout=0: _FakeResponse()
        )

    def test_alles_bereit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch_common(monkeypatch)
        monkeypatch.setattr(keymon.DevToolsClient, "probe", lambda self: None)
        assert keymon.check() == 0

    def test_cdp_nicht_steuerbar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.exceptions import NetworkError

        self._patch_common(monkeypatch)

        def fail(self: object) -> None:
            raise NetworkError("kein Browser")

        monkeypatch.setattr(keymon.DevToolsClient, "probe", fail)
        assert keymon.check() == 1

    def test_keine_tastatur(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch_common(monkeypatch)
        monkeypatch.setattr(keymon, "open_keyboards", lambda logger: [])
        monkeypatch.setattr(keymon.DevToolsClient, "probe", lambda self: None)
        assert keymon.check() == 1

    def test_check_ueber_main_argument(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch_common(monkeypatch)
        monkeypatch.setattr(keymon.DevToolsClient, "probe", lambda self: None)
        monkeypatch.setattr(keymon.sys, "argv", ["keymon", "--check"])
        assert keymon.main() == 0
