# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Center - DeviceService.

Verwaltet die Geraeteliste der Zentrale: aufnehmen, aendern,
entfernen. Alle Eingaben werden validiert, Passwoerter werden vor
dem Speichern verschluesselt.
"""

import re

from app.exceptions import ValidationError
from app.logger import KioskLogger
from app.utils.crypto import encrypt_secret
from center.constants import (
    DEVICE_ADDRESS_MAX_LENGTH,
    DEVICE_NAME_MAX_LENGTH,
)
from center.models.device_model import Device, DeviceModel

ADDRESS_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z0-9.:_-]+$")


class DeviceService:
    """Verwaltung der Geraeteliste.

    Args:
        logger:
            Logger fuer alle Geraeteereignisse.

        device_model:
            Datenbankzugriff auf die Geraetetabelle.

        key:
            Fernet-Schluessel fuer die Zugangsdaten.
    """

    def __init__(
        self, logger: KioskLogger, device_model: DeviceModel, key: bytes
    ) -> None:
        self._logger = logger
        self._device_model = device_model
        self._key = key

    def all(self) -> list[Device]:
        """Liefert alle verwalteten Geraete.

        Returns:
            Alle Geraete, nach Namen sortiert.
        """
        return self._device_model.all()

    def find(self, device_id: int) -> Device | None:
        """Sucht ein Geraet anhand seiner Kennung.

        Args:
            device_id:
                Kennung des Geraets.

        Returns:
            Das Geraet oder None.
        """
        return self._device_model.find(device_id)

    def add(
        self, name: str, address: str, port: str | int, username: str, password: str
    ) -> Device:
        """Nimmt ein Geraet in die Verwaltung auf.

        Args:
            name:
                Anzeigename.

            address:
                Hostname oder IP-Adresse.

            port:
                Port der Weboberflaeche.

            username:
                Administratorname auf dem Geraet.

            password:
                Administratorpasswort des Geraets.

        Returns:
            Das aufgenommene Geraet.

        Raises:
            ValidationError
            DeviceError
        """
        self._validate(name, address, username)
        if not password:
            raise ValidationError("Das Geraetepasswort darf nicht leer sein.")
        device = self._device_model.create(
            name=name.strip(),
            address=address.strip(),
            port=self._validate_port(port),
            username=username.strip(),
            secret=encrypt_secret(password, self._key),
        )
        self._logger.info(f"Geraet aufgenommen: {device.name} ({device.address})")
        return device

    def update(
        self,
        device_id: int,
        name: str,
        address: str,
        port: str | int,
        username: str,
        password: str,
        enabled: bool,
    ) -> Device:
        """Aendert ein vorhandenes Geraet.

        Args:
            device_id:
                Kennung des Geraets.

            name:
                Anzeigename.

            address:
                Hostname oder IP-Adresse.

            port:
                Port der Weboberflaeche.

            username:
                Administratorname auf dem Geraet.

            password:
                Neues Passwort; leer laesst das gespeicherte
                Passwort unveraendert.

            enabled:
                True, wenn das Geraet abgefragt werden soll.

        Returns:
            Das geaenderte Geraet.

        Raises:
            ValidationError
            DeviceError
        """
        self._validate(name, address, username)
        device = self._device_model.update(
            device_id=device_id,
            name=name.strip(),
            address=address.strip(),
            port=self._validate_port(port),
            username=username.strip(),
            secret=encrypt_secret(password, self._key) if password else None,
            enabled=enabled,
        )
        self._logger.info(f"Geraet geaendert: {device.name} ({device.address})")
        return device

    def delete(self, device_id: int) -> None:
        """Entfernt ein Geraet aus der Verwaltung.

        Args:
            device_id:
                Kennung des Geraets.

        Raises:
            DeviceError
        """
        self._device_model.delete(device_id)
        self._logger.info(f"Geraet entfernt: Kennung {device_id}")

    def _validate(self, name: str, address: str, username: str) -> None:
        """Prueft Name, Adresse und Benutzernamen eines Geraets.

        Args:
            name:
                Anzeigename.

            address:
                Hostname oder IP-Adresse.

            username:
                Administratorname auf dem Geraet.

        Raises:
            ValidationError
        """
        if not name.strip():
            raise ValidationError("Der Geraetename darf nicht leer sein.")
        if len(name.strip()) > DEVICE_NAME_MAX_LENGTH:
            raise ValidationError(
                f"Der Geraetename darf maximal {DEVICE_NAME_MAX_LENGTH} "
                "Zeichen lang sein."
            )
        cleaned = address.strip()
        if not cleaned:
            raise ValidationError("Die Adresse darf nicht leer sein.")
        if len(cleaned) > DEVICE_ADDRESS_MAX_LENGTH:
            raise ValidationError("Die Adresse ist zu lang.")
        if not ADDRESS_PATTERN.match(cleaned):
            raise ValidationError(
                "Die Adresse darf nur Buchstaben, Ziffern, Punkte, "
                "Doppelpunkte, Binde- und Unterstriche enthalten."
            )
        if not username.strip():
            raise ValidationError("Der Benutzername darf nicht leer sein.")

    def _validate_port(self, port: str | int) -> int:
        """Prueft und wandelt eine Portangabe.

        Args:
            port:
                Zu pruefender Port.

        Returns:
            Der gueltige Port.

        Raises:
            ValidationError
        """
        try:
            value = int(port)
        except (TypeError, ValueError) as error:
            raise ValidationError("Der Port muss eine Zahl sein.") from error
        if not 1 <= value <= 65535:
            raise ValidationError("Der Port muss zwischen 1 und 65535 liegen.")
        return value
