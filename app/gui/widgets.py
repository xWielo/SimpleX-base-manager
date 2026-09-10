"""
Wspolne, stylizowane komponenty ttk uzywane w calym GUI.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..theme import Palette, Fonts, SPACING_SM, SPACING_MD


def configure_ttk_style(root: tk.Misc) -> ttk.Style:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(
        "App.TFrame",
        background=Palette.BG,
    )
    style.configure(
        "Panel.TFrame",
        background=Palette.BG_PANEL,
    )
    style.configure(
        "Card.TFrame",
        background=Palette.BG_CARD,
    )

    style.configure(
        "Heading.TLabel",
        background=Palette.BG,
        foreground=Palette.TEXT_PRIMARY,
        font=Fonts.heading,
    )
    style.configure(
        "Subheading.TLabel",
        background=Palette.BG,
        foreground=Palette.TEXT_PRIMARY,
        font=Fonts.subheading,
    )
    style.configure(
        "Body.TLabel",
        background=Palette.BG,
        foreground=Palette.TEXT_SECONDARY,
        font=Fonts.body,
    )
    style.configure(
        "BodyOnPanel.TLabel",
        background=Palette.BG_PANEL,
        foreground=Palette.TEXT_SECONDARY,
        font=Fonts.body,
    )
    style.configure(
        "BodyOnCard.TLabel",
        background=Palette.BG_CARD,
        foreground=Palette.TEXT_PRIMARY,
        font=Fonts.body,
    )
    style.configure(
        "Muted.TLabel",
        background=Palette.BG,
        foreground=Palette.TEXT_MUTED,
        font=Fonts.small,
    )
    style.configure(
        "MutedOnCard.TLabel",
        background=Palette.BG_CARD,
        foreground=Palette.TEXT_MUTED,
        font=Fonts.small,
    )

    style.configure(
        "Primary.TButton",
        background=Palette.PURE_WHITE,
        foreground=Palette.BLACK,
        font=Fonts.body_bold,
        borderwidth=0,
        padding=(SPACING_MD, SPACING_SM),
    )
    style.map(
        "Primary.TButton",
        background=[("active", Palette.LIGHT_GRAY), ("disabled", Palette.MID_GRAY)],
        foreground=[("disabled", Palette.GRAY)],
    )

    style.configure(
        "Secondary.TButton",
        background=Palette.BG_CARD,
        foreground=Palette.TEXT_PRIMARY,
        font=Fonts.body,
        borderwidth=1,
        padding=(SPACING_MD, SPACING_SM),
    )
    style.map(
        "Secondary.TButton",
        background=[("active", Palette.DARK_GRAY)],
        bordercolor=[("!disabled", Palette.BORDER)],
    )

    style.configure(
        "Danger.TButton",
        background=Palette.BG,
        foreground=Palette.TEXT_PRIMARY,
        font=Fonts.body_bold,
        borderwidth=1,
        padding=(SPACING_MD, SPACING_SM),
    )
    style.map(
        "Danger.TButton",
        background=[("active", Palette.CHARCOAL)],
        bordercolor=[("!disabled", Palette.OFF_WHITE)],
    )

    style.configure(
        "App.TEntry",
        fieldbackground=Palette.BG_INPUT,
        foreground=Palette.TEXT_PRIMARY,
        insertcolor=Palette.TEXT_PRIMARY,
        borderwidth=1,
        padding=SPACING_SM,
    )

    style.configure(
        "Vertical.TScrollbar",
        background=Palette.BG_CARD,
        troughcolor=Palette.BG,
        bordercolor=Palette.BG,
        arrowcolor=Palette.TEXT_SECONDARY,
    )

    style.configure("App.Treeview", background=Palette.BG_CARD,
                     fieldbackground=Palette.BG_CARD,
                     foreground=Palette.TEXT_PRIMARY,
                     font=Fonts.body, rowheight=28, borderwidth=0)
    style.configure("App.Treeview.Heading", background=Palette.NEAR_BLACK,
                     foreground=Palette.TEXT_SECONDARY, font=Fonts.body_bold,
                     borderwidth=0)
    style.map("App.Treeview", background=[("selected", Palette.DARK_GRAY)],
              foreground=[("selected", Palette.PURE_WHITE)])

    return style


def make_primary_button(parent, text, command) -> ttk.Button:
    return ttk.Button(parent, text=text, command=command, style="Primary.TButton")


def make_secondary_button(parent, text, command) -> ttk.Button:
    return ttk.Button(parent, text=text, command=command, style="Secondary.TButton")


def make_danger_button(parent, text, command) -> ttk.Button:
    return ttk.Button(parent, text=text, command=command, style="Danger.TButton")


class Card(ttk.Frame):
    """Prosta karta z ramka, w stylu czarno-bialym."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, style="Card.TFrame", padding=SPACING_MD, **kwargs)
        self.configure(relief="solid", borderwidth=1)


class StatusBar(ttk.Frame):
    """Pasek statusu na dole okna - pokazuje ostatnia operacje/blad."""

    def __init__(self, parent):
        super().__init__(parent, style="Panel.TFrame", padding=(SPACING_MD, SPACING_SM))
        self.label = ttk.Label(self, text="Gotowe.", style="BodyOnPanel.TLabel")
        self.label.pack(side="left")

    def set_text(self, text: str, is_error: bool = False) -> None:
        color = Palette.OFF_WHITE if is_error else Palette.TEXT_SECONDARY
        self.label.configure(text=text, foreground=color)
