# SimpleX Vault Reader

Lokalna, czarno-biala aplikacja GUI do przegladania wlasnej zaszyfrowanej
bazy SimpleX Chat (SQLCipher). Format SQLCipher jest zaimplementowany od
zera w czystym Pythonie - nie jest wymagana zadna zewnetrzna binarka
sqlcipher. Wszystko dzieje sie w pamieci procesu - zadna konfiguracja,
haslo ani odczytane dane nie sa zapisywane na dysku poza jawnie
zainicjowanym zapisem zmian z powrotem do pliku bazy.

## Wymagania

- Python 3.11 lub nowszy (potrzebny `sqlite3.Connection.deserialize`,
  dostepny od 3.11) z modulem `tkinter` (na Arch Linux: `pacman -S tk`,
  na Debian/Ubuntu: `apt install python3-tk`)
- pakiet pip `cryptography` - jedyna zewnetrzna zaleznosc, dostarcza
  implementacje AES (Python nie ma AES w bibliotece standardowej).
  Ma gotowe skompilowane pakiety (wheels) dla Linuksa, wiec instaluje
  sie jednym poleceniem bez kompilatora C:

  ```
  pip install cryptography --break-system-packages
  ```

  (Na systemach z zarzadzanym srodowiskiem Pythona, jak Arch, flaga
  `--break-system-packages` jest zwykle potrzebna do instalacji poza
  wirtualnym srodowiskiem. Alternatywnie mozna uzyc `python -m venv`.)

Nie jest potrzebny pakiet `sqlcipher` ani `libsqlcipher-dev` w systemie.

Opcjonalnie: font `Inter` lub `JetBrains Mono` w systemie da najlepszy
wyglad. Bez nich aplikacja automatycznie uzyje najblizszego dostepnego
fontu systemowego (Segoe UI, Liberation Sans, DejaVu Sans i tak dalej).

## Uruchomienie

```
python3 main.py
```

Po starcie poda się sciezke do pliku bazy (domyslnie w aplikacji SimpleX
Chat to `simplex_v1_chat.db`, na desktopie zwykle w `~/.simplex/`, na
telefonie w katalogu danych aplikacji) oraz haslo bazy danych (database
passphrase - nie haslo profilu ani PIN urzadzenia).

## Co aplikacja robi

- Odczytuje liste wszystkich profili w bazie, w tym oznaczonych jako
  ukryte (profile z ustawionym haslem widocznosci)
- Pokazuje liste kontaktow dla wybranego profilu
- Wyswietla wiadomosci danej rozmowy
- Pozwala wykryc, ktora kolumna w tabeli `users` przechowuje hash hasla
  profilu (schemat SimpleX zmienial sie miedzy wersjami, wiec nazwa
  kolumny nie jest zakladana na sztywno - jest wykrywana przez skan
  struktury tabeli)
- Pozwala "odkryc" profil ukryty przez wyczyszczenie pola hasla w
  kopii bazy trzymanej w pamieci, a nastepnie osobnym, jawnym
  przyciskiem zapisac ten stan z powrotem na dysk

## Jak dziala warstwa SQLCipher w czystym Pythonie

Modul `app/sqlcipher_codec.py` implementuje domyslny profil formatu
SQLCipher w wersji 4 (najnowsze wersje SimpleX Chat go uzywaja):

- sol: pierwsze 16 bajtow pliku, jawne
- klucz szyfrowania: `PBKDF2-HMAC-SHA512(haslo, sol, 256000 iteracji, 32 bajty)`
- klucz HMAC: `PBKDF2-HMAC-SHA512(klucz_szyfrowania, sol xor 0x3a, 2 iteracje, 32 bajty)`
- kazda strona pliku: AES-256-CBC z losowym IV per strona
- na koncu kazdej strony: `IV(16 bajtow) | HMAC-SHA512(64 bajty)` = 80 bajtow rezerwy
- HMAC liczony po `ciphertext || IV || numer_strony (4 bajty, little-endian)`,
  weryfikowany przed odszyfrowaniem (blad HMAC = od razu czytelny wyjatek,
  nigdy cichy zly wynik)

Wartosci tych parametrow (256000 iteracji, SHA-512, strona 4096 bajtow,
rezerwa 80 bajtow) zostaly zweryfikowane bezposrednio zapytaniami PRAGMA
(`cipher_page_size`, `kdf_iter`, `cipher_hmac_algorithm`,
`cipher_kdf_algorithm`) na realnej bazie utworzonej oficjalna binarka
sqlcipher 4.5.6, a implementacja zostala przetestowana krzyzowo w obie
strony: pliki utworzone oryginalnym sqlcipher sa poprawnie odczytywane
przez ten kod, a pliki zapisane przez ten kod sa poprawnie odczytywane
(wraz z `PRAGMA integrity_check` dajacym `ok`) przez oryginalny sqlcipher.

Po odszyfrowaniu wszystkich stron plaintext trafia do `sqlite3` w trybie
`:memory:` przez `Connection.deserialize()` - od tego momentu wszystkie
zapytania SQL ida przez standardowa biblioteke Pythona, dzialajac
wylacznie na pamieci procesu. Zapis dziala odwrotnie:
`Connection.serialize()` oddaje aktualny plaintext, kazda strona jest
szyfrowana od nowa (nowy losowy IV, przeliczony HMAC), a caly plik
podmieniany na dysku atomowo (zapis do pliku tymczasowego i
`Path.replace()`).

