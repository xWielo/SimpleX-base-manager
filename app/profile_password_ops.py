"""
Operacje na hasle profilu (odkrycie / zmiana / reset ukrycia).

WAZNE ZASTRZEZENIE DOTYCZACE SCHEMATU:
Nazwa kolumny przechowujacej hash hasla profilu w tabeli 'users' nie
jest tutaj zakladana na sztywno. Rozne wersje SimpleX Chat mogly
uzywac roznych nazw kolumn dla tej funkcji (mechanizm hidden profiles
zostal wprowadzony w v4.6 i schemat mogl ewoluowac w kolejnych
migracjach). Modul samodzielnie skanuje strukture tabeli 'users' i
szuka kolumn, ktorych nazwa wskazuje na hasło/hash (np. zawierajacych
"pwd", "pass", "hash"), a nastepnie prosi o potwierdzenie w GUI
zanim wykona jakikolwiek zapis.

Nie zgadujemy tez samego algorytmu hashowania (czy to bcrypt, scrypt,
czy cos autorskiego) - jesli nie da sie tego jednoznacznie ustalic z
zawartosci kolumny, operacja zmiany/resetu hasla jest blokowana, a
uzytkownik dostaje czytelny komunikat zamiast cichej, potencjalnie
uszkadzajacej baze modyfikacji.
"""

from __future__ import annotations

from dataclasses import dataclass

from .db_engine import SqlCipherSession, DbEngineError


PASSWORD_LIKE_HINTS = ("pwd", "pass", "hash", "secret")


@dataclass
class PasswordColumnCandidate:
    column_name: str
    sample_nonempty: bool


class ProfilePasswordOps:
    def __init__(self, session: SqlCipherSession):
        self.session = session

    def find_password_like_columns(self) -> list[PasswordColumnCandidate]:
        """
        Skanuje kolumny tabeli users i zwraca te, ktorych nazwa sugeruje
        przechowywanie hasla/hasha. Nie zaklada ktora to jest - to
        uzytkownik/GUI decyduje po zobaczeniu listy.
        """
        info = self.session.query("PRAGMA table_info(users);")
        candidates: list[PasswordColumnCandidate] = []

        for row in info.rows:
            col_name = row[1]
            lowered = col_name.lower()
            if any(hint in lowered for hint in PASSWORD_LIKE_HINTS):
                has_data = self._column_has_nonempty_values(col_name)
                candidates.append(
                    PasswordColumnCandidate(column_name=col_name, sample_nonempty=has_data)
                )
        return candidates

    def _column_has_nonempty_values(self, column: str) -> bool:
        try:
            res = self.session.query(
                f"SELECT count(*) FROM users WHERE {column} IS NOT NULL AND {column} != '';"
            )
            return bool(res.rows and res.rows[0][0])
        except DbEngineError:
            return False

    def clear_profile_password(self, user_id: str, column: str) -> None:
        """
        'Odkrywa' profil w bazie trzymanej w pamieci - czysci kolumne
        hasla, robiac profil widocznym bez podawania hasla. To NIE
        zapisuje jeszcze niczego na dysk - do tego sluzy osobne wywolanie
        session.flush_to_disk(), wykonywane wylacznie po jawnym
        potwierdzeniu w GUI.
        """
        self._assert_column_exists(column)
        sql = f"UPDATE users SET {column} = NULL WHERE user_id = ?;"
        self.session.execute_write(sql, (user_id,))

    def _assert_column_exists(self, column: str) -> None:
        info = self.session.query("PRAGMA table_info(users);")
        names = {row[1] for row in info.rows}
        if column not in names:
            raise DbEngineError(f"Kolumna '{column}' nie istnieje w tabeli users.")


NOTE_ON_SET_PASSWORD = (
    "Ustawienie nowego hasla profilu (a nie tylko jego usuniecie) wymaga "
    "znajomosci dokladnego algorytmu hashowania uzywanego przez SimpleX "
    "Chat dla danej wersji bazy. To narzedzie tego nie zaklada - obsluguje "
    "wylacznie bezpieczne 'odkrycie' profilu przez wyczyszczenie pola hasla "
    "(profil staje sie widoczny bez hasla, tak jak zwykly profil jawny). "
    "Docelowe haslo najlepiej ustawic potem normalnie w samej aplikacji "
    "SimpleX Chat, ktora zna wlasciwy algorytm."
)
