"""
Implementacja formatu SQLCipher w czystym Pythonie - bez zewnetrznej
binarki sqlcipher. Obsluguje domyslny profil SQLCipher w wersji 4:

  - sol: pierwsze 16 bajtow pliku, jawne (nieszyfrowane)
  - klucz szyfrowania: PBKDF2-HMAC-SHA512(haslo, sol, 256000, 32)
  - klucz HMAC: PBKDF2-HMAC-SHA512(klucz_szyfrowania, sol xor 0x3a, 2, 32)
  - kazda strona: AES-256-CBC, IV losowy per-strona
  - rezerwa na koncu kazdej strony: IV(16) | HMAC-SHA512(64) = 80 bajtow
  - HMAC liczony po: ciphertext || IV || numer_strony (4 bajty, little-endian)
  - rozmiar strony domyslnie 4096 bajtow

Zrodlo specyfikacji: oficjalna dokumentacja projektu SQLCipher (Zetetic,
"SQLCipher Design") oraz kod zrodlowy sqlcipher.c z repozytorium
sqlcipher/sqlcipher. Wartosci parametrow (256000 iteracji, SHA-512,
strona 4096B, rezerwa 80B) zweryfikowane w tym projekcie bezposrednio
zapytaniami PRAGMA na realnej bazie utworzonej binarka sqlcipher 4.5.6.

Strona pierwsza pliku ma szczegolna budowe: pierwsze 16 bajtow to jawna
sol (nie wchodzi w szyfrowanie), a odszyfrowany plaintext tej strony
zaczyna sie od standardowego naglowka SQLite "SQLite format 3\\x00" -
ten naglowek jest doklejany rekonstrukcyjnie, bo w oryginalnym pliku
jego miejsce zajmuje sol.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import struct
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

SQLITE_HEADER = b"SQLite format 3\x00"
SALT_SIZE = 16
KEY_SIZE = 32
IV_SIZE = 16
HMAC_DIGEST_SIZE = 64  # SHA-512
RESERVE_SIZE = IV_SIZE + HMAC_DIGEST_SIZE  # 80 bajtow
DEFAULT_PAGE_SIZE = 4096
DEFAULT_KDF_ITER = 256000
HMAC_KDF_ITER = 2


class SqlCipherFormatError(Exception):
    """Zle haslo, uszkodzony plik, lub nieobslugiwany wariant formatu."""


@dataclass
class DerivedKeys:
    salt: bytes
    enc_key: bytes
    hmac_key: bytes


def derive_keys(passphrase: str, salt: bytes, kdf_iter: int = DEFAULT_KDF_ITER) -> DerivedKeys:
    passphrase_bytes = passphrase.encode("utf-8")

    enc_key = hashlib.pbkdf2_hmac("sha512", passphrase_bytes, salt, kdf_iter, dklen=KEY_SIZE)

    hmac_salt = bytes(b ^ 0x3A for b in salt)
    hmac_key = hashlib.pbkdf2_hmac("sha512", enc_key, hmac_salt, HMAC_KDF_ITER, dklen=KEY_SIZE)

    return DerivedKeys(salt=salt, enc_key=enc_key, hmac_key=hmac_key)


def _page_hmac(hmac_key: bytes, ciphertext_and_iv: bytes, page_no: int) -> bytes:
    mac = hmac.new(hmac_key, digestmod=hashlib.sha512)
    mac.update(ciphertext_and_iv)
    mac.update(struct.pack("<I", page_no))
    return mac.digest()


def decrypt_page(
    raw_page: bytes,
    keys: DerivedKeys,
    page_no: int,
    page_size: int = DEFAULT_PAGE_SIZE,
    reserve: int = RESERVE_SIZE,
) -> bytes:
    """
    Odszyfrowuje jedna strone (page_no liczone od 1, jak w SQLite).
    Zwraca plaintext strony o dlugosci page_size (z wypelniona reszta
    po odjeciu reserve - to jest wlasciwy plaintext SQLite, reserve
    to obszar ktory SQLite i tak traktuje jako "poza uzytkowymi
    danymi strony" ale musi zostac na miejscu w pliku wynikowym, zeby
    dalsze parsowanie SQLite dzialalo tak jak w oryginale).
    """
    if len(raw_page) != page_size:
        raise SqlCipherFormatError(
            f"Nieprawidlowy rozmiar strony {page_no}: {len(raw_page)} vs oczekiwane {page_size}."
        )

    usable = page_size - reserve
    if page_no == 1:
        # Pierwsze SALT_SIZE bajtow to jawna sol, nie wchodzi w szyfrowanie.
        body_start = SALT_SIZE
    else:
        body_start = 0

    ciphertext = raw_page[body_start:usable]
    trailer = raw_page[usable:page_size]
    iv = trailer[:IV_SIZE]
    stored_hmac = trailer[IV_SIZE:IV_SIZE + HMAC_DIGEST_SIZE]

    expected_hmac = _page_hmac(keys.hmac_key, ciphertext + iv, page_no)
    if not hmac.compare_digest(expected_hmac, stored_hmac):
        raise SqlCipherFormatError(
            f"HMAC strony {page_no} nie zgadza sie - bledne haslo lub uszkodzony plik."
        )

    cipher = Cipher(algorithms.AES(keys.enc_key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    plaintext_body = decryptor.update(ciphertext) + decryptor.finalize()

    if page_no == 1:
        return SQLITE_HEADER + plaintext_body + trailer
    return plaintext_body + trailer


def encrypt_page(
    plaintext_page: bytes,
    keys: DerivedKeys,
    page_no: int,
    page_size: int = DEFAULT_PAGE_SIZE,
    reserve: int = RESERVE_SIZE,
) -> bytes:
    """
    Szyfruje jedna strone plaintextu SQLite (dlugosci page_size) z
    powrotem do formatu SQLCipher. Losuje nowy IV dla tej strony -
    zgodnie z formatem SQLCipher IV nie musi byc powiazany z
    poprzednim zapisem tej strony.
    """
    if len(plaintext_page) != page_size:
        raise SqlCipherFormatError(
            f"Nieprawidlowy rozmiar strony {page_no} do zapisu: "
            f"{len(plaintext_page)} vs oczekiwane {page_size}."
        )

    usable = page_size - reserve
    if page_no == 1:
        body = plaintext_page[SALT_SIZE:usable]
    else:
        body = plaintext_page[0:usable]

    iv = os.urandom(IV_SIZE)
    cipher = Cipher(algorithms.AES(keys.enc_key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(body) + encryptor.finalize()

    page_hmac = _page_hmac(keys.hmac_key, ciphertext + iv, page_no)
    trailer = iv + page_hmac

    if page_no == 1:
        return keys.salt + ciphertext + trailer
    return ciphertext + trailer
