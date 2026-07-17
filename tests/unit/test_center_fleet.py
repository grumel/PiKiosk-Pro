# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Center - Unit-Tests fuer Geraeteclient und FleetService.

Der Client wird gegen einen echten HTTP-Testserver geprueft, der die
Geraete-API nachbildet: Token ausstellen, Status liefern, Aktionen
annehmen und abgelaufene Tokens ablehnen.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator

import pytest

from app.exceptions import AuthenticationError, NetworkError, PiKioskError
from app.logger import KioskLogger
from app.utils.crypto import load_or_create_fernet_key
from center.models.device_model import Device, DeviceModel
from center.services.device_client import DeviceClient
from center.services.device_service import DeviceService
from center.services.fleet_service import FleetService

DEVICE_PASSWORD = "Geraet-Geheim-2026!"
DEVICE_STATUS = {
    "hostname": "pikiosk-01",
    "browser_status": "running",
    "watchdog": "online",
    "url": "http://server.local/anzeige",
    "temperature": 44.5,
    "version": "1.1.0",
}


class _DeviceHandler(BaseHTTPRequestHandler):
    """Bildet die REST API eines PiKiosk-Geraets nach."""

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        body = json.loads(raw.decode("utf-8") or "{}")
        if self.path == "/api/token":
            if body.get("password") != self.server.password:  # type: ignore[attr-defined]
                self._json(401, {"error": "invalid_credentials"})
                return
            self.server.token_calls += 1  # type: ignore[attr-defined]
            self._json(
                200,
                {
                    "token": self.server.token,  # type: ignore[attr-defined]
                    "token_type": "Bearer",
                    "expires_in": 86400,
                },
            )
            return
        if not self._authorized():
            self._json(401, {"error": "unauthorized"})
            return
        self.server.actions.append((self.path, body))  # type: ignore[attr-defined]
        self._json(200, {"accepted": True})

    def do_PUT(self) -> None:
        self.do_POST()

    def do_GET(self) -> None:
        if not self._authorized():
            self._json(401, {"error": "unauthorized"})
            return
        if self.path == "/api/status":
            self._json(200, dict(DEVICE_STATUS))
            return
        self._json(404, {"error": "not_found"})

    def _authorized(self) -> bool:
        expected = f"Bearer {self.server.token}"  # type: ignore[attr-defined]
        return self.headers.get("Authorization", "") == expected

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def fake_device() -> Iterator[ThreadingHTTPServer]:
    """Startet ein nachgebildetes PiKiosk-Geraet.

    Yields:
        Der laufende Testserver mit Port, Token und Aufrufliste.
    """
    server = ThreadingHTTPServer(("127.0.0.1", 0), _DeviceHandler)
    server.token = "test-token"  # type: ignore[attr-defined]
    server.password = DEVICE_PASSWORD  # type: ignore[attr-defined]
    server.token_calls = 0  # type: ignore[attr-defined]
    server.actions = []  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    thread.join(timeout=5.0)


@pytest.fixture
def key(tmp_path: Path) -> bytes:
    """Erzeugt einen Verschluesselungsschluessel.

    Args:
        tmp_path:
            Temporaeres Testverzeichnis.

    Returns:
        Der Fernet-Schluessel.
    """
    return load_or_create_fernet_key(tmp_path / "center_key")


@pytest.fixture
def device_service(
    tmp_path: Path, test_logger: KioskLogger, key: bytes
) -> DeviceService:
    """Erzeugt einen DeviceService mit temporaerer Datenbank.

    Args:
        tmp_path:
            Temporaeres Testverzeichnis.

        test_logger:
            Testspezifischer Logger.

        key:
            Fernet-Schluessel.

    Returns:
        Ein einsatzbereiter DeviceService.
    """
    return DeviceService(
        logger=test_logger,
        device_model=DeviceModel(tmp_path / "devices.db"),
        key=key,
    )


def add_device(
    service: DeviceService,
    server: ThreadingHTTPServer,
    name: str = "Empfang",
    password: str = DEVICE_PASSWORD,
) -> Device:
    """Nimmt das nachgebildete Geraet in die Verwaltung auf.

    Args:
        service:
            Der DeviceService.

        server:
            Der Testserver.

        name:
            Name des Geraets.

        password:
            Zu speicherndes Passwort.

    Returns:
        Das aufgenommene Geraet.
    """
    return service.add(name, "127.0.0.1", server.server_port, "admin", password)


