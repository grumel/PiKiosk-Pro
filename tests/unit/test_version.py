# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Unit-Tests fuer die Versionsverwaltung."""

import pytest

from app.exceptions import ValidationError
from app.utils.version import is_backup_compatible, parse_version


class TestParseVersion:
    """Tests fuer das Parsen von Versionsnummern."""

    def test_gueltige_version(self) -> None:
        assert parse_version("1.2.3") == (1, 2, 3)
        assert parse_version("0.5.0") == (0, 5, 0)

    @pytest.mark.parametrize("text", ["", "1.2", "1.2.3.4", "a.b.c", "v1.2.3"])
    def test_ungueltige_version(self, text: str) -> None:
        with pytest.raises(ValidationError):
            parse_version(text)


class TestBackupCompatibility:
    """Tests fuer die Kompatibilitaetspruefung von Sicherungen."""

    def test_gleiche_version_ist_kompatibel(self) -> None:
        assert is_backup_compatible("0.5.0", "0.5.0") is True

    def test_aeltere_sicherung_ist_kompatibel(self) -> None:
        assert is_backup_compatible("0.3.0", "0.5.0") is True
        assert is_backup_compatible("0.5.0", "0.6.2") is True

    def test_neuere_sicherung_ist_inkompatibel(self) -> None:
        assert is_backup_compatible("0.6.0", "0.5.0") is False
        assert is_backup_compatible("0.5.1", "0.5.0") is False

    def test_andere_major_version_ist_inkompatibel(self) -> None:
        assert is_backup_compatible("1.0.0", "0.5.0") is False
        assert is_backup_compatible("0.5.0", "1.0.0") is False

    def test_ungueltige_version_meldet_fehler(self) -> None:
        with pytest.raises(ValidationError):
            is_backup_compatible("kaputt", "0.5.0")
