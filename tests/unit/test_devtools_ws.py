# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer den DevTools-Client mit echtem Server.

Ein minimaler TCP-Server beantwortet die Zielabfrage per HTTP und
nimmt anschliessend die WebSocket-Verbindung samt Frame entgegen.
Zusaetzlich werden Ping- und Gateway-Ermittlung geprueft.
"""

import json
import socket
import subprocess
import threading
from pathlib import Path
from typing import Iterator

import pytest

from app.exceptions import NetworkError
from app.utils import network as network_module
from app.utils.network import (
    DevToolsClient,
    connectivity_ok,
    default_gateway,
    host_reachable,
    ping_host,
    url_host_reachable,
)


def _read_until(connection: socket.socket, marker: bytes) -> bytes:
    """Liest von einer Verbindung bis zur Markierung.

    Args:
        connection:
            Offene Verbindung.

        marker:
            Endemarkierung.

    Returns:
        Die gelesenen Bytes einschliesslich Markierung.
    """
    data = b""
    while marker not in data:
        chunk = connection.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def _read_exact(connection: socket.socket, count: int) -> bytes:
    """Liest exakt die angeforderte Anzahl Bytes.

    Args:
        connection:
            Offene Verbindung.

        count:
            Anzahl der Bytes.

    Returns:
        Die gelesenen Bytes.
    """
    data = b""
    while len(data) < count:
        chunk = connection.recv(count - len(data))
        if not chunk:
            break
        data += chunk
    return data


class MiniDevToolsServer(threading.Thread):
    """Beantwortet /json/list und eine WebSocket-Verbindung.

    Attributes:
        port:
            Zufaellig gewaehlter Port des Servers.

        frames:
            Empfangene, entschluesselte WebSocket-Nutzdaten.

        reject_handshake:
            True, um den WebSocket-Handshake abzulehnen.
    """

    def __init__(self, reject_handshake: bool = False) -> None:
        super().__init__(daemon=True)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.bind(("127.0.0.1", 0))
        self._socket.listen(4)
        self._socket.settimeout(10.0)
        self.port: int = self._socket.getsockname()[1]
        self.frames: list[bytes] = []
        self.reject_handshake = reject_handshake

    def run(self) -> None:
        try:
            while True:
                connection, _ = self._socket.accept()
                if self._serve_connection(connection):
                    break
        except OSError:
            pass
        finally:
            self._socket.close()

    def _serve_connection(self, connection: socket.socket) -> bool:
        request = _read_until(connection, b"\r\n\r\n")
        if request.startswith(b"GET /json/list"):
            targets = [
                {"type": "service_worker"},
                {
                    "type": "page",
                    "webSocketDebuggerUrl": (
                        f"ws://127.0.0.1:{self.port}/devtools/page/1"
                    ),
                },
            ]
            body = json.dumps(targets).encode("utf-8")
            connection.sendall(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                + f"Content-Length: {len(body)}\r\n".encode("ascii")
                + b"Connection: close\r\n\r\n"
                + body
            )
            connection.close()
            return False
        if self.reject_handshake:
            connection.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            connection.close()
            return True
        connection.sendall(
            b"HTTP/1.1 101 Switching Protocols\r\n"
            b"Upgrade: websocket\r\nConnection: Upgrade\r\n\r\n"
        )
        header = _read_exact(connection, 2)
        length = header[1] & 0x7F
        mask = _read_exact(connection, 4)
        masked = _read_exact(connection, length)
        self.frames.append(
            bytes(byte ^ mask[index % 4] for index, byte in enumerate(masked))
        )
        connection.sendall(b"\x81\x02{}")
        connection.close()
        return True


@pytest.fixture
def devtools_server() -> Iterator[MiniDevToolsServer]:
    """Startet den DevTools-Testserver.

    Yields:
        Der laufende Testserver.
    """
    server = MiniDevToolsServer()
    server.start()
    yield server
    server.join(timeout=5.0)


class TestDevToolsClientLive:
    """Tests fuer den kompletten Reload-Ablauf."""

    def test_reload_page_sendet_cdp_kommando(
        self, devtools_server: MiniDevToolsServer
    ) -> None:
        client = DevToolsClient("127.0.0.1", devtools_server.port, timeout=5.0)
        client.reload_page()
        assert len(devtools_server.frames) == 1
        command = json.loads(devtools_server.frames[0])
        assert command["method"] == "Page.reload"

    def test_navigate_sendet_cdp_kommando(
        self, devtools_server: MiniDevToolsServer
    ) -> None:
        client = DevToolsClient("127.0.0.1", devtools_server.port, timeout=5.0)
        client.navigate("http://127.0.0.1:8081/dashboard/")
        assert len(devtools_server.frames) == 1
        command = json.loads(devtools_server.frames[0])
        assert command["method"] == "Page.navigate"
        assert command["params"]["url"] == "http://127.0.0.1:8081/dashboard/"

    def test_abgelehnter_handshake(self) -> None:
        server = MiniDevToolsServer(reject_handshake=True)
        server.start()
        client = DevToolsClient("127.0.0.1", server.port, timeout=5.0)
        with pytest.raises(NetworkError):
            client.reload_page()
        server.join(timeout=5.0)


class TestPingHost:
    """Tests fuer die Ping-Pruefung."""

    def test_erfolgreicher_ping(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class Result:
            returncode = 0

        monkeypatch.setattr(network_module.subprocess, "run", lambda *a, **k: Result())
        assert ping_host("192.0.2.1") is True

    def test_fehlgeschlagener_ping(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class Result:
            returncode = 1

        monkeypatch.setattr(network_module.subprocess, "run", lambda *a, **k: Result())
        assert ping_host("192.0.2.1") is False

    def test_ping_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def raise_timeout(*args: object, **kwargs: object) -> None:
            raise subprocess.TimeoutExpired(cmd=["ping"], timeout=1.0)

        monkeypatch.setattr(network_module.subprocess, "run", raise_timeout)
        assert ping_host("192.0.2.1") is False

    def test_leerer_host(self) -> None:
        assert ping_host("") is False


class TestDefaultGateway:
    """Tests fuer die Gateway-Ermittlung."""

    def test_standardroute_wird_gelesen(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        route_file = tmp_path / "route"
        route_file.write_text(
            "Iface\tDestination\tGateway\tFlags\n" "wlan0\t00000000\t0100A8C0\t0003\n",
            encoding="ascii",
        )
        monkeypatch.setattr(network_module, "PROC_ROUTE_FILE", route_file)
        assert default_gateway() == "192.168.0.1"

    def test_ohne_standardroute(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        route_file = tmp_path / "route"
        route_file.write_text(
            "Iface\tDestination\tGateway\tFlags\n" "wlan0\t0000A8C0\t00000000\t0001\n",
            encoding="ascii",
        )
        monkeypatch.setattr(network_module, "PROC_ROUTE_FILE", route_file)
        assert default_gateway() == ""

    def test_kaputte_routentabelle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        route_file = tmp_path / "route"
        route_file.write_text(
            "Iface\tDestination\tGateway\nwlan0\t00000000\tXYZ\n",
            encoding="ascii",
        )
        monkeypatch.setattr(network_module, "PROC_ROUTE_FILE", route_file)
        assert default_gateway() == ""

    def test_fehlende_datei(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(network_module, "PROC_ROUTE_FILE", tmp_path / "fehlt")
        assert default_gateway() == ""


class TestConnectivityCheck:
    """Tests fuer die konfigurierbare Verbindungspruefung."""

    def test_pruefung_aus_ist_immer_online(self) -> None:
        assert connectivity_ok("off") is True
        assert connectivity_ok("off", "http://gibt-es-nicht.invalid/") is True

    def test_gateway_pruefung(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(network_module, "default_gateway", lambda: "192.0.2.1")
        monkeypatch.setattr(
            network_module, "ping_host", lambda host: host == "192.0.2.1"
        )
        assert connectivity_ok("gateway") is True
        monkeypatch.setattr(network_module, "default_gateway", lambda: "")
        assert connectivity_ok("gateway") is False

    def test_url_pruefung_mit_erreichbarem_host(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        try:
            assert connectivity_ok("url", f"http://127.0.0.1:{port}/anzeige") is True
        finally:
            listener.close()

    def test_url_pruefung_mit_totem_host(self) -> None:
        assert connectivity_ok("url", "http://127.0.0.1:59990/") is False

    def test_url_pruefung_ohne_url(self) -> None:
        assert connectivity_ok("url", "") is False

    def test_standardbetrieb_prueft_internet(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        aufrufe: list[bool] = []
        monkeypatch.setattr(
            network_module,
            "internet_reachable",
            lambda: aufrufe.append(True) or True,
        )
        assert connectivity_ok("internet") is True
        assert aufrufe == [True]


class TestHostReachable:
    """Tests fuer die TCP-Erreichbarkeitspruefung."""

    def test_offener_port(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        try:
            assert host_reachable("127.0.0.1", port) is True
        finally:
            listener.close()

    def test_geschlossener_port(self) -> None:
        assert host_reachable("127.0.0.1", 59989, timeout=0.5) is False

    def test_leerer_host(self) -> None:
        assert host_reachable("", 80) is False

    def test_standardports_der_url(self) -> None:
        assert url_host_reachable("http://127.0.0.1:59988/") is False
        assert url_host_reachable("kein-schema") is False
