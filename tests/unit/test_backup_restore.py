# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer BackupService und RestoreService."""

import json
import zipfile
from pathlib import Path

import pytest

from app.constants import (
    APP_VERSION,
    BACKUP_CONFIG_MEMBER,
    BACKUP_MANIFEST_MEMBER,
    BACKUP_USERS_MEMBER,
)
from app.exceptions import BackupError, RestoreError
from app.extensions import ServiceRegistry
from app.models.user_model import UserModel
from app.services import restore_service as restore_module


@pytest.fixture
def prepared(registry: ServiceRegistry, tmp_path: Path) -> ServiceRegistry:
    """Bereitet Konfiguration, Benutzer und Logdatei fuer Tests vor.

    Args:
        registry:
            ServiceRegistry mit temporaeren Datenpfaden.

        tmp_path:
            Temporaeres Testverzeichnis.

    Returns:
        Die vorbereitete ServiceRegistry.
    """
    config = registry.config_service.load()
    config["first_start"] = False
    config["url"] = "https://example.org/"
    registry.config_service.save(config)
    registry.auth_service.create_administrator("admin", "hash-fuer-tests")
    log_dir = tmp_path / "logs"
    log_dir.mkdir(exist_ok=True)
    (log_dir / "system.log").write_text("Testlog\n", encoding="utf-8")
    return registry


class TestBackupService:
    """Tests fuer das Erstellen von Sicherungen."""

    def test_create_erzeugt_zip_mit_inhalt(self, prepared: ServiceRegistry) -> None:
        backup_path = prepared.backup_service.create()
        assert backup_path.exists()
        assert backup_path.name.startswith("PiKiosk_Backup_")
        with zipfile.ZipFile(backup_path) as archive:
            names = archive.namelist()
            assert BACKUP_MANIFEST_MEMBER in names
            assert BACKUP_CONFIG_MEMBER in names
            assert BACKUP_USERS_MEMBER in names
            assert not any(name.startswith("logs/") for name in names)
            manifest = json.loads(archive.read(BACKUP_MANIFEST_MEMBER))
        assert manifest["app_version"]
        assert manifest["include_logs"] is False

    def test_create_mit_logdateien(self, prepared: ServiceRegistry) -> None:
        backup_path = prepared.backup_service.create(include_logs=True)
        with zipfile.ZipFile(backup_path) as archive:
            assert "logs/system.log" in archive.namelist()

    def test_list_backups(self, prepared: ServiceRegistry) -> None:
        assert prepared.backup_service.list_backups() == []
        backup_path = prepared.backup_service.create()
        backups = prepared.backup_service.list_backups()
        assert len(backups) == 1
        assert backups[0]["name"] == backup_path.name
        assert backups[0]["size_kb"] >= 1

    def test_backup_file_validiert_namen(self, prepared: ServiceRegistry) -> None:
        backup_path = prepared.backup_service.create()
        assert prepared.backup_service.backup_file(backup_path.name) == backup_path
        with pytest.raises(BackupError):
            prepared.backup_service.backup_file("../../../etc/passwd")
        with pytest.raises(BackupError):
            prepared.backup_service.backup_file("PiKiosk_Backup_99999999_9999.zip")


