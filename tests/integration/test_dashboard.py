# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Integrationstests fuer Anmeldung und Dashboard."""

from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.controllers import SESSION_CSRF_KEY
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


def csrf_token(client: FlaskClient) -> str:
    """Oeffnet die Anmeldeseite und liefert das CSRF-Token.

    Args:
        client:
            Flask-Testclient.

    Returns:
        Das CSRF-Token.
    """
    client.get("/login")
    with client.session_transaction() as session:
        token = str(session[SESSION_CSRF_KEY])
    return token


def login(client: FlaskClient) -> str:
    """Meldet den Administrator an.

    Args:
        client:
            Flask-Testclient.

    Returns:
        Das CSRF-Token der Sitzung.
    """
    token = csrf_token(client)
    client.post(
        "/login",
        data={
            "username": ADMIN_USERNAME,
            "password": VALID_PASSWORD,
            "csrf_token": token,
        },
    )
    return token


class TestLogin:
    """Integrationstests fuer die Anmeldung."""

    def test_dashboard_ohne_anmeldung_leitet_zum_login(
        self, client: FlaskClient
    ) -> None:
        response = client.get("/dashboard/")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_login_mit_falschem_passwort(self, client: FlaskClient) -> None:
        token = csrf_token(client)
        response = client.post(
            "/login",
            data={
                "username": ADMIN_USERNAME,
                "password": "Falsch-2026-Kiosk",
                "csrf_token": token,
            },
        )
        assert response.status_code == 200
        assert "alert-danger" in response.get_data(as_text=True)

    def test_login_und_logout(self, client: FlaskClient) -> None:
        token = login(client)
        response = client.get("/dashboard/")
        assert response.status_code == 200
        response = client.post("/logout", data={"csrf_token": token})
        assert response.status_code == 302
        response = client.get("/dashboard/")
        assert response.status_code == 302

    def test_logout_ohne_csrf_token(self, client: FlaskClient) -> None:
        login(client)
        response = client.post("/logout")
        assert response.status_code == 400

    def test_abgelaufene_sitzung_leitet_zur_anmeldung(
        self, client: FlaskClient
    ) -> None:
        response = client.post("/logout")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
        assert "expired=1" in response.headers["Location"]

    def test_abgelaufene_sitzung_mit_htmx_liefert_hx_redirect(
        self, client: FlaskClient
    ) -> None:
        response = client.post("/logout", headers={"HX-Request": "true"})
        assert response.status_code == 204
        assert "/login" in response.headers["HX-Redirect"]

    def test_anmeldeseite_zeigt_hinweis_nach_sitzungsablauf(
        self, client: FlaskClient
    ) -> None:
        response = client.get("/login?expired=1")
        assert "abgelaufen" in response.get_data(as_text=True)

    def test_offener_redirect_wird_verhindert(self, client: FlaskClient) -> None:
        token = csrf_token(client)
        response = client.post(
            "/login?next=https://boese.example.org",
            data={
                "username": ADMIN_USERNAME,
                "password": VALID_PASSWORD,
                "csrf_token": token,
            },
        )
        assert response.status_code == 302
        assert response.headers["Location"].startswith("/dashboard")


