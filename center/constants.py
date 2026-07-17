# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Center - Zentrale Konstanten.

Buendelt alle Konstanten der Verwaltungszentrale: Pfade, Port,
Zeitgrenzen und die zulaessigen Massenaktionen. Die Zentrale
verwaltet beliebig viele PiKiosk-Geraete ueber deren REST API.
"""

from pathlib import Path

CENTER_NAME: str = "PiKiosk Center"
CENTER_VERSION: str = "1.2.0"

BASE_DIR: Path = Path(__file__).resolve().parent.parent
CONFIG_DIR: Path = BASE_DIR / "config"
CENTER_TEMPLATE_DIR: Path = BASE_DIR / "center" / "templates"
STATIC_DIR: Path = BASE_DIR / "static"
LOG_DIR: Path = BASE_DIR / "logs"

CENTER_LOG_FILE: Path = LOG_DIR / "center.log"
DEVICES_DB_FILE: Path = CONFIG_DIR / "center_devices.db"
CENTER_USERS_DB_FILE: Path = CONFIG_DIR / "center_users.db"
CENTER_KEY_FILE: Path = CONFIG_DIR / "center_key"

CENTER_HOST: str = "0.0.0.0"
CENTER_PORT: int = 8090

DEVICE_DEFAULT_PORT: int = 8080
DEVICE_HTTP_TIMEOUT_SECONDS: float = 6.0
DEVICE_TOKEN_MARGIN_SECONDS: int = 300
FLEET_MAX_WORKERS: int = 16
FLEET_REFRESH_SECONDS: int = 15

DEVICE_NAME_MAX_LENGTH: int = 64
DEVICE_ADDRESS_MAX_LENGTH: int = 253

DEVICE_ACTIONS: tuple[str, ...] = (
    "browser_restart",
    "browser_start",
    "browser_stop",
    "reboot",
    "shutdown",
)

DEVICE_STATE_ONLINE: str = "online"
DEVICE_STATE_OFFLINE: str = "offline"
DEVICE_STATE_AUTH: str = "auth_error"
DEVICE_STATE_DISABLED: str = "disabled"
