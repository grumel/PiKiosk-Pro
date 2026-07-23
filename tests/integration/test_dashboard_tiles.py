# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Integrationstests fuer weitere Dashboard-Kacheln.

Deckt WLAN-Kachel, Einstellungs- und Wiederherstellungsfehlerfaelle
sowie Browser-, Update- und interne Endpunkte ab. Alle
Netzwerkzugriffe sind durch Ersatzobjekte ersetzt.
"""

from pathlib import Path
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.exceptions import NetworkError, UpdateError, WifiError
from app.extensions import ServiceRegistry
from app.services import browser_service as browser_module
from tests.integration.test_dashboard import flask_app, login  # noqa: F401
from tests.unit.test_browser_service import FAKE_BINARY, FakeProcess

CONNECTION = {"ssid": "Zuhause", "signal": 70, "security": "WPA2"}


@pytest.fixture
def client(flask_app: Flask) -> FlaskClient:  # noqa: F811
    """Erzeugt einen Testclient.

    Args:
        flask_app:
            Die Flask-Anwendung.

    Returns:
        Ein Flask-Testclient.
    """
    return flask_app.test_client()


def mock_wifi(
    registry: ServiceRegistry,
    monkeypatch: pytest.MonkeyPatch,
    connected: bool = True,
) -> None:
    """Ersetzt die WLAN-Abfragen durch feste Werte.

    Args:
        registry:
            ServiceRegistry mit temporaeren Datenpfaden.

        monkeypatch:
            Pytest-Patchwerkzeug.

        connected:
            True, wenn eine aktive Verbindung simuliert wird.
    """
    network = registry.network_service
    monkeypatch.setattr(
        network, "current", lambda: dict(CONNECTION) if connected else None
    )
    monkeypatch.setattr(network, "ip", lambda: "10.0.0.2")
    monkeypatch.setattr(network, "gateway", lambda: "10.0.0.1")
    monkeypatch.setattr(network, "dns", lambda: ["10.0.0.1"])


class TestWifiTile:
    """Integrationstests fuer die WLAN-Kachel."""

    def test_status_mit_verbindung(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_wifi(registry, monkeypatch)
        login(client)
        body = client.get("/dashboard/wifi/").get_data(as_text=True)
        assert "Zuhause" in body
        assert "10.0.0.2" in body

    def test_status_ohne_verbindung(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            registry.network_service,
            "current",
            lambda: (_ for _ in ()).throw(NetworkError("kein nmcli")),
        )
        login(client)
        body = client.get("/dashboard/wifi/").get_data(as_text=True)
        assert "Nicht verbunden" in body

    def test_scan_liefert_netzliste(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_wifi(registry, monkeypatch, connected=False)
        networks = [
            {"ssid": "Netz-A", "signal": 90, "security": "WPA2", "frequency": "5"},
        ]
        monkeypatch.setattr(registry.network_service, "scan", lambda: networks)
        token = login(client)
        response = client.post("/dashboard/wifi/scan", data={"csrf_token": token})
        assert "Netz-A" in response.get_data(as_text=True)

    def test_scan_fehler(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_wifi(registry, monkeypatch, connected=False)
        monkeypatch.setattr(
            registry.network_service,
            "scan",
            lambda: (_ for _ in ()).throw(NetworkError("nmcli kaputt")),
        )
        token = login(client)
        response = client.post("/dashboard/wifi/scan", data={"csrf_token": token})
        assert "alert-danger" in response.get_data(as_text=True)

    def test_verbinden_und_trennen(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_wifi(registry, monkeypatch)
        monkeypatch.setattr(
            registry.network_service, "connect", lambda ssid, password: None
        )
        monkeypatch.setattr(registry.network_service, "disconnect", lambda: None)
        token = login(client)
        response = client.post(
            "/dashboard/wifi/connect",
            data={"ssid": "Zuhause", "password": "geheim", "csrf_token": token},
        )
        assert "alert-success" in response.get_data(as_text=True)
        response = client.post("/dashboard/wifi/disconnect", data={"csrf_token": token})
        assert "alert-success" in response.get_data(as_text=True)

    def test_falsches_passwort_wird_uebersetzt(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_wifi(registry, monkeypatch, connected=False)

        def fail_connect(ssid: str, password: str) -> None:
            raise WifiError("secrets", reason="wrong_password")

        monkeypatch.setattr(registry.network_service, "connect", fail_connect)
        token = login(client)
        response = client.post(
            "/dashboard/wifi/connect",
            data={"ssid": "Zuhause", "password": "falsch", "csrf_token": token},
        )
        assert "WLAN-Passwort ist falsch" in response.get_data(as_text=True)


class TestPreferredWifi:
    """Integrationstests fuer das Standard-WLAN."""

    def test_kachel_zeigt_auswahl(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_wifi(registry, monkeypatch)
        monkeypatch.setattr(
            registry.network_service, "saved", lambda: ["Zuhause", "Buero"]
        )
        login(client)
        body = client.get("/dashboard/wifi/").get_data(as_text=True)
        assert "Standard-WLAN" in body
        assert "Buero" in body

    def test_standard_wlan_ohne_passwort_setzt_autoconnect(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_wifi(registry, monkeypatch)
        monkeypatch.setattr(registry.network_service, "saved", lambda: ["Zuhause"])
        calls: list[tuple[str, int]] = []
        monkeypatch.setattr(
            registry.network_service,
            "set_autoconnect",
            lambda ssid, priority: calls.append((ssid, priority)),
        )
        token = login(client)
        response = client.post(
            "/dashboard/wifi/preferred",
            data={"preferred_ssid": "Zuhause", "csrf_token": token},
        )
        assert "alert-success" in response.get_data(as_text=True)
        assert calls == [("Zuhause", 10)]
        assert registry.config_service.load()["wifi_preferred_ssid"] == "Zuhause"

    def test_standard_wlan_mit_passwort_speichert_profil(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_wifi(registry, monkeypatch)
        saved_args: list[tuple[str, str, int]] = []
        monkeypatch.setattr(
            registry.network_service,
            "save_profile",
            lambda ssid, password, priority=0: saved_args.append(
                (ssid, password, priority)
            )
            or True,
        )
        token = login(client)
        response = client.post(
            "/dashboard/wifi/preferred",
            data={
                "preferred_ssid": "Zuhause",
                "preferred_password": "Geheim-2026!",
                "csrf_token": token,
            },
        )
        assert "alert-success" in response.get_data(as_text=True)
        assert saved_args == [("Zuhause", "Geheim-2026!", 10)]
        assert registry.config_service.load()["wifi_preferred_ssid"] == "Zuhause"

    def test_standard_wlan_meldet_ungueltiges_passwort(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_wifi(registry, monkeypatch)

        def _raise(ssid: str, password: str, priority: int = 0) -> bool:
            raise WifiError("zu kurz", reason="invalid_password")

        monkeypatch.setattr(registry.network_service, "save_profile", _raise)
        token = login(client)
        response = client.post(
            "/dashboard/wifi/preferred",
            data={
                "preferred_ssid": "Zuhause",
                "preferred_password": "kurz",
                "csrf_token": token,
            },
        )
        body = response.get_data(as_text=True)
        assert "alert-danger" in body
        assert "8 bis 63" in body

    def test_standard_wlan_entfernen(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_wifi(registry, monkeypatch)
        monkeypatch.setattr(registry.network_service, "saved", lambda: [])
        config = registry.config_service.load()
        config["wifi_preferred_ssid"] = "Zuhause"
        registry.config_service.save(config)
        token = login(client)
        response = client.post(
            "/dashboard/wifi/preferred",
            data={"preferred_ssid": "", "csrf_token": token},
        )
        assert "alert-success" in response.get_data(as_text=True)
        assert registry.config_service.load()["wifi_preferred_ssid"] == ""

    def test_knopfdruck_verbindet(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_wifi(registry, monkeypatch)
        monkeypatch.setattr(registry.network_service, "saved", lambda: ["Zuhause"])
        verbunden: list[str] = []
        monkeypatch.setattr(
            registry.network_service,
            "connect_saved",
            lambda ssid: verbunden.append(ssid),
        )
        config = registry.config_service.load()
        config["wifi_preferred_ssid"] = "Zuhause"
        registry.config_service.save(config)
        token = login(client)
        body = client.get("/dashboard/wifi/").get_data(as_text=True)
        assert "Mit „Zuhause" in body
        response = client.post(
            "/dashboard/wifi/preferred/connect", data={"csrf_token": token}
        )
        assert "alert-success" in response.get_data(as_text=True)
        assert verbunden == ["Zuhause"]

    def test_knopfdruck_meldet_fehler(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_wifi(registry, monkeypatch)
        monkeypatch.setattr(registry.network_service, "saved", lambda: ["Zuhause"])

        def fail(ssid: str) -> None:
            raise WifiError("kein Profil", reason="not_found")

        monkeypatch.setattr(registry.network_service, "connect_saved", fail)
        config = registry.config_service.load()
        config["wifi_preferred_ssid"] = "Zuhause"
        registry.config_service.save(config)
        token = login(client)
        response = client.post(
            "/dashboard/wifi/preferred/connect", data={"csrf_token": token}
        )
        assert "alert-danger" in response.get_data(as_text=True)


class TestSettingsBranches:
    """Integrationstests fuer Einstellungs-Sonderpfade."""

    def test_url_test_nicht_erreichbar(self, client: FlaskClient) -> None:
        token = login(client)
        response = client.post(
            "/dashboard/url/test",
            data={"url": "http://127.0.0.1:59992/", "csrf_token": token},
        )
        assert "nicht erreichbar" in response.get_data(as_text=True)

    def test_url_save_startet_laufenden_browser_neu(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        http_status_server: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(browser_module.subprocess, "Popen", FakeProcess)
        monkeypatch.setattr(browser_module.shutil, "which", lambda name: FAKE_BINARY)
        registry.browser_service.start("https://example.org/")
        token = login(client)
        response = client.post(
            "/dashboard/url/save",
            data={"url": f"{http_status_server}/ok", "csrf_token": token},
        )
        assert "alert-success" in response.get_data(as_text=True)
        assert registry.browser_service._command[-1] == f"{http_status_server}/ok"

    def test_hostname_fehler_wird_angezeigt(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fail_set(hostname: str) -> None:
            raise NetworkError("sudo fehlt")

        monkeypatch.setattr(registry.hostname_service, "set", fail_set)
        token = login(client)
        response = client.post(
            "/dashboard/hostname",
            data={"hostname": "neuer-name", "csrf_token": token},
        )
        assert "alert-danger" in response.get_data(as_text=True)


class TestRestoreBranches:
    """Integrationstests fuer Wiederherstellungs-Fehlerfaelle."""

    def test_upload_mit_kaputter_datei(self, client: FlaskClient) -> None:
        import io

        token = login(client)
        response = client.post(
            "/dashboard/restore/upload",
            data={
                "csrf_token": token,
                "backup_file": (io.BytesIO(b"kein zip"), "kaputt.zip"),
            },
            content_type="multipart/form-data",
        )
        assert "alert-danger" in response.get_data(as_text=True)

    def test_usb_import_mit_unzulaessigem_pfad(self, client: FlaskClient) -> None:
        token = login(client)
        response = client.post(
            "/dashboard/restore/usb",
            data={"path": "/etc/passwd", "csrf_token": token},
        )
        assert "alert-danger" in response.get_data(as_text=True)


class TestUpdateBranches:
    """Integrationstests fuer Update-Sonderpfade."""

    def test_check_fehler(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            registry.update_service,
            "check",
            lambda: (_ for _ in ()).throw(UpdateError("GitHub weg")),
        )
        token = login(client)
        response = client.post("/dashboard/update/check", data={"csrf_token": token})
        assert "alert-danger" in response.get_data(as_text=True)

    def test_github_installation(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            registry.update_service,
            "apply",
            lambda: {"version": "9.9.9", "backup": "b.zip", "changed": 1},
        )
        token = login(client)
        response = client.post("/dashboard/update/install", data={"csrf_token": token})
        assert "alert-success" in response.get_data(as_text=True)

    def test_upload_ohne_datei(self, client: FlaskClient) -> None:
        token = login(client)
        response = client.post("/dashboard/update/upload", data={"csrf_token": token})
        assert "alert-danger" in response.get_data(as_text=True)

    def test_rollback_fehler(
        self,
        client: FlaskClient,
        registry: ServiceRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            registry.update_service,
            "rollback",
            lambda: (_ for _ in ()).throw(UpdateError("kein Stand")),
        )
        token = login(client)
        response = client.post("/dashboard/update/rollback", data={"csrf_token": token})
        assert "alert-danger" in response.get_data(as_text=True)


class TestBrowserAndInternalBranches:
    """Integrationstests fuer Browser- und interne Sonderpfade."""

    def test_unbekannte_browseraktion(self, client: FlaskClient) -> None:
        token = login(client)
        response = client.post("/dashboard/browser/explode", data={"csrf_token": token})
        assert response.status_code == 404

    def test_browserfehler_in_der_kachel(self, client: FlaskClient) -> None:
        token = login(client)
        response = client.post("/dashboard/browser/restart", data={"csrf_token": token})
        assert "alert-danger" in response.get_data(as_text=True)

    def test_interner_neustart_mit_browserfehler(
        self,
        client: FlaskClient,
        flask_app: Flask,  # noqa: F811
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(browser_module.shutil, "which", lambda name: None)
        response = client.post(
            "/internal/browser/restart",
            headers={"X-Watchdog-Token": flask_app.config["SECRET_KEY"]},
        )
        assert response.status_code == 500
        assert response.get_json()["restarted"] is False

    def test_log_download_fehlender_datei(self, client: FlaskClient) -> None:
        login(client)
        response = client.get("/dashboard/system/logs/update/download")
        assert response.status_code == 404

    def test_systemaktion_shutdown(
        self, client: FlaskClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services import system_service as system_module

        calls: list[list[str]] = []

        class Result:
            returncode = 0
            stderr = ""
            stdout = ""

        def fake_run(command: list[str], **kwargs: Any) -> Result:
            calls.append(command)
            return Result()

        monkeypatch.setattr(system_module.subprocess, "run", fake_run)
        token = login(client)
        response = client.post("/dashboard/system/shutdown", data={"csrf_token": token})
        assert "alert" in response.get_data(as_text=True)
        assert calls[0][-2:] == ["systemctl", "poweroff"]


class TestMonitoringTile:
    """Integrationstests fuer die Ueberwachungs-Kachel."""

    def test_kachel_zeigt_einstellungen(self, client: FlaskClient) -> None:
        login(client)
        body = client.get("/dashboard/monitoring").get_data(as_text=True)
        assert "Verbindungsprüfung" in body
        assert "Watchdog aktiv" in body

    def test_kachel_zeigt_einzelpruefungen(
        self,
        client: FlaskClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import json as json_module
        from datetime import datetime, timezone

        from app.services import dashboard_service as dashboard_module

        status_file = tmp_path / "watchdog_status.json"
        status_file.write_text(
            json_module.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "overall": "warning",
                    "browser": {
                        "status": "running",
                        "failed": False,
                        "restarts_in_window": 0,
                    },
                    "network": {
                        "gateway": False,
                        "dns": True,
                        "internet": True,
                        "url": None,
                    },
                    "system": {
                        "cpu_percent": 12.0,
                        "ram_percent": 91.5,
                        "disk_percent": 40.0,
                        "temperature": 62.0,
                        "warnings": ["ram_warning"],
                    },
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(dashboard_module, "WATCHDOG_STATUS_FILE", status_file)
        login(client)
        body = client.get("/dashboard/monitoring").get_data(as_text=True)
        assert "Letzte Prüfung" in body
        assert "Nicht OK" in body
        assert "91.5" in body
        assert "62.0" in body

    def test_kachel_ohne_statusdatei_zeigt_keine_pruefungen(
        self,
        client: FlaskClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.services import dashboard_service as dashboard_module

        monkeypatch.setattr(
            dashboard_module, "WATCHDOG_STATUS_FILE", tmp_path / "fehlt.json"
        )
        login(client)
        body = client.get("/dashboard/monitoring").get_data(as_text=True)
        assert "Letzte Prüfung" not in body

    def test_verbindungspruefung_umstellen(
        self, client: FlaskClient, registry: ServiceRegistry
    ) -> None:
        config = registry.config_service.load()
        config["url"] = "http://192.168.0.50/anzeige"
        registry.config_service.save(config)
        token = login(client)
        response = client.post(
            "/dashboard/monitoring",
            data={
                "watchdog": "on",
                "connectivity_check": "url",
                "csrf_token": token,
            },
        )
        assert "alert-success" in response.get_data(as_text=True)
        assert registry.config_service.load()["connectivity_check"] == "url"

    def test_watchdog_abschalten(
        self, client: FlaskClient, registry: ServiceRegistry
    ) -> None:
        token = login(client)
        response = client.post(
            "/dashboard/monitoring",
            data={"connectivity_check": "internet", "csrf_token": token},
        )
        assert response.status_code == 200
        assert registry.config_service.load()["watchdog"] is False

    def test_tastenkombination_speichern(
        self, client: FlaskClient, registry: ServiceRegistry
    ) -> None:
        token = login(client)
        response = client.post(
            "/dashboard/monitoring",
            data={
                "watchdog": "on",
                "connectivity_check": "internet",
                "escape_hotkey": "Ctrl+Shift+D",
                "csrf_token": token,
            },
        )
        assert "alert-success" in response.get_data(as_text=True)
        assert registry.config_service.load()["escape_hotkey"] == "ctrl+shift+d"

    def test_ungueltige_tastenkombination_wird_abgelehnt(
        self, client: FlaskClient, registry: ServiceRegistry
    ) -> None:
        token = login(client)
        response = client.post(
            "/dashboard/monitoring",
            data={
                "watchdog": "on",
                "connectivity_check": "internet",
                "escape_hotkey": "ctrl+alt+gibtsnicht",
                "csrf_token": token,
            },
        )
        assert "alert-danger" in response.get_data(as_text=True)

    def test_url_pruefung_ohne_kiosk_url_wird_abgelehnt(
        self, client: FlaskClient, registry: ServiceRegistry
    ) -> None:
        token = login(client)
        response = client.post(
            "/dashboard/monitoring",
            data={
                "watchdog": "on",
                "connectivity_check": "url",
                "csrf_token": token,
            },
        )
        assert "alert-danger" in response.get_data(as_text=True)
        assert registry.config_service.load()["connectivity_check"] == "internet"


class TestUpdateSourceTile:
    """Integrationstests fuer die Wahl der Updatequelle."""

    def test_kachel_zeigt_quelle(self, client: FlaskClient) -> None:
        login(client)
        body = client.get("/dashboard/update/").get_data(as_text=True)
        assert "Updatequelle" in body
        assert "Lokale Quelle" in body

    def test_lokale_quelle_speichern(
        self, client: FlaskClient, registry: ServiceRegistry
    ) -> None:
        token = login(client)
        response = client.post(
            "/dashboard/update/source",
            data={
                "update_source": "local",
                "update_url": "http://server.local/pikiosk",
                "csrf_token": token,
            },
        )
        assert "alert-success" in response.get_data(as_text=True)
        config = registry.config_service.load()
        assert config["update_source"] == "local"
        assert config["update_url"] == "http://server.local/pikiosk"

    def test_lokale_quelle_ohne_url_wird_abgelehnt(
        self, client: FlaskClient, registry: ServiceRegistry
    ) -> None:
        token = login(client)
        response = client.post(
            "/dashboard/update/source",
            data={
                "update_source": "local",
                "update_url": "",
                "csrf_token": token,
            },
        )
        assert "alert-danger" in response.get_data(as_text=True)
        assert registry.config_service.load()["update_source"] == "github"

    def test_quelle_abschalten_und_pruefen(
        self, client: FlaskClient, registry: ServiceRegistry
    ) -> None:
        token = login(client)
        client.post(
            "/dashboard/update/source",
            data={"update_source": "off", "update_url": "", "csrf_token": token},
        )
        assert registry.config_service.load()["update_source"] == "off"
        response = client.post("/dashboard/update/check", data={"csrf_token": token})
        assert "deaktiviert" in response.get_data(as_text=True)
