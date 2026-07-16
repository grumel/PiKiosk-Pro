# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Benutzermodell.

Verwaltet die Benutzertabelle in der SQLite-Datenbank. Passwoerter
werden ausschliesslich als bcrypt-Hash gespeichert, niemals im
Klartext. Alle Zugriffe verwenden Parameterbindung, es gibt keine
SQL-Injection-Angriffsflaeche.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.constants import USERS_DB_FILE
from app.exceptions import AuthenticationError

USERS_TABLE_SCHEMA: str = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_login TEXT,
    enabled INTEGER NOT NULL DEFAULT 1
)
"""


@dataclass(frozen=True)
class User:
    """Ein Benutzerkonto von PiKiosk Pro.

    Attributes:
        id:
            Eindeutige Benutzerkennung.

        username:
            Anmeldename.

        password_hash:
            bcrypt-Hash des Passworts.

        role:
            Rolle des Benutzers.

        created_at:
            Zeitpunkt der Anlage (ISO 8601, UTC).

        last_login:
            Zeitpunkt der letzten Anmeldung oder None.

        enabled:
            True, wenn das Konto aktiv ist.
    """

    id: int
    username: str
    password_hash: str
    role: str
    created_at: str
    last_login: str | None
    enabled: bool


class UserModel:
    """Datenbankzugriff auf die Benutzertabelle.

    Args:
        db_file:
            Pfad der SQLite-Datenbankdatei.
    """

    def __init__(self, db_file: Path = USERS_DB_FILE) -> None:
        self._db_file = db_file
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        """Oeffnet eine Datenbankverbindung.

        Returns:
            Eine SQLite-Verbindung mit Zeilenzugriff per Name.

        Raises:
            AuthenticationError
        """
        try:
            self._db_file.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self._db_file)
            connection.row_factory = sqlite3.Row
            return connection
        except (sqlite3.Error, OSError) as error:
            raise AuthenticationError(
                f"Benutzerdatenbank nicht verfuegbar: {error}"
            ) from error

    def _ensure_schema(self) -> None:
        """Legt die Benutzertabelle an, falls sie fehlt.

        Raises:
            AuthenticationError
        """
        with self._connect() as connection:
            connection.execute(USERS_TABLE_SCHEMA)

    def create_user(self, username: str, password_hash: str, role: str) -> User:
        """Legt einen neuen Benutzer an.

        Args:
            username:
                Anmeldename.

            password_hash:
                bcrypt-Hash des Passworts.

            role:
                Rolle des Benutzers.

        Returns:
            Der angelegte Benutzer.

        Raises:
            AuthenticationError
        """
        created_at = datetime.now(timezone.utc).isoformat()
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO users "
                    "(username, password_hash, role, created_at, enabled) "
                    "VALUES (?, ?, ?, ?, 1)",
                    (username, password_hash, role, created_at),
                )
        except sqlite3.IntegrityError as error:
            raise AuthenticationError(
                f"Der Benutzer '{username}' existiert bereits."
            ) from error
        user = self.find_by_username(username)
        if user is None:
            raise AuthenticationError(
                f"Der Benutzer '{username}' konnte nicht angelegt werden."
            )
        return user

    def find_by_username(self, username: str) -> User | None:
        """Sucht einen Benutzer anhand des Anmeldenamens.

        Args:
            username:
                Anmeldename.

        Returns:
            Der Benutzer oder None.

        Raises:
            AuthenticationError
        """
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, username, password_hash, role, created_at, "
                "last_login, enabled FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        if row is None:
            return None
        return User(
            id=int(row["id"]),
            username=str(row["username"]),
            password_hash=str(row["password_hash"]),
            role=str(row["role"]),
            created_at=str(row["created_at"]),
            last_login=row["last_login"],
            enabled=bool(row["enabled"]),
        )

    def find_by_id(self, user_id: int) -> User | None:
        """Sucht einen Benutzer anhand seiner Kennung.

        Args:
            user_id:
                Eindeutige Benutzerkennung.

        Returns:
            Der Benutzer oder None.

        Raises:
            AuthenticationError
        """
        with self._connect() as connection:
            row = connection.execute(
                "SELECT username FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return self.find_by_username(str(row["username"]))

    def update_last_login(self, user_id: int) -> None:
        """Setzt den Zeitpunkt der letzten Anmeldung auf jetzt.

        Args:
            user_id:
                Eindeutige Benutzerkennung.

        Raises:
            AuthenticationError
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (timestamp, user_id),
            )

    def count_users(self) -> int:
        """Zaehlt alle vorhandenen Benutzer.

        Returns:
            Anzahl der Benutzerkonten.

        Raises:
            AuthenticationError
        """
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()
        return int(row["total"])
