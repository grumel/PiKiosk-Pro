# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer den DashboardService."""

from datetime import datetime, timedelta

from app.constants import APP_VERSION
from app.extensions import ServiceRegistry

EXPECTED_KEYS = {
    "hostname",
    "device",
    "ip_address",
    "mac_address",
    "cpu_percent",
    "ram_percent",
    "ram_used_mb",
    "ram_total_mb",
    "temperature",
    "disk_percent",
    "disk_free_gb",
    "disk_total_gb",
    "browser_status",
    "internet_online",
    "watchdog",
    "url",
    "version",
    "last_boot",
    "uptime",
}


class TestDashboardService:
    """Tests fuer die Dashboard-Systeminformationen."""

    def test_data_enthaelt_alle_felder(self, registry: ServiceRegistry) -> None:
        data = registry.dashboard_service.data()
        assert set(data.keys()) == EXPECTED_KEYS

    def test_data_liefert_plausible_werte(self, registry: ServiceRegistry) -> None:
        data = registry.dashboard_service.data()
        assert data["version"] == APP_VERSION
        assert data["browser_status"] == "not_started"
        assert 0 <= float(data["ram_percent"]) <= 100
        assert 0 <= float(data["disk_percent"]) <= 100
        assert data["ram_total_mb"] > 0
        assert isinstance(data["internet_online"], bool)
        assert isinstance(data["hostname"], str) and data["hostname"]

    def test_uptime_formatierung(self, registry: ServiceRegistry) -> None:
        boot_time = datetime.now() - timedelta(days=2, hours=3, minutes=15)
        uptime = registry.dashboard_service._format_uptime(boot_time)
        assert uptime == "2d 03:15"

    def test_uptime_niemals_negativ(self, registry: ServiceRegistry) -> None:
        boot_time = datetime.now() + timedelta(minutes=5)
        uptime = registry.dashboard_service._format_uptime(boot_time)
        assert uptime == "0d 00:00"
