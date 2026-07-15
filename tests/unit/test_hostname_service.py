# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer den HostnameService."""

import socket
import subprocess
from pathlib import Path

import pytest

from app.exceptions import NetworkError, ValidationError
from app.logger import KioskLogger
from app.services import hostname_service as hostname_module
from app.services.hostname_service import HostnameService


class FakeResult:
    """Ersatz fuer subprocess.CompletedProcess in den Tests."""

    def __init__(self, returncode: int, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


@pytest.fixture
def service(test_logger: KioskLogger) -> HostnameService:
    """Erzeugt einen HostnameService fuer die Tests.

    Args:
        test_logger:
            Testspezifischer Logger.

    Returns:
        Ein einsatzbereiter HostnameService.
    """
    return HostnameService(logger=test_logger)


class TestHostnameService:
    """Tests fuer die Hostnameverwaltung."""

    def test_get_liefert_systemhostnamen(self, service: HostnameService) -> None:
        assert service.get() == socket.gethostname()

    def test_validate_lehnt_ungueltigen_namen_ab(
        self, service: HostnameService
    ) -> None:
        with pytest.raises(ValidationError):
            service.validate("kiosk_01")

    def test_set_ohne_aenderung_ruft_kein_kommando(
        self, service: HostnameService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail_run(*args: object, **kwargs: object) -> None:
            raise AssertionError("subprocess.run darf nicht aufgerufen werden")

        monkeypatch.setattr(hostname_module.subprocess, "run", fail_run)
        service.set(socket.gethostname())

    def test_set_ruft_helferskript(
        self, service: HostnameService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], **kwargs: object) -> FakeResult:
            calls.append(command)
            return FakeResult(0)

        monkeypatch.setattr(hostname_module.subprocess, "run", fake_run)
        service.set("neuer-kiosk")
        assert len(calls) == 1
        assert calls[0][-1] == "neuer-kiosk"
        assert "hostname_apply.py" in calls[0][-2]

    def test_fehlgeschlagenes_helferskript(
        self, service: HostnameService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_run(command: list[str], **kwargs: object) -> FakeResult:
            return FakeResult(1, stderr="keine Rechte")

        monkeypatch.setattr(hostname_module.subprocess, "run", fake_run)
        with pytest.raises(NetworkError):
            service.set("neuer-kiosk")

    def test_timeout_beim_helferskript(
        self, service: HostnameService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_run(command: list[str], **kwargs: object) -> FakeResult:
            raise subprocess.TimeoutExpired(cmd=command, timeout=1.0)

        monkeypatch.setattr(hostname_module.subprocess, "run", fake_run)
        with pytest.raises(NetworkError):
            service.apply("neuer-kiosk")

    def test_reboot_required(
        self,
        service: HostnameService,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        hostname_file = tmp_path / "hostname"
        monkeypatch.setattr(hostname_module, "ETC_HOSTNAME_FILE", hostname_file)
        assert service.reboot_required() is False
        hostname_file.write_text("anderer-name\n", encoding="utf-8")
        assert service.reboot_required() is True
        hostname_file.write_text(f"{socket.gethostname()}\n", encoding="utf-8")
        assert service.reboot_required() is False
