# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Anwendungsfabrik.

Erzeugt die Flask-Anwendung, initialisiert alle Dienste und
registriert Routen, Setup-Wizard, Anmeldung, Dashboard und
Fehlerbehandlung. Alle Schreibanfragen sind CSRF-geschuetzt, die
Sitzung laeuft nach 30 Minuten ab. Solange die Ersteinrichtung
nicht abgeschlossen ist, leitet die Anwendung alle Anfragen auf
den Setup-Wizard um. Python-Tracebacks werden niemals im Browser
angezeigt.
"""

from datetime import timedelta

from flask import Flask, abort, redirect, render_template, request, session, url_for
from flask_login import LoginManager
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

from app.constants import (
    BASE_DIR,
    BROWSER_LOG_FILE,
    MAX_UPLOAD_BYTES,
    NETWORK_LOG_FILE,
    REMEMBER_COOKIE_DAYS,
    SESSION_TIMEOUT_MINUTES,
    SYSTEM_LOG_FILE,
)
from app.controllers import SESSION_CSRF_KEY, ensure_csrf_token
from app.controllers.auth_controller import auth_blueprint
from app.controllers.backup_controller import backup_blueprint
from app.controllers.browser_controller import browser_blueprint
from app.controllers.dashboard_controller import dashboard_blueprint
from app.controllers.internal_controller import internal_blueprint
from app.controllers.network_controller import network_blueprint
from app.controllers.restore_controller import restore_blueprint
from app.controllers.settings_controller import settings_blueprint
from app.controllers.setup_controller import setup_blueprint
from app.controllers.system_controller import system_blueprint
from app.extensions import ServiceRegistry, get_services, register_services
from app.logger import KioskLogger
from app.models.user_model import UserModel
from app.routes import main_blueprint
from app.services.auth_service import AuthService, LoginUser
from app.services.backup_service import BackupService
from app.services.browser_service import BrowserService
from app.services.config_service import ConfigService
from app.services.dashboard_service import DashboardService
from app.services.hostname_service import HostnameService
from app.services.network_service import NetworkService
from app.services.restore_service import RestoreService
from app.services.system_service import SystemService
from app.utils.helpers import load_language, load_or_create_secret_key

SETUP_EXEMPT_ENDPOINTS: tuple[str, ...] = ("static", "main.health")
CSRF_PROTECTED_METHODS: tuple[str, ...] = ("POST", "PUT", "PATCH", "DELETE")
TOKEN_AUTHENTICATED_BLUEPRINTS: tuple[str, ...] = ("internal",)


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
    _configure_session(app)
    if registry is None:
        registry = _build_services()
    register_services(app, registry)
    _register_blueprints(app)
    _configure_login(app, registry)
    _register_csrf_protection(app)
    _register_setup_gate(app)
    _register_error_handlers(app, registry)
    registry.config_service.load()
    registry.logger.info("Anwendung initialisiert.")
    return app


def _configure_session(app: Flask) -> None:
    """Konfiguriert Sitzungsschluessel und Cookie-Sicherheit.

    Args:
        app:
            Flask-Anwendung.
    """
    app.config["SECRET_KEY"] = load_or_create_secret_key()
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
        minutes=SESSION_TIMEOUT_MINUTES
    )
    app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=REMEMBER_COOKIE_DAYS)
    app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES


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
    dashboard_logger = KioskLogger("dashboard", SYSTEM_LOG_FILE)
    config_service = ConfigService(logger=config_logger)
    browser_service = BrowserService(logger=browser_logger)
    return ServiceRegistry(
        logger=system_logger,
        config_service=config_service,
        browser_service=browser_service,
        network_service=NetworkService(logger=network_logger),
        hostname_service=HostnameService(logger=system_logger),
        auth_service=AuthService(logger=auth_logger, user_model=UserModel()),
        dashboard_service=DashboardService(
            logger=dashboard_logger,
            config_service=config_service,
            browser_service=browser_service,
        ),
        system_service=SystemService(
            logger=system_logger, browser_service=browser_service
        ),
        backup_service=BackupService(
            logger=KioskLogger("backup", SYSTEM_LOG_FILE),
            config_service=config_service,
        ),
        restore_service=RestoreService(
            logger=KioskLogger("restore", SYSTEM_LOG_FILE),
            config_service=config_service,
        ),
    )


def _register_blueprints(app: Flask) -> None:
    """Registriert alle Blueprints der Anwendung.

    Args:
        app:
            Flask-Anwendung.
    """
    app.register_blueprint(main_blueprint)
    app.register_blueprint(setup_blueprint)
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(dashboard_blueprint)
    app.register_blueprint(browser_blueprint)
    app.register_blueprint(settings_blueprint)
    app.register_blueprint(network_blueprint)
    app.register_blueprint(system_blueprint)
    app.register_blueprint(backup_blueprint)
    app.register_blueprint(restore_blueprint)
    app.register_blueprint(internal_blueprint)


def _configure_login(app: Flask, registry: ServiceRegistry) -> None:
    """Richtet Flask-Login ein.

    Args:
        app:
            Flask-Anwendung.

        registry:
            Registrierte Anwendungsdienste.
    """
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.session_protection = "strong"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str) -> LoginUser | None:
        return registry.auth_service.load_user(user_id)


def _register_csrf_protection(app: Flask) -> None:
    """Erzwingt CSRF-Token fuer alle Schreibanfragen.

    Args:
        app:
            Flask-Anwendung.
    """

    @app.before_request
    def verify_csrf_token() -> None:
        if request.method not in CSRF_PROTECTED_METHODS:
            return
        if request.blueprint in TOKEN_AUTHENTICATED_BLUEPRINTS:
            return
        token = request.headers.get("X-CSRF-Token", "") or request.form.get(
            "csrf_token", ""
        )
        expected = session.get(SESSION_CSRF_KEY, "")
        if not expected or token != expected:
            abort(400)

    @app.context_processor
    def inject_csrf_token() -> dict[str, str]:
        return {"csrf_token": ensure_csrf_token()}


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
        if request.blueprint in TOKEN_AUTHENTICATED_BLUEPRINTS:
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
