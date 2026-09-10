"""
Silnik dostepu do bazy SimpleX Chat - w calosci w czystym Pythonie.

Zamiast wywolywac zewnetrzna binarke sqlcipher, ten modul:
  1. czyta zaszyfrowany plik .db z dysku (tylko odczyt pliku zrodlowego)
  2. deszyfruje kazda strone w pamieci przy pomocy app.sqlcipher_codec
  3. sklada plaintext SQLite i laduje go do sqlite3 w trybie :memory:
     przez Connection.deserialize (Python 3.11+) - od tego momentu
     wszystkie zapytania SQL ida przez standardowa biblioteke sqlite3,
     operujac wylacznie na pamieci procesu
  4. przy zapisie: Connection.serialize() daje plaintext z powrotem,
     kazda strona jest szyfrowana od nowa i caly plik zapisywany na
     dysk w miejscu oryginalnego pliku (po potwierdzeniu w GUI)

Zadny plaintext nigdy nie trafia na dysk - ani jako plik tymczasowy,
ani jako baza posrednia. Jedyny zapis na dysk to koncowy, ponownie
zaszyfrowany plik, i tylko gdy uzytkownik jawnie wykona operacje
zapisu.
"""

from __future__ import annotations

import sqlite3
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .sqlcipher_codec import (
    derive_keys,
    decrypt_page,
    encrypt_page,
    DerivedKeys,
    SqlCipherFormatError,
    DEFAULT_PAGE_SIZE,
    SALT_SIZE,
)


class DbEngineError(Exception):
    """Blad odczytu/zapisu bazy lub bledne haslo."""


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]


