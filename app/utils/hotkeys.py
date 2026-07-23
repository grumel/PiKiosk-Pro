# Copyright (c) 2026 Holger John
# Lizenz: MIT License (siehe LICENSE)
"""PiKiosk Pro - Tastenkombinationen.

Wandelt eine lesbare Tastenkombination wie "ctrl+alt+k" in die
Tastencodes des Linux-Eingabesystems (evdev) um und erkennt anhand
eines Stroms von Tastenereignissen, wann die Kombination vollstaendig
gedrueckt ist. Die Logik ist bewusst frei von Geraetezugriffen,
damit sie ohne Hardware getestet werden kann.
"""

from app.exceptions import ValidationError

EV_KEY: int = 1
KEY_PRESS: int = 1
KEY_RELEASE: int = 0

# Modifier werden als Gruppe gefuehrt: links oder rechts zaehlt.
MODIFIER_GROUPS: dict[str, tuple[int, ...]] = {
    "ctrl": (29, 97),
    "control": (29, 97),
    "strg": (29, 97),
    "alt": (56, 100),
    "altgr": (100,),
    "shift": (42, 54),
    "umschalt": (42, 54),
    "meta": (125, 126),
    "super": (125, 126),
    "win": (125, 126),
}

_LETTERS: dict[str, int] = {
    "a": 30,
    "b": 48,
    "c": 46,
    "d": 32,
    "e": 18,
    "f": 33,
    "g": 34,
    "h": 35,
    "i": 23,
    "j": 36,
    "k": 37,
    "l": 38,
    "m": 50,
    "n": 49,
    "o": 24,
    "p": 25,
    "q": 16,
    "r": 19,
    "s": 31,
    "t": 20,
    "u": 22,
    "v": 47,
    "w": 17,
    "x": 45,
    "y": 21,
    "z": 44,
}
_DIGITS: dict[str, int] = {
    "1": 2,
    "2": 3,
    "3": 4,
    "4": 5,
    "5": 6,
    "6": 7,
    "7": 8,
    "8": 9,
    "9": 10,
    "0": 11,
}
_FUNCTION_KEYS: dict[str, int] = {
    "f1": 59,
    "f2": 60,
    "f3": 61,
    "f4": 62,
    "f5": 63,
    "f6": 64,
    "f7": 65,
    "f8": 66,
    "f9": 67,
    "f10": 68,
    "f11": 87,
    "f12": 88,
}
_NAMED_KEYS: dict[str, int] = {
    "esc": 1,
    "escape": 1,
    "space": 57,
    "enter": 28,
    "return": 28,
    "tab": 15,
    "del": 111,
    "delete": 111,
    "entf": 111,
    "backspace": 14,
    "home": 102,
    "end": 107,
    "insert": 110,
    "pause": 119,
}

# Reine Tasten (keine Modifier) als Name -> Tastencode.
KEY_NAMES: dict[str, int] = {**_LETTERS, **_DIGITS, **_FUNCTION_KEYS, **_NAMED_KEYS}


def parse_combo(text: str) -> tuple[frozenset[int], ...]:
    """Zerlegt eine Tastenkombination in Tastencode-Gruppen.

    Jede Gruppe enthaelt die zulaessigen Tastencodes fuer ein Element
    der Kombination; bei Modifiern sind das die linke und die rechte
    Variante. Die Kombination gilt als erfuellt, wenn aus jeder
    Gruppe mindestens eine Taste gedrueckt ist.

    Args:
        text:
            Kombination wie "ctrl+alt+k" (Gross-/Kleinschreibung
            egal, Trennzeichen "+").

    Returns:
        Ein Tupel von Tastencode-Gruppen.

    Raises:
        ValidationError
    """
    parts = [part.strip().lower() for part in text.split("+") if part.strip()]
    if not parts:
        raise ValidationError("Die Tastenkombination ist leer.")
    groups: list[frozenset[int]] = []
    has_regular_key = False
    for part in parts:
        if part in MODIFIER_GROUPS:
            groups.append(frozenset(MODIFIER_GROUPS[part]))
        elif part in KEY_NAMES:
            groups.append(frozenset({KEY_NAMES[part]}))
            has_regular_key = True
        else:
            raise ValidationError(f"Unbekannte Taste in der Kombination: '{part}'.")
    if not has_regular_key:
        raise ValidationError(
            "Die Tastenkombination braucht mindestens eine normale Taste "
            "zusaetzlich zu den Modifiern."
        )
    return tuple(groups)


class HotkeyMatcher:
    """Erkennt das Ausloesen einer Tastenkombination.

    Verarbeitet einzelne Tastenereignisse (Tastencode und Wert) und
    meldet genau dann ein Ausloesen, wenn die Kombination vollstaendig
    gedrueckt wird. Ein erneutes Ausloesen ist erst moeglich, nachdem
    die Kombination zwischenzeitlich unvollstaendig war.

    Args:
        groups:
            Tastencode-Gruppen aus parse_combo.
    """

    def __init__(self, groups: tuple[frozenset[int], ...]) -> None:
        self._groups = groups
        self._pressed: set[int] = set()
        self._active = False

    def reset(self) -> None:
        """Verwirft den gemerkten Tastenzustand.

        Wird nach einem Neu-Oeffnen der Eingabegeraete aufgerufen,
        weil dabei keine Aussage mehr ueber gehaltene Tasten moeglich
        ist.
        """
        self._pressed.clear()
        self._active = False

    def feed(self, code: int, value: int) -> bool:
        """Verarbeitet ein Tastenereignis.

        Args:
            code:
                Tastencode des Ereignisses.

            value:
                1 = gedrueckt, 0 = losgelassen, 2 = Wiederholung.

        Returns:
            True, wenn die Kombination durch dieses Ereignis
            vollstaendig wurde.
        """
        if value == KEY_RELEASE:
            self._pressed.discard(code)
        else:
            self._pressed.add(code)
        satisfied = all(bool(group & self._pressed) for group in self._groups)
        triggered = satisfied and not self._active
        self._active = satisfied
        return triggered
