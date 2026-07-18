# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Ende-zu-Ende-Rauchtests mit echtem Chromium.

Diese Tests fahren die Anwendung auf dem Cheroot-Server hoch und
bedienen sie mit einem echten Browser (Playwright). Sie sichern
genau die Fehlerklasse ab, die reine Python-Tests nicht sehen:
das Zusammenspiel von Browser, HTMX und JavaScript. Ohne
installiertes Playwright samt Browser werden die Tests
uebersprungen.
"""

import socket
import threading
import time
from typing import Any, Iterator

import pytest

playwright_api = pytest.importorskip(
    "playwright.sync_api", reason="Playwright ist nicht installiert."
)

from app import create_app  # noqa: E402
from app.extensions import ServiceRegistry  # noqa: E402
from app.server import build_server  # noqa: E402

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Sicher-2026-Kiosk!"
E2E_TIMEOUT_MS = 20000


def _free_port() -> int:
    """Reserviert einen freien TCP-Port.

    Returns:
        Ein aktuell freier Port.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture
def app_url(registry: ServiceRegistry) -> Iterator[str]:
    """Startet die Anwendung auf einem freien Port.

    Args:
        registry:
            ServiceRegistry mit temporaeren Datenpfaden.

    Yields:
        Basis-URL der laufenden Anwendung.
    """
    app = create_app(registry)
    port = _free_port()
    server = build_server(app, "127.0.0.1", port)
    thread = threading.Thread(target=server.safe_start, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.1)
    else:
        raise AssertionError("Anwendung wurde nicht bereit.")
    yield f"http://127.0.0.1:{port}"
    server.stop()
    thread.join(timeout=5.0)


@pytest.fixture
def page() -> Iterator[Any]:
    """Stellt eine Chromium-Seite bereit.

    Yields:
        Eine Playwright-Seite; uebersprungen, wenn kein Browser
        startbar ist.
    """
    with playwright_api.sync_playwright() as manager:
        try:
            browser = manager.chromium.launch()
        except Exception as error:  # noqa: BLE001 - Umgebung ohne Browser.
            pytest.skip(f"Chromium nicht startbar: {error}")
        browser_page = browser.new_page()
        browser_page.set_default_timeout(E2E_TIMEOUT_MS)
        yield browser_page
        browser.close()


class TestWizardSmoke:
    """Rauchtest fuer den Einrichtungsassistenten im echten Browser."""

    def test_hostname_pruefen_funktioniert(
        self, app_url: str, page: Any, registry: ServiceRegistry
    ) -> None:
        page.goto(f"{app_url}/setup/")
        playwright_api.expect(
            page.get_by_text("Willkommen bei PiKiosk Pro")
        ).to_be_visible(timeout=E2E_TIMEOUT_MS)
        page.get_by_role("button", name="Weiter").click()
        hostname_field = page.locator("#hostname")
        playwright_api.expect(hostname_field).to_be_visible(timeout=E2E_TIMEOUT_MS)
        hostname_field.fill("PiKiosk-E2E")
        page.get_by_role("button", name="Prüfen").click()
        playwright_api.expect(
            page.get_by_text("Der Hostname ist gültig und wurde übernommen.")
        ).to_be_visible(timeout=E2E_TIMEOUT_MS)


class TestLoginSmoke:
    """Rauchtest fuer die Anmeldung im echten Browser."""

    def test_anmeldung_bis_zum_dashboard(
        self, app_url: str, page: Any, registry: ServiceRegistry
    ) -> None:
        config = registry.config_service.load()
        config["first_start"] = False
        registry.config_service.save(config)
        password_hash = registry.auth_service.hash_password(ADMIN_PASSWORD)
        registry.auth_service.create_administrator(ADMIN_USERNAME, password_hash)
        page.goto(f"{app_url}/login")
        page.locator("#username").fill(ADMIN_USERNAME)
        page.locator("#password").fill(ADMIN_PASSWORD)
        page.get_by_role("button", name="Anmelden").click()
        playwright_api.expect(page.locator("#dashboard-data")).to_be_visible(
            timeout=E2E_TIMEOUT_MS
        )
