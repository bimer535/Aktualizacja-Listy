# MK Canal+ E2 — tylko TV

**Pomysł i projekt: MK.** Niezależna wtyczka Enigma2 dla Octagon SF8008 / ARMv7,
OpenATV z Pythonem 3. Każdy użytkownik korzysta z własnego abonamentu CANAL+.

![Logo MK Canal+ E2](src/CanalE2Test/logo.svg)

## Wersja 0.6.0

Baza to działający, potwierdzony przez użytkownika pakiet **0.4.0**.
Logowanie, API kanałów, licencje, natywny odtwarzacz i EPG odtworzono z tego
pakietu. Zmienione są wyłącznie sterowanie kanałami, domyślny pułap automatycznej
jakości, numer wersji i opis. Nie ma katalogu VOD ani ręcznego okna jakości.

- **CH+ lub ↑**: następny kanał, **CH− lub ↓**: poprzedni.
- Zmiana działa bez opuszczania odtwarzacza; kolejność jak na liście kanałów.
- Po końcu listy wybór wraca na jej początek. Szybkie naciśnięcia wybierają
  ostatni kanał, a procesy używające dekodera nie uruchamiają się jednocześnie.
- Jakość jest dobierana automatycznie: najwyższa rozdzielczość z manifestu,
  z zachowanym mechanizmem dopasowania do jakości objętej otrzymaną licencją.
- **OK** pokazuje/ukrywa informacje, **INFO/EPG** pokazuje Teraz/Następnie,
  **EXIT** wraca do listy kanałów.
- Na liście: **zielony** logowanie kodem, **żółty** odświeżenie,
  **niebieski** sprawdzenie aktualizacji.

Numer 0.6.0 pozwala zainstalować tę samą wtyczkę jako aktualizację po testowych
wersjach 0.5.x. Dane konta i pozostałe wtyczki pozostają na miejscu.

## Instalacja

```sh
wget -O /tmp/MK_Canal_E2_0.6.0.ipk https://raw.githubusercontent.com/bimer535/Aktualizacja-Listy/main/mk-canal-e2/packages/MK_Canal_E2_0.6.0.ipk
opkg install /tmp/MK_Canal_E2_0.6.0.ipk
```

Zrestartuj interfejs Enigma2. W menu wtyczek wybierz **MK Canal+ E2** — otwiera
się bezpośrednio lista kanałów TV. Nie trzeba usuwać danych ani innych wtyczek.

Manifest nowego pakietu jest w `tv-test.json`. Automatyczny aktualizator nadal
wskazuje potwierdzoną 0.4.0 do czasu próby nowego pakietu na dekoderze.

## Sprawdzenie

Lokalne testy obejmują zmianę kanału w obu kierunkach, koniec listy, szybkie
przełączanie, EXIT podczas zmiany, zmianę po błędzie, wybór najwyższej dostępnej
rozdzielczości i dopasowanie do przyznanej licencji. Sprawdzana jest też zgodność
niezmienionych plików z oryginalnym IPK 0.4.0 oraz poprawność i suma IPK.
Obraz, dźwięk i pilot 0.6.0 wymagają potwierdzenia na rzeczywistym dekoderze.

Przywrócenie klienta z 0.4.0 nie jest potwierdzoną naprawą zgłoszonego później
HTTP 403 z serwera logowania. Nie zmieniano w tej wersji logowania ani zapisanej
sesji i nie deklarujemy rozwiązania tej odmowy przez sam powrót do starego kodu.

## Odnowienie istniejącej sesji

Próba 0.6.0 na dekoderze nadal zakończyła się `live_initialization_failed`.
Wcześniejszy test pokazał status usługi -3, a pobieranie nowego kodu parowania
HTTP 403 także ze standardowym nagłówkiem przeglądarki. Nie uznajemy tego za
potwierdzone rozwiązanie ani nie przypisujemy kodowi -3 nieudokumentowanego znaczenia.

`tools/session_recover.py` podejmuje jedną próbę standardowego PASS createToken
z tożsamością i identyfikatorem urządzenia już zapisanymi przez użytkownika.
Nie pobiera danych z innych aplikacji. Nowy token jest najpierw sprawdzany przez
zwykłe InitLiveTV. Dopiero gdy usługa zwróci kanały z uprawnieniami, odświeżona
sesja i lista są zapisywane lokalnie. Błąd odnowienia lub sprawdzenia kanałów
zostawia poprzednią sesję bez zmian. Skuteczność wymaga próby na dekoderze.

```sh
wget -O /tmp/mk_session_recover.py https://raw.githubusercontent.com/bimer535/Aktualizacja-Listy/main/mk-canal-e2/tools/session_recover.py
python3 /tmp/mk_session_recover.py
```

Raport zawiera tylko status, liczbę kanałów i kody błędów. Tokeny, identyfikatory,
odpowiedzi konta i adresy strumieni nie są wypisywane. Nie zastępuje to logowania
nowego konta: narzędzie wymaga istniejącej, wcześniej sparowanej tożsamości.

## Bezpieczeństwo danych

Tokeny konta i odpowiedzi serwera pozostają w `/etc/canal-e2` z uprawnieniami
0600. Nie udostępniaj `session.json`, `live.json`, `client.json` ani surowych
logów natywnego odtwarzacza. W repozytorium są kod, grafiki i pakiety wtyczki.
Nie ma danych kont ani kluczy DRM. Wtyczka nie importuje Kodi lub E2iPlayera.
Nie podmienia systemowego exteplayer3 ani jego bibliotek.

## Źródła

Pakiet bazowy: `packages/MK_Canal_E2_0.4.0.ipk`, SHA256
`642062e1a43e1c720d7943da506649b3dc51093496e431208a008e95c2096e9f`.
Mapowanie CH+/CH− korzysta z NavigationActions/pageUp/pageDown OpenATV:
https://github.com/openatv/enigma2/blob/master/data/keymap.xml.
