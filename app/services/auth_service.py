# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - AuthService.

Verwaltet die Anlage des Administratorkontos. Passwoerter werden
ausschliesslich mit bcrypt gehasht und niemals im Klartext
gespeichert oder protokolliert.
"""

import bcrypt

from app.constants import ADMIN_ROLE
from app.exceptions import AuthenticationError
from app.logger import KioskLogger
from app.models.user_model import User, UserModel
from app.utils.validators import PasswordValidator


class AuthService:
    """Benutzer- und Passwortverwaltung.

    Args:
        logger:
            Logger fuer alle Authentifizierungsereignisse.

        user_model:
            Datenbankzugriff auf die Benutzertabelle.
    """

    def __init__(self, logger: KioskLogger, user_model: UserModel) -> None:
        self._logger = logger
        self._user_model = user_model
        self._password_validator = PasswordValidator()

    def hash_password(self, password: str) -> str:
        """Erzeugt einen bcrypt-Hash fuer ein validiertes Passwort.

        Args:
            password:
                Klartextpasswort.

        Returns:
            Der bcrypt-Hash als Zeichenkette.

        Raises:
            ValidationError
        """
        self._password_validator.validate(password)
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")

    def check_password_rules(self, password: str) -> dict[str, bool]:
        """Prueft die Passwortqualitaet regelweise.

        Args:
            password:
                Zu pruefendes Passwort.

        Returns:
            Regelname und Ergebnis jeder Einzelpruefung.
        """
        return self._password_validator.check_rules(password)

    def create_administrator(self, username: str, password_hash: str) -> User:
        """Legt das Administratorkonto an.

        Args:
            username:
                Anmeldename des Administrators.

            password_hash:
                Bereits erzeugter bcrypt-Hash des Passworts.

        Returns:
            Der angelegte Administrator.

        Raises:
            AuthenticationError
        """
        if not username or not username.strip():
            raise AuthenticationError("Der Administratorname darf nicht leer sein.")
        user = self._user_model.create_user(
            username=username.strip(),
            password_hash=password_hash,
            role=ADMIN_ROLE,
        )
        self._logger.info(f"Administrator angelegt: {user.username}")
        return user

    def administrator_exists(self) -> bool:
        """Prueft, ob bereits ein Benutzerkonto existiert.

        Returns:
            True, wenn mindestens ein Benutzer angelegt wurde.
        """
        return self._user_model.count_users() > 0
