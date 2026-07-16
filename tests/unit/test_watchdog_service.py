# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer den WatchdogService.

Alle externen Zugriffe (Health-Endpunkt, Neustart-Endpunkt,
Netzwerkpruefungen, Uhrzeit) werden durch steuerbare Ersatzobjekte
ausgetauscht, damit die Tests deterministisch laufen.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from app.constants import BROWSER_RESTART_LIMIT
from app.logger import KioskLogger
from app.services import watchdog_service as watchdog_module
from app.services.config_service import ConfigService
from app.services.watchdog_service import WatchdogService

DEFAULTS: dict[str, Any] = {
    "hostname": "PiKiosk",
    "url": "",
    "language": "de",
    "theme": "dark",
    "fullscreen": True,
    "watchdog": True,
    "browser": "chromium",
    "first_start": False,
}


@pytest.fixture
def service(
    tmp_path: Path,
    test_logger: KioskLogger,
    monkeypatch: pytest.MonkeyPatch,
) -> WatchdogService:
    """Erzeugt einen WatchdogService mit temporaeren Pfaden.

    Args:
        tmp_path:
            Temporaeres Testverzeichnis.

        test_logger:
            Testspezifischer Logger.

        monkeypatch:
            Pytest-Patchwerkzeug.

    Returns:
        Ein testbarer WatchdogService.
    """
    defaults_file = tmp_path / "defaults.json"
    defaults_file.write_text(
        json.dumps(DEFAULTS, ensure_ascii=False, indent=4), encoding="utf-8"
    )
    config_service = ConfigService(
        logger=test_logger,
        config_file=tmp_path / "config.json",
        defaults_file=defaults_file,
        backup_dir=tmp_path / "backup",
    )
    monkeypatch.setattr(
        watchdog_module,
        "WATCHDOG_STATUS_FILE",
        tmp_path / "watchdog_status.json",
    )
    return WatchdogService(
        logger=test_logger, config_service=config_service, token="test-token"
    )


class Clock:
    """Steuerbare Uhr fuer die Neustartverwaltung."""

    def __init__(self) -> None:
        self.value = 1000.0

    def advance(self, seconds: float) -> None:
        self.value += seconds


def use_clock(service: WatchdogService, monkeypatch: pytest.MonkeyPatch) -> Clock:
    """Ersetzt die monotone Uhr des Watchdogs.

    Args:
        service:
            Zu patchender WatchdogService.

        monkeypatch:
            Pytest-Patchwerkzeug.

    Returns:
        Die steuerbare Uhr.
    """
    clock = Clock()
    monkeypatch.setattr(service, "_now", lambda: clock.value)
    return clock


