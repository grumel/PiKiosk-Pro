# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Center - Integrationstests der Verwaltungszentrale.

Prueft Ersteinrichtung, Anmeldung, Geraeteverwaltung und
Massenaktionen gegen ein nachgebildetes PiKiosk-Geraet.
"""

from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.logger import KioskLogger
from app.models.user_model import UserModel
from app.services.auth_service import AuthService
from app.utils.crypto import load_or_create_fernet_key
from center import create_center_app
from center.controllers import SESSION_CSRF_KEY
from center.extensions import CenterRegistry
from center.models.device_model import DeviceModel
from center.services.device_client import DeviceClient
from center.services.device_service import DeviceService
from center.services.fleet_service import FleetService
from tests.unit.test_center_fleet import DEVICE_PASSWORD, fake_device  # noqa: F401

CENTER_PASSWORD = "Zentrale-2026-Sicher!"


@pytest.fixture
def center_registry(tmp_path: Path, test_logger: KioskLogger) -> CenterRegistry:
    """Erzeugt die Dienste der Zentrale mit temporaeren Pfaden.

    Args:
        tmp_path:
            Temporaeres Testverzeichnis.

        test_logger:
            Testspezifischer Logger.

    Returns:
        Eine befuellte CenterRegistry.
    """
    key = load_or_create_fernet_key(tmp_path / "center_key")
    device_service = DeviceService(
        logger=test_logger,
        device_model=DeviceModel(tmp_path / "devices.db"),
        key=key,
    )
    client = DeviceClient(key=key)
    return CenterRegistry(
        logger=test_logger,
        auth_service=AuthService(
            logger=test_logger, user_model=UserModel(tmp_path / "center_users.db")
        ),
        device_service=device_service,
        fleet_service=FleetService(
            logger=test_logger, device_service=device_service, client=client
        ),
        client=client,
    )


@pytest.fixture
def center_app(center_registry: CenterRegistry) -> Flask:
    """Erzeugt die Zentrale fuer die Tests.

    Args:
        center_registry:
            Die Dienste der Zentrale.

    Returns:
        Die initialisierte Flask-Anwendung.
    """
    application = create_center_app(center_registry)
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(center_app: Flask) -> FlaskClient:
    """Erzeugt einen Testclient.

    Args:
        center_app:
            Die Flask-Anwendung der Zentrale.

    Returns:
        Ein Flask-Testclient.
    """
    return center_app.test_client()


def csrf_token(client: FlaskClient, path: str = "/setup") -> str:
    """Oeffnet eine Seite und liefert das CSRF-Token der Sitzung.

    Args:
        client:
            Flask-Testclient.

        path:
            Aufzurufender Pfad.

    Returns:
        Das CSRF-Token.
    """
    client.get(path)
    with client.session_transaction() as session:
        return str(session[SESSION_CSRF_KEY])


def setup_and_login(client: FlaskClient) -> str:
    """Richtet die Zentrale ein und meldet den Administrator an.

    Args:
        client:
            Flask-Testclient.

    Returns:
        Das CSRF-Token der Sitzung.
    """
    token = csrf_token(client)
    client.post(
        "/setup",
        data={
            "username": "admin",
            "password": CENTER_PASSWORD,
            "password_repeat": CENTER_PASSWORD,
            "csrf_token": token,
        },
    )
    client.post(
        "/login",
        data={
            "username": "admin",
            "password": CENTER_PASSWORD,
            "csrf_token": token,
        },
    )
    return token


class TestCenterSetup:
    """Integrationstests fuer die Ersteinrichtung."""

    def test_ohne_konto_zeigt_einrichtung(self, client: FlaskClient) -> None:
        response = client.get("/login")
        assert response.status_code == 302
        assert "/setup" in response.headers["Location"]
        assert "Zentrale einrichten" in client.get("/setup").get_data(as_text=True)

    def test_konto_anlegen(
        self, client: FlaskClient, center_registry: CenterRegistry
    ) -> None:
        token = csrf_token(client)
        response = client.post(
            "/setup",
            data={
                "username": "admin",
                "password": CENTER_PASSWORD,
                "password_repeat": CENTER_PASSWORD,
                "csrf_token": token,
            },
        )
        assert response.status_code == 302
        assert center_registry.auth_service.administrator_exists() is True

    def test_passwoerter_muessen_uebereinstimmen(self, client: FlaskClient) -> None:
        token = csrf_token(client)
        response = client.post(
            "/setup",
            data={
                "username": "admin",
                "password": CENTER_PASSWORD,
                "password_repeat": "anders",
                "csrf_token": token,
            },
        )
        assert "alert-danger" in response.get_data(as_text=True)

    def test_schwaches_passwort(self, client: FlaskClient) -> None:
        token = csrf_token(client)
        response = client.post(
            "/setup",
            data={
                "username": "admin",
                "password": "kurz",
                "password_repeat": "kurz",
                "csrf_token": token,
            },
        )
        assert "alert-danger" in response.get_data(as_text=True)

    def test_einrichtung_nach_abschluss_gesperrt(self, client: FlaskClient) -> None:
        setup_and_login(client)
        response = client.get("/setup")
        assert response.status_code == 302


class TestCenterAuth:
    """Integrationstests fuer die Anmeldung."""

    def test_uebersicht_ohne_anmeldung_gesperrt(self, client: FlaskClient) -> None:
        response = client.get("/")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_anmelden_und_abmelden(self, client: FlaskClient) -> None:
        token = setup_and_login(client)
        assert client.get("/").status_code == 200
        response = client.post("/logout", data={"csrf_token": token})
        assert response.status_code == 302
        assert client.get("/").status_code == 302

    def test_falsches_passwort(self, client: FlaskClient) -> None:
        setup_and_login(client)
        client.post("/logout", data={"csrf_token": csrf_token(client, "/login")})
        token = csrf_token(client, "/login")
        response = client.post(
            "/login",
            data={"username": "admin", "password": "falsch", "csrf_token": token},
        )
        assert "alert-danger" in response.get_data(as_text=True)

    def test_ohne_csrf_token_abgelehnt(self, client: FlaskClient) -> None:
        setup_and_login(client)
        response = client.post("/action", data={"action": "browser_restart"})
        assert response.status_code == 400


class TestCenterDevices:
    """Integrationstests fuer die Geraeteverwaltung."""

    def test_geraet_aufnehmen(
        self,
        client: FlaskClient,
        center_registry: CenterRegistry,
        fake_device: ThreadingHTTPServer,  # noqa: F811
    ) -> None:
        token = setup_and_login(client)
        response = client.post(
            "/devices/",
            data={
                "name": "Empfang",
                "address": "127.0.0.1",
                "port": str(fake_device.server_port),
                "username": "admin",
                "password": DEVICE_PASSWORD,
                "csrf_token": token,
            },
        )
        assert "alert-success" in response.get_data(as_text=True)
        assert len(center_registry.device_service.all()) == 1

    def test_unerreichbares_geraet_wird_nicht_gespeichert(
        self, client: FlaskClient, center_registry: CenterRegistry
    ) -> None:
        token = setup_and_login(client)
        response = client.post(
            "/devices/",
            data={
                "name": "Kaputt",
                "address": "127.0.0.1",
                "port": "59982",
                "username": "admin",
                "password": DEVICE_PASSWORD,
                "csrf_token": token,
            },
        )
        assert "alert-danger" in response.get_data(as_text=True)
        assert center_registry.device_service.all() == []

    def test_falsche_zugangsdaten_werden_nicht_gespeichert(
        self,
        client: FlaskClient,
        center_registry: CenterRegistry,
        fake_device: ThreadingHTTPServer,  # noqa: F811
    ) -> None:
        token = setup_and_login(client)
        response = client.post(
            "/devices/",
            data={
                "name": "Falsch",
                "address": "127.0.0.1",
                "port": str(fake_device.server_port),
                "username": "admin",
                "password": "Falsches-Passwort!",
                "csrf_token": token,
            },
        )
        assert "alert-danger" in response.get_data(as_text=True)
        assert center_registry.device_service.all() == []

    def test_ungueltige_eingabe(self, client: FlaskClient) -> None:
        token = setup_and_login(client)
        response = client.post(
            "/devices/",
            data={
                "name": "",
                "address": "127.0.0.1",
                "port": "8080",
                "username": "admin",
                "password": DEVICE_PASSWORD,
                "csrf_token": token,
            },
        )
        assert "alert-danger" in response.get_data(as_text=True)

    def test_aendern_testen_und_entfernen(
        self,
        client: FlaskClient,
        center_registry: CenterRegistry,
        fake_device: ThreadingHTTPServer,  # noqa: F811
    ) -> None:
        token = setup_and_login(client)
        device = center_registry.device_service.add(
            "Empfang", "127.0.0.1", fake_device.server_port, "admin", DEVICE_PASSWORD
        )
        response = client.post(
            f"/devices/{device.id}",
            data={
                "name": "Foyer",
                "address": "127.0.0.1",
                "port": str(fake_device.server_port),
                "username": "admin",
                "password": "",
                "enabled": "on",
                "csrf_token": token,
            },
        )
        assert "alert-success" in response.get_data(as_text=True)
        response = client.post(f"/devices/{device.id}/test", data={"csrf_token": token})
        assert "1.1.0" in response.get_data(as_text=True)
        response = client.post(
            f"/devices/{device.id}/delete", data={"csrf_token": token}
        )
        assert "alert-success" in response.get_data(as_text=True)
        assert center_registry.device_service.all() == []

    def test_test_unbekanntes_geraet(self, client: FlaskClient) -> None:
        token = setup_and_login(client)
        response = client.post("/devices/999/test", data={"csrf_token": token})
        assert "alert-danger" in response.get_data(as_text=True)


class TestCenterFleet:
    """Integrationstests fuer Uebersicht und Massenaktionen."""

    def test_uebersicht_zeigt_geraet(
        self,
        client: FlaskClient,
        center_registry: CenterRegistry,
        fake_device: ThreadingHTTPServer,  # noqa: F811
    ) -> None:
        setup_and_login(client)
        center_registry.device_service.add(
            "Empfang", "127.0.0.1", fake_device.server_port, "admin", DEVICE_PASSWORD
        )
        body = client.get("/overview").get_data(as_text=True)
        assert "Empfang" in body
        assert "Online" in body
        assert "1.1.0" in body
        assert f'href="http://127.0.0.1:{fake_device.server_port}/"' in body
        assert 'target="_blank"' in body

    def test_leere_uebersicht(self, client: FlaskClient) -> None:
        setup_and_login(client)
        body = client.get("/overview").get_data(as_text=True)
        assert "noch keine Geräte" in body

    def test_massenaktion(
        self,
        client: FlaskClient,
        center_registry: CenterRegistry,
        fake_device: ThreadingHTTPServer,  # noqa: F811
    ) -> None:
        token = setup_and_login(client)
        erstes = center_registry.device_service.add(
            "Empfang", "127.0.0.1", fake_device.server_port, "admin", DEVICE_PASSWORD
        )
        zweites = center_registry.device_service.add(
            "Foyer", "127.0.0.1", fake_device.server_port, "admin", DEVICE_PASSWORD
        )
        response = client.post(
            "/action",
            data={
                "action": "browser_restart",
                "device_ids": [str(erstes.id), str(zweites.id)],
                "csrf_token": token,
            },
        )
        assert "alert-success" in response.get_data(as_text=True)
        assert len(fake_device.actions) == 2

    def test_aktion_ohne_auswahl(self, client: FlaskClient) -> None:
        token = setup_and_login(client)
        response = client.post(
            "/action", data={"action": "browser_restart", "csrf_token": token}
        )
        assert "mindestens ein Gerät" in response.get_data(as_text=True)

    def test_unbekannte_aktion(self, client: FlaskClient) -> None:
        token = setup_and_login(client)
        response = client.post(
            "/action", data={"action": "explodieren", "csrf_token": token}
        )
        assert "alert-danger" in response.get_data(as_text=True)

    def test_url_massenweise_setzen(
        self,
        client: FlaskClient,
        center_registry: CenterRegistry,
        fake_device: ThreadingHTTPServer,  # noqa: F811
    ) -> None:
        token = setup_and_login(client)
        device = center_registry.device_service.add(
            "Empfang", "127.0.0.1", fake_device.server_port, "admin", DEVICE_PASSWORD
        )
        response = client.post(
            "/url",
            data={
                "url": "http://server.local/neu",
                "device_ids": [str(device.id)],
                "csrf_token": token,
            },
        )
        assert "alert-success" in response.get_data(as_text=True)
        assert fake_device.actions[0][1] == {"url": "http://server.local/neu"}

    def test_url_ohne_eingabe(
        self,
        client: FlaskClient,
        center_registry: CenterRegistry,
        fake_device: ThreadingHTTPServer,  # noqa: F811
    ) -> None:
        token = setup_and_login(client)
        device = center_registry.device_service.add(
            "Empfang", "127.0.0.1", fake_device.server_port, "admin", DEVICE_PASSWORD
        )
        response = client.post(
            "/url",
            data={
                "url": "",
                "device_ids": [str(device.id)],
                "csrf_token": token,
            },
        )
        assert "alert-danger" in response.get_data(as_text=True)

    def test_unbekannte_seite_zeigt_fehlerseite(self, client: FlaskClient) -> None:
        setup_and_login(client)
        response = client.get("/gibt-es-nicht")
        assert response.status_code == 404
        assert "Traceback" not in response.get_data(as_text=True)
