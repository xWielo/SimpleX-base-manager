#!/usr/bin/env python3
"""
Punkt wejscia. Implementacja SQLCipher jest w calosci w Pythonie
(patrz app/sqlcipher_codec.py) - nie jest wymagana zadna zewnetrzna
binarka sqlcipher. Jedyna zewnetrzna zaleznosc to pakiet pip
'cryptography' (dostarcza AES - Python nie ma go w bibliotece
standardowej). Reszta korzysta wylacznie ze standardowej biblioteki
(tkinter, sqlite3, hashlib, hmac, threading).
"""

from app.application import Application


def main() -> None:
    app = Application()
    app.run()


if __name__ == "__main__":
    main()
