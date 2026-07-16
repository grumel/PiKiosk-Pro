# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Integrationstests fuer die REST API."""

from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.constants import APP_VERSION
from app.extensions import ServiceRegistry
from app.services import browser_service as browser_module
from tests.unit.test_browser_service import FAKE_BINARY, FakeProcess

VALID_PASSWORD = "Sicher-2026-Kiosk"
ADMIN_USERNAME = "admin"


@pytest.fixture
def flask_app(registry: ServiceRegistry) -> Flask:
    """Erzeugt die Flask-Anwendung mit Administrator und Abschluss.

    Args:
        registry:
            ServiceRegistry mit temporaeren Datenpfaden.

    Returns:
        Die initialisierte Flask-Anwendung.
    """
    application = create_app(registry)
    application.config["TESTING"] = True
    config = registry.config_service.load()
    config["first_start"] = False
    registry.config_service.save(config)
    password_hash = registry.auth_service.hash_password(VALID_PASSWORD)
    registry.auth_service.create_administrator(ADMIN_USERNAME, password_hash)
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


def bearer(client: FlaskClient) -> dict[str, str]:
    """Holt ein JWT und baut den Authorization-Header.

    Args:
        client:
            Flask-Testclient.

    Returns:
        Header-Woerterbuch mit Bearer-Token.
    """
    response = client.post(
        "/api/token",
        json={"username": ADMIN_USERNAME, "password": VALID_PASSWORD},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


class TestToken:
    """Integrationstests fuer die Token-Ausgabe."""

    def test_token_mit_gueltigen_anmeldedaten(self, client: FlaskClient) -> None:
        response = client.post(
            "/api/token",
            json={"username": ADMIN_USERNAME, "password": VALID_PASSWORD},
        )
        payload = response.get_json()
        assert response.status_code == 200
        assert payload["token_type"] == "Bearer"
        assert payload["token"].count(".") == 2

    def test_token_mit_falschem_passwort(self, client: FlaskClient) -> None:
        response = client.post(
            "/api/token",
            json={"username": ADMIN_USERNAME, "password": "falsch"},
        )
        assert response.status_code == 401
        assert response.get_json()["error"] == "invalid_credentials"

    def test_token_ohne_koerper(self, client: FlaskClient) -> None:
        response = client.post("/api/token")
        assert response.status_code == 401


class TestAuthentication:
    """Integrationstests fuer den Endpunktschutz."""

    def test_ohne_token_401(self, client: FlaskClient) -> None:
        for path in ("/api/status", "/api/version", "/api/settings", "/api/logs"):
            response = client.get(path)
            assert response.status_code == 401
            assert response.get_json()["error"] == "unauthorized"

    def test_mit_kaputtem_token_401(self, client: FlaskClient) -> None:
        response = client.get("/api/status", headers={"Authorization": "Bearer kaputt"})
        assert response.status_code == 401

    def test_unbekannter_pfad_liefert_json(self, client: FlaskClient) -> None:
        response = client.get("/api/gibt-es-nicht", headers=bearer(client))
        assert response.status_code == 404
        assert response.get_json()["error"] == "not_found"


class TestStatusAndVersion:
    """Integrationstests fuer Status und Version."""

    def test_version(self, client: FlaskClient) -> None:
        response = client.get("/api/version", headers=bearer(client))
        assert response.status_code == 200
        assert response.get_json()["version"] == APP_VERSION

    def test_status(self, client: FlaskClient) -> None:
        response = client.get("/api/status", headers=bearer(client))
        payload = response.get_json()
        assert response.status_code == 200
        assert payload["browser_status"] == "not_started"
        assert payload["version"] == APP_VERSION


class TestBrowserApi:
    """Integrationstests fuer die Browsersteuerung."""

    def test_start_und_stopp(
        self, client: FlaskClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(browser_module.subprocess, "Popen", FakeProcess)
        monkeypatch.setattr(browser_module.shutil, "which", lambda name: FAKE_BINARY)
        headers = bearer(client)
        response = client.post(
            "/api/browser", json={"action": "start"}, headers=headers
        )
        assert response.get_json()["status"] == "running"
        response = client.post("/api/browser", json={"action": "stop"}, headers=headers)
        assert response.get_json()["status"] == "not_started"

    def test_ungueltige_aktion(self, client: FlaskClient) -> None:
        response = client.post(
            "/api/browser", json={"action": "explode"}, headers=bearer(client)
        )
        assert response.status_code == 400

    def test_fehler_als_json(self, client: FlaskClient) -> None:
        response = client.post(
            "/api/browser", json={"action": "restart"}, headers=bearer(client)
        )
        assert response.status_code == 400
        assert "error" in response.get_json()


class TestSettingsApi:
    """Integrationstests fuer die Einstellungen."""

    def test_get_settings(self, client: FlaskClient) -> None:
        response = client.get("/api/settings", headers=bearer(client))
        assert response.status_code == 200
        assert response.get_json()["language"] == "de"

    def test_put_settings(self, client: FlaskClient, registry: ServiceRegistry) -> None:
        response = client.put(
            "/api/settings",
            json={"url": "https://example.org/", "theme": "light"},
            headers=bearer(client),
        )
        assert response.status_code == 200
        config = registry.config_service.load()
        assert config["url"] == "https://example.org/"
        assert config["theme"] == "light"

    def test_put_ungueltiger_wert(
        self, client: FlaskClient, registry: ServiceRegistry
    ) -> None:
        response = client.put(
            "/api/settings", json={"theme": "neon"}, headers=bearer(client)
        )
        assert response.status_code == 400
        assert registry.config_service.load()["theme"] == "dark"

    def test_put_unbekannter_schluessel(self, client: FlaskClient) -> None:
        response = client.put(
            "/api/settings",
            json={"url": "https://example.org/", "boese": 1},
            headers=bearer(client),
        )
        assert response.status_code == 400

    def test_put_ohne_schluessel(self, client: FlaskClient) -> None:
        response = client.put("/api/settings", json={}, headers=bearer(client))
        assert response.status_code == 400


class TestSystemApi:
    """Integrationstests fuer Systemaktionen."""

    def test_reboot(self, client: FlaskClient, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.services import system_service as system_module

        calls: list[list[str]] = []

        class Result:
            returncode = 0
            stderr = ""
            stdout = ""

        def fake_run(command: list[str], **kwargs: object) -> Result:
            calls.append(command)
            return Result()

        monkeypatch.setattr(system_module.subprocess, "run", fake_run)
        response = client.post(
            "/api/system", json={"action": "reboot"}, headers=bearer(client)
        )
        assert response.status_code == 200
        assert response.get_json()["accepted"] is True
        assert calls[0][-2:] == ["systemctl", "reboot"]

    def test_watchdog_status(self, client: FlaskClient) -> None:
        response = client.get("/api/system", headers=bearer(client))
        assert response.status_code == 200
        assert "watchdog_state" in response.get_json()


class TestUpdateApi:
    """Integrationstests fuer die Aktualisierung."""

    def test_get_update(self, client: FlaskClient) -> None:
        response = client.get("/api/update", headers=bearer(client))
        payload = response.get_json()
        assert payload["current"] == APP_VERSION
        assert payload["can_rollback"] is False

    def test_check(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(registry.update_service, "_github_latest", lambda: None)
        response = client.post(
            "/api/update", json={"action": "check"}, headers=bearer(client)
        )
        assert response.get_json()["status"] == "no_release"

    def test_rollback_ohne_stand(self, client: FlaskClient) -> None:
        response = client.post(
            "/api/update", json={"action": "rollback"}, headers=bearer(client)
        )
        assert response.status_code == 400


class TestBackupApi:
    """Integrationstests fuer Sicherungen."""

    def test_erstellen_auflisten_und_herunterladen(self, client: FlaskClient) -> None:
        headers = bearer(client)
        response = client.post(
            "/api/backup", json={"include_logs": False}, headers=headers
        )
        assert response.status_code == 200
        name = response.get_json()["name"]
        response = client.get("/api/backup", headers=headers)
        assert response.get_json()["backups"][0]["name"] == name
        response = client.get(f"/api/backup/{name}", headers=headers)
        assert response.status_code == 200
        assert response.data[:2] == b"PK"

    def test_unbekannte_sicherung(self, client: FlaskClient) -> None:
        response = client.get("/api/backup/boese.zip", headers=bearer(client))
        assert response.status_code == 404


class TestLogsApi:
    """Integrationstests fuer Logdateien."""

    def test_liste_und_inhalt(self, client: FlaskClient) -> None:
        headers = bearer(client)
        response = client.get("/api/logs", headers=headers)
        names = {entry["name"] for entry in response.get_json()["logs"]}
        assert {"system", "browser", "watchdog"} <= names
        response = client.get("/api/logs/system", headers=headers)
        assert response.status_code == 200
        assert isinstance(response.get_json()["lines"], list)

    def test_unbekanntes_log(self, client: FlaskClient) -> None:
        response = client.get("/api/logs/unbekannt", headers=bearer(client))
        assert response.status_code == 404


class TestNetworkApi:
    """Integrationstests fuer die Netzwerkverwaltung."""

    def test_get_network(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        outputs = {
            ("-t", "-f", "ACTIVE,SSID,SIGNAL,SECURITY", "device", "wifi"): (
                "yes:Zuhause:80:WPA2\n"
            ),
            ("-t", "-f", "DEVICE,TYPE", "device"): "wlan0:wifi\n",
            ("-t", "-f", "NAME,TYPE", "connection", "show"): (
                "Zuhause:802-11-wireless\n"
            ),
        }

        def fake_run(arguments: list[str]) -> str:
            key = tuple(arguments)
            if key in outputs:
                return outputs[key]
            if arguments[:2] == ["-t", "-f"] and "show" in arguments:
                return "IP4.ADDRESS[1]:10.0.0.2/24\n"
            return ""

        monkeypatch.setattr(registry.network_service, "_run", fake_run)
        response = client.get("/api/network", headers=bearer(client))
        payload = response.get_json()
        assert response.status_code == 200
        assert payload["connected"]["ssid"] == "Zuhause"
        assert payload["saved"] == ["Zuhause"]

    def test_delete_unbekanntes_profil(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(registry.network_service, "saved", lambda: ["Zuhause"])
        response = client.delete("/api/network/profiles/Fremd", headers=bearer(client))
        assert response.status_code == 404


class TestSetupGate:
    """Integrationstests fuer die API waehrend der Ersteinrichtung."""

    def test_api_wird_nicht_zum_wizard_umgeleitet(
        self, client: FlaskClient, registry: ServiceRegistry
    ) -> None:
        headers = bearer(client)
        config = registry.config_service.load()
        config["first_start"] = True
        registry.config_service.save(config)
        response = client.get("/api/version", headers=headers)
        assert response.status_code == 200
        assert response.get_json()["version"] == APP_VERSION


class TestApiBranches:
    """Integrationstests fuer weitere API-Pfade."""

    def test_browser_clear_cache(self, client: FlaskClient) -> None:
        response = client.post(
            "/api/browser", json={"action": "clear_cache"}, headers=bearer(client)
        )
        assert response.status_code == 200
        assert response.get_json()["status"] == "not_started"

    def test_browser_reload_ohne_browser(self, client: FlaskClient) -> None:
        response = client.post(
            "/api/browser", json={"action": "reload"}, headers=bearer(client)
        )
        assert response.status_code == 400

    def test_settings_hostname_wird_angewendet(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        applied: list[str] = []
        monkeypatch.setattr(
            registry.hostname_service, "set", lambda hostname: applied.append(hostname)
        )
        response = client.put(
            "/api/settings", json={"hostname": "api-kiosk"}, headers=bearer(client)
        )
        assert response.status_code == 200
        assert applied == ["api-kiosk"]
        assert registry.config_service.load()["hostname"] == "api-kiosk"

    def test_network_aktionen(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        network = registry.network_service
        monkeypatch.setattr(network, "scan", lambda: [{"ssid": "Netz-A"}])
        monkeypatch.setattr(network, "connect", lambda ssid, password: None)
        monkeypatch.setattr(network, "disconnect", lambda: None)
        monkeypatch.setattr(network, "current", lambda: {"ssid": "Netz-A"})
        headers = bearer(client)
        response = client.post("/api/network", json={"action": "scan"}, headers=headers)
        assert response.get_json()["networks"][0]["ssid"] == "Netz-A"
        response = client.post(
            "/api/network",
            json={"action": "connect", "ssid": "Netz-A", "password": "x"},
            headers=headers,
        )
        assert response.get_json()["connected"]["ssid"] == "Netz-A"
        response = client.post(
            "/api/network", json={"action": "disconnect"}, headers=headers
        )
        assert response.status_code == 200
        response = client.post(
            "/api/network", json={"action": "explode"}, headers=headers
        )
        assert response.status_code == 400

    def test_network_profil_loeschen(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        profiles = ["Zuhause", "Buero"]
        network = registry.network_service
        monkeypatch.setattr(network, "saved", lambda: list(profiles))
        monkeypatch.setattr(network, "delete", lambda name: profiles.remove(name))
        response = client.delete("/api/network/profiles/Buero", headers=bearer(client))
        assert response.status_code == 200
        assert response.get_json()["deleted"] == "Buero"

    def test_system_shutdown_und_statusdatei(
        self,
        client: FlaskClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import json as json_module

        from app.api import system as system_api
        from app.services import system_service as system_module

        status_file = tmp_path / "watchdog_status.json"
        status_file.write_text(json_module.dumps({"overall": "online"}))
        monkeypatch.setattr(system_api, "WATCHDOG_STATUS_FILE", status_file)
        headers = bearer(client)
        response = client.get("/api/system", headers=headers)
        assert response.get_json()["watchdog"]["overall"] == "online"

        class Result:
            returncode = 0
            stderr = ""
            stdout = ""

        monkeypatch.setattr(system_module.subprocess, "run", lambda *a, **k: Result())
        response = client.post(
            "/api/system", json={"action": "shutdown"}, headers=headers
        )
        assert response.get_json()["accepted"] is True
        response = client.post(
            "/api/system", json={"action": "explode"}, headers=headers
        )
        assert response.status_code == 400

    def test_update_install_und_rollback(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            registry.update_service, "apply_github", lambda: {"version": "9.9.9"}
        )
        monkeypatch.setattr(
            registry.update_service, "rollback", lambda: {"version": "0.1.0"}
        )
        headers = bearer(client)
        response = client.post(
            "/api/update", json={"action": "install"}, headers=headers
        )
        assert response.get_json()["version"] == "9.9.9"
        response = client.post(
            "/api/update", json={"action": "rollback"}, headers=headers
        )
        assert response.get_json()["version"] == "0.1.0"
        response = client.post(
            "/api/update", json={"action": "explode"}, headers=headers
        )
        assert response.status_code == 400