class TestBrowserWatchdog:
    """Tests fuer die Browserueberwachung."""

    def test_neustart_bei_absturz(
        self, service: WatchdogService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        restarts: list[bool] = []
        monkeypatch.setattr(service, "_fetch_health", lambda: {"browser": "crashed"})
        monkeypatch.setattr(
            service, "_request_restart", lambda: restarts.append(True) or True
        )
        use_clock(service, monkeypatch)
        result = service._check_browser()
        assert len(restarts) == 1
        assert result["failed"] is False
        assert result["restarts_in_window"] == 1

    def test_maximal_drei_neustarts_in_60_sekunden(
        self, service: WatchdogService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        restarts: list[bool] = []
        monkeypatch.setattr(service, "_fetch_health", lambda: {"browser": "crashed"})
        monkeypatch.setattr(
            service, "_request_restart", lambda: restarts.append(True) or True
        )
        clock = use_clock(service, monkeypatch)
        for _ in range(6):
            service._check_browser()
            clock.advance(5.0)
        assert len(restarts) == BROWSER_RESTART_LIMIT
        assert service._check_browser()["failed"] is True

    def test_fehlerstatus_wird_bei_laufendem_browser_geloescht(
        self, service: WatchdogService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(service, "_fetch_health", lambda: {"browser": "crashed"})
        monkeypatch.setattr(service, "_request_restart", lambda: True)
        clock = use_clock(service, monkeypatch)
        for _ in range(5):
            service._check_browser()
            clock.advance(1.0)
        assert service._browser_failed is True
        monkeypatch.setattr(service, "_fetch_health", lambda: {"browser": "running"})
        result = service._check_browser()
        assert result["failed"] is False
        assert result["restarts_in_window"] == 0

    def test_neustarts_ausserhalb_des_fensters_zaehlen_nicht(
        self, service: WatchdogService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        restarts: list[bool] = []
        monkeypatch.setattr(service, "_fetch_health", lambda: {"browser": "crashed"})
        monkeypatch.setattr(
            service, "_request_restart", lambda: restarts.append(True) or True
        )
        clock = use_clock(service, monkeypatch)
        for _ in range(6):
            service._check_browser()
            clock.advance(61.0)
        assert len(restarts) == 6
        assert service._browser_failed is False

    def test_hauptanwendung_offline(
        self, service: WatchdogService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(service, "_fetch_health", lambda: None)
        result = service._check_browser()
        assert result["status"] == "app_offline"

    def test_gestoppter_browser_wird_nicht_neu_gestartet(
        self, service: WatchdogService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_restart() -> bool:
            raise AssertionError("Neustart darf nicht ausgeloest werden")

        monkeypatch.setattr(
            service, "_fetch_health", lambda: {"browser": "not_started"}
        )
        monkeypatch.setattr(service, "_request_restart", fail_restart)
        result = service._check_browser()
        assert result["status"] == "not_started"


class TestOverallStatus:
    """Tests fuer die Gesamtbewertung."""

    def make(
        self,
        browser_status: str = "running",
        failed: bool = False,
        internet: bool = True,
        gateway: bool = True,
        dns: bool = True,
        url: bool | None = True,
        warnings: list[str] | None = None,
    ) -> str:
        browser = {"status": browser_status, "failed": failed}
        network = {
            "internet": internet,
            "gateway": gateway,
            "dns": dns,
            "url": url,
        }
        system = {"warnings": warnings or []}
        dummy = WatchdogService.__new__(WatchdogService)
        return dummy._overall(browser, network, system)

    def test_alles_in_ordnung(self) -> None:
        assert self.make() == "online"

    def test_browserfehler_ergibt_error(self) -> None:
        assert self.make(failed=True) == "error"

    def test_app_offline_ergibt_error(self) -> None:
        assert self.make(browser_status="app_offline") == "error"

    def test_kritische_temperatur_ergibt_error(self) -> None:
        assert self.make(warnings=["temperature_critical"]) == "error"

    def test_kein_internet_ergibt_offline(self) -> None:
        assert self.make(internet=False) == "offline"

    def test_systemwarnung_ergibt_warning(self) -> None:
        assert self.make(warnings=["ram_warning"]) == "warning"

    def test_url_fehler_ergibt_warning(self) -> None:
        assert self.make(url=False) == "warning"

    def test_url_ohne_konfiguration_ist_ok(self) -> None:
        assert self.make(url=None) == "online"


class TestCheckOnce:
    """Tests fuer den kompletten Pruefzyklus."""

    def test_status_wird_geschrieben(
        self,
        service: WatchdogService,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(service, "_fetch_health", lambda: {"browser": "running"})
        monkeypatch.setattr(
            service,
            "_check_network",
            lambda url: {
                "gateway": True,
                "dns": True,
                "internet": True,
                "url": None,
            },
        )
        status = service.check_once()
        assert status["overall"] == "online"
        written = json.loads(
            (tmp_path / "watchdog_status.json").read_text(encoding="utf-8")
        )
        assert written["overall"] == "online"
        assert written["browser"]["status"] == "running"
        assert "timestamp" in written

    def test_deaktivierter_watchdog(
        self,
        service: WatchdogService,
        tmp_path: Path,
        test_logger: KioskLogger,
    ) -> None:
        config = service._config_service.load()
        config["watchdog"] = False
        service._config_service.save(config)
        status = service.check_once()
        assert status["overall"] == "disabled"

    def test_systemwarnungen_bei_grenzwerten(
        self, service: WatchdogService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class FakeMemory:
            percent = 90.0

        class FakeDisk:
            percent = 95.0

        monkeypatch.setattr(
            watchdog_module.psutil, "virtual_memory", lambda: FakeMemory()
        )
        monkeypatch.setattr(
            watchdog_module.psutil, "disk_usage", lambda path: FakeDisk()
        )
        monkeypatch.setattr(
            watchdog_module.psutil, "cpu_percent", lambda interval: 10.0
        )
        monkeypatch.setattr(watchdog_module, "cpu_temperature", lambda: 78.0)
        system = service._check_system()
        assert set(system["warnings"]) == {
            "temperature_warning",
            "ram_warning",
            "disk_warning",
        }

    def test_kritische_temperatur(
        self, service: WatchdogService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(watchdog_module, "cpu_temperature", lambda: 81.0)
        system = service._check_system()
        assert "temperature_critical" in system["warnings"]
