# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer den UpdateService.

Netzwerkzugriffe auf GitHub und der Download werden durch
steuerbare Ersatzobjekte ausgetauscht, damit die Tests ohne
Internetverbindung deterministisch laufen. Alle Dateioperationen
laufen in temporaeren Verzeichnissen.
"""

import io
import json
import tarfile
import zipfile
from pathlib import Path
from typing import Any

import pytest

from app.constants import APP_VERSION
from app.exceptions import UpdateError
from app.logger import KioskLogger
from app.services.backup_service import BackupService
from app.services.config_service import ConfigService
from app.services.update_service import UpdateService
from tests.conftest import project_defaults

CURRENT = APP_VERSION
NEWER = "9.9.0"
DEFAULTS: dict[str, Any] = project_defaults(first_start=False)


def constants_source(version: str) -> str:
    """Erzeugt einen minimalen Quelltext mit Versionsangabe.

    Args:
        version:
            Versionsnummer.

    Returns:
        Quelltext fuer app/constants.py.
    """
    return f'APP_VERSION: str = "{version}"\n'


def build_zip(path: Path, version: str, extra: dict[str, str] | None = None) -> Path:
    """Baut ein Update-Paket als ZIP-Datei.

    Args:
        path:
            Zielpfad des Pakets.

        version:
            Paketversion.

        extra:
            Zusaetzliche Dateien.

    Returns:
        Pfad des erzeugten Pakets.
    """
    members = {
        "app/constants.py": constants_source(version),
        "app/__init__.py": "# init\n",
        "requirements.txt": "Flask\n",
    }
    if extra:
        members.update(extra)
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return path


def build_tar(path: Path, version: str, root: str = "PiKiosk-Pro-9.9.0") -> Path:
    """Baut ein Update-Paket als tar.gz mit Wurzelverzeichnis.

    Args:
        path:
            Zielpfad des Pakets.

        version:
            Paketversion.

        root:
            Name des Wurzelverzeichnisses.

    Returns:
        Pfad des erzeugten Pakets.
    """
    members = {
        f"{root}/app/constants.py": constants_source(version),
        f"{root}/app/__init__.py": "# init\n",
        f"{root}/requirements.txt": "Flask\n",
    }
    with tarfile.open(path, "w:gz") as archive:
        for name, content in members.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return path


@pytest.fixture
def service(tmp_path: Path, test_logger: KioskLogger) -> UpdateService:
    """Erzeugt einen UpdateService mit vorbereitetem Installationsstand.

    Args:
        tmp_path:
            Temporaeres Testverzeichnis.

        test_logger:
            Testspezifischer Logger.

    Returns:
        Ein einsatzbereiter UpdateService.
    """
    defaults_file = tmp_path / "defaults.json"
    defaults_file.write_text(
        json.dumps(DEFAULTS, ensure_ascii=False, indent=4), encoding="utf-8"
    )
    config_service = ConfigService(
        logger=test_logger,
        config_file=tmp_path / "config.json",
        defaults_file=defaults_file,
        backup_dir=tmp_path / "backup",
    )
    config_service.load()
    backup_service = BackupService(
        logger=test_logger,
        config_service=config_service,
        config_file=tmp_path / "config.json",
        users_db_file=tmp_path / "users.db",
        backup_dir=tmp_path / "backup",
        log_dir=tmp_path / "logs",
    )
    install_dir = tmp_path / "install"
    (install_dir / "app").mkdir(parents=True)
    (install_dir / "app" / "constants.py").write_text(
        constants_source(CURRENT), encoding="utf-8"
    )
    (install_dir / "templates").mkdir()
    (install_dir / "templates" / "base.html").write_text("OLD", encoding="utf-8")
    return UpdateService(
        logger=test_logger,
        config_service=config_service,
        backup_service=backup_service,
        install_dir=install_dir,
        releases_dir=tmp_path / "releases",
        repo="test/repo",
    )


class TestApplyPackage:
    """Tests fuer die Installation von Update-Paketen."""

    def test_zip_wird_installiert(self, service: UpdateService, tmp_path: Path) -> None:
        package = build_zip(
            tmp_path / "pkg.zip",
            NEWER,
            {"templates/base.html": "NEW", "static/neu.txt": "x"},
        )
        result = service.apply_package(package)
        assert result["version"] == NEWER
        assert result["previous"] == CURRENT
        assert result["restart_required"] is True
        install = service._install_dir
        assert (install / "templates" / "base.html").read_text() == "NEW"
        assert (install / "static" / "neu.txt").exists()
        assert NEWER in (install / "app" / "constants.py").read_text()

    def test_backup_wird_vor_update_erstellt(
        self, service: UpdateService, tmp_path: Path
    ) -> None:
        package = build_zip(tmp_path / "pkg.zip", NEWER)
        service.apply_package(package)
        assert len(service._backup_service.list_backups()) == 1

    def test_tar_gz_mit_wurzelverzeichnis(
        self, service: UpdateService, tmp_path: Path
    ) -> None:
        package = build_tar(tmp_path / "pkg.tar.gz", NEWER)
        result = service.apply_package(package)
        assert result["version"] == NEWER

    def test_nicht_neuere_version_wird_abgelehnt(
        self, service: UpdateService, tmp_path: Path
    ) -> None:
        package = build_zip(tmp_path / "pkg.zip", CURRENT)
        with pytest.raises(UpdateError):
            service.apply_package(package)

    def test_unvollstaendiges_paket_wird_abgelehnt(
        self, service: UpdateService, tmp_path: Path
    ) -> None:
        bad = tmp_path / "bad.zip"
        with zipfile.ZipFile(bad, "w") as archive:
            archive.writestr("app/constants.py", constants_source(NEWER))
        with pytest.raises(UpdateError):
            service.apply_package(bad)

    def test_paket_ohne_version_wird_abgelehnt(
        self, service: UpdateService, tmp_path: Path
    ) -> None:
        bad = tmp_path / "bad.zip"
        with zipfile.ZipFile(bad, "w") as archive:
            archive.writestr("app/constants.py", "# keine Version\n")
            archive.writestr("app/__init__.py", "# init\n")
            archive.writestr("requirements.txt", "Flask\n")
        with pytest.raises(UpdateError):
            service.apply_package(bad)

    def test_pfad_ausbruch_wird_abgelehnt(
        self, service: UpdateService, tmp_path: Path
    ) -> None:
        bad = tmp_path / "evil.zip"
        with zipfile.ZipFile(bad, "w") as archive:
            archive.writestr("app/constants.py", constants_source(NEWER))
            archive.writestr("app/__init__.py", "# init\n")
            archive.writestr("requirements.txt", "Flask\n")
            archive.writestr("../evil.txt", "boese")
        with pytest.raises(UpdateError):
            service.apply_package(bad)

    def test_kein_archiv_wird_abgelehnt(
        self, service: UpdateService, tmp_path: Path
    ) -> None:
        bad = tmp_path / "kein_archiv.zip"
        bad.write_text("nur Text", encoding="utf-8")
        with pytest.raises(UpdateError):
            service.apply_package(bad)


class TestRollback:
    """Tests fuer den Rollback."""

    def test_rollback_stellt_alten_stand_wieder_her(
        self, service: UpdateService, tmp_path: Path
    ) -> None:
        package = build_zip(
            tmp_path / "pkg.zip",
            NEWER,
            {"templates/base.html": "NEW", "static/neu.txt": "x"},
        )
        service.apply_package(package)
        assert service.can_rollback() is True
        result = service.rollback()
        assert result["version"] == CURRENT
        install = service._install_dir
        assert (install / "templates" / "base.html").read_text() == "OLD"
        assert not (install / "static" / "neu.txt").exists()
        assert CURRENT in (install / "app" / "constants.py").read_text()
        assert service.can_rollback() is False

    def test_rollback_ohne_stand(self, service: UpdateService) -> None:
        assert service.can_rollback() is False
        assert service.rollback_info() is None
        with pytest.raises(UpdateError):
            service.rollback()

    def test_rollback_info(self, service: UpdateService, tmp_path: Path) -> None:
        service.apply_package(build_zip(tmp_path / "pkg.zip", NEWER))
        info = service.rollback_info()
        assert info is not None
        assert info["from_version"] == CURRENT
        assert info["to_version"] == NEWER


class TestGithub:
    """Tests fuer die GitHub-Anbindung."""

    def test_update_verfuegbar(
        self, service: UpdateService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            service,
            "_github_latest",
            lambda: {
                "tag_name": f"v{NEWER}",
                "body": "Neue Funktionen",
                "tarball_url": "https://example.org/archive.tar.gz",
            },
        )
        info = service.check()
        assert info["available"] is True
        assert info["latest"] == NEWER
        assert info["status"] == "available"
        assert info["notes"] == "Neue Funktionen"

    def test_bereits_aktuell(
        self, service: UpdateService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            service, "_github_latest", lambda: {"tag_name": f"v{CURRENT}"}
        )
        info = service.check()
        assert info["available"] is False
        assert info["status"] == "up_to_date"

    def test_kein_release(
        self, service: UpdateService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(service, "_github_latest", lambda: None)
        info = service.check()
        assert info["available"] is False
        assert info["status"] == "no_release"

    def test_ungueltige_version(
        self, service: UpdateService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            service, "_github_latest", lambda: {"tag_name": "release-xyz"}
        )
        info = service.check()
        assert info["available"] is False
        assert info["status"] == "invalid_version"

    def test_apply_github(
        self, service: UpdateService, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        package = build_tar(tmp_path / "release.tar.gz", NEWER)
        monkeypatch.setattr(
            service,
            "_github_latest",
            lambda: {
                "tag_name": f"v{NEWER}",
                "tarball_url": "https://example.org/archive.tar.gz",
            },
        )
        monkeypatch.setattr(service, "_download", lambda url: package)
        result = service.apply()
        assert result["version"] == NEWER

    def test_apply_github_ohne_update(
        self, service: UpdateService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            service, "_github_latest", lambda: {"tag_name": f"v{CURRENT}"}
        )
        with pytest.raises(UpdateError):
            service.apply()
