# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - UpdateService.

Aktualisiert die Anwendung ueber lokale Update-Pakete oder direkt
aus GitHub-Releases. Vor jedem Update wird automatisch eine
Sicherung erstellt und ein Rollback-Stand des aktuellen Programm-
codes angelegt. Ungueltige Pakete werden niemals installiert.
Konfiguration, Benutzerdatenbank und Logs bleiben beim Update
unangetastet.
"""

import json
import os
import re
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.constants import (
    APP_VERSION,
    BASE_DIR,
    GITHUB_API_BASE,
    GITHUB_REPO,
    RELEASES_DIR,
    UPDATE_HTTP_TIMEOUT_SECONDS,
    UPDATE_MAX_UNCOMPRESSED_BYTES,
    UPDATE_PACKAGE_MAX_BYTES,
    UPDATE_PROTECTED_PATHS,
    UPDATE_PROTECTED_PREFIXES,
    UPDATE_REQUIRED_MEMBERS,
    UPDATE_USER_AGENT,
)
from app.exceptions import ConfigurationError, UpdateError, ValidationError
from app.logger import KioskLogger
from app.services.backup_service import BackupService
from app.services.config_service import ConfigService
from app.utils.filesystem import read_json_file, write_json_atomic
from app.utils.version import is_newer

CONSTANTS_MEMBER: str = "app/constants.py"
VERSION_IN_SOURCE: re.Pattern[str] = re.compile(
    r'APP_VERSION:\s*str\s*=\s*"(\d+\.\d+\.\d+)"'
)
MANIFEST_NAME: str = "update_manifest.json"
SNAPSHOT_IGNORE_ANY: frozenset[str] = frozenset(
    {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
)
SNAPSHOT_IGNORE_TOP: frozenset[str] = frozenset(
    {".venv", "venv", ".git", "logs", "backup", ".env"}
)
SNAPSHOT_IGNORE_FILES: frozenset[str] = frozenset(
    {"config.json", "users.db", "secret_key"}
)


class UpdateService:
    """Verwaltet Updates und Rollbacks der Anwendung.

    Args:
        logger:
            Logger fuer alle Updateereignisse.

        config_service:
            Dienst fuer die Konfigurationsverwaltung.

        backup_service:
            Dienst fuer die Sicherung vor dem Update.

        install_dir:
            Installationsverzeichnis der Anwendung.

        releases_dir:
            Verzeichnis fuer Rollback-Staende und das Manifest.

        repo:
            GitHub-Repository im Format "eigner/name".
    """

    def __init__(
        self,
        logger: KioskLogger,
        config_service: ConfigService,
        backup_service: BackupService,
        install_dir: Path = BASE_DIR,
        releases_dir: Path = RELEASES_DIR,
        repo: str = GITHUB_REPO,
    ) -> None:
        self._logger = logger
        self._config_service = config_service
        self._backup_service = backup_service
        self._install_dir = install_dir
        self._releases_dir = releases_dir
        self._repo = repo
        self._manifest_file = releases_dir / MANIFEST_NAME

    def current_version(self) -> str:
        """Liefert die Version der laufenden Anwendung.

        Returns:
            Die aktuelle Versionsnummer.
        """
        return APP_VERSION

    def check_github(self) -> dict[str, Any]:
        """Prueft, ob im GitHub-Repository ein Update bereitsteht.

        Returns:
            Ergebnis mit Verfuegbarkeit, aktueller und neuester
            Version, Release-Notizen, Archiv-URL und einem
            maschinenlesbaren Statuscode.

        Raises:
            UpdateError
        """
        current = self.current_version()
        data = self._github_latest()
        if data is None:
            return self._github_result(current, None, "", None, "no_release", False)
        tag = str(data.get("tag_name", "")).strip()
        latest = tag[1:] if tag.startswith("v") else tag
        try:
            available = is_newer(latest, current)
        except ValidationError:
            return self._github_result(current, tag, "", None, "invalid_version", False)
        archive = str(
            data.get("tarball_url")
            or f"{GITHUB_API_BASE}/repos/{self._repo}/tarball/{tag}"
        )
        status = "available" if available else "up_to_date"
        return self._github_result(
            current, latest, str(data.get("body", "")), archive, status, available
        )

    def apply_github(self) -> dict[str, Any]:
        """Laedt das neueste GitHub-Release und installiert es.

        Returns:
            Ergebnis der Installation.

        Raises:
            UpdateError
        """
        info = self.check_github()
        if not info["available"] or not info["archive_url"]:
            raise UpdateError("Es steht kein neueres GitHub-Release bereit.")
        archive = self._download(str(info["archive_url"]))
        try:
            return self.apply_package(archive)
        finally:
            archive.unlink(missing_ok=True)

    def apply_package(self, package_path: Path) -> dict[str, Any]:
        """Installiert ein lokales Update-Paket.

        Args:
            package_path:
                Pfad des Update-Pakets (ZIP oder tar.gz).

        Returns:
            Ergebnis mit neuer und vorheriger Version.

        Raises:
            UpdateError
        """
        version, files = self._load_package(package_path)
        current = self.current_version()
        if not is_newer(version, current):
            raise UpdateError(
                f"Die Version {version} ist nicht neuer als die installierte "
                f"Version {current}."
            )
        backup_path = self._backup_service.create(include_logs=False)
        snapshot = self._snapshot()
        installed = self._extract(files)
        manifest = {
            "from_version": current,
            "to_version": version,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "snapshot": str(snapshot),
            "backup": str(backup_path),
            "package_files": installed,
        }
        write_json_atomic(self._manifest_file, manifest)
        self._logger.info(f"Update installiert: {current} -> {version}")
        return {
            "version": version,
            "previous": current,
            "restart_required": True,
        }

    def can_rollback(self) -> bool:
        """Prueft, ob ein Rollback moeglich ist.

        Returns:
            True, wenn ein gueltiger Rollback-Stand vorliegt.
        """
        manifest = self._safe_manifest()
        if manifest is None:
            return False
        return Path(str(manifest.get("snapshot", ""))).exists()

    def rollback_info(self) -> dict[str, str] | None:
        """Liefert die Eckdaten des moeglichen Rollbacks.

        Returns:
            Von- und Zielversion des Rollbacks oder None.
        """
        manifest = self._safe_manifest()
        if manifest is None:
            return None
        return {
            "from_version": str(manifest.get("from_version", "")),
            "to_version": str(manifest.get("to_version", "")),
        }

    def rollback(self) -> dict[str, Any]:
        """Setzt die Anwendung auf den letzten Stand zurueck.

        Returns:
            Ergebnis mit der wiederhergestellten Version.

        Raises:
            UpdateError
        """
        manifest = self._safe_manifest()
        if manifest is None:
            raise UpdateError("Es ist kein Rollback-Stand vorhanden.")
        snapshot = Path(str(manifest.get("snapshot", "")))
        if not snapshot.exists():
            raise UpdateError("Der Rollback-Stand wurde nicht gefunden.")
        snapshot_files = self._relative_files(snapshot)
        self._remove_added_files(manifest, snapshot_files)
        self._restore_snapshot(snapshot, snapshot_files)
        restored = str(manifest.get("from_version", ""))
        self._manifest_file.unlink(missing_ok=True)
        shutil.rmtree(snapshot, ignore_errors=True)
        self._logger.info(f"Rollback auf Version {restored} durchgefuehrt.")
        return {"version": restored, "restart_required": True}

    def _github_result(
        self,
        current: str,
        latest: str | None,
        notes: str,
        archive_url: str | None,
        status: str,
        available: bool,
    ) -> dict[str, Any]:
        """Baut das Ergebnisobjekt der GitHub-Pruefung.

        Args:
            current:
                Aktuelle Version.

            latest:
                Neueste gefundene Version oder None.

            notes:
                Release-Notizen.

            archive_url:
                URL des Release-Archivs oder None.

            status:
                Maschinenlesbarer Statuscode.

            available:
                True, wenn ein Update verfuegbar ist.

        Returns:
            Das Ergebnisobjekt.
        """
        return {
            "current": current,
            "latest": latest,
            "notes": notes,
            "archive_url": archive_url,
            "status": status,
            "available": available,
        }

    def _github_latest(self) -> dict[str, Any] | None:
        """Fragt das neueste Release ueber die GitHub-API ab.

        Returns:
            Die Release-Daten oder None, wenn kein Release existiert.

        Raises:
            UpdateError
        """
        url = f"{GITHUB_API_BASE}/repos/{self._repo}/releases/latest"
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": UPDATE_USER_AGENT,
                "Accept": "application/vnd.github+json",
            },
        )
        try:
            with urllib.request.urlopen(
                request, timeout=UPDATE_HTTP_TIMEOUT_SECONDS
            ) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise UpdateError(
                f"GitHub-Abfrage fehlgeschlagen: HTTP {error.code}"
            ) from error
        except (urllib.error.URLError, OSError, ValueError) as error:
            raise UpdateError(f"GitHub ist nicht erreichbar: {error}") from error
        return data if isinstance(data, dict) else None

    def _download(self, url: str) -> Path:
        """Laedt ein Update-Archiv in eine temporaere Datei.

        Args:
            url:
                URL des Archivs.

        Returns:
            Pfad der heruntergeladenen Datei.

        Raises:
            UpdateError
        """
        request = urllib.request.Request(url, headers={"User-Agent": UPDATE_USER_AGENT})
        descriptor, temp_name = tempfile.mkstemp(
            suffix=".tar.gz", prefix="pikiosk_update_"
        )
        path = Path(temp_name)
        try:
            with urllib.request.urlopen(
                request, timeout=UPDATE_HTTP_TIMEOUT_SECONDS
            ) as response, os.fdopen(descriptor, "wb") as output:
                total = 0
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > UPDATE_PACKAGE_MAX_BYTES:
                        raise UpdateError("Das Update-Archiv ist zu gross.")
                    output.write(chunk)
        except (urllib.error.URLError, OSError) as error:
            path.unlink(missing_ok=True)
            raise UpdateError(f"Download fehlgeschlagen: {error}") from error
        except UpdateError:
            path.unlink(missing_ok=True)
            raise
        return path

    def _load_package(self, path: Path) -> tuple[str, dict[str, bytes]]:
        """Liest und prueft ein Update-Paket.

        Args:
            path:
                Pfad des Update-Pakets.

        Returns:
            Tupel aus Paketversion und Dateizuordnung.

        Raises:
            UpdateError
        """
        if not path.exists():
            raise UpdateError("Das Update-Paket wurde nicht gefunden.")
        if zipfile.is_zipfile(path):
            files = self._read_zip(path)
        elif tarfile.is_tarfile(path):
            files = self._read_tar(path)
        else:
            raise UpdateError("Das Paket ist weder ein ZIP- noch ein tar.gz-Archiv.")
        files = self._strip_root(files)
        for member in UPDATE_REQUIRED_MEMBERS:
            if member not in files:
                raise UpdateError(
                    f"Das Update-Paket ist unvollstaendig: {member} fehlt."
                )
        version = self._version_from_source(files[CONSTANTS_MEMBER])
        return version, files

    def _read_zip(self, path: Path) -> dict[str, bytes]:
        """Liest die Dateien eines ZIP-Pakets.

        Args:
            path:
                Pfad des ZIP-Archivs.

        Returns:
            Zuordnung von Pfad zu Dateiinhalt.

        Raises:
            UpdateError
        """
        files: dict[str, bytes] = {}
        total = 0
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise UpdateError("Das Update-Paket ist beschaedigt.")
            for info in archive.infolist():
                if info.is_dir():
                    continue
                name = self._safe_member_name(info.filename)
                total += info.file_size
                if total > UPDATE_MAX_UNCOMPRESSED_BYTES:
                    raise UpdateError("Das Update-Paket ist zu gross.")
                files[name] = archive.read(info)
        return files

    def _read_tar(self, path: Path) -> dict[str, bytes]:
        """Liest die Dateien eines tar.gz-Pakets.

        Args:
            path:
                Pfad des tar.gz-Archivs.

        Returns:
            Zuordnung von Pfad zu Dateiinhalt.

        Raises:
            UpdateError
        """
        files: dict[str, bytes] = {}
        total = 0
        with tarfile.open(path, "r:*") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                name = self._safe_member_name(member.name)
                total += member.size
                if total > UPDATE_MAX_UNCOMPRESSED_BYTES:
                    raise UpdateError("Das Update-Paket ist zu gross.")
                extracted = archive.extractfile(member)
                if extracted is None:
                    continue
                files[name] = extracted.read()
        return files

    def _safe_member_name(self, name: str) -> str:
        """Normalisiert einen Archivpfad und verhindert Ausbrueche.

        Args:
            name:
                Pfad eines Archiveintrags.

        Returns:
            Der normalisierte relative Pfad.

        Raises:
            UpdateError
        """
        cleaned = name.replace("\\", "/")
        parts = Path(cleaned).parts
        if cleaned.startswith("/") or ".." in parts:
            raise UpdateError(f"Unsicherer Pfad im Update-Paket: {name!r}")
        while cleaned.startswith("./"):
            cleaned = cleaned[2:]
        return cleaned

    def _strip_root(self, files: dict[str, bytes]) -> dict[str, bytes]:
        """Entfernt ein einzelnes Wurzelverzeichnis aus den Pfaden.

        GitHub-Archive legen alle Dateien unter einem Wurzelordner
        ab; eigene Pakete nicht. Beide Formen werden unterstuetzt.

        Args:
            files:
                Zuordnung von Pfad zu Dateiinhalt.

        Returns:
            Die bereinigte Zuordnung.

        Raises:
            UpdateError
        """
        if CONSTANTS_MEMBER in files:
            return files
        roots = {name.split("/", 1)[0] for name in files if "/" in name}
        if len(roots) == 1:
            root = roots.pop() + "/"
            if root + CONSTANTS_MEMBER not in files:
                raise UpdateError("Die Struktur des Update-Pakets ist ungueltig.")
            return {
                name[len(root) :]: data
                for name, data in files.items()
                if name.startswith(root)
            }
        raise UpdateError("Die Struktur des Update-Pakets ist ungueltig.")

    def _version_from_source(self, data: bytes) -> str:
        """Liest die Versionsnummer aus dem Quelltext der Konstanten.

        Args:
            data:
                Inhalt der Datei app/constants.py.

        Returns:
            Die gefundene Versionsnummer.

        Raises:
            UpdateError
        """
        match = VERSION_IN_SOURCE.search(data.decode("utf-8", "replace"))
        if match is None:
            raise UpdateError("Im Update-Paket wurde keine Version gefunden.")
        return match.group(1)

    def _is_protected(self, relative_path: str) -> bool:
        """Prueft, ob ein Pfad beim Update unangetastet bleibt.

        Args:
            relative_path:
                Pfad relativ zum Installationsverzeichnis.

        Returns:
            True, wenn der Pfad geschuetzt ist.
        """
        if relative_path in UPDATE_PROTECTED_PATHS:
            return True
        return any(
            relative_path.startswith(prefix) for prefix in UPDATE_PROTECTED_PREFIXES
        )

    def _extract(self, files: dict[str, bytes]) -> list[str]:
        """Schreibt die Paketdateien in das Installationsverzeichnis.

        Args:
            files:
                Zuordnung von Pfad zu Dateiinhalt.

        Returns:
            Liste der installierten Pfade.

        Raises:
            UpdateError
        """
        installed: list[str] = []
        try:
            for relative_path, data in files.items():
                if self._is_protected(relative_path):
                    continue
                target = self._install_dir / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                self._atomic_write(target, data)
                if relative_path.endswith(".sh") or relative_path.startswith(
                    "scripts/"
                ):
                    target.chmod(0o755)
                installed.append(relative_path)
        except OSError as error:
            raise UpdateError(
                f"Das Update konnte nicht geschrieben werden: {error}"
            ) from error
        return installed

    def _snapshot(self) -> Path:
        """Erstellt einen Rollback-Stand des aktuellen Programmcodes.

        Returns:
            Pfad des angelegten Rollback-Standes.

        Raises:
            UpdateError
        """
        self._install_dir.mkdir(parents=True, exist_ok=True)
        self._releases_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot = self._releases_dir / f"rollback_{timestamp}"
        if snapshot.exists():
            shutil.rmtree(snapshot)
        try:
            shutil.copytree(
                self._install_dir,
                snapshot,
                ignore=self._snapshot_ignore,
                dirs_exist_ok=True,
            )
        except OSError as error:
            raise UpdateError(
                f"Der Rollback-Stand konnte nicht erstellt werden: {error}"
            ) from error
        return snapshot

    def _snapshot_ignore(self, directory: str, names: list[str]) -> set[str]:
        """Bestimmt, welche Eintraege der Rollback-Stand auslaesst.

        Args:
            directory:
                Aktuell kopiertes Verzeichnis.

            names:
                Eintraege in diesem Verzeichnis.

        Returns:
            Auszulassende Eintraege.
        """
        ignored: set[str] = set()
        current = Path(directory)
        for name in names:
            if name in SNAPSHOT_IGNORE_ANY or name.endswith(".pyc"):
                ignored.add(name)
            elif current == self._install_dir and name in SNAPSHOT_IGNORE_TOP:
                ignored.add(name)
            elif name in SNAPSHOT_IGNORE_FILES:
                ignored.add(name)
        return ignored

    def _relative_files(self, root: Path) -> set[str]:
        """Sammelt alle Dateien unterhalb eines Verzeichnisses.

        Args:
            root:
                Wurzelverzeichnis.

        Returns:
            Relative Pfade aller enthaltenen Dateien.
        """
        return {
            str(path.relative_to(root)).replace(os.sep, "/")
            for path in root.rglob("*")
            if path.is_file()
        }

    def _remove_added_files(
        self, manifest: dict[str, Any], snapshot_files: set[str]
    ) -> None:
        """Entfernt Dateien, die das Update neu hinzugefuegt hatte.

        Args:
            manifest:
                Manifest des zuletzt installierten Updates.

            snapshot_files:
                Dateien des Rollback-Standes.
        """
        for relative_path in manifest.get("package_files", []):
            if relative_path in snapshot_files or self._is_protected(relative_path):
                continue
            (self._install_dir / relative_path).unlink(missing_ok=True)

    def _restore_snapshot(self, snapshot: Path, snapshot_files: set[str]) -> None:
        """Stellt die Dateien des Rollback-Standes wieder her.

        Args:
            snapshot:
                Pfad des Rollback-Standes.

            snapshot_files:
                Relative Pfade der wiederherzustellenden Dateien.

        Raises:
            UpdateError
        """
        try:
            for relative_path in snapshot_files:
                target = self._install_dir / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                self._atomic_write(target, (snapshot / relative_path).read_bytes())
                if relative_path.endswith(".sh") or relative_path.startswith(
                    "scripts/"
                ):
                    target.chmod(0o755)
        except OSError as error:
            raise UpdateError(
                f"Der Rollback konnte nicht abgeschlossen werden: {error}"
            ) from error

    def _atomic_write(self, target: Path, data: bytes) -> None:
        """Schreibt eine Datei atomar.

        Args:
            target:
                Zielpfad.

            data:
                Zu schreibende Bytes.
        """
        descriptor, temp_name = tempfile.mkstemp(
            dir=target.parent, prefix=target.name, suffix=".tmp"
        )
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        os.replace(temp_name, target)

    def _safe_manifest(self) -> dict[str, Any] | None:
        """Liest das Update-Manifest ohne Fehler nach aussen zu geben.

        Returns:
            Das Manifest oder None, wenn es fehlt oder defekt ist.
        """
        try:
            return read_json_file(self._manifest_file)
        except ConfigurationError:
            return None
