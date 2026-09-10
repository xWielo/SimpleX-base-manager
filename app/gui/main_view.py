"""
Glowny widok po otwarciu bazy: lista profili po lewej, kontakty i
wiadomosci po prawej, panel operacji na hasle profilu na dole.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..theme import Palette, Fonts, SPACING_SM, SPACING_MD, SPACING_LG
from ..simplex_repo import SimplexRepo, Profile, Contact, SchemaError
from ..profile_password_ops import ProfilePasswordOps, NOTE_ON_SET_PASSWORD
from ..db_engine import DbEngineError
from .widgets import make_primary_button, make_secondary_button, make_danger_button, Card, StatusBar


class MainView(ttk.Frame):
    def __init__(self, parent, repo: SimplexRepo, pwd_ops: ProfilePasswordOps, on_lock):
        super().__init__(parent, style="App.TFrame")
        self.repo = repo
        self.pwd_ops = pwd_ops
        self.on_lock = on_lock

        self.profiles: list[Profile] = []
        self.contacts: list[Contact] = []
        self.selected_profile: Profile | None = None
        self.selected_contact: Contact | None = None

        self._build()
        self._load_profiles()

    def _build(self) -> None:
        self.columnconfigure(0, weight=0, minsize=260)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, style="Panel.TFrame", padding=(SPACING_MD, SPACING_SM))
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        title = ttk.Label(header, text="SimpleX Vault Reader", style="Subheading.TLabel",
                           background=Palette.BG_PANEL)
        title.pack(side="left")
        lock_btn = make_secondary_button(header, "Zamknij baze", self._lock)
        lock_btn.pack(side="right")

        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=2, column=0, columnspan=2, sticky="ew")

        self._build_profile_panel()
        self._build_content_panel()

    def _build_profile_panel(self) -> None:
        panel = ttk.Frame(self, style="Panel.TFrame", padding=SPACING_MD)
        panel.grid(row=1, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)

        label = ttk.Label(panel, text="Profile", style="BodyOnPanel.TLabel", font=Fonts.body_bold)
        label.grid(row=0, column=0, sticky="w", pady=(0, SPACING_SM))

        self.profile_list = tk.Listbox(
            panel,
            bg=Palette.BG_CARD,
            fg=Palette.TEXT_PRIMARY,
            selectbackground=Palette.DARK_GRAY,
            selectforeground=Palette.PURE_WHITE,
            font=Fonts.body,
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
        )
        self.profile_list.grid(row=1, column=0, sticky="nsew")
        self.profile_list.bind("<<ListboxSelect>>", self._on_profile_select)

        self.profile_ops_card = Card(panel)
        self.profile_ops_card.grid(row=2, column=0, sticky="ew", pady=(SPACING_MD, 0))
        self._build_profile_ops(self.profile_ops_card)

    def _build_profile_ops(self, card: ttk.Frame) -> None:
        card.columnconfigure(0, weight=1)

        heading = ttk.Label(card, text="Operacje na profilu", style="BodyOnCard.TLabel",
                             font=Fonts.body_bold)
        heading.grid(row=0, column=0, sticky="w", pady=(0, SPACING_SM))

        self.profile_ops_status = ttk.Label(
            card, text="Wybierz profil z listy powyzej.",
            style="MutedOnCard.TLabel", wraplength=220, justify="left"
        )
        self.profile_ops_status.grid(row=1, column=0, sticky="w", pady=(0, SPACING_SM))

        scan_btn = make_secondary_button(card, "Wykryj pole hasla", self._scan_password_columns)
        scan_btn.grid(row=2, column=0, sticky="ew", pady=(0, SPACING_SM))

        self.reveal_btn = make_danger_button(card, "Odkryj profil (usun haslo)", self._reveal_profile)
        self.reveal_btn.grid(row=3, column=0, sticky="ew", pady=(0, SPACING_SM))
        self.reveal_btn.state(["disabled"])

        self.save_to_disk_btn = make_danger_button(card, "Zapisz zmiany na dysk", self._save_to_disk)
        self.save_to_disk_btn.grid(row=4, column=0, sticky="ew")
        self.save_to_disk_btn.state(["disabled"])

        self._password_candidates = []
        self.pending_write = False

    def _build_content_panel(self) -> None:
        content = ttk.Frame(self, style="App.TFrame", padding=SPACING_MD)
        content.grid(row=1, column=1, sticky="nsew")
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        contacts_frame = ttk.Frame(content, style="App.TFrame")
        contacts_frame.grid(row=0, column=0, sticky="ns", padx=(0, SPACING_MD))
        contacts_frame.rowconfigure(1, weight=1)

        c_label = ttk.Label(contacts_frame, text="Kontakty", style="Body.TLabel", font=Fonts.body_bold)
        c_label.grid(row=0, column=0, sticky="w", pady=(0, SPACING_SM))

        self.contact_list = tk.Listbox(
            contacts_frame,
            width=28,
            bg=Palette.BG_CARD,
            fg=Palette.TEXT_PRIMARY,
            selectbackground=Palette.DARK_GRAY,
            selectforeground=Palette.PURE_WHITE,
            font=Fonts.body,
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
        )
        self.contact_list.grid(row=1, column=0, sticky="ns")
        self.contact_list.bind("<<ListboxSelect>>", self._on_contact_select)

        messages_frame = ttk.Frame(content, style="App.TFrame")
        messages_frame.grid(row=0, column=1, sticky="nsew")
        messages_frame.columnconfigure(0, weight=1)
        messages_frame.rowconfigure(1, weight=1)

        m_label = ttk.Label(messages_frame, text="Wiadomosci", style="Body.TLabel", font=Fonts.body_bold)
        m_label.grid(row=0, column=0, sticky="w", pady=(0, SPACING_SM))

        self.messages_text = tk.Text(
            messages_frame,
            bg=Palette.BG_CARD,
            fg=Palette.TEXT_PRIMARY,
            font=Fonts.body,
            borderwidth=0,
            highlightthickness=0,
            wrap="word",
            state="disabled",
            padx=SPACING_MD,
            pady=SPACING_MD,
        )
        self.messages_text.grid(row=1, column=0, sticky="nsew")
        self.messages_text.tag_configure("from_us", foreground=Palette.TEXT_PRIMARY,
                                          font=Fonts.body_bold)
        self.messages_text.tag_configure("from_them", foreground=Palette.TEXT_SECONDARY)
        self.messages_text.tag_configure("meta", foreground=Palette.TEXT_MUTED, font=Fonts.small)

    def _load_profiles(self) -> None:
        try:
            self.profiles = self.repo.list_profiles()
        except (SchemaError, DbEngineError) as exc:
            self.status_bar.set_text(str(exc), is_error=True)
            self.profiles = []

        self.profile_list.delete(0, tk.END)
        for profile in self.profiles:
            marker = "[ukryty] " if profile.hidden else ""
            display = f"{marker}{profile.display_name}"
            self.profile_list.insert(tk.END, display)

        if not self.profiles:
            self.status_bar.set_text("Nie znaleziono zadnych profili w tej bazie.", is_error=True)
        else:
            self.status_bar.set_text(f"Wczytano {len(self.profiles)} profil(i).")

    def _on_profile_select(self, event) -> None:
        selection = self.profile_list.curselection()
        if not selection:
            return
        self.selected_profile = self.profiles[selection[0]]
        self.reveal_btn.state(["disabled"])
        self.profile_ops_status.configure(
            text=f"Wybrano: {self.selected_profile.display_name}. Kliknij 'Wykryj pole hasla'."
        )
        self._load_contacts()

    def _load_contacts(self) -> None:
        if not self.selected_profile:
            return
        try:
            self.contacts = self.repo.list_contacts(self.selected_profile.user_id)
        except (SchemaError, DbEngineError) as exc:
            self.status_bar.set_text(str(exc), is_error=True)
            self.contacts = []

        self.contact_list.delete(0, tk.END)
        for contact in self.contacts:
            self.contact_list.insert(tk.END, contact.local_display_name)

        self._clear_messages()

    def _on_contact_select(self, event) -> None:
        selection = self.contact_list.curselection()
        if not selection:
            return
        self.selected_contact = self.contacts[selection[0]]
        self._load_messages()

    def _load_messages(self) -> None:
        if not self.selected_contact:
            return
        try:
            messages = self.repo.list_messages(self.selected_contact.contact_id)
        except (SchemaError, DbEngineError) as exc:
            self.status_bar.set_text(str(exc), is_error=True)
            messages = []

        self.messages_text.configure(state="normal")
        self.messages_text.delete("1.0", tk.END)
        for msg in messages:
            who = "Ty" if msg.from_us else self.selected_contact.local_display_name
            tag = "from_us" if msg.from_us else "from_them"
            self.messages_text.insert(tk.END, f"{who}  ", ("meta",))
            self.messages_text.insert(tk.END, f"{msg.created_at}\n", ("meta",))
            self.messages_text.insert(tk.END, f"{msg.body}\n\n", (tag,))
        self.messages_text.configure(state="disabled")

        if not messages:
            self.status_bar.set_text("Brak wiadomosci lub nieobslugiwany schemat dla tego kontaktu.")

    def _clear_messages(self) -> None:
        self.messages_text.configure(state="normal")
        self.messages_text.delete("1.0", tk.END)
        self.messages_text.configure(state="disabled")

    def _scan_password_columns(self) -> None:
        try:
            candidates = self.pwd_ops.find_password_like_columns()
        except DbEngineError as exc:
            self.status_bar.set_text(str(exc), is_error=True)
            return

        self._password_candidates = candidates
        if not candidates:
            self.profile_ops_status.configure(
                text="Nie znaleziono kolumny przypominajacej pole hasla w tabeli users."
            )
            self.reveal_btn.state(["disabled"])
            return

        names = ", ".join(c.column_name for c in candidates)
        self.profile_ops_status.configure(
            text=f"Znalezione kolumny: {names}. Uzyta zostanie pierwsza z danymi."
        )
        self.reveal_btn.state(["!disabled"])

    def _reveal_profile(self) -> None:
        """
        Krok 1 z 2: czysci pole hasla wylacznie w kopii bazy trzymanej
        w pamieci (RAM). Plik na dysku pozostaje na razie nietkniety -
        do jego nadpisania sluzy osobny przycisk 'Zapisz zmiany na dysk',
        zeby modyfikacja w pamieci i nieodwracalny zapis na dysk byly
        dwoma oddzielnymi, swiadomymi decyzjami.
        """
        if not self.selected_profile or not self._password_candidates:
            return

        target_column = None
        for candidate in self._password_candidates:
            if candidate.sample_nonempty:
                target_column = candidate.column_name
                break
        if target_column is None:
            target_column = self._password_candidates[0].column_name

        confirmed = self._confirm_dialog(
            "Potwierdz operacje",
            f"To wyczysci pole '{target_column}' dla profilu "
            f"'{self.selected_profile.display_name}' w kopii bazy trzymanej "
            f"w pamieci (RAM). Plik na dysku NIE zostanie jeszcze zmieniony.\n\n"
            f"Profil stanie sie widoczny bez hasla.\n\n{NOTE_ON_SET_PASSWORD}\n\n"
            "Kontynuowac?"
        )
        if not confirmed:
            return

        try:
            self.pwd_ops.clear_profile_password(self.selected_profile.user_id, target_column)
        except DbEngineError as exc:
            self.status_bar.set_text(f"Blad podczas zapisu w pamieci: {exc}", is_error=True)
            return

        self.pending_write = True
        self.save_to_disk_btn.state(["!disabled"])
        self.status_bar.set_text(
            f"Profil '{self.selected_profile.display_name}' odkryty w pamieci. "
            "Kliknij 'Zapisz zmiany na dysk', zeby utrwalic zmiane w pliku."
        )
        self._load_profiles()

    def _save_to_disk(self) -> None:
        confirmed = self._confirm_dialog(
            "Zapisz na dysk",
            "To nadpisze oryginalny plik bazy na dysku aktualnym stanem z "
            "pamieci (wlacznie z wprowadzonymi zmianami). Upewnij sie, ze "
            "masz kopie zapasowa pliku przed kontynuacja.\n\n"
            "Kontynuowac zapis?"
        )
        if not confirmed:
            return

        try:
            self.repo.session.flush_to_disk()
        except DbEngineError as exc:
            self.status_bar.set_text(f"Blad zapisu na dysk: {exc}", is_error=True)
            return

        self.pending_write = False
        self.save_to_disk_btn.state(["disabled"])
        self.status_bar.set_text("Zmiany zapisane na dysku.")

    def _confirm_dialog(self, title: str, message: str) -> bool:
        result = {"ok": False}
        top = tk.Toplevel(self)
        top.configure(bg=Palette.BLACK)
        top.title(title)
        top.grab_set()

        label = ttk.Label(top, text=message, style="Body.TLabel", wraplength=420,
                           justify="left", padding=SPACING_MD)
        label.pack()

        btn_row = ttk.Frame(top, style="App.TFrame", padding=SPACING_MD)
        btn_row.pack()

        def confirm():
            result["ok"] = True
            top.destroy()

        make_danger_button(btn_row, "Tak, wykonaj", confirm).pack(side="left", padx=SPACING_SM)
        make_secondary_button(btn_row, "Anuluj", top.destroy).pack(side="left")

        top.wait_window()
        return result["ok"]

    def _lock(self) -> None:
        if self.pending_write:
            confirmed = self._confirm_dialog(
                "Niezapisane zmiany",
                "Masz zmiany w pamieci, ktore nie zostaly zapisane na dysk. "
                "Zamkniecie bazy teraz je odrzuci.\n\nZamknac mimo to?"
            )
            if not confirmed:
                return
        self.on_lock()
