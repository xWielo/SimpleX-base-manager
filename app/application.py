"""
Glowna klasa aplikacji - okno tk.Tk, przelaczanie miedzy ekranem
logowania a widokiem glownym. Zaden stan (haslo, sciezka, dane z
bazy) nie jest zapisywany poza zmiennymi w pamieci tego obiektu.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from .theme import Palette, Fonts
from .db_engine import SqlCipherSession, DbEngineError
from .simplex_repo import SimplexRepo
from .profile_password_ops import ProfilePasswordOps
from .gui.widgets import configure_ttk_style
from .gui.login_view import LoginView
from .gui.main_view import MainView


class Application:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SimpleX Vault Reader")
        self.root.geometry("1000x640")
        self.root.configure(bg=Palette.BG)
        self.root.minsize(820, 520)

        Fonts.init()
        configure_ttk_style(self.root)

        self.session: SqlCipherSession | None = None
        self.current_view: ttk.Frame | None = None

        self._show_login()

    def run(self) -> None:
        self.root.mainloop()

    def _show_login(self) -> None:
        self._clear_current_view()
        view = LoginView(self.root, on_submit=self._handle_login)
        view.pack(fill="both", expand=True)
        self.current_view = view

    def _handle_login(self, db_path: str, passphrase: str) -> None:
        """
        Deszyfrowanie calego pliku (KDF + AES na wszystkich stronach) jest
        praca czysto obliczeniowa i moze zajac zauwazalna chwile dla
        wiekszych baz, dlatego odbywa sie w osobnym watku, zeby okno GUI
        nie zamrozilo sie w miedzyczasie.

        Utworzenie polaczenia sqlite3 (load_plaintext) MUSI natomiast
        nastapic w watku glownym: modul sqlite3 wiaze polaczenie z
        watkiem, w ktorym powstalo, i wszystkie pozniejsze zapytania z
        GUI (wywolywane z watku glownego Tk) zawiodlyby, gdyby polaczenie
        powstalo w watku roboczym. Dlatego worker() robi tylko
        decrypt_to_plaintext() (czysto obliczeniowe, bez sqlite3), a
        samo utworzenie polaczenia dzieje sie juz po powrocie do watku
        glownego w _on_decrypted().
        """
        if isinstance(self.current_view, LoginView):
            self.current_view.set_busy(True)

        def worker():
            session = SqlCipherSession(db_path=db_path, passphrase=passphrase)
            try:
                plaintext = session.decrypt_to_plaintext()
            except DbEngineError as exc:
                self.root.after(0, lambda: self._on_login_failed(str(exc)))
                return

            self.root.after(0, lambda: self._on_decrypted(session, plaintext))

        threading.Thread(target=worker, daemon=True).start()

    def _on_decrypted(self, session: SqlCipherSession, plaintext: bytes) -> None:
        """Wykonywane w watku glownym - tu bezpiecznie tworzymy polaczenie sqlite3."""
        try:
            session.load_plaintext(plaintext)
            ok = session.verify_passphrase()
        except DbEngineError as exc:
            self._on_login_failed(str(exc))
            return

        if not ok:
            self._on_login_failed("Nie udalo sie zweryfikowac hasla bazy.")
            return

        self._on_login_succeeded(session)

    def _on_login_failed(self, message: str) -> None:
        self._show_login_error(message)

    def _on_login_succeeded(self, session: SqlCipherSession) -> None:
        self.session = session
        self._show_main_view()

    def _show_login_error(self, message: str) -> None:
        if isinstance(self.current_view, LoginView):
            self.current_view.set_busy(False)
            self.current_view._flash_error(message)
            self.current_view.clear_passphrase()

    def _show_main_view(self) -> None:
        self._clear_current_view()
        repo = SimplexRepo(self.session)
        pwd_ops = ProfilePasswordOps(self.session)
        view = MainView(self.root, repo=repo, pwd_ops=pwd_ops, on_lock=self._handle_lock)
        view.pack(fill="both", expand=True)
        self.current_view = view

    def _handle_lock(self) -> None:
        """
        Zamkniecie biezacej sesji: zamykamy polaczenie sqlite3 w pamieci,
        usuwamy referencje do wyprowadzonych kluczy i hasla, i wracamy
        do ekranu logowania.
        """
        if self.session is not None:
            self.session.close()
        self.session = None
        self._show_login()

    def _clear_current_view(self) -> None:
        if self.current_view is not None:
            self.current_view.destroy()
            self.current_view = None
