# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer den DevTools-Netzwerkclient."""

import pytest

from app.exceptions import NetworkError
from app.utils.network import DevToolsClient, check_url_status, encode_text_frame


def decode_masked_frame(frame: bytes) -> bytes:
    """Entschluesselt ein maskiertes WebSocket-Textframe.

    Args:
        frame:
            Vollstaendiges Frame.

    Returns:
        Die entschluesselten Nutzdaten.
    """
    length = frame[1] & 0x7F
    if length < 126:
        offset = 2
    elif length == 126:
        length = int.from_bytes(frame[2:4], "big")
        offset = 4
    else:
        length = int.from_bytes(frame[2:10], "big")
        offset = 10
    mask = frame[offset : offset + 4]
    payload = frame[offset + 4 : offset + 4 + length]
    return bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))


class TestEncodeTextFrame:
    """Tests fuer die WebSocket-Frame-Kodierung."""

    def test_kurzes_frame(self) -> None:
        payload = b'{"id":1}'
        frame = encode_text_frame(payload)
        assert frame[0] == 0x81
        assert frame[1] & 0x80 == 0x80
        assert decode_masked_frame(frame) == payload

    def test_mittleres_frame(self) -> None:
        payload = b"x" * 500
        frame = encode_text_frame(payload)
        assert frame[1] & 0x7F == 126
        assert decode_masked_frame(frame) == payload

    def test_grosses_frame(self) -> None:
        payload = b"y" * 70000
        frame = encode_text_frame(payload)
        assert frame[1] & 0x7F == 127
        assert decode_masked_frame(frame) == payload


class TestDevToolsClient:
    """Tests fuer den DevTools-Client."""

    def test_nicht_erreichbarer_endpunkt(self) -> None:
        client = DevToolsClient("127.0.0.1", 59999, timeout=0.5)
        with pytest.raises(NetworkError):
            client.reload_page()

    def test_zielsuche_findet_seite(self) -> None:
        client = DevToolsClient("127.0.0.1", 59999)
        targets = [
            {"type": "service_worker", "webSocketDebuggerUrl": "ws://a/1"},
            {"type": "page", "webSocketDebuggerUrl": "ws://a/2"},
        ]
        assert client._first_page_websocket_url(targets) == "ws://a/2"

    def test_zielsuche_ohne_seite(self) -> None:
        client = DevToolsClient("127.0.0.1", 59999)
        with pytest.raises(NetworkError):
            client._first_page_websocket_url([{"type": "service_worker"}])


class TestCheckUrlStatus:
    """Tests fuer die URL-Statuspruefung."""

    def test_status_200_ist_gueltig(self, http_status_server: str) -> None:
        valid, status = check_url_status(f"{http_status_server}/ok")
        assert valid is True
        assert status == 200

    def test_status_302_ist_gueltig_ohne_weiterleitung(
        self, http_status_server: str
    ) -> None:
        valid, status = check_url_status(f"{http_status_server}/redirect")
        assert valid is True
        assert status == 302

    def test_status_404_ist_ungueltig(self, http_status_server: str) -> None:
        valid, status = check_url_status(f"{http_status_server}/fehlt")
        assert valid is False
        assert status == 404

    def test_nicht_erreichbare_url(self) -> None:
        with pytest.raises(NetworkError):
            check_url_status("http://127.0.0.1:59998/", timeout=0.5)
