# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Gemeinsame Testkonfiguration.

Macht das Projektpaket importierbar und stellt wiederverwendbare
Fixtures fuer alle Testebenen bereit.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.logger import KioskLogger  # noqa: E402


@pytest.fixture
def test_logger(tmp_path: Path, request: pytest.FixtureRequest) -> KioskLogger:
    """Erzeugt einen isolierten Logger fuer einen Testfall.

    Args:
        tmp_path:
            Temporaeres Testverzeichnis.

        request:
            Pytest-Anfrageobjekt fuer eindeutige Loggernamen.

    Returns:
        Ein testspezifischer KioskLogger.
    """
    return KioskLogger(f"test_{request.node.name}", tmp_path / "test.log")
