# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Zentrale Konstanten.

Dieses Modul buendelt alle projektweiten Konstanten wie Pfade,
Versionsnummer, Browser-Startparameter und Validierungsgrenzen.
Alle anderen Module greifen ausschliesslich auf diese Definitionen
zu, damit keine doppelten Definitionen entstehen.
"""

from pathlib import Path

APP_NAME: str = "PiKiosk Pro"
APP_VERSION: str = "0.1.0"

BASE_DIR: Path = Path(__file__).resolve().parent.parent
CONFIG_DIR: Path = BASE_DIR / "config"
CONFIG_FILE: Path = CONFIG_DIR / "config.json"
DEFAULTS_FILE: Path = CONFIG_DIR / "defaults.json"
LOG_DIR: Path = BASE_DIR / "logs"
BACKUP_DIR: Path = BASE_DIR / "backup"

SYSTEM_LOG_FILE: Path = LOG_DIR / "system.log"
BROWSER_LOG_FILE: Path = LOG_DIR / "browser.log"

LOG_MAX_BYTES: int = 10 * 1024 * 1024
LOG_BACKUP_COUNT: int = 10
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

DEFAULT_HOST: str = "0.0.0.0"
DEFAULT_PORT: int = 8080
LOCAL_URL: str = f"http://127.0.0.1:{DEFAULT_PORT}/"
SERVER_START_TIMEOUT_SECONDS: float = 30.0

CHROMIUM_BINARIES: tuple[str, ...] = ("chromium-browser", "chromium")
BROWSER_USER_DATA_DIR: Path = Path.home() / ".pikiosk" / "chromium"
BROWSER_STOP_TIMEOUT_SECONDS: float = 10.0

CDP_HOST: str = "127.0.0.1"
CDP_PORT: int = 9222

BROWSER_ARGS: tuple[str, ...] = (
    "--kiosk",
    "--start-fullscreen",
    "--noerrdialogs",
    "--disable-infobars",
    "--disable-session-crashed-bubble",
    "--disable-translate",
    "--overscroll-history-navigation=0",
    "--disable-pinch",
    "--incognito",
)

HOSTNAME_MAX_LENGTH: int = 63
ALLOWED_URL_SCHEMES: tuple[str, ...] = ("http", "https")
SUPPORTED_LANGUAGES: tuple[str, ...] = ("de", "en")
SUPPORTED_THEMES: tuple[str, ...] = ("dark", "light", "auto")
SUPPORTED_BROWSERS: tuple[str, ...] = ("chromium",)

CONFIG_SCHEMA: dict[str, type] = {
    "hostname": str,
    "url": str,
    "language": str,
    "theme": str,
    "fullscreen": bool,
    "watchdog": bool,
    "browser": str,
    "first_start": bool,
}
