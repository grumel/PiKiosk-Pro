# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Center - Unit-Tests fuer Geraetemodell und DeviceService."""

from pathlib import Path

import pytest

from app.exceptions import ValidationError
from app.logger import KioskLogger
from app.utils.crypto import decrypt_secret, load_or_create_fernet_key
from center.models.device_model import DeviceError, DeviceModel
from center.services.device_service import DeviceService

DEVICE_PASSWORD = "Geraet-Geheim-2026!"


@pytest.fixture
def key(tmp_path: Path) -> bytes:
    """Erzeugt einen Verschluesselungsschluessel fuer die Tests.

    Args:
        tmp_path:
            Temporaeres Testverzeichnis.

    Returns:
        Der Fernet-Schluessel.
    """
    return load_or_create_fernet_key(tmp_path / "center_key")


@pytest.fixture
def service(tmp_path: Path, test_logger: KioskLogger, key: bytes) -> DeviceService:
    """Erzeugt einen DeviceService mit temporaerer Datenbank.

    Args:
        tmp_path:
            Temporaeres Testverzeichnis.

        test_logger:
            Testspezifischer Logger.

        key:
            Fernet-Schluessel.

    Returns:
        Ein einsatzbereiter DeviceService.
    """
    return DeviceService(
        logger=test_logger,
        device_model=DeviceModel(tmp_path / "devices.db"),
        key=key,
    )


class TestDeviceService:
    """Tests fuer die Geraeteverwaltung."""

    def test_aufnehmen_und_auflisten(self, service: DeviceService) -> None:
        assert service.all() == []
        device = service.add(
            "Empfang", "pikiosk-01.local", 8080, "admin", DEVICE_PASSWORD
        )
        assert device.name == "Empfang"
        assert device.enabled is True
        assert device.base_url == "http://pikiosk-01.local:8080"
        assert len(service.all()) == 1

    def test_passwort_wird_verschluesselt_gespeichert(
        self, service: DeviceService, key: bytes
    ) -> None:
        device = service.add("Empfang", "10.0.0.5", 8080, "admin", DEVICE_PASSWORD)
        assert DEVICE_PASSWORD not in device.secret
        assert decrypt_secret(device.secret, key) == DEVICE_PASSWORD

    def test_doppelter_name_wird_abgelehnt(self, service: DeviceService) -> None:
        service.add("Empfang", "10.0.0.5", 8080, "admin", DEVICE_PASSWORD)
        with pytest.raises(DeviceError):
            service.add("Empfang", "10.0.0.6", 8080, "admin", DEVICE_PASSWORD)

    @pytest.mark.parametrize(
        ("name", "address", "username"),
        [
            ("", "10.0.0.5", "admin"),
            ("x" * 65, "10.0.0.5", "admin"),
            ("Empfang", "", "admin"),
            ("Empfang", "http://10.0.0.5", "admin"),
            ("Empfang", "10.0.0.5 boese", "admin"),
            ("Empfang", "10.0.0.5", ""),
        ],
    )
    def test_ungueltige_eingaben(
        self, service: DeviceService, name: str, address: str, username: str
    ) -> None:
        with pytest.raises(ValidationError):
            service.add(name, address, 8080, username, DEVICE_PASSWORD)

    def test_leeres_passwort_wird_abgelehnt(self, service: DeviceService) -> None:
        with pytest.raises(ValidationError):
            service.add("Empfang", "10.0.0.5", 8080, "admin", "")

    @pytest.mark.parametrize("port", ["keine-zahl", 0, 70000, -1])
    def test_ungueltiger_port(self, service: DeviceService, port: object) -> None:
        with pytest.raises(ValidationError):
            service.add("Empfang", "10.0.0.5", port, "admin", DEVICE_PASSWORD)

    def test_aendern_ohne_neues_passwort(
        self, service: DeviceService, key: bytes
    ) -> None:
        device = service.add("Empfang", "10.0.0.5", 8080, "admin", DEVICE_PASSWORD)
        geaendert = service.update(
            device.id, "Foyer", "10.0.0.7", 8081, "admin", "", True
        )
        assert geaendert.name == "Foyer"
        assert geaendert.address == "10.0.0.7"
        assert geaendert.port == 8081
        assert decrypt_secret(geaendert.secret, key) == DEVICE_PASSWORD

    def test_aendern_mit_neuem_passwort(
        self, service: DeviceService, key: bytes
    ) -> None:
        device = service.add("Empfang", "10.0.0.5", 8080, "admin", DEVICE_PASSWORD)
        geaendert = service.update(
            device.id, "Empfang", "10.0.0.5", 8080, "admin", "Neu-Geheim-2026!", False
        )
        assert decrypt_secret(geaendert.secret, key) == "Neu-Geheim-2026!"
        assert geaendert.enabled is False

    def test_aendern_unbekanntes_geraet(self, service: DeviceService) -> None:
        with pytest.raises(DeviceError):
            service.update(999, "X", "10.0.0.5", 8080, "admin", "", True)

    def test_entfernen(self, service: DeviceService) -> None:
        device = service.add("Empfang", "10.0.0.5", 8080, "admin", DEVICE_PASSWORD)
        service.delete(device.id)
        assert service.all() == []
        with pytest.raises(DeviceError):
            service.delete(device.id)

    def test_sortierung_nach_namen(self, service: DeviceService) -> None:
        for name in ("Zugang", "Empfang", "foyer"):
            service.add(name, "10.0.0.5", 8080, "admin", DEVICE_PASSWORD)
        assert [d.name for d in service.all()] == ["Empfang", "foyer", "Zugang"]

    def test_fremder_schluessel_meldet_fehler(
        self, service: DeviceService, tmp_path: Path
    ) -> None:
        from app.exceptions import AuthenticationError

        device = service.add("Empfang", "10.0.0.5", 8080, "admin", DEVICE_PASSWORD)
        fremd = load_or_create_fernet_key(tmp_path / "anderer_key")
        with pytest.raises(AuthenticationError):
            decrypt_secret(device.secret, fremd)