class TestRestoreService:
    """Tests fuer das Wiederherstellen von Sicherungen."""

    def test_roundtrip_stellt_konfiguration_wieder_her(
        self, prepared: ServiceRegistry
    ) -> None:
        backup_path = prepared.backup_service.create()
        config = prepared.config_service.load()
        config["url"] = "https://geaendert.example.org/"
        config["hostname"] = "Geaendert"
        prepared.config_service.save(config)
        manifest = prepared.restore_service.restore(backup_path)
        restored = prepared.config_service.load()
        assert restored["url"] == "https://example.org/"
        assert restored["hostname"] == "PiKiosk"
        assert manifest["app_version"]

    def test_roundtrip_stellt_benutzer_wieder_her(
        self, prepared: ServiceRegistry, tmp_path: Path
    ) -> None:
        backup_path = prepared.backup_service.create()
        (tmp_path / "users.db").unlink()
        UserModel(tmp_path / "users.db").create_user("anderer", "hash", "admin")
        prepared.restore_service.restore(backup_path)
        restored_model = UserModel(tmp_path / "users.db")
        assert restored_model.find_by_username("admin") is not None
        assert restored_model.find_by_username("anderer") is None

    def test_fehlende_datei(self, prepared: ServiceRegistry) -> None:
        with pytest.raises(RestoreError):
            prepared.restore_service.restore(Path("/tmp/fehlt-sicher.zip"))

    def test_keine_zip_datei(self, prepared: ServiceRegistry, tmp_path: Path) -> None:
        bad = tmp_path / "kaputt.zip"
        bad.write_text("kein zip", encoding="utf-8")
        with pytest.raises(RestoreError):
            prepared.restore_service.validate(bad)

    def test_fehlendes_manifest(
        self, prepared: ServiceRegistry, tmp_path: Path
    ) -> None:
        bad = tmp_path / "ohne_manifest.zip"
        with zipfile.ZipFile(bad, "w") as archive:
            archive.writestr(BACKUP_CONFIG_MEMBER, "{}")
        with pytest.raises(RestoreError):
            prepared.restore_service.validate(bad)

    def test_inkompatible_version(
        self, prepared: ServiceRegistry, tmp_path: Path
    ) -> None:
        bad = tmp_path / "zu_neu.zip"
        with zipfile.ZipFile(bad, "w") as archive:
            archive.writestr(
                BACKUP_MANIFEST_MEMBER, json.dumps({"app_version": "99.0.0"})
            )
            archive.writestr(BACKUP_CONFIG_MEMBER, "{}")
        with pytest.raises(RestoreError) as info:
            prepared.restore_service.validate(bad)
        assert "kompatibl" in str(info.value)

    def test_ungueltige_konfiguration_wird_nicht_uebernommen(
        self, prepared: ServiceRegistry, tmp_path: Path
    ) -> None:
        bad = tmp_path / "bad_config.zip"
        with zipfile.ZipFile(bad, "w") as archive:
            archive.writestr(
                BACKUP_MANIFEST_MEMBER, json.dumps({"app_version": APP_VERSION})
            )
            archive.writestr(BACKUP_CONFIG_MEMBER, json.dumps({"theme": "neon"}))
        before = prepared.config_service.load()
        with pytest.raises(RestoreError):
            prepared.restore_service.restore(bad)
        assert prepared.config_service.load() == before

    def test_ungueltige_benutzerdatenbank_wird_abgelehnt(
        self, prepared: ServiceRegistry, tmp_path: Path
    ) -> None:
        bad = tmp_path / "bad_users.zip"
        config = prepared.config_service.load()
        with zipfile.ZipFile(bad, "w") as archive:
            archive.writestr(
                BACKUP_MANIFEST_MEMBER, json.dumps({"app_version": APP_VERSION})
            )
            archive.writestr(BACKUP_CONFIG_MEMBER, json.dumps(config))
            archive.writestr(BACKUP_USERS_MEMBER, b"kein sqlite")
        with pytest.raises(RestoreError):
            prepared.restore_service.restore(bad)
        assert UserModel(tmp_path / "users.db").find_by_username("admin") is not None

    def test_usb_scan_und_import(
        self,
        prepared: ServiceRegistry,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        usb_root = tmp_path / "media"
        stick = usb_root / "pi" / "STICK"
        stick.mkdir(parents=True)
        backup_path = prepared.backup_service.create()
        usb_backup = stick / "PiKiosk_Backup.zip"
        usb_backup.write_bytes(backup_path.read_bytes())
        monkeypatch.setattr(restore_module, "USB_MOUNT_ROOTS", (usb_root,))
        found = prepared.restore_service.scan_usb()
        assert len(found) == 1
        assert found[0]["name"] == "PiKiosk_Backup.zip"
        manifest = prepared.restore_service.import_from_path(found[0]["path"])
        assert manifest["app_version"]

    def test_import_ausserhalb_usb_wird_abgelehnt(
        self, prepared: ServiceRegistry, tmp_path: Path
    ) -> None:
        backup_path = prepared.backup_service.create()
        with pytest.raises(RestoreError):
            prepared.restore_service.import_from_path(str(backup_path))


class TestRestoreEdgeCases:
    """Tests fuer weitere Wiederherstellungs-Randfaelle."""

    def test_beschaedigtes_archiv_wird_erkannt(self, prepared: ServiceRegistry) -> None:
        backup_path = prepared.backup_service.create()
        raw = bytearray(backup_path.read_bytes())
        raw[len(raw) // 2] ^= 0xFF
        broken = backup_path.with_name("beschaedigt.zip")
        broken.write_bytes(bytes(raw))
        with pytest.raises(RestoreError):
            prepared.restore_service.validate(broken)

    def test_konfiguration_ist_kein_objekt(
        self, prepared: ServiceRegistry, tmp_path: Path
    ) -> None:
        bad = tmp_path / "liste.zip"
        with zipfile.ZipFile(bad, "w") as archive:
            archive.writestr(
                BACKUP_MANIFEST_MEMBER, json.dumps({"app_version": APP_VERSION})
            )
            archive.writestr(BACKUP_CONFIG_MEMBER, "[]")
        with pytest.raises(RestoreError):
            prepared.restore_service.validate(bad)

    def test_manifest_ohne_version(
        self, prepared: ServiceRegistry, tmp_path: Path
    ) -> None:
        bad = tmp_path / "ohne_version.zip"
        with zipfile.ZipFile(bad, "w") as archive:
            archive.writestr(BACKUP_MANIFEST_MEMBER, json.dumps({"x": 1}))
            archive.writestr(BACKUP_CONFIG_MEMBER, "{}")
        with pytest.raises(RestoreError):
            prepared.restore_service.validate(bad)

    def test_leere_benutzerdatenbank_wird_abgelehnt(
        self, prepared: ServiceRegistry, tmp_path: Path
    ) -> None:
        import sqlite3

        empty_db = tmp_path / "leer.db"
        connection = sqlite3.connect(empty_db)
        connection.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, "
            "password_hash TEXT, role TEXT, created_at TEXT, "
            "last_login TEXT, enabled INTEGER)"
        )
        connection.commit()
        connection.close()
        config = prepared.config_service.load()
        bad = tmp_path / "leere_benutzer.zip"
        with zipfile.ZipFile(bad, "w") as archive:
            archive.writestr(
                BACKUP_MANIFEST_MEMBER, json.dumps({"app_version": APP_VERSION})
            )
            archive.writestr(BACKUP_CONFIG_MEMBER, json.dumps(config))
            archive.write(empty_db, BACKUP_USERS_MEMBER)
        with pytest.raises(RestoreError):
            prepared.restore_service.restore(bad)

    def test_restore_ohne_benutzerdatenbank(
        self, prepared: ServiceRegistry, tmp_path: Path
    ) -> None:
        config = prepared.config_service.load()
        config["hostname"] = "NurKonfig"
        nur_config = tmp_path / "nur_config.zip"
        with zipfile.ZipFile(nur_config, "w") as archive:
            archive.writestr(
                BACKUP_MANIFEST_MEMBER, json.dumps({"app_version": APP_VERSION})
            )
            archive.writestr(BACKUP_CONFIG_MEMBER, json.dumps(config))
        prepared.restore_service.restore(nur_config)
        assert prepared.config_service.load()["hostname"] == "NurKonfig"
        assert UserModel(tmp_path / "users.db").find_by_username("admin") is not None


class TestBackupEdgeCases:
    """Tests fuer Sicherungs-Randfaelle."""

    def test_fremde_zip_wird_nicht_gelistet(
        self, prepared: ServiceRegistry, tmp_path: Path
    ) -> None:
        prepared.backup_service.create()
        (tmp_path / "backup" / "fremd.zip").write_bytes(b"PK")
        backups = prepared.backup_service.list_backups()
        assert len(backups) == 1

    def test_schreibfehler_meldet_backupfehler(
        self, prepared: ServiceRegistry, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services import backup_service as backup_module

        def broken_zip(*args: object, **kwargs: object) -> None:
            raise OSError("Datentraeger voll")

        monkeypatch.setattr(backup_module.zipfile, "ZipFile", broken_zip)
        with pytest.raises(BackupError):
            prepared.backup_service.create()
