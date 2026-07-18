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
APP_VERSION: str = "1.6.1"

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
SERVER_THREADS: int = 8

LOOPBACK_HOST: str = "127.0.0.1"
LOOPBACK_PORT: int = 8081
TLS_DIR: Path = CONFIG_DIR / "tls"
TLS_CERT_FILE: Path = TLS_DIR / "cert.pem"
TLS_KEY_FILE: Path = TLS_DIR / "key.pem"

LOGIN_MAX_ATTEMPTS: int = 5
LOGIN_ATTEMPT_WINDOW_SECONDS: int = 900
LOGIN_LOCKOUT_SECONDS: int = 300

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
SUPPORTED_UPDATE_SOURCES: tuple[str, ...] = ("github", "local", "off")
SUPPORTED_CONNECTIVITY_CHECKS: tuple[str, ...] = (
    "internet",
    "url",
    "gateway",
    "off",
)

USERS_DB_FILE: Path = CONFIG_DIR / "users.db"
SECRET_KEY_FILE: Path = CONFIG_DIR / "secret_key"

DEFAULT_ADMIN_USERNAME: str = "admin"
ADMIN_ROLE: str = "admin"
PASSWORD_MIN_LENGTH: int = 12

URL_CHECK_TIMEOUT_SECONDS: float = 5.0
URL_CHECK_VALID_STATUS: tuple[int, ...] = (200, 301, 302)

WIFI_SSID_MAX_LENGTH: int = 32
NMCLI_BINARY: str = "nmcli"
NMCLI_TIMEOUT_SECONDS: float = 45.0
NETWORK_LOG_FILE: Path = LOG_DIR / "network.log"

ETC_HOSTNAME_FILE: Path = Path("/etc/hostname")
ETC_HOSTS_FILE: Path = Path("/etc/hosts")
HOSTNAME_APPLY_SCRIPT: Path = BASE_DIR / "scripts" / "hostname_apply.py"

SETUP_STEPS: tuple[str, ...] = (
    "welcome",
    "hostname",
    "wifi",
    "admin",
    "url",
    "summary",
)

SESSION_TIMEOUT_MINUTES: int = 30
REMEMBER_COOKIE_DAYS: int = 7
API_TOKEN_TTL_SECONDS: int = 4 * 3600
API_KEY_FILE: Path = CONFIG_DIR / "api_key"

INTERNET_CHECK_HOST: str = "1.1.1.1"
INTERNET_CHECK_PORT: int = 53
INTERNET_CHECK_TIMEOUT_SECONDS: float = 2.0

THERMAL_ZONE_FILE: Path = Path("/sys/class/thermal/thermal_zone0/temp")

LOG_VIEW_LINES: int = 200
LOG_FILES: dict[str, Path] = {
    "system": LOG_DIR / "system.log",
    "browser": LOG_DIR / "browser.log",
    "watchdog": LOG_DIR / "watchdog.log",
    "network": LOG_DIR / "network.log",
    "install": LOG_DIR / "install.log",
    "update": LOG_DIR / "update.log",
}

WATCHDOG_LOG_FILE: Path = LOG_DIR / "watchdog.log"
WATCHDOG_STATUS_FILE: Path = LOG_DIR / "watchdog_status.json"
WATCHDOG_INTERVAL_SECONDS: float = 5.0
WATCHDOG_STATUS_MAX_AGE_SECONDS: float = 20.0
WATCHDOG_TOKEN_HEADER: str = "X-Watchdog-Token"
HEALTH_CHECK_URL: str = f"http://127.0.0.1:{DEFAULT_PORT}/health"
BROWSER_RESTART_URL: str = f"http://127.0.0.1:{DEFAULT_PORT}/internal/browser/restart"
WATCHDOG_HTTP_TIMEOUT_SECONDS: float = 3.0

BROWSER_RESTART_LIMIT: int = 3
BROWSER_RESTART_WINDOW_SECONDS: float = 60.0

TEMPERATURE_WARNING_CELSIUS: float = 75.0
TEMPERATURE_CRITICAL_CELSIUS: float = 80.0
RAM_WARNING_PERCENT: float = 85.0
DISK_WARNING_PERCENT: float = 90.0

PING_BINARY: str = "ping"
PING_TIMEOUT_SECONDS: int = 2

BACKUP_PREFIX: str = "PiKiosk_Backup_"
BACKUP_TIMESTAMP_FORMAT: str = "%Y%m%d_%H%M"
BACKUP_NAME_REGEX: str = r"^PiKiosk_Backup_\d{8}_\d{4}\.zip$"
BACKUP_MANIFEST_MEMBER: str = "manifest.json"
BACKUP_CONFIG_MEMBER: str = "config/config.json"
BACKUP_USERS_MEMBER: str = "config/users.db"
USB_MOUNT_ROOTS: tuple[Path, ...] = (Path("/media"), Path("/run/media"))
USB_BACKUP_GLOB: str = "PiKiosk_Backup*.zip"
MAX_UPLOAD_BYTES: int = 50 * 1024 * 1024

UPDATE_MANIFEST_NAME: str = "manifest.json"
GITHUB_REPO: str = "grumel/PiKiosk-Pro"
GITHUB_API_BASE: str = "https://api.github.com"
UPDATE_HTTP_TIMEOUT_SECONDS: float = 15.0
UPDATE_PACKAGE_MAX_BYTES: int = 50 * 1024 * 1024
UPDATE_MAX_UNCOMPRESSED_BYTES: int = 200 * 1024 * 1024
RELEASES_DIR: Path = BACKUP_DIR / "releases"
UPDATE_USER_AGENT: str = f"PiKiosk-Pro/{APP_VERSION}"
UPDATE_REQUIRED_MEMBERS: tuple[str, ...] = (
    "app/constants.py",
    "app/__init__.py",
    "requirements.txt",
)
UPDATE_PROTECTED_PATHS: tuple[str, ...] = (
    "config/config.json",
    "config/users.db",
    "config/secret_key",
)
UPDATE_PROTECTED_PREFIXES: tuple[str, ...] = (
    "logs/",
    "backup/",
    ".venv/",
    "venv/",
    ".git/",
)

SYSTEMCTL_BINARY: str = "systemctl"
SYSTEM_COMMAND_TIMEOUT_SECONDS: float = 30.0

CONFIG_SCHEMA: dict[str, type] = {
    "hostname": str,
    "url": str,
    "language": str,
    "theme": str,
    "fullscreen": bool,
    "watchdog": bool,
    "browser": str,
    "first_start": bool,
    "update_source": str,
    "update_url": str,
    "connectivity_check": str,
    "wifi_preferred_ssid": str,
}
