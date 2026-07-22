# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer Tastenkombinationen."""

import pytest

from app.exceptions import ValidationError
from app.utils.hotkeys import HotkeyMatcher, parse_combo

CTRL_LEFT = 29
CTRL_RIGHT = 97
ALT_LEFT = 56
KEY_K = 37


class TestParseCombo:
    """Tests fuer das Zerlegen einer Tastenkombination."""

    def test_ctrl_alt_k(self) -> None:
        groups = parse_combo("ctrl+alt+k")
        assert groups == (
            frozenset({29, 97}),
            frozenset({56, 100}),
            frozenset({37}),
        )

    def test_gross_klein_und_leerzeichen(self) -> None:
        assert parse_combo("  Strg + ALT + K ") == parse_combo("ctrl+alt+k")

    def test_deutsche_namen(self) -> None:
        assert parse_combo("strg+umschalt+entf") == parse_combo("ctrl+shift+del")

    def test_leere_kombination(self) -> None:
        with pytest.raises(ValidationError):
            parse_combo("   ")

    def test_unbekannte_taste(self) -> None:
        with pytest.raises(ValidationError):
            parse_combo("ctrl+alt+gibtsnicht")

    def test_nur_modifier_wird_abgelehnt(self) -> None:
        with pytest.raises(ValidationError):
            parse_combo("ctrl+alt")


class TestHotkeyMatcher:
    """Tests fuer die Erkennung des Ausloesens."""

    def test_ausloesen_bei_vollstaendiger_kombination(self) -> None:
        matcher = HotkeyMatcher(parse_combo("ctrl+alt+k"))
        assert matcher.feed(CTRL_LEFT, 1) is False
        assert matcher.feed(ALT_LEFT, 1) is False
        assert matcher.feed(KEY_K, 1) is True

    def test_kein_erneutes_ausloesen_ohne_loslassen(self) -> None:
        matcher = HotkeyMatcher(parse_combo("ctrl+alt+k"))
        matcher.feed(CTRL_LEFT, 1)
        matcher.feed(ALT_LEFT, 1)
        assert matcher.feed(KEY_K, 1) is True
        # Autowiederholung der Taste loest nicht erneut aus.
        assert matcher.feed(KEY_K, 2) is False
        assert matcher.feed(KEY_K, 2) is False

    def test_erneutes_ausloesen_nach_loslassen(self) -> None:
        matcher = HotkeyMatcher(parse_combo("ctrl+alt+k"))
        matcher.feed(CTRL_LEFT, 1)
        matcher.feed(ALT_LEFT, 1)
        assert matcher.feed(KEY_K, 1) is True
        assert matcher.feed(KEY_K, 0) is False
        assert matcher.feed(KEY_K, 1) is True

    def test_rechter_modifier_zaehlt_auch(self) -> None:
        matcher = HotkeyMatcher(parse_combo("ctrl+alt+k"))
        matcher.feed(CTRL_RIGHT, 1)
        matcher.feed(ALT_LEFT, 1)
        assert matcher.feed(KEY_K, 1) is True

    def test_ohne_modifier_kein_ausloesen(self) -> None:
        matcher = HotkeyMatcher(parse_combo("ctrl+alt+k"))
        assert matcher.feed(KEY_K, 1) is False
