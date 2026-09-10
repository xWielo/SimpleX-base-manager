"""
Ekran startowy: wybor pliku bazy simplex_v1_chat.db i wpisanie hasla.

Sciezka do pliku i haslo trafiaja wylacznie do zmiennych w pamieci
tego procesu - nic nie jest zapisywane do pliku konfiguracyjnego,
zmiennej srodowiskowej ani historii powloki.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog

from ..theme import Palette, Fonts, SPACING_MD, SPACING_LG, SPACING_SM
from .widgets import make_primary_button, make_secondary_button, Card


class LoginView(ttk.Frame):
    def __init__(self, parent, on_submit):
        """
        on_submit: callback(db_path: str, passphrase: str) -> None
        wywolywany po kliknieciu 'Otworz baze'.
        """
        super().__init__(parent, style="App.TFrame", padding=SPACING_LG)
        self.on_submit = on_submit
        self._db_path_var = tk.StringVar()
        self._passphrase_var = tk.StringVar()
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)

        title = ttk.Label(self, text="SimpleX Vault Reader", style="Heading.TLabel")
        title.grid(row=0, column=0, sticky="w", pady=(0, SPACING_SM))

        subtitle = ttk.Label(
            self,
            text="Podglad lokalnej bazy SimpleX Chat. Nic nie opuszcza tego okna.",
            style="Body.TLabel",
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(0, SPACING_LG))

        card = Card(self)
        card.grid(row=2, column=0, sticky="ew")
        card.columnconfigure(0, weight=1)

        path_label = ttk.Label(card, text="Plik bazy (simplex_v1_chat.db)", style="BodyOnCard.TLabel")
        path_label.grid(row=0, column=0, sticky="w")

        path_row = ttk.Frame(card, style="Card.TFrame")
        path_row.grid(row=1, column=0, sticky="ew", pady=(SPACING_SM, SPACING_MD))
        path_row.columnconfigure(0, weight=1)

        path_entry = ttk.Entry(
            path_row, textvariable=self._db_path_var, style="App.TEntry", font=Fonts.mono
        )
        path_entry.grid(row=0, column=0, sticky="ew", padx=(0, SPACING_SM))

        browse_btn = make_secondary_button(path_row, "Wybierz plik", self._browse)
        browse_btn.grid(row=0, column=1)

        pass_label = ttk.Label(card, text="Haslo bazy danych", style="BodyOnCard.TLabel")
        pass_label.grid(row=2, column=0, sticky="w")

        pass_entry = ttk.Entry(
            card, textvariable=self._passphrase_var, show="•", style="App.TEntry"
        )
        pass_entry.grid(row=3, column=0, sticky="ew", pady=(SPACING_SM, SPACING_MD))
        pass_entry.bind("<Return>", lambda e: self._submit())

        self._submit_btn = make_primary_button(card, "Otworz baze", self._submit)
        self._submit_btn.grid(row=4, column=0, sticky="ew")

        self._busy_label = ttk.Label(
            card, text="Odszyfrowuje baze...", style="MutedOnCard.TLabel"
        )

        note = ttk.Label(
            self,
            text=(
                "Haslo trafia wylacznie do pamieci RAM tego procesu i jest przekazywane\n"
                "do sqlcipher przez stdin. Aplikacja nie tworzy zadnych plikow ani wpisow\n"
                "konfiguracyjnych na dysku."
            ),
            style="Muted.TLabel",
            justify="left",
        )
        note.grid(row=3, column=0, sticky="w", pady=(SPACING_LG, 0))

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Wybierz plik bazy SimpleX",
            filetypes=[("Baza SimpleX", "*.db"), ("Wszystkie pliki", "*.*")],
        )
        if path:
            self._db_path_var.set(path)

    def _submit(self) -> None:
        db_path = self._db_path_var.get().strip()
        passphrase = self._passphrase_var.get()
        if not db_path:
            self._flash_error("Podaj sciezke do pliku bazy.")
            return
        if not passphrase:
            self._flash_error("Podaj haslo bazy.")
            return
        self.on_submit(db_path, passphrase)

    def _flash_error(self, message: str) -> None:
        # Prosty komunikat inline zamiast osobnego modulu alertow,
        # zeby nie mnozyc zaleznosci - patrz app.py po obsluge bledow po otwarciu.
        top = tk.Toplevel(self)
        top.configure(bg=Palette.BLACK)
        top.title("Blad")
        label = ttk.Label(top, text=message, style="Body.TLabel", padding=SPACING_MD)
        label.pack()
        ok_btn = make_secondary_button(top, "OK", top.destroy)
        ok_btn.pack(pady=(0, SPACING_MD))

    def clear_passphrase(self) -> None:
        self._passphrase_var.set("")

    def set_busy(self, busy: bool) -> None:
        if busy:
            self._submit_btn.state(["disabled"])
            self._busy_label.grid(row=5, column=0, pady=(SPACING_SM, 0))
        else:
            self._submit_btn.state(["!disabled"])
            self._busy_label.grid_forget()
