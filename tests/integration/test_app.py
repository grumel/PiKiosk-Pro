# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Integrationstests fuer die Flask-Anwendung."""

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.constants import APP_VERSION
from app.extensions import ServiceRegistry


@pytest.fixture
def flask_app(registry: ServiceRegistry) -> Flask:
    """Erzeugt die Flask-Anwendung mit abgeschlossener Einrichtung.

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


class TestFlaskApp:
    """Integrationstests fuer Webserver und Routen."""

    def test_statusseite_liefert_html(self, client: FlaskClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "PiKiosk Pro" in body
        assert APP_VERSION in body

    def test_statusseite_verlinkt_das_dashboard(self, client: FlaskClient) -> None:
        body = client.get("/").get_data(as_text=True)
        assert 'href="/dashboard/"' in body
        assert "Zum Dashboard" in body

    def test_dashboard_link_fuehrt_ohne_anmeldung_zur_anmeldung(
        self, client: FlaskClient
    ) -> None:
        response = client.get("/dashboard/")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_health_liefert_json(self, client: FlaskClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["status"] == "ok"
        assert payload["version"] == APP_VERSION
        assert payload["browser"] == "not_started"

    def test_unbekannte_seite_zeigt_fehlerseite(self, client: FlaskClient) -> None:
        response = client.get("/gibt-es-nicht")
        assert response.status_code == 404
        body = response.get_data(as_text=True)
        assert "404" in body
        assert "Traceback" not in body

    def test_statische_dateien_erreichbar(self, client: FlaskClient) -> None:
        response = client.get("/static/css/style.css")
        assert response.status_code == 200

    def test_setup_leitet_nach_abschluss_zur_statusseite(
        self, client: FlaskClient
    ) -> None:
        response = client.get("/setup/")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")