class TestDeviceClient:
    """Tests fuer den Geraeteclient gegen ein echtes Geraet."""

    def test_status_abfragen(
        self,
        device_service: DeviceService,
        fake_device: ThreadingHTTPServer,
        key: bytes,
    ) -> None:
        device = add_device(device_service, fake_device)
        client = DeviceClient(key=key)
        status = client.status(device)
        assert status["hostname"] == "pikiosk-01"
        assert status["version"] == "1.1.0"

    def test_token_wird_wiederverwendet(
        self,
        device_service: DeviceService,
        fake_device: ThreadingHTTPServer,
        key: bytes,
    ) -> None:
        device = add_device(device_service, fake_device)
        client = DeviceClient(key=key)
        client.status(device)
        client.status(device)
        client.status(device)
        assert fake_device.token_calls == 1

    def test_abgelaufenes_token_wird_erneuert(
        self,
        device_service: DeviceService,
        fake_device: ThreadingHTTPServer,
        key: bytes,
    ) -> None:
        device = add_device(device_service, fake_device)
        client = DeviceClient(key=key)
        client.status(device)
        fake_device.token = "neues-token"  # type: ignore[attr-defined]
        status = client.status(device)
        assert status["hostname"] == "pikiosk-01"
        assert fake_device.token_calls == 2

    def test_falsches_passwort(
        self,
        device_service: DeviceService,
        fake_device: ThreadingHTTPServer,
        key: bytes,
    ) -> None:
        device = add_device(device_service, fake_device, password="Falsch-2026!")
        client = DeviceClient(key=key)
        with pytest.raises(AuthenticationError):
            client.status(device)

    def test_geraet_nicht_erreichbar(
        self,
        device_service: DeviceService,
        fake_device: ThreadingHTTPServer,
        key: bytes,
    ) -> None:
        device = add_device(device_service, fake_device)
        device_service.update(
            device.id, device.name, "127.0.0.1", 59986, "admin", "", True
        )
        offline = device_service.find(device.id)
        assert offline is not None
        client = DeviceClient(key=key)
        with pytest.raises(NetworkError):
            client.status(offline)

    def test_aktionen_erreichen_das_geraet(
        self,
        device_service: DeviceService,
        fake_device: ThreadingHTTPServer,
        key: bytes,
    ) -> None:
        device = add_device(device_service, fake_device)
        client = DeviceClient(key=key)
        client.action(device, "browser_restart")
        client.action(device, "reboot")
        client.set_url(device, "http://server.local/neu")
        pfade = [pfad for pfad, _ in fake_device.actions]
        koerper = [body for _, body in fake_device.actions]
        assert pfade == ["/api/browser", "/api/system", "/api/settings"]
        assert koerper[0] == {"action": "restart"}
        assert koerper[1] == {"action": "reboot"}
        assert koerper[2] == {"url": "http://server.local/neu"}

    def test_unbekannter_pfad_meldet_fehler(
        self,
        device_service: DeviceService,
        fake_device: ThreadingHTTPServer,
        key: bytes,
    ) -> None:
        device = add_device(device_service, fake_device)
        client = DeviceClient(key=key)
        with pytest.raises(PiKioskError):
            client._request(device, "GET", "/api/gibt-es-nicht")


