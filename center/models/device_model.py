# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Center - Geraetemodell.

Verwaltet die Geraetetabelle in der SQLite-Datenbank der Zentrale.
Die Zugangsdaten der Geraete werden ausschliesslich verschluesselt
gespeichert, niemals im Klartext. Alle Zugriffe verwenden
Parameterbindung.
"""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.exceptions import PiKioskError
from center.constants import DEVICES_DB_FILE

DEVICES_TABLE_SCHEMA: str = """
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    address TEXT NOT NULL,
    port INTEGER NOT NULL,
    username TEXT NOT NULL,
    secret TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
)
"""


class DeviceError(PiKioskError):
    """Fehler bei der Geraeteverwaltung der Zentrale."""


@dataclass(frozen=True)
class Device:
    """Ein verwaltetes PiKiosk-Geraet.

    Attributes:
        id:
            Eindeutige Kennung.

        name:
            Anzeigename des Geraets.

        address:
            Hostname oder IP-Adresse.

        port:
            Port der Weboberflaeche.

        username:
            Administratorname auf dem Geraet.

        secret:
            Verschluesseltes Administratorpasswort.

        enabled:
            True, wenn das Geraet abgefragt werden soll.

        created_at:
            Zeitpunkt der Aufnahme (ISO 8601, UTC).
    """

    id: int
    name: str
    address: str
    port: int
    username: str
    secret: str
    enabled: bool
    created_at: str

    @property
    def base_url(self) -> str:
        """Liefert die Basis-URL der Geraete-API.

        Returns:
            Die Basis-URL ohne abschliessenden Schraegstrich.
        """
        return f"http://{self.address}:{self.port}"


class DeviceModel:
    """Datenbankzugriff auf die Geraetetabelle.

    Args:
        db_file:
            Pfad der SQLite-Datenbankdatei.
    """

    def __init__(self, db_file: Path = DEVICES_DB_FILE) -> None:
        self._db_file = db_file
        self._ensure_schema()

    @contextmanager
    def _database(self) -> Iterator[sqlite3.Connection]:
        """Oeffnet eine Datenbankverbindung und schliesst sie sicher.

        Yields:
            Eine SQLite-Verbindung mit Zeilenzugriff per Name.

        Raises:
            DeviceError
        """
        try:
            self._db_file.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self._db_file)
            connection.row_factory = sqlite3.Row
        except (sqlite3.Error, OSError) as error:
            raise DeviceError(f"Geraetedatenbank nicht verfuegbar: {error}") from error
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _ensure_schema(self) -> None:
        """Legt die Geraetetabelle an, falls sie fehlt.

        Raises:
            DeviceError
        """
        with self._database() as connection:
            connection.execute(DEVICES_TABLE_SCHEMA)

    def create(
        self, name: str, address: str, port: int, username: str, secret: str
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

            secret:
                Verschluesseltes Passwort.

        Returns:
            Das aufgenommene Geraet.

        Raises:
            DeviceError
        """
        created_at = datetime.now(timezone.utc).isoformat()
        try:
            with self._database() as connection:
                cursor = connection.execute(
                    "INSERT INTO devices "
                    "(name, address, port, username, secret, enabled, created_at) "
                    "VALUES (?, ?, ?, ?, ?, 1, ?)",
                    (name, address, port, username, secret, created_at),
                )
                device_id = int(cursor.lastrowid or 0)
        except sqlite3.IntegrityError as error:
            raise DeviceError(
                f"Ein Geraet mit dem Namen '{name}' ist bereits vorhanden."
            ) from error
        device = self.find(device_id)
        if device is None:
            raise DeviceError(f"Das Geraet '{name}' konnte nicht angelegt werden.")
        return device

    def update(
        self,
        device_id: int,
        name: str,
        address: str,
        port: int,
        username: str,
        secret: str | None,
        enabled: bool,
    ) -> Device:
        """Aktualisiert ein vorhandenes Geraet.

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

            secret:
                Neues verschluesseltes Passwort oder None, wenn das
                gespeicherte Passwort bestehen bleiben soll.

            enabled:
                True, wenn das Geraet abgefragt werden soll.

        Returns:
            Das aktualisierte Geraet.

        Raises:
            DeviceError
        """
        current = self.find(device_id)
        if current is None:
            raise DeviceError("Das Geraet wurde nicht gefunden.")
        try:
            with self._database() as connection:
                connection.execute(
                    "UPDATE devices SET name = ?, address = ?, port = ?, "
                    "username = ?, secret = ?, enabled = ? WHERE id = ?",
                    (
                        name,
                        address,
                        port,
                        username,
                        secret if secret is not None else current.secret,
                        1 if enabled else 0,
                        device_id,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise DeviceError(
                f"Ein Geraet mit dem Namen '{name}' ist bereits vorhanden."
            ) from error
        updated = self.find(device_id)
        if updated is None:
            raise DeviceError("Das Geraet wurde nicht gefunden.")
        return updated

    def delete(self, device_id: int) -> None:
        """Entfernt ein Geraet aus der Verwaltung.

        Args:
            device_id:
                Kennung des Geraets.

        Raises:
            DeviceError
        """
        with self._database() as connection:
            cursor = connection.execute(
                "DELETE FROM devices WHERE id = ?", (device_id,)
            )
            if cursor.rowcount == 0:
                raise DeviceError("Das Geraet wurde nicht gefunden.")

    def find(self, device_id: int) -> Device | None:
        """Sucht ein Geraet anhand seiner Kennung.

        Args:
            device_id:
                Kennung des Geraets.

        Returns:
            Das Geraet oder None.

        Raises:
            DeviceError
        """
        with self._database() as connection:
            row = connection.execute(
                "SELECT id, name, address, port, username, secret, enabled, "
                "created_at FROM devices WHERE id = ?",
                (device_id,),
            ).fetchone()
        return self._to_device(row) if row is not None else None

    def all(self) -> list[Device]:
        """Listet alle verwalteten Geraete auf.

        Returns:
            Alle Geraete, nach Namen sortiert.

        Raises:
            DeviceError
        """
        with self._database() as connection:
            rows = connection.execute(
                "SELECT id, name, address, port, username, secret, enabled, "
                "created_at FROM devices ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [self._to_device(row) for row in rows]

    def _to_device(self, row: sqlite3.Row) -> Device:
        """Wandelt eine Datenbankzeile in ein Geraet.

        Args:
            row:
                Datenbankzeile.

        Returns:
            Das Geraet.
        """
        return Device(
            id=int(row["id"]),
            name=str(row["name"]),
            address=str(row["address"]),
            port=int(row["port"]),
            username=str(row["username"]),
            secret=str(row["secret"]),
            enabled=bool(row["enabled"]),
            created_at=str(row["created_at"]),
        )
