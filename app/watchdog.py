# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Watchdog-Einstiegspunkt.

Startet den eigenstaendigen Watchdogprozess, der von systemd als
pikiosk-watchdog.service betrieben wird. Der Watchdog prueft alle
5 Sekunden Browser, Netzwerk und System und schreibt den Zustand
in die Statusdatei fuer das Dashboard.
"""

import sys

from app.constants import APP_NAME, APP_VERSION, WATCHDOG_LOG_FILE
from app.exceptions import PiKioskError
from app.logger import KioskLogger
from app.services.config_service import ConfigService
from app.services.watchdog_service import WatchdogService
from app.utils.helpers import load_or_create_secret_key


def main() -> int:
    """Startet den Watchdog.

    Returns:
        Exit-Code des Programms.
    """
    logger = KioskLogger("watchdog", WATCHDOG_LOG_FILE)
    try:
        config_service = ConfigService(logger=logger)
        token = load_or_create_secret_key()
    except PiKioskError as error:
        logger.critical(f"Watchdog kann nicht starten: {error}", exc_info=True)
        return 1
    service = WatchdogService(logger=logger, config_service=config_service, token=token)
    logger.info(f"{APP_NAME} Watchdog {APP_VERSION} gestartet.")
    try:
        service.run_forever()
    except KeyboardInterrupt:
        logger.info("Watchdog beendet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
