# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Anwendungsfabrik.

Erzeugt die Flask-Anwendung, initialisiert alle Dienste und
registriert Routen sowie Fehlerbehandlung. Python-Tracebacks
werden niemals im Browser angezeigt.
"""

from flask import Flask, render_template
from werkzeug.exceptions import HTTPException

from app.constants import (
    BASE_DIR,
    BROWSER_LOG_FILE,
    SYSTEM_LOG_FILE,
)
from app.extensions import ServiceRegistry, register_services
from app.logger import KioskLogger
from app.routes import main_blueprint
from app.services.browser_service import BrowserService
from app.services.config_service import ConfigService
from app.utils.helpers import load_language


def create_app() -> Flask:
    """Erzeugt und konfiguriert die Flask-Anwendung.

    Returns:
        Die vollstaendig initialisierte Flask-Anwendung.
    """
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    registry = _build_services()
    register_services(app, registry)
    app.register_blueprint(main_blueprint)
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
    config_service = ConfigService(logger=config_logger)
    browser_service = BrowserService(logger=browser_logger)
    return ServiceRegistry(
        logger=system_logger,
        config_service=config_service,
        browser_service=browser_service,
    )


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