### Ograniczenie zwiazane z watkami

Modul `sqlite3` wiaze kazde polaczenie z watkiem, w ktorym zostalo
utworzone. Deszyfrowanie duzej bazy (glownie PBKDF2) jest wykonywane w
osobnym watku, zeby GUI sie nie zamrazalo, ale samo utworzenie
polaczenia `sqlite3` (czyli zaladowanie juz gotowego plaintextu) musi
nastapic w watku glownym - stad podzial `open()` na
`decrypt_to_plaintext()` (bezpieczne z dowolnego watku) i
`load_plaintext()` (tylko watek glowny) w `app/db_engine.py`. Widac to
w `app/application.py` w metodzie `_handle_login`.

## Czego aplikacja NIE robi

Ustawianie nowego hasla profilu (a nie tylko jego usuwanie) wymagaloby
znajomosci dokladnego algorytmu hashowania uzywanego przez konkretna
wersje SimpleX Chat do haszowania hasla profilu (to zupelnie inny
algorytm niz szyfrowanie calej bazy opisane wyzej). Zamiast zgadywac ten
algorytm i ryzykowac zapisanie hasha w formacie niekompatybilnym z sama
aplikacja SimpleX, to narzedzie ogranicza sie do bezpiecznego czyszczenia
pola hasla. Docelowe nowe haslo najlepiej ustawic potem normalnie w
samej aplikacji SimpleX Chat, ktora zna wlasciwy algorytm dla swojej
wersji.

## Dlaczego zero zapisu na dysku (poza jawnym zapisem zmian)

Sciezka do pliku bazy i haslo trafiaja wylacznie do zmiennych w pamieci
procesu Pythona. Caly plik zrodlowy jest odczytywany raz, deszyfrowany w
pamieci, i dalej dziala jako baza `sqlite3 :memory:` - zaden plik
tymczasowy ani plaintext nigdy nie trafia na dysk. Operacje typu
odkrycie profilu modyfikuja wylacznie te kopie w pamieci. Jedyny moment,
w ktorym cokolwiek trafia na dysk, to jawne kliknieicie przycisku
"Zapisz zmiany na dysk" w interfejsie, po dodatkowym potwierdzeniu w
oknie dialogowym - wtedy caly plik jest szyfrowany na nowo i podmieniany
w miejscu oryginalu.

Po kliknieciu "Zamknij baze" polaczenie sqlite3 w pamieci jest zamykane,
a referencje do wyprowadzonych kluczy i hasla usuwane z obiektu sesji.

## Struktura kodu

```
main.py                        punkt wejscia
app/
  application.py               glowna klasa spinajaca ekrany, obsluga watkow
  sqlcipher_codec.py            implementacja formatu SQLCipher (KDF, AES, HMAC)
  db_engine.py                  sesja bazy: odszyfrowanie do RAM, zapytania, zapis
  simplex_repo.py               zapytania dopasowane do schematu SimpleX
  profile_password_ops.py       operacje na polu hasla profilu
  theme.py                      paleta kolorow i dobor fontow
  gui/
    widgets.py                  wspolne stylizowane komponenty ttk
    login_view.py                ekran wyboru pliku bazy i hasla
    main_view.py                 glowny widok: profile, kontakty, wiadomosci
```

Kazdy modul ma jedna odpowiedzialnosc, zeby zmiana w jednym miejscu
(np. inny wyglad przycisku) nie wymagala dotykania logiki kryptografii,
i odwrotnie.

## Uwaga o schemacie bazy

Schemat tabel SimpleX Chat zmienial sie miedzy wersjami aplikacji.
`simplex_repo.py` probuje wykryc obecne kolumny (np. `local_display_name`
kontra starsze nazwy) i zglasza czytelny blad zamiast sie wywalic, jesli
trafi na baze z nieobslugiwanym jeszcze wariantem schematu (np. starsza
tabela `messages` zamiast `chat_items`). Jesli trafisz na taki przypadek,
`app/db_engine.py` ma metode `list_tables()` i `query()`, ktorych mozesz
uzyc bezposrednio do reczne sprawdzenia struktury swojej bazy.

Jesli trafisz na baze SQLCipher w wersji 3 (starsze konfiguracje, inny
domyslny KDF - SHA1 zamiast SHA512, mniejsza liczba iteracji), obecna
implementacja `sqlcipher_codec.py` tego nie obsluguje - jest napisana
pod domyslny profil SQLCipher 4. Rozszerzenie o profil wersji 3 wymagaloby
dodania alternatywnej sciezki w `derive_keys()` z `hashlib.pbkdf2_hmac("sha1", ...)`.

## Testowanie zmian

Modul `db_engine.py` da sie przetestowac bez GUI, bezposrednio na
dowolnym pliku SQLCipher:

```python
from app.db_engine import SqlCipherSession
from app.simplex_repo import SimplexRepo

session = SqlCipherSession("sciezka/do/bazy.db", "haslo")
session.open()
repo = SimplexRepo(session)
print(repo.list_profiles())
session.close()
```
