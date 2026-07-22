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

    def test_ohne_geraete_meldet_fehler(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            keymon, "ConfigService", lambda **kwargs: _FakeConfigService("ctrl+alt+k")
        )
        monkeypatch.setattr(keymon, "open_keyboards", lambda logger: [])
        assert keymon.main() == 1
