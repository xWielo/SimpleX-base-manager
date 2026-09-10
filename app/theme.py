"""
Definicje motywu wizualnego: paleta czarno-biala, fonty, odstepy.

Cel: spokojny, kontrastowy, czytelny wyglad bez kolorow - czern,
biel i odcienie szarosci jako jedyne akcenty. Fonty wybierane z listy
kandydatow w kolejnosci preferencji, z fallbackiem na systemowe jesli
zaden z preferowanych nie jest zainstalowany.
"""

from __future__ import annotations

import tkinter.font as tkfont


class Palette:
    BLACK = "#0a0a0a"
    NEAR_BLACK = "#141414"
    CHARCOAL = "#1f1f1f"
    DARK_GRAY = "#2b2b2b"
    MID_GRAY = "#4a4a4a"
    GRAY = "#7a7a7a"
    LIGHT_GRAY = "#bdbdbd"
    OFF_WHITE = "#e8e8e8"
    WHITE = "#f5f5f5"
    PURE_WHITE = "#ffffff"

    BG = BLACK
    BG_PANEL = NEAR_BLACK
    BG_CARD = CHARCOAL
    BG_INPUT = DARK_GRAY
    BORDER = MID_GRAY
    TEXT_PRIMARY = WHITE
    TEXT_SECONDARY = LIGHT_GRAY
    TEXT_MUTED = GRAY
    ACCENT = PURE_WHITE
    DANGER_BORDER = OFF_WHITE


HEADING_FONT_CANDIDATES = [
    "Inter",
    "SF Pro Display",
    "Segoe UI",
    "Helvetica Neue",
    "Liberation Sans",
    "DejaVu Sans",
]

BODY_FONT_CANDIDATES = [
    "Inter",
    "SF Pro Text",
    "Segoe UI",
    "Helvetica Neue",
    "Liberation Sans",
    "DejaVu Sans",
]

MONO_FONT_CANDIDATES = [
    "JetBrains Mono",
    "Fira Code",
    "SF Mono",
    "Cascadia Mono",
    "Liberation Mono",
    "DejaVu Sans Mono",
]


def _pick_available(candidates: list[str]) -> str:
    available = set(tkfont.families())
    for name in candidates:
        if name in available:
            return name
    return "TkDefaultFont"


class Fonts:
    """
    Instancjonowane leniwie (po utworzeniu tk.Tk()), bo tkfont.families()
    wymaga zainicjowanego interpretera Tcl/Tk.
    """

    heading: tkfont.Font
    subheading: tkfont.Font
    body: tkfont.Font
    body_bold: tkfont.Font
    small: tkfont.Font
    mono: tkfont.Font

    @classmethod
    def init(cls) -> None:
        heading_family = _pick_available(HEADING_FONT_CANDIDATES)
        body_family = _pick_available(BODY_FONT_CANDIDATES)
        mono_family = _pick_available(MONO_FONT_CANDIDATES)

        cls.heading = tkfont.Font(family=heading_family, size=20, weight="bold")
        cls.subheading = tkfont.Font(family=heading_family, size=13, weight="bold")
        cls.body = tkfont.Font(family=body_family, size=11)
        cls.body_bold = tkfont.Font(family=body_family, size=11, weight="bold")
        cls.small = tkfont.Font(family=body_family, size=9)
        cls.mono = tkfont.Font(family=mono_family, size=10)


SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 16
SPACING_LG = 24
SPACING_XL = 36
