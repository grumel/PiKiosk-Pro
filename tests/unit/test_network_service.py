# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer den NetworkService.

Alle nmcli-Aufrufe werden durch vorbereitete Ausgaben ersetzt,
damit die Tests ohne NetworkManager laufen.
"""

from typing import Any

import pytest

from app.exceptions import NetworkError, WifiError
from app.logger import KioskLogger
from app.services import network_service as network_module
from app.services.network_service import NetworkService, split_terse_line

SCAN_OUTPUT = (
    "*:Zuhause:87:WPA2:5180 MHz\n"
    ":Nachbarn:42:WPA1 WPA2:2412 MHz\n"
    ":Zuhause:55:WPA2:2437 MHz\n"
    ":Offen:30::2462 MHz\n"
    "::17:WPA2:2422 MHz\n"
)
ACTIVE_OUTPUT = "no:Nachbarn:42:WPA2\nyes:Zuhause:87:WPA2\n"
CONNECTIONS_OUTPUT = (
    "Zuhause:802-11-wireless\nKabel:802-3-ethernet\nBuero:802-11-wireless\n"
)
DEVICE_OUTPUT = "eth0:ethernet\nwlan0:wifi\n"
DEVICE_SHOW_IP = "IP4.ADDRESS[1]:192.168.178.85/24\n"
DEVICE_SHOW_DNS = "IP4.DNS[1]:192.168.178.1\nIP4.DNS[2]:9.9.9.9\n"
DEVICE_SHOW_MAC = "GENERAL.HWADDR:AA\\:BB\\:CC\\:DD\\:EE\\:FF\n"


class ScriptedRunner:
    """Liefert vorbereitete nmcli-Ausgaben je Aufruf."""

    def __init__(self, outputs: list[str | NetworkError]) -> None:
        self.outputs = outputs
        self.calls: list[list[str]] = []

    def __call__(self, arguments: list[str]) -> str:
        self.calls.append(arguments)
        result = self.outputs.pop(0)
        if isinstance(result, NetworkError):
            raise result
        return result


@pytest.fixture
def service(test_logger: KioskLogger) -> NetworkService:
    """Erzeugt einen NetworkService fuer die Tests.

    Args:
        test_logger:
            Testspezifischer Logger.

    Returns:
        Ein einsatzbereiter NetworkService.
    """
    return NetworkService(logger=test_logger)


def scripted(
    service: NetworkService,
    monkeypatch: pytest.MonkeyPatch,
    outputs: list[str | NetworkError],
) -> ScriptedRunner:
    """Ersetzt die nmcli-Ausfuehrung durch vorbereitete Ausgaben.

    Args:
        service:
            Zu patchender NetworkService.

        monkeypatch:
            Pytest-Patchwerkzeug.

        outputs:
            Ausgaben oder Fehler in Aufrufreihenfolge.

    Returns:
        Der eingesetzte ScriptedRunner.
    """
    runner = ScriptedRunner(outputs)
    monkeypatch.setattr(service, "_run", runner)
    return runner


class TestSplitTerseLine:
    """Tests fuer den Terse-Zeilenparser."""

    def test_einfache_felder(self) -> None:
        assert split_terse_line("a:b:c") == ["a", "b", "c"]

    def test_maskierte_doppelpunkte(self) -> None:
        assert split_terse_line("GENERAL.HWADDR:AA\\:BB\\:CC") == [
            "GENERAL.HWADDR",
            "AA:BB:CC",
        ]

    def test_leere_felder(self) -> None:
        assert split_terse_line("::x") == ["", "", "x"]


class TestNetworkService:
    """Tests fuer die WLAN-Verwaltung."""

    def test_scan_dedupliziert_und_sortiert(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(service, monkeypatch, [SCAN_OUTPUT])
        networks = service.scan()
        assert [n["ssid"] for n in networks] == ["Zuhause", "Nachbarn", "Offen"]
        assert networks[0]["signal"] == 87
        assert networks[0]["in_use"] is True
        assert networks[2]["security"] == "-"

    def test_current_liefert_aktives_wlan(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(service, monkeypatch, [ACTIVE_OUTPUT])
        active = service.current()
        assert active is not None
        assert active["ssid"] == "Zuhause"
        assert active["signal"] == 87

    def test_current_ohne_verbindung(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(service, monkeypatch, ["no:Nachbarn:42:WPA2\n"])
        assert service.current() is None

    def test_saved_filtert_wlan_profile(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(service, monkeypatch, [CONNECTIONS_OUTPUT])
        assert service.saved() == ["Zuhause", "Buero"]

    def test_ip_entfernt_praefix(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(service, monkeypatch, [DEVICE_OUTPUT, DEVICE_SHOW_IP])
        assert service.ip() == "192.168.178.85"

    def test_dns_liefert_alle_server(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(service, monkeypatch, [DEVICE_OUTPUT, DEVICE_SHOW_DNS])
        assert service.dns() == ["192.168.178.1", "9.9.9.9"]

    def test_mac_mit_maskierten_doppelpunkten(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(service, monkeypatch, [DEVICE_OUTPUT, DEVICE_SHOW_MAC])
        assert service.mac() == "AA:BB:CC:DD:EE:FF"

    def test_mac_ohne_maskierte_doppelpunkte(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(
            service,
            monkeypatch,
            [DEVICE_OUTPUT, "GENERAL.HWADDR:AA:BB:CC:DD:EE:FF\n"],
        )
        assert service.mac() == "AA:BB:CC:DD:EE:FF"

    def test_signal_ohne_verbindung(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(service, monkeypatch, ["no:Nachbarn:42:WPA2\n"])
        assert service.signal() == 0

    def test_kein_wlan_geraet(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(service, monkeypatch, ["eth0:ethernet\n"])
        with pytest.raises(NetworkError):
            service.ip()

    def test_connect_erfolgreich(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = scripted(
            service,
            monkeypatch,
            ["Device 'wlan0' successfully activated.\n", DEVICE_OUTPUT, DEVICE_SHOW_IP],
        )
        service.connect("Zuhause", "geheim")
        assert runner.calls[0][:4] == ["device", "wifi", "connect", "Zuhause"]
        assert "password" in runner.calls[0]

    def test_connect_falsches_passwort(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(
            service,
            monkeypatch,
            [NetworkError("Error: Secrets were required, but not provided.")],
        )
        with pytest.raises(WifiError) as info:
            service.connect("Zuhause", "falsch")
        assert info.value.reason == "wrong_password"

    def test_connect_ssid_nicht_gefunden(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(
            service,
            monkeypatch,
            [NetworkError("Error: No network with SSID 'Fehlt' found.")],
        )
        with pytest.raises(WifiError) as info:
            service.connect("Fehlt", "egal")
        assert info.value.reason == "not_found"

    def test_connect_ohne_ip(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(
            service,
            monkeypatch,
            ["Device 'wlan0' successfully activated.\n", DEVICE_OUTPUT, ""],
        )
        with pytest.raises(WifiError) as info:
            service.connect("Zuhause", "geheim")
        assert info.value.reason == "no_ip"

    def test_connect_ohne_ssid(self, service: NetworkService) -> None:
        with pytest.raises(WifiError):
            service.connect("")

    def test_delete_ruft_nmcli(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = scripted(service, monkeypatch, [""])
        service.delete("Zuhause")
        assert runner.calls[0] == ["connection", "delete", "Zuhause"]

    def test_disconnect_verwendet_wlan_geraet(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = scripted(service, monkeypatch, [DEVICE_OUTPUT, ""])
        service.disconnect()
        assert runner.calls[1] == ["device", "disconnect", "wlan0"]

    def test_run_setzt_neutrale_locale(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}

        class FakeResult:
            returncode = 0
            stdout = ""
            stderr = ""

        def fake_run(command: list[str], **kwargs: Any) -> FakeResult:
            captured["command"] = command
            captured["env"] = kwargs["env"]
            return FakeResult()

        monkeypatch.setattr(network_module.subprocess, "run", fake_run)
        service._run(["device"])
        assert captured["env"]["LC_ALL"] == "C"
        assert captured["command"][0] == "nmcli"
