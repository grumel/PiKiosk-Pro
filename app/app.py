# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Einstiegspunkt.

Startet den Flask-Webserver und anschliessend den Kioskbrowser.
Ist die Ersteinrichtung noch nicht abgeschlossen oder keine URL
konfiguriert, zeigt der Browser die lokale Statusseite an.
"""

import argparse
import socket
import sys
import threading
import time
from typing import Any

from app import create_app
from app.constants import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_HOST,
    DEFAULT_PORT,
    LOCAL_URL,
    SERVER_START_TIMEOUT_SECONDS,
)
from app.exceptions import PiKioskError
from app.extensions import ServiceRegistry, get_services


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """Wertet die Kommandozeilenargumente aus.

    Args:
        argv:
            Argumente ohne Programmnamen.

    Returns:
        Die ausgewerteten Argumente.
    """
    parser = argparse.ArgumentParser(
        prog="pikiosk", description=f"{APP_NAME} {APP_VERSION}"
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help="Netzwerkschnittstelle des Webservers",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Port des Webservers",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Startet nur den Webserver ohne Kioskbrowser",
    )
    return parser.parse_args(argv)


def determine_kiosk_url(config: dict[str, Any]) -> str:
    """Bestimmt die URL, die der Kioskbrowser anzeigen soll.

    Args:
        config:
            Aktive Konfiguration.

    Returns:
        Konfigurierte Kiosk-URL oder die lokale Statusseite.
    """
    if config["first_start"] or not config["url"]:
        return LOCAL_URL
    return str(config["url"])


def wait_for_server(host: str, port: int, timeout: float) -> bool:
    """Wartet, bis der Webserver Verbindungen annimmt.

    Args:
        host:
            Host des Webservers.

        port:
            Port des Webservers.

        timeout:
            Maximale Wartezeit in Sekunden.

    Returns:
        True, wenn der Server erreichbar ist.
    """
    target = "127.0.0.1" if host == "0.0.0.0" else host
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((target, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _start_browser_when_ready(registry: ServiceRegistry, host: str, port: int) -> None:
    """Startet den Browser, sobald der Webserver bereit ist.

    Args:
        registry:
            Registrierte Anwendungsdienste.

        host:
            Host des Webservers.

        port:
            Port des Webservers.
    """
    if not wait_for_server(host, port, SERVER_START_TIMEOUT_SECONDS):
        registry.logger.error("Webserver nicht erreichbar, Browserstart abgebrochen.")
        return
    try:
        config = registry.config_service.load()
        registry.browser_service.start(determine_kiosk_url(config))
    except PiKioskError as error:
        registry.logger.error(f"Browserstart fehlgeschlagen: {error}")


def main(argv: list[str] | None = None) -> int:
    """Startet PiKiosk Pro.

    Args:
        argv:
            Optionale Kommandozeilenargumente fuer Tests.

    Returns:
        Exit-Code des Programms.
    """
    arguments = parse_arguments(argv if argv is not None else sys.argv[1:])
    app = create_app()
    registry = get_services(app)
    registry.logger.info(
        f"{APP_NAME} {APP_VERSION} startet auf " f"{arguments.host}:{arguments.port}."
    )
    if not arguments.no_browser:
        browser_thread = threading.Thread(
            target=_start_browser_when_ready,
            args=(registry, arguments.host, arguments.port),
            daemon=True,
        )
        browser_thread.start()
    try:
        app.run(
            host=arguments.host,
            port=arguments.port,
            threaded=True,
            use_reloader=False,
        )
    finally:
        registry.browser_service.stop()
        registry.logger.info("Anwendung beendet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
