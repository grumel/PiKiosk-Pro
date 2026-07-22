# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Kiosk-Tastenueberwachung.

Liest die Tastatur direkt ueber die Kernel-Schnittstelle
/dev/input (unabhaengig von X11 oder Wayland) und lenkt den
Kioskbrowser bei einer konfigurierten Tastenkombination auf die
lokale Verwaltung um. So kommt der Administrator per Tastendruck
aus dem Kiosk-Vollbild in das Dashboard, ohne den Browser neu zu
starten.

Der Zugriff auf /dev/input setzt Mitgliedschaft in der Gruppe
"input" voraus; die systemd-Unit gewaehrt sie ueber
SupplementaryGroups.
"""

import glob
import selectors
import struct
import sys
import urllib.error
import urllib.request
from typing import BinaryIO

from app.constants import (
    CDP_HOST,
    CDP_PORT,
    DEFAULT_HOST,
    DEFAULT_PORT,
    SYSTEM_LOG_FILE,
)
from app.exceptions import ValidationError
from app.logger import KioskLogger
from app.services.config_service import ConfigService
from app.utils.helpers import local_base_url
from app.utils.hotkeys import EV_KEY, HotkeyMatcher, parse_combo
from app.utils.network import DevToolsClient

# Groesse einer struct input_event der laufenden Plattform. Die
# letzten acht Bytes sind immer type (H), code (H) und value (i);
# davor liegt der plattformabhaengig grosse Zeitstempel.
EVENT_SIZE: int = struct.calcsize("@llHHi")
EVENT_TAIL: str = "HHi"
INPUT_DEVICE_GLOB: str = "/dev/input/event*"
DASHBOARD_PATH: str = "dashboard/"


def dashboard_url() -> str:
    """Bestimmt die lokale Dashboard-URL fuer die Umleitung.

    Es wird die lokale Basis-URL verwendet (bei aktivem TLS der
    HTTP-Loopback-Listener), damit der Browser ohne
    Zertifikatswarnung landet.

    Returns:
        Vollstaendige URL des lokalen Dashboards.
    """
    return local_base_url().rstrip("/") + "/" + DASHBOARD_PATH


def open_keyboards(logger: KioskLogger) -> list[BinaryIO]:
    """Oeffnet alle lesbaren Eingabegeraete.

    Args:
        logger:
            Logger fuer Hinweise.

    Returns:
        Liste geoeffneter Geraetedateien.
    """
    devices: list[BinaryIO] = []
    for path in sorted(glob.glob(INPUT_DEVICE_GLOB)):
        try:
            devices.append(open(path, "rb", buffering=0))
        except OSError as error:
            logger.warning(f"Eingabegeraet {path} nicht lesbar: {error}")
    return devices


def read_events(device: BinaryIO) -> list[tuple[int, int, int]]:
    """Liest anstehende Ereignisse eines Geraets.

    Args:
        device:
            Geoeffnete Geraetedatei.

    Returns:
        Liste von (Typ, Code, Wert). Bei einem Lesefehler leer.
    """
    try:
        data = device.read(EVENT_SIZE * 64)
    except OSError:
        return []
    if not data:
        return []
    events: list[tuple[int, int, int]] = []
    for offset in range(0, len(data) - EVENT_SIZE + 1, EVENT_SIZE):
        chunk = data[offset : offset + EVENT_SIZE]
        event_type, code, value = struct.unpack(EVENT_TAIL, chunk[-8:])
        events.append((event_type, code, value))
    return events


def _trigger(logger: KioskLogger, client: DevToolsClient, url: str) -> None:
    """Lenkt den Browser auf die Dashboard-URL um.

    Args:
        logger:
            Logger fuer das Ergebnis.

        client:
            DevTools-Client des Kioskbrowsers.

        url:
            Zieladresse.
    """
    logger.info(f"Tastenkombination erkannt, Browser wird auf {url} umgeleitet.")
    try:
        client.navigate(url)
    except Exception as error:  # noqa: BLE001 - Dienst darf nie sterben.
        logger.error(f"Umleitung fehlgeschlagen: {error}")


def monitor(
    logger: KioskLogger,
    matcher: HotkeyMatcher,
    client: DevToolsClient,
    devices: list[BinaryIO],
    url: str,
) -> None:
    """Ueberwacht die Tastatur dauerhaft und loest die Umleitung aus.

    Args:
        logger:
            Logger fuer alle Ereignisse.

        matcher:
            Erkenner der Tastenkombination.

        client:
            DevTools-Client des Kioskbrowsers.

        devices:
            Geoeffnete Eingabegeraete.

        url:
            Zieladresse der Umleitung.
    """
    selector = selectors.DefaultSelector()
    for device in devices:
        selector.register(device, selectors.EVENT_READ)
    while True:
        for key, _ in selector.select():
            for event_type, code, value in read_events(key.fileobj):  # type: ignore[arg-type]
                if event_type != EV_KEY:
                    continue
                if matcher.feed(code, value):
                    _trigger(logger, client, url)


def _check_line(label: str, ok: bool, detail: str) -> None:
    """Gibt eine Zeile des Selbsttests aus.

    Args:
        label:
            Kurzbezeichnung der Pruefung.

        ok:
            True, wenn die Pruefung bestanden ist.

        detail:
            Erklaerung des Ergebnisses.
    """
    mark = "OK  " if ok else "FEHL"
    print(f"[{mark}] {label:<14} {detail}", flush=True)


def check() -> int:
    """Fuehrt einen Selbsttest aus und gibt einen Bericht aus.

    Prueft nacheinander die vier Voraussetzungen fuer die
    Tastenkombination: gueltige Kombination, lesbare Tastatur,
    fernsteuerbarer Browser und erreichbares Dashboard. Das Ergebnis
    wird kompakt auf die Standardausgabe geschrieben.

    Returns:
        0, wenn alles bereit ist, sonst 1.
    """
    from app.exceptions import NetworkError

    print("PiKiosk Kiosk-Tastenueberwachung - Selbsttest", flush=True)
    ready = True

    config_service = ConfigService(logger=KioskLogger("keymon-check", SYSTEM_LOG_FILE))
    try:
        combo = str(config_service.load().get("escape_hotkey", "")).strip()
    except Exception as error:  # noqa: BLE001 - Selbsttest darf nie abstuerzen.
        _check_line("Kombination", False, f"Konfiguration nicht lesbar: {error}")
        return 1
    try:
        parse_combo(combo) if combo else None
        _check_line(
            "Kombination",
            bool(combo),
            combo or "leer (Funktion ist ausgeschaltet)",
        )
        ready = ready and bool(combo)
    except ValidationError as error:
        _check_line("Kombination", False, f"'{combo}' ungueltig: {error}")
        ready = False

    devices = open_keyboards(KioskLogger("keymon-check", SYSTEM_LOG_FILE))
    names = ", ".join(
        getattr(device, "name", "?").rsplit("/", 1)[-1] for device in devices
    )
    _check_line(
        "Tastatur",
        bool(devices),
        (
            f"{len(devices)} Eingabegeraete lesbar ({names})"
            if devices
            else "keine lesbar - als root testen bzw. Gruppe 'input' pruefen"
        ),
    )
    for device in devices:
        device.close()
    ready = ready and bool(devices)

    client = DevToolsClient(CDP_HOST, CDP_PORT)
    try:
        client.probe()
        _check_line("Browser-CDP", True, f"{CDP_HOST}:{CDP_PORT} steuerbar")
    except NetworkError as error:
        _check_line(
            "Browser-CDP",
            False,
            f"{CDP_HOST}:{CDP_PORT} nicht steuerbar ({error}) - "
            "laeuft der Kioskbrowser? Ggf. pikiosk.service neu starten.",
        )
        ready = False

    url = dashboard_url()
    try:
        with urllib.request.urlopen(url, timeout=4.0) as response:
            status = int(response.status)
        _check_line("Dashboard", True, f"{url} erreichbar (HTTP {status})")
    except (urllib.error.URLError, OSError) as error:
        _check_line("Dashboard", False, f"{url} nicht erreichbar ({error})")
        ready = False

    print("Ergebnis:", "BEREIT" if ready else "NICHT BEREIT (siehe oben)")
    return 0 if ready else 1


def main() -> int:
    """Startet die Kiosk-Tastenueberwachung.

    Returns:
        Exit-Code des Programms.
    """
    if "--check" in sys.argv[1:]:
        return check()

    logger = KioskLogger("keymon", SYSTEM_LOG_FILE)
    config_service = ConfigService(logger=logger)
    try:
        combo = str(config_service.load().get("escape_hotkey", "")).strip()
    except Exception as error:  # noqa: BLE001 - ohne Konfiguration kein Betrieb.
        logger.error(f"Konfiguration nicht lesbar: {error}")
        return 1
    if not combo:
        logger.info("Keine Escape-Tastenkombination konfiguriert, Dienst beendet.")
        return 0
    try:
        groups = parse_combo(combo)
    except ValidationError as error:
        logger.error(f"Ungueltige Tastenkombination '{combo}': {error}")
        return 1
    devices = open_keyboards(logger)
    if not devices:
        logger.error("Keine lesbaren Eingabegeraete gefunden (Gruppe 'input'?).")
        return 1
    url = dashboard_url()
    logger.info(
        f"Kiosk-Tastenueberwachung aktiv: '{combo}' leitet auf {url} um "
        f"(Server {DEFAULT_HOST}:{DEFAULT_PORT})."
    )
    client = DevToolsClient(CDP_HOST, CDP_PORT)
    try:
        monitor(logger, HotkeyMatcher(groups), client, devices, url)
    except KeyboardInterrupt:
        return 0
    finally:
        for device in devices:
            device.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
