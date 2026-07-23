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

    def test_connect_mit_passwort_speichert_profil_dauerhaft(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = scripted(
            service,
            monkeypatch,
            ["", "", "", DEVICE_OUTPUT, DEVICE_SHOW_IP],
        )
        service.connect("Zuhause", "geheim-123")
        assert runner.calls[0] == ["-t", "-f", "NAME,TYPE", "connection", "show"]
        assert runner.calls[1][:4] == ["connection", "add", "type", "wifi"]
        assert "wifi-sec.psk-flags" in runner.calls[1]
        assert "0" in runner.calls[1]
        assert "connection.autoconnect" in runner.calls[1]
        assert runner.calls[2] == ["connection", "up", "id", "Zuhause"]

    def test_connect_offenes_netz_ohne_profil(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = scripted(
            service,
            monkeypatch,
            ["Device 'wlan0' successfully activated.\n", DEVICE_OUTPUT, DEVICE_SHOW_IP],
        )
        service.connect("Offen")
        assert runner.calls[0] == ["device", "wifi", "connect", "Offen"]

    def test_connect_falsches_passwort_entfernt_neues_profil(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = scripted(
            service,
            monkeypatch,
            [
                "",
                "",
                NetworkError("Error: Secrets were required, but not provided."),
                "",
            ],
        )
        with pytest.raises(WifiError) as info:
            service.connect("Zuhause", "falsch-123")
        assert info.value.reason == "wrong_password"
        assert runner.calls[-1] == ["connection", "delete", "Zuhause"]

    def test_connect_ohne_berechtigung(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(
            service,
            monkeypatch,
            [
                "",
                NetworkError(
                    "Error: Failed to add/activate new connection: "
                    "Not authorized to control networking."
                ),
            ],
        )
        with pytest.raises(WifiError) as info:
            service.connect("Zuhause", "geheim-123")
        assert info.value.reason == "not_authorized"

    def test_connect_ssid_nicht_gefunden(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(
            service,
            monkeypatch,
            [
                "",
                "",
                NetworkError("Error: No network with SSID 'Fehlt' found."),
                "",
            ],
        )
        with pytest.raises(WifiError) as info:
            service.connect("Fehlt", "egal-1234")
        assert info.value.reason == "not_found"

    def test_connect_ohne_ip(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(
            service,
            monkeypatch,
            ["", "", "", DEVICE_OUTPUT, ""],
        )
        with pytest.raises(WifiError) as info:
            service.connect("Zuhause", "geheim-123")
        assert info.value.reason == "no_ip"

    def test_connect_ohne_ssid(self, service: NetworkService) -> None:
        with pytest.raises(WifiError):
            service.connect("")

    def test_connect_zu_kurzes_passwort(self, service: NetworkService) -> None:
        with pytest.raises(WifiError) as info:
            service.connect("Zuhause", "kurz")
        assert info.value.reason == "invalid_password"

    def test_connect_offenes_netz_fehler_wird_uebersetzt(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(
            service,
            monkeypatch,
            [NetworkError("Error: No network with SSID 'Offen' found.")],
        )
        with pytest.raises(WifiError) as info:
            service.connect("Offen")
        assert info.value.reason == "not_found"

    def test_connect_aufraeumen_scheitert_wird_geloggt(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(
            service,
            monkeypatch,
            [
                "",
                "",
                NetworkError("Error: Secrets were required, but not provided."),
                NetworkError("Error: connection could not be deleted."),
            ],
        )
        with pytest.raises(WifiError) as info:
            service.connect("Zuhause", "geheim-123")
        assert info.value.reason == "wrong_password"


class TestSaveProfile:
    """Tests fuer das dauerhafte Speichern von WLAN-Profilen."""

    def test_neues_profil_wird_angelegt(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = scripted(service, monkeypatch, ["", ""])
        created = service.save_profile("Zuhause", "geheim-123", priority=10)
        assert created is True
        add = runner.calls[1]
        assert add[:4] == ["connection", "add", "type", "wifi"]
        assert add[add.index("wifi-sec.psk") + 1] == "geheim-123"
        assert add[add.index("wifi-sec.psk-flags") + 1] == "0"
        assert add[add.index("connection.autoconnect") + 1] == "yes"
        assert add[add.index("connection.autoconnect-priority") + 1] == "10"

    def test_vorhandenes_profil_wird_aktualisiert(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = scripted(service, monkeypatch, ["Zuhause:802-11-wireless\n", ""])
        created = service.save_profile("Zuhause", "Neu-Pass-2026!", priority=10)
        assert created is False
        assert runner.calls[1][:4] == ["connection", "modify", "id", "Zuhause"]

    def test_sonderzeichen_bleiben_erhalten(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = scripted(service, monkeypatch, ["", ""])
        service.save_profile("Café Netz", "Pa%s wört mit Leerzeichen!")
        add = runner.calls[1]
        assert add[add.index("ssid") + 1] == "Café Netz"
        assert add[add.index("wifi-sec.psk") + 1] == "Pa%s wört mit Leerzeichen!"

    def test_zu_kurzes_passwort_wird_abgelehnt(self, service: NetworkService) -> None:
        with pytest.raises(WifiError) as info:
            service.save_profile("Zuhause", "kurz")
        assert info.value.reason == "invalid_password"

    def test_leere_ssid_wird_abgelehnt(self, service: NetworkService) -> None:
        with pytest.raises(WifiError):
            service.save_profile("", "geheim-123")

    def test_nmcli_fehler_wird_uebersetzt(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(
            service,
            monkeypatch,
            [
                "Zuhause:802-11-wireless\n",
                NetworkError("Error: Not authorized to control networking."),
            ],
        )
        with pytest.raises(WifiError) as info:
            service.save_profile("Zuhause", "geheim-123")
        assert info.value.reason == "not_authorized"


class TestSetAutoconnect:
    """Tests fuer die automatische Verbindung gespeicherter Profile."""

    def test_setzt_autoconnect_und_prioritaet(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = scripted(service, monkeypatch, ["Zuhause:802-11-wireless\n", ""])
        service.set_autoconnect("Zuhause", 10)
        modify = runner.calls[1]
        assert modify[:4] == ["connection", "modify", "id", "Zuhause"]
        assert modify[modify.index("connection.autoconnect-priority") + 1] == "10"

    def test_unbekanntes_profil_wird_abgelehnt(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(service, monkeypatch, [""])
        with pytest.raises(WifiError) as info:
            service.set_autoconnect("Fehlt", 10)
        assert info.value.reason == "not_found"

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


class TestConnectSaved:
    """Tests fuer die Verbindung mit gespeicherten Profilen."""

    def test_verbindet_ohne_passwort(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = scripted(service, monkeypatch, [CONNECTIONS_OUTPUT, ""])
        service.connect_saved("Zuhause")
        assert runner.calls[1] == ["connection", "up", "id", "Zuhause"]

    def test_unbekanntes_profil(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(service, monkeypatch, [CONNECTIONS_OUTPUT])
        with pytest.raises(WifiError) as info:
            service.connect_saved("Fremd")
        assert info.value.reason == "not_found"

    def test_ohne_ssid(self, service: NetworkService) -> None:
        with pytest.raises(WifiError):
            service.connect_saved("")

    def test_fehler_wird_uebersetzt(
        self, service: NetworkService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        scripted(
            service,
            monkeypatch,
            [
                CONNECTIONS_OUTPUT,
                NetworkError("Error: Not authorized to control networking."),
            ],
        )
        with pytest.raises(WifiError):
            service.connect_saved("Zuhause")
