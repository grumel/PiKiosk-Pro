# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer den DevTools-Netzwerkclient."""

import pytest

from app.exceptions import NetworkError
from app.utils.network import DevToolsClient, encode_text_frame


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
