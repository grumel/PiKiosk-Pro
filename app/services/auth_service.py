# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - AuthService.

Verwaltet Administratorkonto und Anmeldung. Passwoerter werden
ausschliesslich mit bcrypt gehasht und niemals im Klartext
gespeichert oder protokolliert. Die Anmeldung erfolgt ueber
Flask-Login, LoginUser kapselt dafuer einen Datenbankbenutzer.
Die LoginThrottle bremst Passwort-Rateversuche: Nach zu vielen
Fehlversuchen aus derselben Quelle wird die Anmeldung fuer eine
begrenzte Zeit gesperrt.
"""

import threading
import time
from collections import deque
from typing import Callable

import bcrypt
from flask_login import UserMixin

from app.constants import (
    ADMIN_ROLE,
    LOGIN_ATTEMPT_WINDOW_SECONDS,
    LOGIN_LOCKOUT_SECONDS,
    LOGIN_MAX_ATTEMPTS,
)
from app.exceptions import AuthenticationError
from app.logger import KioskLogger
from app.models.user_model import User, UserModel
from app.utils.validators import PasswordValidator


class LoginThrottle:
    """Begrenzt Anmelde-Fehlversuche je Quelle.

    Erreicht eine Quelle innerhalb des Zeitfensters die maximale
    Zahl an Fehlversuchen, wird sie fuer die Sperrdauer blockiert.
    Weitere Fehlversuche waehrend der Sperre verlaengern sie.
    Erfolgreiche Anmeldungen setzen die Quelle zurueck.

    Args:
        max_attempts:
            Fehlversuche, bis die Sperre greift.

        window_seconds:
            Zeitfenster, in dem Fehlversuche gezaehlt werden.

        lockout_seconds:
            Dauer der Sperre in Sekunden.

        clock:
            Zeitquelle; nur fuer Tests austauschbar.
    """

    def __init__(
        self,
        max_attempts: int = LOGIN_MAX_ATTEMPTS,
        window_seconds: float = LOGIN_ATTEMPT_WINDOW_SECONDS,
        lockout_seconds: float = LOGIN_LOCKOUT_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._lockout_seconds = lockout_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._failures: dict[str, deque[float]] = {}
        self._blocked_until: dict[str, float] = {}

    def blocked_seconds(self, source: str) -> int:
        """Liefert die verbleibende Sperrzeit einer Quelle.

        Args:
            source:
                Kennung der Quelle, etwa die IP-Adresse.

        Returns:
            Verbleibende Sekunden, aufgerundet; 0 ohne Sperre.
        """
        now = self._clock()
        with self._lock:
            until = self._blocked_until.get(source, 0.0)
            if until <= now:
                self._blocked_until.pop(source, None)
                return 0
            return int(until - now) + 1

    def register_failure(self, source: str) -> None:
        """Registriert einen Fehlversuch einer Quelle.

        Args:
            source:
                Kennung der Quelle, etwa die IP-Adresse.
        """
        now = self._clock()
        with self._lock:
            attempts = self._failures.setdefault(source, deque())
            attempts.append(now)
            while attempts and attempts[0] <= now - self._window_seconds:
                attempts.popleft()
            if len(attempts) >= self._max_attempts:
                self._blocked_until[source] = now + self._lockout_seconds

    def register_success(self, source: str) -> None:
        """Setzt eine Quelle nach erfolgreicher Anmeldung zurueck.

        Args:
            source:
                Kennung der Quelle, etwa die IP-Adresse.
        """
        with self._lock:
            self._failures.pop(source, None)
            self._blocked_until.pop(source, None)


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

        throttle:
            Optionale Anmeldebremse; ohne Angabe wird eine mit den
            Standardwerten erzeugt.
    """

    def __init__(
        self,
        logger: KioskLogger,
        user_model: UserModel,
        throttle: LoginThrottle | None = None,
    ) -> None:
        self._logger = logger
        self._user_model = user_model
        self._password_validator = PasswordValidator()
        self._throttle = throttle if throttle is not None else LoginThrottle()

    @property
    def throttle(self) -> LoginThrottle:
        """Liefert die Anmeldebremse dieses Dienstes.

        Returns:
            Die LoginThrottle-Instanz.
        """
        return self._throttle

    def blocked_seconds(self, source: str) -> int:
        """Liefert die verbleibende Anmeldesperre einer Quelle.

        Args:
            source:
                Kennung der Quelle, etwa die IP-Adresse.

        Returns:
            Verbleibende Sekunden; 0 ohne Sperre.
        """
        remaining = self._throttle.blocked_seconds(source)
        if remaining:
            self._logger.warning(
                f"Anmeldung gesperrt fuer Quelle {source} "
                f"({remaining} Sekunden verbleibend)."
            )
        return remaining

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

    def authenticate(
        self, username: str, password: str, source: str | None = None
    ) -> LoginUser | None:
        """Prueft Anmeldedaten und meldet den Benutzer an.

        Args:
            username:
                Anmeldename.

            password:
                Klartextpasswort.

            source:
                Optionale Kennung der Quelle (etwa die IP-Adresse);
                Fehlversuche werden dann in der Anmeldebremse
                gezaehlt, Erfolge setzen sie zurueck.

        Returns:
            Der angemeldete Benutzer oder None bei ungueltigen
            Anmeldedaten oder deaktiviertem Konto.
        """
        user = self._user_model.find_by_username(username.strip())
        if user is None or not user.enabled:
            self._logger.warning(
                f"Anmeldung fehlgeschlagen fuer Benutzer: {username.strip()!r}"
                + (f" von {source}" if source else "")
            )
            if source:
                self._throttle.register_failure(source)
            return None
        if not bcrypt.checkpw(
            password.encode("utf-8"), user.password_hash.encode("ascii")
        ):
            self._logger.warning(
                f"Anmeldung mit falschem Passwort fuer: {user.username}"
                + (f" von {source}" if source else "")
            )
            if source:
                self._throttle.register_failure(source)
            return None
        self._user_model.update_last_login(user.id)
        if source:
            self._throttle.register_success(source)
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
