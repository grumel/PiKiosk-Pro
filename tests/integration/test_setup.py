# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Integrationstests fuer den Setup-Wizard."""

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.controllers import SESSION_CSRF_KEY
from app.extensions import ServiceRegistry

VALID_PASSWORD = "Sicher-2026-Kiosk"


@pytest.fixture
def flask_app(registry: ServiceRegistry) -> Flask:
    """Erzeugt die Flask-Anwendung im Ersteinrichtungszustand.

    Args:
        registry:
            ServiceRegistry mit temporaeren Datenpfaden.

    Returns:
        Die initialisierte Flask-Anwendung.
    """
    application = create_app(registry)
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(flask_app: Flask) -> FlaskClient:
    """Erzeugt einen Testclient.

    Args:
        flask_app:
            Die Flask-Anwendung.

    Returns:
        Ein Flask-Testclient.
    """
    return flask_app.test_client()


def csrf_token(client: FlaskClient) -> str:
    """Oeffnet den Wizard und liefert das CSRF-Token der Sitzung.

    Args:
        client:
            Flask-Testclient.

    Returns:
        Das CSRF-Token.
    """
    client.get("/setup/")
    with client.session_transaction() as session:
        token = str(session[SESSION_CSRF_KEY])
    return token


class TestSetupWizard:
    """Integrationstests fuer den kompletten Wizard-Ablauf."""

    def test_erststart_leitet_zum_wizard(self, client: FlaskClient) -> None:
        response = client.get("/")
        assert response.status_code == 302
        assert "/setup" in response.headers["Location"]

    def test_wizard_zeigt_willkommensseite(self, client: FlaskClient) -> None:
        response = client.get("/setup/")
        assert response.status_code == 200
        assert "Willkommen" in response.get_data(as_text=True)

    def test_post_ohne_csrf_token_wird_abgelehnt(self, client: FlaskClient) -> None:
        client.get("/setup/")
        response = client.post("/setup/hostname", data={"hostname": "kiosk"})
        assert response.status_code == 400

    def test_ungueltiger_hostname_zeigt_fehler(self, client: FlaskClient) -> None:
        token = csrf_token(client)
        response = client.post(
            "/setup/hostname",
            data={"hostname": "kiosk_01", "csrf_token": token},
        )
        assert response.status_code == 200
        assert "alert-danger" in response.get_data(as_text=True)

    def test_gueltiger_hostname_wird_uebernommen(self, client: FlaskClient) -> None:
        token = csrf_token(client)
        response = client.post(
            "/setup/hostname",
            data={"hostname": "pikiosk-test", "csrf_token": token},
        )
        assert response.status_code == 200
        assert "alert-success" in response.get_data(as_text=True)

    def test_schwaches_passwort_zeigt_regeln(self, client: FlaskClient) -> None:
        token = csrf_token(client)
        response = client.post(
            "/setup/admin",
            data={
                "username": "admin",
                "password": "kurz",
                "password_repeat": "kurz",
                "csrf_token": token,
            },
        )
        body = response.get_data(as_text=True)
        assert "alert-danger" in body

    def test_passwort_wiederholung_muss_stimmen(self, client: FlaskClient) -> None:
        token = csrf_token(client)
        response = client.post(
            "/setup/admin",
            data={
                "username": "admin",
                "password": VALID_PASSWORD,
                "password_repeat": "anders",
                "csrf_token": token,
            },
        )
        assert "alert-danger" in response.get_data(as_text=True)

    def test_ungueltige_url_zeigt_fehler(
        self, client: FlaskClient, http_status_server: str
    ) -> None:
        token = csrf_token(client)
        response = client.post(
            "/setup/url",
            data={"url": f"{http_status_server}/fehlt", "csrf_token": token},
        )
        assert "alert-danger" in response.get_data(as_text=True)

    def test_kompletter_ablauf(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        http_status_server: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(registry.hostname_service, "apply", lambda hostname: None)
        token = csrf_token(client)
        client.post(
            "/setup/hostname",
            data={"hostname": "pikiosk-test", "csrf_token": token},
        )
        client.post(
            "/setup/admin",
            data={
                "username": "admin",
                "password": VALID_PASSWORD,
                "password_repeat": VALID_PASSWORD,
                "csrf_token": token,
            },
        )
        client.post(
            "/setup/url",
            data={"url": f"{http_status_server}/ok", "csrf_token": token},
        )
        response = client.post("/setup/install", data={"csrf_token": token})
        assert response.status_code == 200
        assert "alert-success" in response.get_data(as_text=True)
        config = registry.config_service.load()
        assert config["first_start"] is False
        assert config["hostname"] == "pikiosk-test"
        assert config["url"] == f"{http_status_server}/ok"
        assert registry.auth_service.administrator_exists() is True
        response = client.get("/setup/")
        assert response.status_code == 302

    def test_installation_ohne_daten_zeigt_fehler(self, client: FlaskClient) -> None:
        token = csrf_token(client)
        response = client.post("/setup/install", data={"csrf_token": token})
        assert response.status_code == 200
        assert "alert-danger" in response.get_data(as_text=True)

    def test_fehlgeschlagene_kontoanlage_sperrt_wizard_nicht(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        http_status_server: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.exceptions import AuthenticationError

        monkeypatch.setattr(registry.hostname_service, "apply", lambda hostname: None)

        def fail_create(username: str, password_hash: str) -> None:
            raise AuthenticationError("Datenbank nicht verfuegbar")

        monkeypatch.setattr(registry.auth_service, "create_administrator", fail_create)
        token = csrf_token(client)
        client.post(
            "/setup/hostname",
            data={"hostname": "pikiosk-test", "csrf_token": token},
        )
        client.post(
            "/setup/admin",
            data={
                "username": "admin",
                "password": VALID_PASSWORD,
                "password_repeat": VALID_PASSWORD,
                "csrf_token": token,
            },
        )
        client.post(
            "/setup/url",
            data={"url": f"{http_status_server}/ok", "csrf_token": token},
        )
        response = client.post("/setup/install", data={"csrf_token": token})
        assert "alert-danger" in response.get_data(as_text=True)
        assert registry.config_service.load()["first_start"] is True
        assert client.get("/setup/").status_code == 200

    def test_sprachwahl_im_wizard(
        self, client: FlaskClient, registry: ServiceRegistry
    ) -> None:
        token = csrf_token(client)
        response = client.post(
            "/setup/language",
            data={"language": "en", "csrf_token": token},
        )
        assert response.status_code == 200
        assert "Welcome to PiKiosk Pro" in response.get_data(as_text=True)
        assert registry.config_service.load()["language"] == "en"
        response = client.post(
            "/setup/language",
            data={"language": "de", "csrf_token": token},
        )
        assert "Willkommen bei PiKiosk Pro" in response.get_data(as_text=True)


class TestWizardWifi:
    """Integrationstests fuer den WLAN-Schritt des Wizards."""

    def test_wifi_schritt_mit_verbindung(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        network = registry.network_service
        monkeypatch.setattr(
            network,
            "current",
            lambda: {"ssid": "Zuhause", "signal": 66, "security": "WPA2"},
        )
        monkeypatch.setattr(network, "ip", lambda: "10.0.0.2")
        monkeypatch.setattr(network, "gateway", lambda: "10.0.0.1")
        monkeypatch.setattr(network, "dns", lambda: ["10.0.0.1"])
        client.get("/setup/")
        body = client.get("/setup/step/wifi").get_data(as_text=True)
        assert "Zuhause" in body
        assert "10.0.0.2" in body

    def test_wifi_scan_und_verbinden(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:

        network = registry.network_service
        monkeypatch.setattr(
            network,
            "scan",
            lambda: [
                {
                    "ssid": "Netz-A",
                    "signal": 90,
                    "security": "WPA2",
                    "frequency": "5180 MHz",
                }
            ],
        )
        monkeypatch.setattr(network, "connect", lambda ssid, password: None)
        monkeypatch.setattr(
            network,
            "current",
            lambda: {"ssid": "Netz-A", "signal": 90, "security": "WPA2"},
        )
        monkeypatch.setattr(network, "ip", lambda: "10.0.0.3")
        monkeypatch.setattr(network, "gateway", lambda: "10.0.0.1")
        monkeypatch.setattr(network, "dns", lambda: ["10.0.0.1"])
        token = csrf_token(client)
        response = client.post("/setup/wifi/scan", data={"csrf_token": token})
        assert "Netz-A" in response.get_data(as_text=True)
        response = client.post(
            "/setup/wifi/connect",
            data={"ssid": "Netz-A", "password": "geheim", "csrf_token": token},
        )
        assert "alert-success" in response.get_data(as_text=True)

    def test_wifi_scan_fehler(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.exceptions import NetworkError

        monkeypatch.setattr(
            registry.network_service,
            "scan",
            lambda: (_ for _ in ()).throw(NetworkError("nmcli kaputt")),
        )
        token = csrf_token(client)
        response = client.post("/setup/wifi/scan", data={"csrf_token": token})
        assert "alert-danger" in response.get_data(as_text=True)

    def test_wifi_falsches_passwort(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.exceptions import WifiError

        def fail_connect(ssid: str, password: str) -> None:
            raise WifiError("secrets", reason="wrong_password")

        monkeypatch.setattr(registry.network_service, "connect", fail_connect)
        monkeypatch.setattr(registry.network_service, "current", lambda: None)
        token = csrf_token(client)
        response = client.post(
            "/setup/wifi/connect",
            data={"ssid": "Netz-A", "password": "falsch", "csrf_token": token},
        )
        assert "WLAN-Passwort ist falsch" in response.get_data(as_text=True)


class TestHostnameTaken:
    """Integrationstests fuer die Hostname-Vergabepruefung."""

    def test_vergebener_hostname_wird_abgelehnt(
        self, client: FlaskClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services import hostname_service as hostname_module

        monkeypatch.setattr(
            hostname_module.socket, "gethostbyname", lambda host: "203.0.113.5"
        )
        monkeypatch.setattr(hostname_module, "local_ip_address", lambda: "10.0.0.9")
        token = csrf_token(client)
        response = client.post(
            "/setup/hostname",
            data={"hostname": "belegter-name", "csrf_token": token},
        )
        assert "bereits vergeben" in response.get_data(as_text=True)

    def test_eigene_aufloesung_ist_kein_konflikt(
        self, client: FlaskClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services import hostname_service as hostname_module

        monkeypatch.setattr(
            hostname_module.socket, "gethostbyname", lambda host: "10.0.0.9"
        )
        monkeypatch.setattr(hostname_module, "local_ip_address", lambda: "10.0.0.9")
        token = csrf_token(client)
        response = client.post(
            "/setup/hostname",
            data={"hostname": "freier-name", "csrf_token": token},
        )
        assert "alert-success" in response.get_data(as_text=True)