class TestDashboard:
    """Integrationstests fuer die Dashboard-Kacheln."""

    def test_dashboard_zeigt_kacheln(self, client: FlaskClient) -> None:
        login(client)
        body = client.get("/dashboard/").get_data(as_text=True)
        for element_id in (
            "dashboard-data",
            "browser-tile",
            "url-tile",
            "hostname-tile",
            "wifi-tile",
            "system-tile",
            "log-viewer",
        ):
            assert element_id in body

    def test_datenfragment(self, client: FlaskClient) -> None:
        login(client)
        response = client.get("/dashboard/data")
        assert response.status_code == 200
        assert "CPU" in response.get_data(as_text=True)

    def test_browser_start_und_stopp(
        self, client: FlaskClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(browser_module.subprocess, "Popen", FakeProcess)
        monkeypatch.setattr(browser_module.shutil, "which", lambda name: FAKE_BINARY)
        token = login(client)
        response = client.post("/dashboard/browser/start", data={"csrf_token": token})
        assert "text-bg-success" in response.get_data(as_text=True)
        response = client.post("/dashboard/browser/stop", data={"csrf_token": token})
        assert "alert-success" in response.get_data(as_text=True)

    def test_url_speichern(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        http_status_server: str,
    ) -> None:
        token = login(client)
        response = client.post(
            "/dashboard/url/save",
            data={"url": f"{http_status_server}/ok", "csrf_token": token},
        )
        assert "alert-success" in response.get_data(as_text=True)
        config = registry.config_service.load()
        assert config["url"] == f"{http_status_server}/ok"

    def test_ungueltige_url_wird_nicht_gespeichert(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        http_status_server: str,
    ) -> None:
        token = login(client)
        response = client.post(
            "/dashboard/url/save",
            data={"url": f"{http_status_server}/fehlt", "csrf_token": token},
        )
        assert "alert-danger" in response.get_data(as_text=True)
        assert registry.config_service.load()["url"] == ""

    def test_hostname_speichern(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(registry.hostname_service, "apply", lambda hostname: None)
        token = login(client)
        response = client.post(
            "/dashboard/hostname",
            data={"hostname": "pikiosk-neu", "csrf_token": token},
        )
        assert "alert-success" in response.get_data(as_text=True)
        assert registry.config_service.load()["hostname"] == "pikiosk-neu"

    def test_logansicht_und_download(self, client: FlaskClient) -> None:
        login(client)
        response = client.get("/dashboard/system/logs/system")
        assert response.status_code == 200
        response = client.get("/dashboard/system/logs/unbekannt")
        assert response.status_code == 404
        response = client.get("/dashboard/system/logs/system/download")
        assert response.status_code in (200, 404)

    def test_systemaktion_mit_fehler(
        self, client: FlaskClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services import system_service as system_module

        def fake_run(command: list[str], **kwargs: object) -> object:
            class Result:
                returncode = 1
                stderr = "keine Rechte"
                stdout = ""

            return Result()

        monkeypatch.setattr(system_module.subprocess, "run", fake_run)
        token = login(client)
        response = client.post("/dashboard/system/reboot", data={"csrf_token": token})
        assert "alert-danger" in response.get_data(as_text=True)


class TestBackupTile:
    """Integrationstests fuer Sicherung und Wiederherstellung."""

    def test_kachel_ohne_anmeldung_gesperrt(self, client: FlaskClient) -> None:
        response = client.get("/dashboard/backup/")
        assert response.status_code == 302

    def test_erstellen_auflisten_und_wiederherstellen(
        self, client: FlaskClient, registry: ServiceRegistry
    ) -> None:
        token = login(client)
        response = client.post("/dashboard/backup/create", data={"csrf_token": token})
        assert "alert-success" in response.get_data(as_text=True)
        backups = registry.backup_service.list_backups()
        assert len(backups) == 1
        name = backups[0]["name"]
        tile = client.get("/dashboard/backup/").get_data(as_text=True)
        assert name in tile
        config = registry.config_service.load()
        config["hostname"] = "Geaendert"
        registry.config_service.save(config)
        response = client.post(
            f"/dashboard/restore/file/{name}", data={"csrf_token": token}
        )
        assert "alert-success" in response.get_data(as_text=True)
        assert registry.config_service.load()["hostname"] == "PiKiosk"

    def test_download(self, client: FlaskClient, registry: ServiceRegistry) -> None:
        login(client)
        name = registry.backup_service.create().name
        response = client.get(f"/dashboard/backup/download/{name}")
        assert response.status_code == 200
        assert response.data[:2] == b"PK"
        response = client.get("/dashboard/backup/download/boese.zip")
        assert response.status_code == 404

    def test_upload_wiederherstellung(
        self, client: FlaskClient, registry: ServiceRegistry
    ) -> None:
        token = login(client)
        backup_path = registry.backup_service.create()
        config = registry.config_service.load()
        config["hostname"] = "Geaendert"
        registry.config_service.save(config)
        with backup_path.open("rb") as handle:
            response = client.post(
                "/dashboard/restore/upload",
                data={
                    "csrf_token": token,
                    "backup_file": (handle, backup_path.name),
                },
                content_type="multipart/form-data",
            )
        assert "alert-success" in response.get_data(as_text=True)
        assert registry.config_service.load()["hostname"] == "PiKiosk"

    def test_upload_ohne_datei(self, client: FlaskClient) -> None:
        token = login(client)
        response = client.post("/dashboard/restore/upload", data={"csrf_token": token})
        assert "alert-danger" in response.get_data(as_text=True)

    def test_usb_fragment(self, client: FlaskClient) -> None:
        login(client)
        response = client.get("/dashboard/backup/usb")
        assert response.status_code == 200


class TestAppearanceTile:
    """Integrationstests fuer die Darstellungs-Kachel."""

    def test_dashboard_zeigt_darstellungs_kachel(self, client: FlaskClient) -> None:
        login(client)
        body = client.get("/dashboard/").get_data(as_text=True)
        assert "appearance-tile" in body
        assert 'data-theme-mode="dark"' in body

    def test_sprache_und_theme_umschalten(
        self, client: FlaskClient, registry: ServiceRegistry
    ) -> None:
        token = login(client)
        response = client.post(
            "/dashboard/appearance",
            data={"language": "en", "theme": "auto", "csrf_token": token},
        )
        assert response.status_code == 200
        assert response.headers.get("HX-Refresh") == "true"
        config = registry.config_service.load()
        assert config["language"] == "en"
        assert config["theme"] == "auto"
        body = client.get("/dashboard/").get_data(as_text=True)
        assert 'lang="en"' in body
        assert 'data-theme-mode="auto"' in body
        assert "Appearance" in body

    def test_ungueltiges_theme_wird_abgelehnt(
        self, client: FlaskClient, registry: ServiceRegistry
    ) -> None:
        token = login(client)
        response = client.post(
            "/dashboard/appearance",
            data={"language": "de", "theme": "neon", "csrf_token": token},
        )
        assert response.status_code == 200
        assert "alert-danger" in response.get_data(as_text=True)
        assert registry.config_service.load()["theme"] == "dark"


class TestUpdateTile:
    """Integrationstests fuer die Update-Kachel."""

    def test_kachel_ohne_anmeldung_gesperrt(self, client: FlaskClient) -> None:
        response = client.get("/dashboard/update/")
        assert response.status_code == 302

    def test_kachel_zeigt_version(self, client: FlaskClient) -> None:
        login(client)
        from app.constants import APP_VERSION

        body = client.get("/dashboard/update/").get_data(as_text=True)
        assert APP_VERSION in body

    def test_check_ohne_release(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(registry.update_service, "_github_latest", lambda: None)
        token = login(client)
        response = client.post("/dashboard/update/check", data={"csrf_token": token})
        assert response.status_code == 200
        assert "GitHub-Release" in response.get_data(as_text=True)

    def test_check_zeigt_verfuegbares_update(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            registry.update_service,
            "_github_latest",
            lambda: {"tag_name": "v9.9.0", "tarball_url": "https://example.org/a.tgz"},
        )
        token = login(client)
        response = client.post("/dashboard/update/check", data={"csrf_token": token})
        assert "9.9.0" in response.get_data(as_text=True)

    def test_upload_installiert_paket(
        self, client: FlaskClient, registry: ServiceRegistry, tmp_path: Path
    ) -> None:
        import zipfile

        package = tmp_path / "pkg.zip"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("app/constants.py", 'APP_VERSION: str = "9.9.0"\n')
            archive.writestr("app/__init__.py", "# init\n")
            archive.writestr("requirements.txt", "Flask\n")
            archive.writestr("marker.txt", "installiert")
        token = login(client)
        with package.open("rb") as handle:
            response = client.post(
                "/dashboard/update/upload",
                data={"csrf_token": token, "update_file": (handle, "pkg.zip")},
                content_type="multipart/form-data",
            )
        assert "alert-success" in response.get_data(as_text=True)
        assert (registry.update_service._install_dir / "marker.txt").exists()

    def test_upload_ohne_datei(self, client: FlaskClient) -> None:
        token = login(client)
        response = client.post("/dashboard/update/upload", data={"csrf_token": token})
        assert "alert-danger" in response.get_data(as_text=True)

    def test_rollback_ohne_stand(self, client: FlaskClient) -> None:
        token = login(client)
        response = client.post("/dashboard/update/rollback", data={"csrf_token": token})
        assert "alert-danger" in response.get_data(as_text=True)


class TestInternalRestart:
    """Integrationstests fuer den internen Watchdog-Endpunkt."""

    def test_neustart_mit_gueltigem_token(
        self,
        client: FlaskClient,
        flask_app: Flask,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(browser_module.subprocess, "Popen", FakeProcess)
        monkeypatch.setattr(browser_module.shutil, "which", lambda name: FAKE_BINARY)
        response = client.post(
            "/internal/browser/restart",
            headers={"X-Watchdog-Token": flask_app.config["SECRET_KEY"]},
        )
        assert response.status_code == 200
        assert response.get_json()["restarted"] is True

    def test_laufender_browser_wird_nicht_angefasst(
        self,
        client: FlaskClient,
        flask_app: Flask,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(browser_module.subprocess, "Popen", FakeProcess)
        monkeypatch.setattr(browser_module.shutil, "which", lambda name: FAKE_BINARY)
        registry.browser_service.start("https://example.org/")
        response = client.post(
            "/internal/browser/restart",
            headers={"X-Watchdog-Token": flask_app.config["SECRET_KEY"]},
        )
        assert response.status_code == 200
        assert response.get_json()["restarted"] is False

    def test_falsches_token_wird_abgelehnt(self, client: FlaskClient) -> None:
        response = client.post(
            "/internal/browser/restart",
            headers={"X-Watchdog-Token": "falsches-token"},
        )
        assert response.status_code == 403

    def test_fehlendes_token_wird_abgelehnt(self, client: FlaskClient) -> None:
        response = client.post("/internal/browser/restart")
        assert response.status_code == 403
