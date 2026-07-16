# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - AuthService.

Verwaltet Administratorkonto und Anmeldung. Passwoerter werden
ausschliesslich mit bcrypt gehasht und niemals im Klartext
gespeichert oder protokolliert. Die Anmeldung erfolgt ueber
Flask-Login, LoginUser kapselt dafuer einen Datenbankbenutzer.
"""

import bcrypt
from flask_login import UserMixin

from app.constants import ADMIN_ROLE
from app.exceptions import AuthenticationError
from app.logger import KioskLogger
from app.models.user_model import User, UserModel
from app.utils.validators import PasswordValidator


class LoginUser(UserMixin):
    """Flask-Login-Huelle um einen Datenbankbenutzer.

    Args:
        user:
            Der zugrunde liegende Datenbankbenutzer.
    """

    def __init__(self, user: User) -> None:
        self.user = user

    def get_id(self) -> str:
        """Liefert die Benutzerkennung fuer Flask-Login.

        Returns:
            Die Benutzerkennung als Zeichenkette.
        """
        return str(self.user.id)

    @property
    def username(self) -> str:
        """Liefert den Anmeldenamen des Benutzers.

        Returns:
            Der Anmeldename.
        """
        return self.user.username


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

    def authenticate(self, username: str, password: str) -> LoginUser | None:
        """Prueft Anmeldedaten und meldet den Benutzer an.

        Args:
            username:
                Anmeldename.

            password:
                Klartextpasswort.

        Returns:
            Der angemeldete Benutzer oder None bei ungueltigen
            Anmeldedaten oder deaktiviertem Konto.
        """
        user = self._user_model.find_by_username(username.strip())
        if user is None or not user.enabled:
            self._logger.warning(
                f"Anmeldung fehlgeschlagen fuer Benutzer: {username.strip()!r}"
            )
            return None
        if not bcrypt.checkpw(
            password.encode("utf-8"), user.password_hash.encode("ascii")
        ):
            self._logger.warning(
                f"Anmeldung mit falschem Passwort fuer: {user.username}"
            )
            return None
        self._user_model.update_last_login(user.id)
        self._logger.info(f"Benutzer angemeldet: {user.username}")
        return LoginUser(user)

    def load_user(self, user_id: str) -> LoginUser | None:
        """Laedt einen Benutzer fuer die Flask-Login-Sitzung.

        Args:
            user_id:
                Benutzerkennung aus der Sitzung.

        Returns:
            Der Benutzer oder None.
        """
        try:
            user = self._user_model.find_by_id(int(user_id))
        except (ValueError, AuthenticationError):
            return None
        if user is None or not user.enabled:
            return None
        return LoginUser(user)