class TestFleetService:
    """Tests fuer die Flottenabfrage und Massenaktionen."""

    def fleet(
        self, device_service: DeviceService, key: bytes, test_logger: KioskLogger
    ) -> FleetService:
        """Erzeugt einen FleetService.

        Args:
            device_service:
                Die Geraeteverwaltung.

            key:
                Fernet-Schluessel.

            test_logger:
                Testspezifischer Logger.

        Returns:
            Ein einsatzbereiter FleetService.
        """
        return FleetService(
            logger=test_logger,
            device_service=device_service,
            client=DeviceClient(key=key),
        )

    def test_uebersicht_mit_online_geraet(
        self,
        device_service: DeviceService,
        fake_device: ThreadingHTTPServer,
        key: bytes,
        test_logger: KioskLogger,
    ) -> None:
        add_device(device_service, fake_device)
        entries = self.fleet(device_service, key, test_logger).overview()
        assert len(entries) == 1
        assert entries[0]["state"] == "online"
        assert entries[0]["status"]["version"] == "1.1.0"

    def test_uebersicht_mischt_zustaende(
        self,
        device_service: DeviceService,
        fake_device: ThreadingHTTPServer,
        key: bytes,
        test_logger: KioskLogger,
    ) -> None:
        add_device(device_service, fake_device, name="Online")
        device_service.add("Offline", "127.0.0.1", 59985, "admin", DEVICE_PASSWORD)
        falsch = device_service.add(
            "Anmeldefehler", "127.0.0.1", fake_device.server_port, "admin", "Falsch!"
        )
        deaktiviert = device_service.add(
            "Aus", "127.0.0.1", fake_device.server_port, "admin", DEVICE_PASSWORD
        )
        device_service.update(
            deaktiviert.id,
            "Aus",
            "127.0.0.1",
            fake_device.server_port,
            "admin",
            "",
            False,
        )
        service = self.fleet(device_service, key, test_logger)
        entries = service.overview()
        zustaende = {e["name"]: e["state"] for e in entries}
        assert zustaende["Online"] == "online"
        assert zustaende["Offline"] == "offline"
        assert zustaende["Anmeldefehler"] == "auth_error"
        assert zustaende["Aus"] == "disabled"
        assert falsch.id > 0
        summary = service.summary(entries)
        assert summary == {
            "total": 4,
            "online": 1,
            "offline": 1,
            "auth_error": 1,
            "disabled": 1,
        }

    def test_leere_uebersicht(
        self, device_service: DeviceService, key: bytes, test_logger: KioskLogger
    ) -> None:
        assert self.fleet(device_service, key, test_logger).overview() == []

    def test_massenaktion_auf_mehreren_geraeten(
        self,
        device_service: DeviceService,
        fake_device: ThreadingHTTPServer,
        key: bytes,
        test_logger: KioskLogger,
    ) -> None:
        erstes = add_device(device_service, fake_device, name="Empfang")
        zweites = add_device(device_service, fake_device, name="Foyer")
        service = self.fleet(device_service, key, test_logger)
        results = service.run_action([erstes.id, zweites.id], "browser_restart")
        assert len(results) == 2
        assert all(r["success"] for r in results)
        assert len(fake_device.actions) == 2

    def test_massenaktion_meldet_einzelfehler(
        self,
        device_service: DeviceService,
        fake_device: ThreadingHTTPServer,
        key: bytes,
        test_logger: KioskLogger,
    ) -> None:
        gut = add_device(device_service, fake_device, name="Empfang")
        schlecht = device_service.add(
            "Kaputt", "127.0.0.1", 59984, "admin", DEVICE_PASSWORD
        )
        service = self.fleet(device_service, key, test_logger)
        results = service.run_action([gut.id, schlecht.id], "browser_restart")
        nach_namen = {r["name"]: r for r in results}
        assert nach_namen["Empfang"]["success"] is True
        assert nach_namen["Kaputt"]["success"] is False
        assert nach_namen["Kaputt"]["error"]

    def test_deaktivierte_geraete_werden_uebersprungen(
        self,
        device_service: DeviceService,
        fake_device: ThreadingHTTPServer,
        key: bytes,
        test_logger: KioskLogger,
    ) -> None:
        device = add_device(device_service, fake_device)
        device_service.update(
            device.id,
            device.name,
            "127.0.0.1",
            fake_device.server_port,
            "admin",
            "",
            False,
        )
        service = self.fleet(device_service, key, test_logger)
        assert service.run_action([device.id], "browser_restart") == []
        assert fake_device.actions == []

    def test_unbekannte_aktion(
        self,
        device_service: DeviceService,
        fake_device: ThreadingHTTPServer,
        key: bytes,
        test_logger: KioskLogger,
    ) -> None:
        device = add_device(device_service, fake_device)
        service = self.fleet(device_service, key, test_logger)
        with pytest.raises(ValueError):
            service.run_action([device.id], "explodieren")

    def test_url_massenweise_setzen(
        self,
        device_service: DeviceService,
        fake_device: ThreadingHTTPServer,
        key: bytes,
        test_logger: KioskLogger,
    ) -> None:
        erstes = add_device(device_service, fake_device, name="Empfang")
        zweites = add_device(device_service, fake_device, name="Foyer")
        service = self.fleet(device_service, key, test_logger)
        results = service.set_url([erstes.id, zweites.id], "http://server.local/neu")
        assert all(r["success"] for r in results)
        assert all(
            body == {"url": "http://server.local/neu"}
            for _, body in fake_device.actions
        )

    def test_url_setzen_meldet_fehler(
        self, device_service: DeviceService, key: bytes, test_logger: KioskLogger
    ) -> None:
        device = device_service.add(
            "Kaputt", "127.0.0.1", 59983, "admin", DEVICE_PASSWORD
        )
        service = self.fleet(device_service, key, test_logger)
        results = service.set_url([device.id], "http://server.local/neu")
        assert results[0]["success"] is False

    def test_unbekannte_kennung_wird_ignoriert(
        self, device_service: DeviceService, key: bytes, test_logger: KioskLogger
    ) -> None:
        service = self.fleet(device_service, key, test_logger)
        assert service.run_action([999], "browser_restart") == []
