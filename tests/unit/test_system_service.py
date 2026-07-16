# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer den SystemService."""

from typing import Any

import pytest

from app.exceptions import PiKioskError
from app.extensions import ServiceRegistry
from app.services import system_service as system_module


class FakeResult:
    """Ersatz fuer subprocess.CompletedProcess in den Tests."""

    def __init__(self, returncode: int, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


class TestSystemService:
    """Tests fuer Neustart und Herunterfahren."""

    def test_reboot_ruft_systemctl(
        self, registry: ServiceRegistry, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], **kwargs: Any) -> FakeResult:
            calls.append(command)
            return FakeResult(0)

        monkeypatch.setattr(system_module.subprocess, "run", fake_run)
        registry.system_service.reboot()
        assert calls[0][-2:] == ["systemctl", "reboot"]

    def test_shutdown_ruft_systemctl(
        self, registry: ServiceRegistry, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], **kwargs: Any) -> FakeResult:
            calls.append(command)
            return FakeResult(0)

        monkeypatch.setattr(system_module.subprocess, "run", fake_run)
        registry.system_service.shutdown()
        assert calls[0][-2:] == ["systemctl", "poweroff"]

    def test_sudo_wird_ohne_root_verwendet(
        self, registry: ServiceRegistry, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], **kwargs: Any) -> FakeResult:
            calls.append(command)
            return FakeResult(0)

        monkeypatch.setattr(system_module.subprocess, "run", fake_run)
        monkeypatch.setattr(system_module.os, "geteuid", lambda: 1000)
        registry.system_service.reboot()
        assert calls[0][:2] == ["sudo", "-n"]

    def test_fehlgeschlagenes_kommando(
        self, registry: ServiceRegistry, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_run(command: list[str], **kwargs: Any) -> FakeResult:
            return FakeResult(1, stderr="keine Rechte")

        monkeypatch.setattr(system_module.subprocess, "run", fake_run)
        with pytest.raises(PiKioskError):
            registry.system_service.reboot()
