# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Anwendungsfabrik.

Erzeugt die Flask-Anwendung, initialisiert alle Dienste und
registriert Routen, Setup-Wizard und Fehlerbehandlung. Solange die
Ersteinrichtung nicht abgeschlossen ist, leitet die Anwendung alle
Anfragen auf den Setup-Wizard um. Python-Tracebacks werden niemals
im Browser angezeigt.
"""

from flask import Flask, redirect, render_template, request, url_for
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

from app.constants import (
    BASE_DIR,
    BROWSER_LOG_FILE,
    NETWORK_LOG_FILE,
    SYSTEM_LOG_FILE,
)
from app.controllers.setup_controller import setup_blueprint
from app.extensions import ServiceRegistry, get_services, register_services
from app.logger import KioskLogger
from app.models.user_model import UserModel
from app.routes import main_blueprint
from app.services.auth_service import AuthService
from app.services.browser_service import BrowserService
from app.services.config_service import ConfigService
from app.services.hostname_service import HostnameService
from app.services.network_service import NetworkService
from app.utils.helpers import load_language, load_or_create_secret_key

SETUP_EXEMPT_ENDPOINTS: tuple[str, ...] = ("static", "main.health")


def create_app(registry: ServiceRegistry | None = None) -> Flask:
    """Erzeugt und konfiguriert die Flask-Anwendung.

    Args:
        registry:
            Optionale, bereits befuellte ServiceRegistry. Wird sie
            nicht uebergeben, werden alle Dienste neu erzeugt.

    Returns:
        Die vollstaendig initialisierte Flask-Anwendung.
    """
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config["SECRET_KEY"] = load_or_create_secret_key()
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    if registry is None:
        registry = _build_services()
    register_services(app, registry)
    app.register_blueprint(main_blueprint)
    app.register_blueprint(setup_blueprint)
    _register_setup_gate(app)
    _register_error_handlers(app, registry)
    registry.config_service.load()
    registry.logger.info("Anwendung initialisiert.")
    return app


def _build_services() -> ServiceRegistry:
    """Erzeugt alle Anwendungsdienste.

    Returns:
        Die befuellte ServiceRegistry.
    """
    system_logger = KioskLogger("system", SYSTEM_LOG_FILE)
    config_logger = KioskLogger("config", SYSTEM_LOG_FILE)
    browser_logger = KioskLogger("browser", BROWSER_LOG_FILE)
    network_logger = KioskLogger("network", NETWORK_LOG_FILE)
    auth_logger = KioskLogger("authentication", SYSTEM_LOG_FILE)
    return ServiceRegistry(
        logger=system_logger,
        config_service=ConfigService(logger=config_logger),
        browser_service=BrowserService(logger=browser_logger),
        network_service=NetworkService(logger=network_logger),
        hostname_service=HostnameService(logger=system_logger),
        auth_service=AuthService(logger=auth_logger, user_model=UserModel()),
    )


def _register_setup_gate(app: Flask) -> None:
    """Erzwingt den Setup-Wizard bis zum Abschluss der Einrichtung.

    Args:
        app:
            Flask-Anwendung.
    """

    @app.before_request
    def enforce_setup_state() -> Response | None:
        endpoint = request.endpoint or ""
        if endpoint in SETUP_EXEMPT_ENDPOINTS or endpoint == "static":
            return None
        registry = get_services(app)
        config = registry.config_service.load()
        in_setup = request.blueprint == "setup"
        if config["first_start"] and not in_setup:
            return redirect(url_for("setup.wizard"))
        if not config["first_start"] and in_setup:
            return redirect(url_for("main.index"))
        return None


def _load_error_texts(registry: ServiceRegistry) -> dict[str, str]:
    """Laedt die Oberflaechentexte fuer Fehlerseiten.

    Faellt bei einer defekten Konfiguration auf Deutsch zurueck,
    damit die Fehlerseite immer angezeigt werden kann.

    Args:
        registry:
            Registrierte Anwendungsdienste.

    Returns:
        Woerterbuch mit Oberflaechentexten.
    """
    try:
        config = registry.config_service.load()
        return load_language(config["language"])
    except Exception:  # noqa: BLE001 - Fehlerseite darf nie scheitern.
        return load_language("de")


def _register_error_handlers(app: Flask, registry: ServiceRegistry) -> None:
    """Registriert die zentrale Fehlerbehandlung.

    Args:
        app:
            Flask-Anwendung.

        registry:
            Registrierte Anwendungsdienste.
    """

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException) -> tuple[str, int]:
        texts = _load_error_texts(registry)
        code = error.code if error.code is not None else 500
        registry.logger.warning(f"HTTP-Fehler {code}: {error.description}")
        return render_template("error.html", texts=texts, code=code), code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception) -> tuple[str, int]:
        texts = _load_error_texts(registry)
        registry.logger.error(f"Unerwarteter Fehler: {error}", exc_info=True)
        return render_template("error.html", texts=texts, code=500), 500
