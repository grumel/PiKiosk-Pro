# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer AuthService und UserModel."""

from pathlib import Path

import bcrypt
import pytest

from app.exceptions import AuthenticationError, ValidationError
from app.logger import KioskLogger
from app.models.user_model import UserModel
from app.services.auth_service import AuthService

VALID_PASSWORD = "Sicher-2026-Kiosk"


@pytest.fixture
def user_model(tmp_path: Path) -> UserModel:
    """Erzeugt ein Benutzermodell mit temporaerer Datenbank.

    Args:
        tmp_path:
            Temporaeres Testverzeichnis.

    Returns:
        Ein einsatzbereites UserModel.
    """
    return UserModel(tmp_path / "users.db")


@pytest.fixture
def service(test_logger: KioskLogger, user_model: UserModel) -> AuthService:
    """Erzeugt einen AuthService fuer die Tests.

    Args:
        test_logger:
            Testspezifischer Logger.

        user_model:
            Benutzermodell mit temporaerer Datenbank.

    Returns:
        Ein einsatzbereiter AuthService.
    """
    return AuthService(logger=test_logger, user_model=user_model)


class TestUserModel:
    """Tests fuer den Datenbankzugriff."""

    def test_create_und_find(self, user_model: UserModel) -> None:
        created = user_model.create_user("admin", "hash", "admin")
        found = user_model.find_by_username("admin")
        assert found is not None
        assert found.id == created.id
        assert found.role == "admin"
        assert found.enabled is True
        assert found.last_login is None

    def test_doppelter_benutzer_wird_abgelehnt(self, user_model: UserModel) -> None:
        user_model.create_user("admin", "hash", "admin")
        with pytest.raises(AuthenticationError):
            user_model.create_user("admin", "hash2", "admin")

    def test_unbekannter_benutzer(self, user_model: UserModel) -> None:
        assert user_model.find_by_username("fehlt") is None

    def test_count_users(self, user_model: UserModel) -> None:
        assert user_model.count_users() == 0
        user_model.create_user("admin", "hash", "admin")
        assert user_model.count_users() == 1


class TestAuthService:
    """Tests fuer die Benutzer- und Passwortverwaltung."""

    def test_hash_password_erzeugt_bcrypt_hash(self, service: AuthService) -> None:
        password_hash = service.hash_password(VALID_PASSWORD)
        assert password_hash.startswith("$2b$")
        assert VALID_PASSWORD not in password_hash
        assert bcrypt.checkpw(
            VALID_PASSWORD.encode("utf-8"), password_hash.encode("ascii")
        )

    def test_hash_password_lehnt_schwaches_passwort_ab(
        self, service: AuthService
    ) -> None:
        with pytest.raises(ValidationError):
            service.hash_password("kurz")

    def test_create_administrator(self, service: AuthService) -> None:
        assert service.administrator_exists() is False
        user = service.create_administrator("admin", "hash")
        assert user.username == "admin"
        assert user.role == "admin"
        assert service.administrator_exists() is True

    def test_leerer_administratorname(self, service: AuthService) -> None:
        with pytest.raises(AuthenticationError):
            service.create_administrator("   ", "hash")

    def test_check_password_rules(self, service: AuthService) -> None:
        rules = service.check_password_rules("nur-klein-123")
        assert rules["min_length"] is True
        assert rules["uppercase"] is False

    def test_authenticate_erfolgreich(
        self, service: AuthService, user_model: UserModel
    ) -> None:
        password_hash = service.hash_password(VALID_PASSWORD)
        service.create_administrator("admin", password_hash)
        login_user = service.authenticate("admin", VALID_PASSWORD)
        assert login_user is not None
        assert login_user.username == "admin"
        refreshed = user_model.find_by_username("admin")
        assert refreshed is not None
        assert refreshed.last_login is not None

    def test_authenticate_falsches_passwort(self, service: AuthService) -> None:
        password_hash = service.hash_password(VALID_PASSWORD)
        service.create_administrator("admin", password_hash)
        assert service.authenticate("admin", "Falsch-2026-Kiosk") is None

    def test_authenticate_unbekannter_benutzer(self, service: AuthService) -> None:
        assert service.authenticate("fehlt", VALID_PASSWORD) is None

    def test_load_user(self, service: AuthService) -> None:
        password_hash = service.hash_password(VALID_PASSWORD)
        created = service.create_administrator("admin", password_hash)
        loaded = service.load_user(str(created.id))
        assert loaded is not None
        assert loaded.username == "admin"
        assert service.load_user("99999") is None
        assert service.load_user("keine-zahl") is None
