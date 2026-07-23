# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Pruefungen der systemd-Unit-Dateien.

Sichert Eigenschaften der ausgelieferten Unit-Dateien ab, die ohne
laufendes systemd nicht auffallen - insbesondere den Ordnungs-Zyklus,
der dazu fuehrte, dass keymon- und Watchdog-Dienst beim Booten nie
gestartet wurden.
"""

from pathlib import Path

import pytest

SERVICES_DIR = Path(__file__).resolve().parent.parent.parent / "services"

# Diese Unit haengt in graphical.target und wird erst nach dem
# multi-user.target gestartet. Ein After= darauf aus einer Unit in
# multi-user.target erzeugt einen Ordnungs-Zyklus.
GRAPHICAL_UNIT = "pikiosk.service"


def _directive_values(text: str, key: str) -> list[str]:
    """Sammelt alle Werte einer Unit-Direktive (z. B. After=).

    Args:
        text:
            Inhalt der Unit-Datei.

        key:
            Name der Direktive ohne Gleichheitszeichen.

    Returns:
        Alle whitespace-getrennten Einzelwerte aller Vorkommen.
    """
    values: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        if name.strip() == key:
            values.extend(value.split())
    return values


def _unit_files() -> list[Path]:
    """Listet die ausgelieferten Unit-Dateien.

    Returns:
        Alle .service-Dateien im services-Verzeichnis.
    """
    return sorted(SERVICES_DIR.glob("*.service"))


class TestOrderingCycle:
    """Verhindert das erneute Einschleichen des Boot-Ordnungs-Zyklus."""

    def test_unit_dateien_vorhanden(self) -> None:
        assert _unit_files(), "Keine Unit-Dateien gefunden."

    @pytest.mark.parametrize("unit_file", _unit_files(), ids=lambda p: p.name)
    def test_kein_multiuser_dienst_ordnet_nach_pikiosk(self, unit_file: Path) -> None:
        text = unit_file.read_text(encoding="utf-8")
        wanted_by = _directive_values(text, "WantedBy")
        after = _directive_values(text, "After")
        if "multi-user.target" in wanted_by and GRAPHICAL_UNIT in after:
            pytest.fail(
                f"{unit_file.name}: 'After={GRAPHICAL_UNIT}' zusammen mit "
                "'WantedBy=multi-user.target' erzeugt einen Ordnungs-Zyklus "
                "(pikiosk.service haengt in graphical.target). systemd loescht "
                "den Startauftrag dann beim Booten - der Dienst startet nie."
            )

    def test_keymon_startet_unabhaengig_von_pikiosk(self) -> None:
        text = (SERVICES_DIR / "pikiosk-keymon.service").read_text(encoding="utf-8")
        assert GRAPHICAL_UNIT not in _directive_values(text, "After")
        assert GRAPHICAL_UNIT not in _directive_values(text, "Wants")

    def test_watchdog_startet_unabhaengig_von_pikiosk(self) -> None:
        text = (SERVICES_DIR / "pikiosk-watchdog.service").read_text(encoding="utf-8")
        assert GRAPHICAL_UNIT not in _directive_values(text, "After")