class SqlCipherSession:
    """
    Sesja pracy na jednym pliku bazy SQLCipher, w calosci w pamieci.

    Otwarcie (open()) odszyfrowuje caly plik do sqlite3 :memory:.
    Zapytania odczytu ida bezposrednio na to polaczenie. Operacje
    zapisu modyfikuja to samo polaczenie w pamieci, a flush_to_disk()
    dopiero wtedy szyfruje aktualny stan z powrotem i nadpisuje plik
    zrodlowy - do tego momentu plik na dysku pozostaje nietkniety.
    """

    def __init__(self, db_path: str, passphrase: str):
        self.db_path = str(Path(db_path).expanduser())
        self.passphrase = passphrase
        self._keys: DerivedKeys | None = None
        self._conn: sqlite3.Connection | None = None
        self._page_size = DEFAULT_PAGE_SIZE

    def open(self) -> None:
        """
        Odczytuje i deszyfruje caly plik do plaintextu w pamieci (praca
        czysto obliczeniowa - KDF + AES, bez dotykania sqlite3), po czym
        laduje ten plaintext do polaczenia sqlite3 w trybie :memory:.

        WAZNE dla wywolujacych z GUI: modul sqlite3 wiaze polaczenie z
        watkiem, w ktorym zostalo utworzone (check_same_thread=True domyslnie),
        i zglasza blad przy uzyciu z innego watku. Jesli open() jest wolany
        z watku roboczego (np. zeby nie blokowac GUI podczas deszyfrowania),
        nalezy zamiast tego uzyc decrypt_to_plaintext() w watku roboczym,
        a nastepnie load_plaintext() w watku glownym - patrz uzycie w
        app/application.py.
        """
        plaintext = self.decrypt_to_plaintext()
        self.load_plaintext(plaintext)

    def decrypt_to_plaintext(self) -> bytes:
        """
        Czysto obliczeniowa czesc otwierania bazy: czyta plik, wyprowadza
        klucze, deszyfruje wszystkie strony. Nie tworzy zadnego obiektu
        sqlite3, wiec bezpiecznie mozna to wywolac z dowolnego watku.
        Zwraca gotowy plaintext SQLite gotowy do zaladowania przez
        load_plaintext() - koniecznie w watku, w ktorym docelowo beda
        wykonywane zapytania.
        """
        try:
            # Najpierw spróbuj otworzyć jako ZIP (niezależnie od rozszerzenia)
            raw = self._try_extract_db_from_zip(self.db_path)
            if raw is None:
                # Jeśli to nie ZIP, otwórz jako zwykły plik .db
                with open(self.db_path, "rb") as f:
                    raw = f.read()
        except OSError as exc:
            raise DbEngineError(f"Nie mozna otworzyc pliku bazy: {exc}") from exc

        if len(raw) < SALT_SIZE:
            raise DbEngineError("Plik jest za maly, zeby byc baza SQLCipher.")

        salt = raw[:SALT_SIZE]
        keys = derive_keys(self.passphrase, salt)

        page_size = self._detect_page_size(raw, keys)
        if len(raw) % page_size != 0:
            raise DbEngineError(
                "Rozmiar pliku nie jest wielokrotnoscia rozmiaru strony - "
                "plik moze byc uszkodzony lub obciety."
            )

        page_count = len(raw) // page_size
        plaintext_parts = []
        try:
            for i in range(page_count):
                page_no = i + 1
                raw_page = raw[i * page_size:(i + 1) * page_size]
                plaintext_parts.append(decrypt_page(raw_page, keys, page_no, page_size=page_size))
        except SqlCipherFormatError as exc:
            raise DbEngineError(f"Bledne haslo bazy lub uszkodzony plik: {exc}") from exc

        self._keys = keys
        self._page_size = page_size
        return b"".join(plaintext_parts)

    def load_plaintext(self, plaintext: bytes) -> None:
        """
        Tworzy polaczenie sqlite3 :memory: i laduje do niego plaintext
        wyprodukowany przez decrypt_to_plaintext(). Musi byc wywolane w
        tym samym watku, w ktorym pozniej beda wykonywane zapytania
        (query/execute_write) - to ograniczenie modulu sqlite3, nie
        tego kodu.
        """
        if self._keys is None:
            raise DbEngineError(
                "Brak wyprowadzonych kluczy - wywolaj decrypt_to_plaintext() najpierw."
            )
        conn = sqlite3.connect(":memory:")
        try:
            conn.deserialize(plaintext)
        except sqlite3.Error as exc:
            raise DbEngineError(
                f"Haslo bylo poprawne kryptograficznie, ale sqlite3 nie rozpoznaje "
                f"wynikowej struktury jako bazy danych: {exc}"
            ) from exc
        self._conn = conn

    def _try_extract_db_from_zip(self, zip_path: str) -> bytes | None:
        """
        Spróbuj rozpakować plik .db z archiwum .zip bez zapisywania na dysk.
        Preferuje simplex_v1_chat.db (główna baza aplikacji), ale akceptuje
        dowolny .db plik. Wszystko dzieje się w pamięci.
        Zwraca None jeśli plik nie jest archiwum ZIP.
        """
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                db_files = [f for f in zf.namelist() if f.lower().endswith('.db')]
                if not db_files:
                    return None

                # Preferuj simplex_v1_chat.db (główna baza aplikacji)
                for f in db_files:
                    if 'simplex_v1_chat' in f.lower():
                        return zf.read(f)

                # Jeśli nie ma, weź pierwszy .db
                return zf.read(db_files[0])
        except (zipfile.BadZipFile, OSError):
            # Nie ZIP - zwróć None i spróbuj zwykły plik
            return None

    def _detect_page_size(self, raw: bytes, keys: DerivedKeys) -> int:
        """
        Probuje domyslny rozmiar strony SQLCipher 4 (4096). Jesli HMAC
        pierwszej strony przy tym rozmiarze sie nie zgadza, probuje
        typowych alternatyw (starsze bazy / niestandardowa konfiguracja)
        zanim odda kontrole do pelnego bledu w open().
        """
        candidates = [4096, 1024, 2048, 8192, 16384]
        for size in candidates:
            if len(raw) < size:
                continue
            try:
                decrypt_page(raw[:size], keys, page_no=1, page_size=size)
                return size
            except SqlCipherFormatError:
                continue
        return DEFAULT_PAGE_SIZE

    def _require_open(self) -> sqlite3.Connection:
        if self._conn is None:
            raise DbEngineError("Sesja nie jest otwarta - wywolaj open() najpierw.")
        return self._conn

    def verify_passphrase(self) -> bool:
        conn = self._require_open()
        try:
            conn.execute("SELECT count(*) FROM sqlite_master;").fetchone()
            return True
        except sqlite3.Error:
            return False

    def query(self, sql: str, params: tuple = ()) -> QueryResult:
        conn = self._require_open()
        try:
            cur = conn.execute(sql, params)
            columns = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
            return QueryResult(columns=columns, rows=rows)
        except sqlite3.Error as exc:
            raise DbEngineError(f"Blad zapytania SQL: {exc}") from exc

    def execute_write(self, sql: str, params: tuple = ()) -> None:
        """
        Modyfikuje baze w pamieci. Nie zapisuje na dysk - do tego
        sluzy osobne, jawne wywolanie flush_to_disk().
        """
        conn = self._require_open()
        try:
            conn.execute(sql, params)
            conn.commit()
        except sqlite3.Error as exc:
            raise DbEngineError(f"Blad zapisu SQL: {exc}") from exc

    def flush_to_disk(self) -> None:
        """
        Serializuje biezacy stan bazy z pamieci, szyfruje kazda strone
        i nadpisuje oryginalny plik na dysku. Wywolywane wylacznie po
        jawnym potwierdzeniu operacji zapisu w GUI.
        """
        conn = self._require_open()
        if self._keys is None:
            raise DbEngineError("Brak wyprowadzonych kluczy szyfrowania.")

        plaintext = conn.serialize()
        page_size = self._page_size

        if len(plaintext) % page_size != 0:
            raise DbEngineError(
                "Rozmiar zserializowanej bazy nie jest wielokrotnoscia rozmiaru "
                "strony - przerywam zapis, zeby nie uszkodzic pliku."
            )

        page_count = len(plaintext) // page_size
        encrypted_parts = []
        for i in range(page_count):
            page_no = i + 1
            plain_page = plaintext[i * page_size:(i + 1) * page_size]
            encrypted_parts.append(encrypt_page(plain_page, self._keys, page_no, page_size=page_size))

        encrypted_bytes = b"".join(encrypted_parts)

        tmp_path = self.db_path + ".tmp_write"
        try:
            with open(tmp_path, "wb") as f:
                f.write(encrypted_bytes)
            Path(tmp_path).replace(self.db_path)
        except OSError as exc:
            raise DbEngineError(f"Blad zapisu pliku na dysk: {exc}") from exc

    def list_tables(self) -> list[str]:
        res = self.query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        return [row[0] for row in res.rows]

    def close(self) -> None:
        """Zamyka polaczenie w pamieci i usuwa referencje do kluczy."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        self._keys = None
