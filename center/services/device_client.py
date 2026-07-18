# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Center - Geraeteclient.

Spricht die REST API eines PiKiosk-Geraets an: Token holen, Status
abfragen, Aktionen ausloesen. Tokens werden je Geraet bis kurz vor
Ablauf zwischengespeichert, damit nicht bei jeder Abfrage eine neue
Anmeldung noetig ist. Verbindungen werden zuerst ueber HTTPS
versucht; antwortet ein Geraet dort nicht (aeltere Installation
ohne TLS), merkt sich der Client HTTP je Geraet. Selbstsignierte
Zertifikate werden akzeptiert: Die Verbindung ist damit gegen
Mitlesen geschuetzt; wer zusaetzlich Serverpruefung will, verteilt
Firmenzertifikate ueber den Systemspeicher. Die Geraete bleiben
unveraendert; es wird ausschliesslich die dokumentierte API
verwendet.
"""

import json
import ssl
import threading
import time
import urllib.error
import urllib.request
from typing import Any

from app.exceptions import AuthenticationError, NetworkError, PiKioskError
from app.utils.crypto import decrypt_secret
from center.constants import (
    DEVICE_HTTP_TIMEOUT_SECONDS,
    DEVICE_TOKEN_MARGIN_SECONDS,
)
from center.models.device_model import Device


def _tolerant_ssl_context() -> ssl.SSLContext:
    """Erzeugt einen TLS-Kontext, der selbstsignierte Zertifikate erlaubt.

    Returns:
        TLS-Kontext ohne Zertifikatspruefung.
    """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


class DeviceClient:
    """HTTP-Client fuer die REST API eines Geraets.

    Args:
        key:
            Fernet-Schluessel zum Entschluesseln der Zugangsdaten.

        timeout:
            Timeout in Sekunden fuer alle Anfragen.
    """

    def __init__(
        self, key: bytes, timeout: float = DEVICE_HTTP_TIMEOUT_SECONDS
    ) -> None:
        self._key = key
        self._timeout = timeout
        self._tokens: dict[int, tuple[str, float]] = {}
        self._lock = threading.Lock()
        self._schemes: dict[str, str] = {}
        self._ssl_context = _tolerant_ssl_context()

    def scheme(self, device: Device) -> str:
        """Liefert das zuletzt erfolgreiche Schema eines Geraets.

        Args:
            device:
                Das Geraet.

        Returns:
            "https" oder "http"; ohne bisherigen Kontakt "http".
        """
        with self._lock:
            return self._schemes.get(self._endpoint(device), "http")

    def _endpoint(self, device: Device) -> str:
        """Bildet den Schluessel fuer den Schema-Cache.

        Args:
            device:
                Das Geraet.

        Returns:
            Adresse und Port als Schluessel.
        """
        return f"{device.address}:{device.port}"

    def _base_url(self, device: Device, scheme: str) -> str:
        """Baut die Basis-URL eines Geraets fuer ein Schema.

        Args:
            device:
                Das Geraet.

            scheme:
                "https" oder "http".

        Returns:
            Die Basis-URL ohne abschliessenden Schraegstrich.
        """
        return f"{scheme}://{device.address}:{device.port}"

    def status(self, device: Device) -> dict[str, Any]:
        """Fragt den Status eines Geraets ab.

        Args:
            device:
                Das abzufragende Geraet.

        Returns:
            Die Statusdaten des Geraets.

        Raises:
            PiKioskError
        """
        return self._request(device, "GET", "/api/status")

    def action(self, device: Device, action: str) -> dict[str, Any]:
        """Loest eine Aktion auf einem Geraet aus.

        Args:
            device:
                Das Zielgeraet.

            action:
                Aktion aus DEVICE_ACTIONS.

        Returns:
            Die Antwort des Geraets.

        Raises:
            PiKioskError
        """
        if action.startswith("browser_"):
            return self._request(
                device,
                "POST",
                "/api/browser",
                {"action": action.removeprefix("browser_")},
            )
        return self._request(device, "POST", "/api/system", {"action": action})

    def set_url(self, device: Device, url: str) -> dict[str, Any]:
        """Setzt die Kiosk-URL eines Geraets.

        Args:
            device:
                Das Zielgeraet.

            url:
                Neue Kiosk-URL.

        Returns:
            Die gespeicherte Konfiguration des Geraets.

        Raises:
            PiKioskError
        """
        return self._request(device, "PUT", "/api/settings", {"url": url})

    def forget_token(self, device_id: int) -> None:
        """Verwirft ein zwischengespeichertes Token.

        Args:
            device_id:
                Kennung des Geraets.
        """
        with self._lock:
            self._tokens.pop(device_id, None)

    def _token(self, device: Device) -> str:
        """Liefert ein gueltiges Token fuer ein Geraet.

        Args:
            device:
                Das Geraet.

        Returns:
            Ein gueltiges Bearer-Token.

        Raises:
            AuthenticationError
            NetworkError
        """
        with self._lock:
            cached = self._tokens.get(device.id)
        if cached is not None and cached[1] > time.time():
            return cached[0]
        password = decrypt_secret(device.secret, self._key)
        payload = self._call_device(
            device,
            "POST",
            "/api/token",
            {"username": device.username, "password": password},
            None,
        )
        token = str(payload.get("token", ""))
        if not token:
            raise AuthenticationError(
                f"Das Geraet '{device.name}' hat kein Token ausgestellt."
            )
        expires_in = int(payload.get("expires_in", 0))
        valid_until = time.time() + max(60, expires_in - DEVICE_TOKEN_MARGIN_SECONDS)
        with self._lock:
            self._tokens[device.id] = (token, valid_until)
        return token

    def _request(
        self,
        device: Device,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fuehrt eine authentifizierte Anfrage an ein Geraet aus.

        Laeuft das zwischengespeicherte Token ab, wird die Anfrage
        einmalig mit einem neuen Token wiederholt.

        Args:
            device:
                Das Zielgeraet.

            method:
                HTTP-Methode.

            path:
                Pfad der API.

            body:
                Optionaler JSON-Koerper.

        Returns:
            Die JSON-Antwort des Geraets.

        Raises:
            PiKioskError
        """
        try:
            return self._call_device(device, method, path, body, self._token(device))
        except AuthenticationError:
            self.forget_token(device.id)
            return self._call_device(device, method, path, body, self._token(device))

    def _call_device(
        self,
        device: Device,
        method: str,
        path: str,
        body: dict[str, Any] | None,
        token: str | None,
    ) -> dict[str, Any]:
        """Fuehrt eine Anfrage mit Schema-Aufloesung aus.

        Ist noch kein Schema bekannt, wird zuerst HTTPS und danach
        HTTP versucht; das erfolgreiche Schema wird je Geraet
        gemerkt. Schlaegt ein gemerktes Schema fehl, wird es
        verworfen, damit der naechste Versuch neu aushandelt.

        Args:
            device:
                Das Zielgeraet.

            method:
                HTTP-Methode.

            path:
                Pfad der API.

            body:
                Optionaler JSON-Koerper.

            token:
                Optionales Bearer-Token.

        Returns:
            Die JSON-Antwort des Geraets.

        Raises:
            PiKioskError
        """
        endpoint = self._endpoint(device)
        with self._lock:
            pinned = self._schemes.get(endpoint)
        schemes = (pinned,) if pinned else ("https", "http")
        last_error: NetworkError | None = None
        for scheme in schemes:
            url = self._base_url(device, scheme) + path
            try:
                payload = self._call(url, method, body, token)
            except NetworkError as error:
                last_error = error
                continue
            with self._lock:
                self._schemes[endpoint] = scheme
            return payload
        with self._lock:
            self._schemes.pop(endpoint, None)
        if last_error is None:  # pragma: no cover - Schemaliste nie leer
            raise NetworkError("Das Geraet ist nicht erreichbar.")
        raise last_error

    def _call(
        self,
        url: str,
        method: str,
        body: dict[str, Any] | None,
        token: str | None,
    ) -> dict[str, Any]:
        """Fuehrt eine einzelne HTTP-Anfrage aus.

        Args:
            url:
                Vollstaendige URL.

            method:
                HTTP-Methode.

            body:
                Optionaler JSON-Koerper.

            token:
                Optionales Bearer-Token.

        Returns:
            Die JSON-Antwort.

        Raises:
            AuthenticationError
            NetworkError
            PiKioskError
        """
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(
                request, timeout=self._timeout, context=self._ssl_context
            ) as response:
                return self._decode(response.read())
        except urllib.error.HTTPError as error:
            raise self._map_http_error(error) from error
        except (urllib.error.URLError, OSError) as error:
            raise NetworkError(f"Das Geraet ist nicht erreichbar: {error}") from error

    def _map_http_error(self, error: urllib.error.HTTPError) -> PiKioskError:
        """Uebersetzt einen HTTP-Fehler in einen Anwendungsfehler.

        Args:
            error:
                Der aufgetretene HTTP-Fehler.

        Returns:
            Der passende Anwendungsfehler.
        """
        if error.code == 401:
            return AuthenticationError("Die Zugangsdaten wurden abgelehnt.")
        try:
            payload = self._decode(error.read())
            details = str(payload.get("error", ""))
        except PiKioskError:
            details = ""
        return PiKioskError(
            f"Das Geraet meldete HTTP {error.code}"
            + (f": {details}" if details else ".")
        )

    def _decode(self, raw: bytes) -> dict[str, Any]:
        """Dekodiert eine JSON-Antwort.

        Args:
            raw:
                Antwortdaten.

        Returns:
            Die dekodierten Daten.

        Raises:
            PiKioskError
        """
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as error:
            raise PiKioskError(
                f"Das Geraet lieferte keine gueltige JSON-Antwort: {error}"
            ) from error
        if not isinstance(payload, dict):
            raise PiKioskError("Das Geraet lieferte kein JSON-Objekt.")
        return payload
