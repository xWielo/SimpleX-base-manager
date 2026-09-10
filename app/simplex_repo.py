"""
Warstwa zapytan dopasowana do schematu bazy simplex_v1_chat.db.

Nazwy tabel/kolumn w SimpleX Chat zmienialy sie miedzy wersjami
(migracje w simplexmq), dlatego kazda metoda najpierw sprawdza czy
oczekiwane kolumny istnieja i w razie braku zglasza czytelny blad
zamiast wywalac wyjatek SQL. To nie jest pelny ORM - to najmniejszy
zestaw zapytan potrzebny do podgladu profili, kontaktow i wiadomosci.
"""

from __future__ import annotations

from dataclasses import dataclass

from .db_engine import SqlCipherSession, DbEngineError


@dataclass
class Profile:
    user_id: str
    display_name: str
    full_name: str
    hidden: bool
    active: bool


@dataclass
class Contact:
    contact_id: str
    local_display_name: str
    profile_display_name: str


@dataclass
class Message:
    msg_id: str
    chat_msg_id: str
    body: str
    created_at: str
    from_us: bool


class SchemaError(Exception):
    pass


class SimplexRepo:
    def __init__(self, session: SqlCipherSession):
        self.session = session
        self._columns_cache: dict[str, set[str]] = {}

    def _table_columns(self, table: str) -> set[str]:
        if table in self._columns_cache:
            return self._columns_cache[table]
        res = self.session.query(f"PRAGMA table_info({table});")
        cols = {row[1] for row in res.rows}
        self._columns_cache[table] = cols
        return cols

    def _require_table(self, table: str) -> None:
        tables = self.session.list_tables()
        if table not in tables:
            raise SchemaError(
                f"Nie znaleziono tabeli '{table}' w tej bazie. "
                "Prawdopodobnie to nie jest baza simplex_v1_chat.db "
                "albo schemat pochodzi z innej wersji aplikacji."
            )

    def list_profiles(self) -> list[Profile]:
        self._require_table("users")
        cols = self._table_columns("users")

        if not cols:
            raise SchemaError(
                "Tabela 'users' istnieje, ale nie zawiera żadnych kolumn. "
                "Baza może być uszkodzona."
            )

        name_col = "local_display_name" if "local_display_name" in cols else "displayName"
        if name_col not in cols and "displayName" not in cols:
            raise SchemaError(
                f"Nie znaleziono kolumny nazwy użytkownika. "
                f"Dostępne kolumny: {', '.join(sorted(cols))}"
            )

        hidden_col = "view_pwd_hash" if "view_pwd_hash" in cols else None
        active_col = "active_user" if "active_user" in cols else None

        select_cols = ["user_id", name_col]
        if "full_name" in cols:
            select_cols.append("full_name")
        else:
            select_cols.append(f"'' as full_name")
        select_cols.append(f"{hidden_col} as hidden" if hidden_col else "NULL as hidden")
        select_cols.append(f"{active_col} as active" if active_col else "0 as active")

        sql = f"SELECT {', '.join(select_cols)} FROM users ORDER BY user_id;"
        res = self.session.query(sql)

        if not res.rows:
            raise SchemaError(
                "Tabela 'users' istnieje i ma prawidłową strukturę, "
                "ale nie zawiera żadnych wierszy (żadnych profili). "
                "Sprawdź, czy hasło bazy danych jest poprawne."
            )

        profiles = []
        for row in res.rows:
            user_id, display_name, full_name, hidden_val, active_val = row
            profiles.append(
                Profile(
                    user_id=user_id,
                    display_name=display_name,
                    full_name=full_name or "",
                    hidden=self._is_truthy_flag(hidden_val),
                    active=self._is_truthy_flag(active_val),
                )
            )
        return profiles

    @staticmethod
    def _is_truthy_flag(value) -> bool:
        """
        Kolumny flagowe w schemacie SimpleX bywaja TEXT ('0'/'1') albo
        INTEGER (0/1) zaleznie od wersji/tabeli. bool() samego stringa
        zawsze daje True dla niepustego '0', wiec porownujemy wartosc
        wprost zamiast polegac na Pythonowej "prawdziwosci" typu.
        """
        if value is None:
            return False
        if isinstance(value, str):
            return value not in ("", "0", "NULL", "false", "False")
        return bool(value)

    def list_contacts(self, user_id: str) -> list[Contact]:
        self._require_table("contacts")
        cols = self._table_columns("contacts")
        name_col = "local_display_name" if "local_display_name" in cols else "displayName"

        sql = (
            f"SELECT contact_id, {name_col} "
            f"FROM contacts WHERE user_id = ? "
            f"ORDER BY {name_col} COLLATE NOCASE;"
        )
        res = self.session.query(sql, (user_id,))
        return [
            Contact(contact_id=row[0], local_display_name=row[1], profile_display_name=row[1])
            for row in res.rows
        ]

    def list_messages(self, contact_id: str, limit: int = 200) -> list[Message]:
        """
        Wiadomosci w SimpleX sa powiazane przez chat_items / messages w
        zaleznosci od wersji schematu. Probujemy najpierw chat_items,
        bo to aktualna tabela przechowujaca tresc widoczna w UI.
        """
        tables = self.session.list_tables()
        if "chat_items" in tables:
            return self._list_messages_chat_items(contact_id, limit)
        if "messages" in tables:
            return self._list_messages_legacy(contact_id, limit)
        raise SchemaError("Nie znaleziono tabeli chat_items ani messages w bazie.")

    def _list_messages_chat_items(self, contact_id: str, limit: int) -> list[Message]:
        cols = self._table_columns("chat_items")
        body_col = "item_text" if "item_text" in cols else "text"
        dir_col = "item_sent" if "item_sent" in cols else "sent"

        sql = (
            f"SELECT chat_item_id, {body_col}, created_at, {dir_col} "
            f"FROM chat_items WHERE contact_id = ? "
            f"ORDER BY created_at DESC LIMIT ?;"
        )
        res = self.session.query(sql, (contact_id, int(limit)))
        out = []
        for row in res.rows:
            item_id, body, created_at, sent = row
            out.append(
                Message(
                    msg_id=item_id,
                    chat_msg_id=item_id,
                    body=body,
                    created_at=created_at,
                    from_us=self._is_truthy_flag(sent),
                )
            )
        return list(reversed(out))

    def _list_messages_legacy(self, contact_id: str, limit: int) -> list[Message]:
        raise SchemaError(
            "Ta baza uzywa starszego schematu wiadomosci (tabela messages), "
            "ktory nie jest jeszcze obslugiwany w tym narzedziu."
        )
