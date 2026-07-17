# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Center - FleetService.

Fragt alle verwalteten Geraete parallel ab und fuehrt Aktionen auf
einzelnen Geraeten oder auf einer Auswahl aus. Ein nicht
erreichbares Geraet beeinflusst die uebrigen nicht: Jedes Ergebnis
traegt seinen eigenen Zustand.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.exceptions import AuthenticationError, NetworkError, PiKioskError
from app.logger import KioskLogger
from center.constants import (
    DEVICE_ACTIONS,
    DEVICE_STATE_AUTH,
    DEVICE_STATE_DISABLED,
    DEVICE_STATE_OFFLINE,
    DEVICE_STATE_ONLINE,
    FLEET_MAX_WORKERS,
)
from center.models.device_model import Device
from center.services.device_client import DeviceClient
from center.services.device_service import DeviceService


class FleetService:
    """Sammelt Zustaende und steuert die verwalteten Geraete.

    Args:
        logger:
            Logger fuer alle Flottenereignisse.

        device_service:
            Verwaltung der Geraeteliste.

        client:
            Client fuer die Geraete-API.
    """

    def __init__(
        self,
        logger: KioskLogger,
        device_service: DeviceService,
        client: DeviceClient,
    ) -> None:
        self._logger = logger
        self._device_service = device_service
        self._client = client

    def overview(self) -> list[dict[str, Any]]:
        """Fragt alle Geraete parallel ab.

        Returns:
            Je Geraet ein Eintrag mit Stammdaten, Zustand und den
            wichtigsten Statuswerten, nach Namen sortiert.
        """
        devices = self._device_service.all()
        if not devices:
            return []
        workers = min(FLEET_MAX_WORKERS, len(devices))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(self.device_state, devices))

    def device_state(self, device: Device) -> dict[str, Any]:
        """Ermittelt den Zustand eines einzelnen Geraets.

        Args:
            device:
                Das abzufragende Geraet.

        Returns:
            Stammdaten, Zustand und Statuswerte des Geraets.
        """
        entry: dict[str, Any] = {
            "id": device.id,
            "name": device.name,
            "address": device.address,
            "port": device.port,
            "enabled": device.enabled,
            "state": DEVICE_STATE_DISABLED,
            "error": "",
            "status": None,
        }
        if not device.enabled:
            return entry
        try:
            status = self._client.status(device)
        except AuthenticationError as error:
            entry["state"] = DEVICE_STATE_AUTH
            entry["error"] = str(error)
            return entry
        except (NetworkError, PiKioskError) as error:
            entry["state"] = DEVICE_STATE_OFFLINE
            entry["error"] = str(error)
            return entry
        entry["state"] = DEVICE_STATE_ONLINE
        entry["status"] = status
        return entry

    def summary(self, entries: list[dict[str, Any]]) -> dict[str, int]:
        """Zaehlt die Geraete je Zustand.

        Args:
            entries:
                Ergebnisse aus overview().

        Returns:
            Anzahl gesamt, online, offline, mit Anmeldefehler und
            deaktiviert.
        """
        return {
            "total": len(entries),
            "online": sum(1 for e in entries if e["state"] == DEVICE_STATE_ONLINE),
            "offline": sum(1 for e in entries if e["state"] == DEVICE_STATE_OFFLINE),
            "auth_error": sum(1 for e in entries if e["state"] == DEVICE_STATE_AUTH),
            "disabled": sum(1 for e in entries if e["state"] == DEVICE_STATE_DISABLED),
        }

    def run_action(self, device_ids: list[int], action: str) -> list[dict[str, Any]]:
        """Fuehrt eine Aktion auf mehreren Geraeten parallel aus.

        Args:
            device_ids:
                Kennungen der Zielgeraete.

            action:
                Aktion aus DEVICE_ACTIONS.

        Returns:
            Je Geraet ein Ergebnis mit Erfolg oder Fehlermeldung.

        Raises:
            ValidationError
        """
        devices = self._resolve(device_ids)
        if action not in DEVICE_ACTIONS:
            raise ValueError(f"Unbekannte Aktion: {action}")

        def execute(device: Device) -> dict[str, Any]:
            return self._single_action(device, action)

        workers = min(FLEET_MAX_WORKERS, len(devices)) or 1
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(execute, devices))

    def set_url(self, device_ids: list[int], url: str) -> list[dict[str, Any]]:
        """Setzt die Kiosk-URL auf mehreren Geraeten parallel.

        Args:
            device_ids:
                Kennungen der Zielgeraete.

            url:
                Neue Kiosk-URL.

        Returns:
            Je Geraet ein Ergebnis mit Erfolg oder Fehlermeldung.
        """
        devices = self._resolve(device_ids)

        def execute(device: Device) -> dict[str, Any]:
            try:
                self._client.set_url(device, url)
            except PiKioskError as error:
                self._logger.error(
                    f"URL-Aenderung auf '{device.name}' fehlgeschlagen: {error}"
                )
                return self._result(device, False, str(error))
            self._logger.info(f"URL auf '{device.name}' gesetzt: {url}")
            return self._result(device, True, "")

        workers = min(FLEET_MAX_WORKERS, len(devices)) or 1
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(execute, devices))

    def _single_action(self, device: Device, action: str) -> dict[str, Any]:
        """Fuehrt eine Aktion auf einem Geraet aus.

        Args:
            device:
                Das Zielgeraet.

            action:
                Auszufuehrende Aktion.

        Returns:
            Das Ergebnis der Aktion.
        """
        try:
            self._client.action(device, action)
        except PiKioskError as error:
            self._logger.error(
                f"Aktion '{action}' auf '{device.name}' fehlgeschlagen: {error}"
            )
            return self._result(device, False, str(error))
        self._logger.info(f"Aktion '{action}' auf '{device.name}' ausgefuehrt.")
        return self._result(device, True, "")

    def _resolve(self, device_ids: list[int]) -> list[Device]:
        """Ermittelt die Geraete zu den uebergebenen Kennungen.

        Args:
            device_ids:
                Kennungen der Geraete.

        Returns:
            Die gefundenen, aktiven Geraete.
        """
        devices: list[Device] = []
        for device_id in device_ids:
            device = self._device_service.find(device_id)
            if device is not None and device.enabled:
                devices.append(device)
        return devices

    def _result(self, device: Device, success: bool, error: str) -> dict[str, Any]:
        """Baut ein Ergebnisobjekt fuer eine Geraeteaktion.

        Args:
            device:
                Das betroffene Geraet.

            success:
                True, wenn die Aktion erfolgreich war.

            error:
                Fehlermeldung, falls vorhanden.

        Returns:
            Das Ergebnisobjekt.
        """
        return {
            "id": device.id,
            "name": device.name,
            "success": success,
            "error": error,
        }
