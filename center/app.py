# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Center - Einstiegspunkt.

Startet den Webserver der Verwaltungszentrale. Die Zentrale laeuft
auf einem beliebigen Rechner im Netzwerk (auch auf einem Raspberry
Pi) und verwaltet von dort alle PiKiosk-Geraete.
"""

import argparse
import sys

from app.server import serve
from app.utils.helpers import tls_files
from center import create_center_app
from center.constants import CENTER_HOST, CENTER_NAME, CENTER_PORT, CENTER_VERSION


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """Wertet die Kommandozeilenargumente aus.

    Args:
        argv:
            Argumente ohne Programmnamen.

    Returns:
        Die ausgewerteten Argumente.
    """
    parser = argparse.ArgumentParser(
        prog="pikiosk-center", description=f"{CENTER_NAME} {CENTER_VERSION}"
    )
    parser.add_argument(
        "--host", default=CENTER_HOST, help="Netzwerkschnittstelle des Webservers"
    )
    parser.add_argument(
        "--port", type=int, default=CENTER_PORT, help="Port des Webservers"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Startet die Zentrale.

    Args:
        argv:
            Optionale Kommandozeilenargumente fuer Tests.

    Returns:
        Exit-Code des Programms.
    """
    arguments = parse_arguments(argv if argv is not None else sys.argv[1:])
    app = create_center_app()
    serve(app, host=arguments.host, port=arguments.port, tls=tls_files())
    return 0


if __name__ == "__main__":
    sys.exit(main())
