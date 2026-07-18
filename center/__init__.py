# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Center - Anwendungsfabrik.

Erzeugt die Flask-Anwendung der Verwaltungszentrale, initialisiert
alle Dienste und registriert Anmeldung, Flottenuebersicht und
Geraeteverwaltung. Die Zentrale spricht die Geraete ausschliesslich
ueber deren REST API an; die Geraete selbst bleiben unveraendert.
"""

from datetime import timedelta

from flask import Flask, abort, redirect, render_template, request, session, url_for
from flask_login import LoginManager
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

from app import AdaptiveSessionInterface
from app.constants import REMEMBER_COOKIE_DAYS, SESSION_TIMEOUT_MINUTES
from app.logger import KioskLogger
from app.models.user_model import UserModel
from app.services.auth_service import AuthService, LoginUser
from app.utils.crypto import load_or_create_fernet_key
from app.utils.helpers import load_or_create_secret_key
from center.constants import (
    CENTER_KEY_FILE,
    CENTER_LOG_FILE,
    CENTER_TEMPLATE_DIR,
    CENTER_USERS_DB_FILE,
    STATIC_DIR,
)
from center.controllers import SESSION_CSRF_KEY, center_texts, ensure_csrf_token
from center.controllers.auth_controller import center_auth_blueprint
from center.controllers.device_controller import device_blueprint
from center.controllers.fleet_controller import fleet_blueprint
from center.extensions import CenterRegistry, register_center_services
from center.models.device_model import DeviceModel
from center.services.device_client import DeviceClient
from center.services.device_service import DeviceService
from center.services.fleet_service import FleetService

CSRF_PROTECTED_METHODS: tuple[str, ...] = ("POST", "PUT", "PATCH", "DELETE")


def create_center_app(registry: CenterRegistry | None = None) -> Flask:
    """Erzeugt und konfiguriert die Zentrale.

    Args:
        registry:
            Optionale, bereits befuellte CenterRegistry. Wird sie
            nicht uebergeben, werden alle Dienste neu erzeugt.

    Returns:
        Die vollstaendig initialisierte Flask-Anwendung.
    """
    app = Flask(
        __name__,
        template_folder=str(CENTER_TEMPLATE_DIR),
        static_folder=str(STATIC_DIR),
    )
    _configure_session(app)
    if registry is None:
        registry = _build_center_services()
    register_center_services(app, registry)
    app.register_blueprint(center_auth_blueprint)
    app.register_blueprint(fleet_blueprint)
    app.register_blueprint(device_blueprint)
    _configure_login(app, registry)
    _register_csrf_protection(app)
    _register_error_handlers(app, registry)
    registry.logger.info("Zentrale initialisiert.")
    return app


def _configure_session(app: Flask) -> None:
    """Konfiguriert Sitzungsschluessel und Cookie-Sicherheit.

    Args:
        app:
            Flask-Anwendung der Zentrale.
    """
    app.session_interface = AdaptiveSessionInterface()
    app.config["SECRET_KEY"] = load_or_create_secret_key()
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
        minutes=SESSION_TIMEOUT_MINUTES
    )
    app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=REMEMBER_COOKIE_DAYS)
    app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"


def _build_center_services() -> CenterRegistry:
    """Erzeugt alle Dienste der Zentrale.

    Returns:
        Die befuellte CenterRegistry.
    """
    logger = KioskLogger("center", CENTER_LOG_FILE)
    key = load_or_create_fernet_key(CENTER_KEY_FILE)
    device_service = DeviceService(logger=logger, device_model=DeviceModel(), key=key)
    client = DeviceClient(key=key)
    return CenterRegistry(
        logger=logger,
        auth_service=AuthService(
            logger=KioskLogger("center_auth", CENTER_LOG_FILE),
            user_model=UserModel(CENTER_USERS_DB_FILE),
        ),
        device_service=device_service,
        fleet_service=FleetService(
            logger=logger, device_service=device_service, client=client
        ),
        client=client,
    )


def _configure_login(app: Flask, registry: CenterRegistry) -> None:
    """Richtet Flask-Login fuer die Zentrale ein.

    Args:
        app:
            Flask-Anwendung der Zentrale.

        registry:
            Registrierte Dienste.
    """
    login_manager = LoginManager()
    login_manager.login_view = "center_auth.login"
    login_manager.session_protection = "basic"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str) -> LoginUser | None:
        return registry.auth_service.load_user(user_id)

    @login_manager.unauthorized_handler
    def handle_unauthorized() -> Response:
        return _login_redirect(app, expired=False)


def _login_redirect(app: Flask, expired: bool) -> Response:
    """Erzeugt eine Weiterleitung zur Anmeldeseite der Zentrale.

    HTMX-Anfragen erhalten eine Antwort mit HX-Redirect-Kopfzeile,
    damit der Browser eine vollstaendige Seite laedt, statt die
    Anmeldeseite in ein Seitenfragment einzusetzen.

    Args:
        app:
            Flask-Anwendung der Zentrale.

        expired:
            True, wenn die Sitzung abgelaufen ist; auf der
            Anmeldeseite erscheint dann ein Hinweis.

    Returns:
        Die Weiterleitungsantwort zur Anmeldeseite.
    """
    if expired:
        login_url = url_for("center_auth.login", expired="1")
    else:
        login_url = url_for("center_auth.login")
    if request.headers.get("HX-Request"):
        response = app.response_class(status=204)
        response.headers["HX-Redirect"] = login_url
        return response
    return redirect(login_url)


def _register_csrf_protection(app: Flask) -> None:
    """Erzwingt CSRF-Token fuer alle Schreibanfragen.

    Args:
        app:
            Flask-Anwendung der Zentrale.
    """

    @app.before_request
    def verify_csrf_token() -> Response | None:
        if request.method not in CSRF_PROTECTED_METHODS:
            return None
        token = request.headers.get("X-CSRF-Token", "") or request.form.get(
            "csrf_token", ""
        )
        expected = session.get(SESSION_CSRF_KEY, "")
        if expected and token == expected:
            return None
        if not expected:
            # Die Sitzung ist abgelaufen: sauber zur Anmeldung
            # umleiten statt einen nackten 400-Fehler zu zeigen.
            return _login_redirect(app, expired=True)
        abort(400)

    @app.context_processor
    def inject_csrf_token() -> dict[str, str]:
        return {"csrf_token": ensure_csrf_token()}


def _register_error_handlers(app: Flask, registry: CenterRegistry) -> None:
    """Registriert die zentrale Fehlerbehandlung.

    Args:
        app:
            Flask-Anwendung der Zentrale.

        registry:
            Registrierte Dienste.
    """

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException) -> tuple[str, int]:
        code = error.code if error.code is not None else 500
        registry.logger.warning(f"HTTP-Fehler {code}: {error.description}")
        return (
            render_template("center_error.html", texts=center_texts(), code=code),
            code,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception) -> tuple[str, int]:
        registry.logger.error(f"Unerwarteter Fehler: {error}", exc_info=True)
        return (
            render_template("center_error.html", texts=center_texts(), code=500),
            500,
        )
