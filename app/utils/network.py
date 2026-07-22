# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - DevTools-Netzwerkclient.

Minimaler Client fuer das Chrome-DevTools-Protokoll (CDP).
Er wird verwendet, um die aktive Kioskseite in Chromium neu zu
laden, ohne den Browserprozess zu beenden. Die WebSocket-
Kommunikation ist bewusst mit Bordmitteln der Standardbibliothek
implementiert, um keine zusaetzlichen Abhaengigkeiten einzufuehren.
"""

import base64
import http.client
import json
import os
import socket
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from app.constants import (
    APP_NAME,
    APP_VERSION,
    INTERNET_CHECK_HOST,
    INTERNET_CHECK_PORT,
    INTERNET_CHECK_TIMEOUT_SECONDS,
    PING_BINARY,
    PING_TIMEOUT_SECONDS,
    URL_CHECK_TIMEOUT_SECONDS,
    URL_CHECK_VALID_STATUS,
)
from app.exceptions import NetworkError

PROC_ROUTE_FILE: Path = Path("/proc/net/route")
DEFAULT_ROUTE_DESTINATION: str = "00000000"

WEBSOCKET_ACCEPT_STATUS: str = "101"
TEXT_FRAME_OPCODE: int = 0x81
MASK_BIT: int = 0x80
URL_CHECK_USER_AGENT: str = (
    f"Mozilla/5.0 (X11; Linux aarch64) {APP_NAME.replace(' ', '')}/{APP_VERSION}"
)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Unterbindet das automatische Folgen von Weiterleitungen."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def check_url_status(
    url: str, timeout: float = URL_CHECK_TIMEOUT_SECONDS
) -> tuple[bool, int]:
    """Prueft die Erreichbarkeit einer URL.

    Weiterleitungen werden nicht verfolgt, damit die Statuscodes
    301 und 302 direkt bewertet werden koennen.

    Args:
        url:
            Zu pruefende URL.

        timeout:
            Timeout in Sekunden.

    Returns:
        Tupel aus Gueltigkeit (Status 200, 301 oder 302) und
        HTTP-Statuscode.

    Raises:
        NetworkError
    """
    opener = urllib.request.build_opener(_NoRedirectHandler)
    request = urllib.request.Request(
        url, method="GET", headers={"User-Agent": URL_CHECK_USER_AGENT}
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            status = int(response.status)
    except urllib.error.HTTPError as error:
        status = int(error.code)
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise NetworkError(f"Die URL ist nicht erreichbar: {error}") from error
    return status in URL_CHECK_VALID_STATUS, status


def internet_reachable() -> bool:
    """Prueft die Internetverbindung ueber einen TCP-Verbindungsaufbau.

    Returns:
        True, wenn das Internet erreichbar ist.
    """
    return host_reachable(INTERNET_CHECK_HOST, INTERNET_CHECK_PORT)


def host_reachable(
    host: str,
    port: int,
    timeout: float = INTERNET_CHECK_TIMEOUT_SECONDS,
) -> bool:
    """Prueft, ob ein Host auf einem Port erreichbar ist.

    Args:
        host:
            Hostname oder IP-Adresse.

        port:
            TCP-Port.

        timeout:
            Timeout in Sekunden.

    Returns:
        True, wenn eine Verbindung aufgebaut werden konnte.
    """
    if not host:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def url_host_reachable(url: str) -> bool:
    """Prueft die Erreichbarkeit des Hosts einer URL.

    Es wird nur eine TCP-Verbindung aufgebaut, kein HTTP-Aufruf
    ausgefuehrt; die Pruefung ist damit auch fuer haeufige
    Wiederholungen guenstig.

    Args:
        url:
            Zu pruefende URL.

    Returns:
        True, wenn der Host der URL erreichbar ist.
    """
    parts = urlsplit(url)
    if not parts.hostname:
        return False
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return host_reachable(parts.hostname, port)


def connectivity_ok(mode: str, url: str = "") -> bool:
    """Prueft die Verbindung gemaess der konfigurierten Betriebsart.

    Args:
        mode:
            Betriebsart: internet, url, gateway oder off.

        url:
            Konfigurierte Kiosk-URL, nur fuer die Betriebsart url.

    Returns:
        True, wenn die Verbindung als in Ordnung gilt.
    """
    if mode == "off":
        return True
    if mode == "gateway":
        return ping_host(default_gateway())
    if mode == "url":
        return url_host_reachable(url)
    return internet_reachable()


def default_gateway() -> str:
    """Ermittelt das Standardgateway aus der Kernel-Routingtabelle.

    Returns:
        IPv4-Adresse des Standardgateways oder leer, wenn keine
        Standardroute existiert.
    """
    try:
        lines = PROC_ROUTE_FILE.read_text(encoding="ascii").splitlines()
    except OSError:
        return ""
    for line in lines[1:]:
        fields = line.split()
        if len(fields) >= 3 and fields[1] == DEFAULT_ROUTE_DESTINATION:
            try:
                return socket.inet_ntoa(bytes.fromhex(fields[2])[::-1])
            except ValueError:
                return ""
    return ""


def ping_host(host: str) -> bool:
    """Prueft die Erreichbarkeit eines Hosts per Ping.

    Args:
        host:
            Hostname oder IP-Adresse.

    Returns:
        True, wenn der Host auf den Ping antwortet.
    """
    if not host:
        return False
    try:
        result = subprocess.run(
            [PING_BINARY, "-c", "1", "-W", str(PING_TIMEOUT_SECONDS), host],
            capture_output=True,
            timeout=PING_TIMEOUT_SECONDS + 2.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def encode_text_frame(payload: bytes) -> bytes:
    """Kodiert eine Nachricht als maskiertes WebSocket-Textframe.

    Args:
        payload:
            Zu sendende Nutzdaten.

    Returns:
        Das vollstaendige WebSocket-Frame.
    """
    header = bytearray([TEXT_FRAME_OPCODE])
    length = len(payload)
    if length < 126:
        header.append(MASK_BIT | length)
    elif length < 65536:
        header.append(MASK_BIT | 126)
        header.extend(length.to_bytes(2, "big"))
    else:
        header.append(MASK_BIT | 127)
        header.extend(length.to_bytes(8, "big"))
    mask_key = os.urandom(4)
    masked = bytes(byte ^ mask_key[index % 4] for index, byte in enumerate(payload))
    return bytes(header) + mask_key + masked


class DevToolsClient:
    """Client fuer das Chrome-DevTools-Protokoll.

    Args:
        host:
            Host des DevTools-Endpunkts.

        port:
            Port des DevTools-Endpunkts.

        timeout:
            Timeout in Sekunden fuer alle Netzwerkoperationen.
    """

    def __init__(self, host: str, port: int, timeout: float = 5.0) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout

    def reload_page(self) -> None:
        """Laedt die erste geoeffnete Browserseite neu.

        Raises:
            NetworkError
        """
        targets = self._fetch_targets()
        websocket_url = self._first_page_websocket_url(targets)
        command = json.dumps(
            {"id": 1, "method": "Page.reload", "params": {"ignoreCache": False}}
        )
        self._send_command(websocket_url, command.encode("utf-8"))

    def navigate(self, url: str) -> None:
        """Lenkt die erste geoeffnete Browserseite auf eine URL um.

        Wird genutzt, um den Kioskbrowser per Tastenkombination aus
        der angezeigten Seite auf die lokale Verwaltung zu holen,
        ohne den Browser neu zu starten.

        Args:
            url:
                Zieladresse.

        Raises:
            NetworkError
        """
        targets = self._fetch_targets()
        websocket_url = self._first_page_websocket_url(targets)
        command = json.dumps(
            {"id": 1, "method": "Page.navigate", "params": {"url": url}}
        )
        self._send_command(websocket_url, command.encode("utf-8"))

    def _fetch_targets(self) -> list[dict[str, Any]]:
        """Fragt alle DevTools-Ziele ueber HTTP ab.

        Returns:
            Liste der DevTools-Ziele.

        Raises:
            NetworkError
        """
        connection = http.client.HTTPConnection(
            self._host, self._port, timeout=self._timeout
        )
        try:
            connection.request("GET", "/json/list")
            response = connection.getresponse()
            if response.status != 200:
                raise NetworkError(
                    f"DevTools-Endpunkt antwortete mit Status {response.status}."
                )
            targets = json.loads(response.read().decode("utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise NetworkError(
                f"DevTools-Endpunkt nicht erreichbar: {error}"
            ) from error
        finally:
            connection.close()
        if not isinstance(targets, list):
            raise NetworkError("DevTools-Endpunkt lieferte keine Zielliste.")
        return targets

    def _first_page_websocket_url(self, targets: list[dict[str, Any]]) -> str:
        """Ermittelt die WebSocket-URL der ersten Browserseite.

        Args:
            targets:
                Liste der DevTools-Ziele.

        Returns:
            WebSocket-Debugger-URL der ersten Seite.

        Raises:
            NetworkError
        """
        for target in targets:
            if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                return str(target["webSocketDebuggerUrl"])
        raise NetworkError("Keine offene Browserseite gefunden.")

    def _send_command(self, websocket_url: str, payload: bytes) -> None:
        """Sendet ein CDP-Kommando ueber eine WebSocket-Verbindung.

        Args:
            websocket_url:
                WebSocket-Debugger-URL des Ziels.

            payload:
                JSON-Kommando als Bytes.

        Raises:
            NetworkError
        """
        path = urlsplit(websocket_url).path
        try:
            with socket.create_connection(
                (self._host, self._port), timeout=self._timeout
            ) as connection:
                self._perform_handshake(connection, path)
                connection.sendall(encode_text_frame(payload))
                self._read_frame_payload(connection)
        except OSError as error:
            raise NetworkError(
                f"WebSocket-Verbindung fehlgeschlagen: {error}"
            ) from error

    def _perform_handshake(self, connection: socket.socket, path: str) -> None:
        """Fuehrt den WebSocket-Handshake durch.

        Args:
            connection:
                Offene TCP-Verbindung.

            path:
                Pfad des WebSocket-Endpunkts.

        Raises:
            NetworkError
        """
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {self._host}:{self._port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        connection.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = connection.recv(4096)
            if not chunk:
                raise NetworkError("Verbindung waehrend des Handshakes beendet.")
            response += chunk
        status_line = response.split(b"\r\n", 1)[0].decode("latin-1")
        if WEBSOCKET_ACCEPT_STATUS not in status_line:
            raise NetworkError(f"WebSocket-Handshake abgelehnt: {status_line}")

    def _read_frame_payload(self, connection: socket.socket) -> bytes:
        """Liest ein einzelnes WebSocket-Frame vom Server.

        Args:
            connection:
                Offene WebSocket-Verbindung.

        Returns:
            Nutzdaten des Frames.

        Raises:
            NetworkError
        """
        header = self._read_exact(connection, 2)
        length = header[1] & 0x7F
        if length == 126:
            length = int.from_bytes(self._read_exact(connection, 2), "big")
        elif length == 127:
            length = int.from_bytes(self._read_exact(connection, 8), "big")
        return self._read_exact(connection, length)

    def _read_exact(self, connection: socket.socket, count: int) -> bytes:
        """Liest exakt die angeforderte Anzahl Bytes.

        Args:
            connection:
                Offene Verbindung.

            count:
                Anzahl der zu lesenden Bytes.

        Returns:
            Die gelesenen Bytes.

        Raises:
            NetworkError
        """
        data = b""
        while len(data) < count:
            chunk = connection.recv(count - len(data))
            if not chunk:
                raise NetworkError("Verbindung unerwartet beendet.")
            data += chunk
        return data
