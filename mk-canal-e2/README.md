# MK Canal+ E2 — tylko TV

**Pomysł i projekt: MK.** Niezależna wtyczka Enigma2 dla Octagon SF8008 / ARMv7,
OpenATV z Pythonem 3. Każdy użytkownik korzysta z własnego abonamentu CANAL+.

![Logo MK Canal+ E2](src/CanalE2Test/logo.svg)

## Wersja 0.6.1

Baza to działający, potwierdzony przez użytkownika pakiet **0.4.0**.
API kanałów, licencje, natywny odtwarzacz i EPG zachowują kod z tego pakietu.
Dodano sterowanie kanałami, automatyczny wybór jakości oraz odnowienie istniejącej
sesji sprawdzone przez użytkownika. Nie ma katalogu VOD ani ręcznego okna jakości.

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

Numer 0.6.1 pozwala zainstalować tę samą wtyczkę jako aktualizację po testowych
wersjach 0.5.x. Dane konta i pozostałe wtyczki pozostają na miejscu.

## Instalacja

```sh
wget -O /tmp/MK_Canal_E2_0.6.1.ipk https://raw.githubusercontent.com/bimer535/Aktualizacja-Listy/main/mk-canal-e2/packages/MK_Canal_E2_0.6.1.ipk
opkg install /tmp/MK_Canal_E2_0.6.1.ipk
```

Zrestartuj interfejs Enigma2. W menu wtyczek wybierz **MK Canal+ E2** — otwiera
się bezpośrednio lista kanałów TV. Nie trzeba usuwać danych ani innych wtyczek.

Niebieski przycisk pobiera `update.json`, który udostępnia wersję 0.6.1.
Ten sam pakiet opisuje `tv-test.json`. Po instalacji zrestartuj interfejs Enigma2.

## Sprawdzenie

Lokalne testy obejmują zmianę kanału w obu kierunkach, koniec listy, szybkie
przełączanie, EXIT podczas zmiany, zmianę po błędzie, wybór najwyższej dostępnej
rozdzielczości i dopasowanie do przyznanej licencji. Sprawdzana jest też zgodność
niezmienionych plików z oryginalnym IPK 0.4.0 oraz poprawność i suma IPK.
Użytkownik potwierdził skuteczność narzędzia odnowienia istniejącej sesji.
Wersja 0.6.1 integruje ten sam mechanizm; pakiet wymaga jeszcze sprawdzenia na
rzeczywistym dekoderze. Testy obejmują też zachowanie starej sesji przy błędzie,
brak odnawiania zdrowego tokena i limit jednej próby odnowienia.

## Odnowienie istniejącej sesji

Przy odświeżaniu listy i uruchamianiu kanału klient najpierw korzysta ze zwykłego
InitLiveTV. Wyłącznie przy zaobserwowanym `live_initialization_failed` ze statusem
usługi -3 podejmuje jedną próbę PASS createToken z zapisaną tożsamością i tym
samym urządzeniem. Kodowi -3 nie przypisujemy nieudokumentowanego znaczenia.
Nowy token jest sprawdzany przez InitLiveTV. Dopiero po uzyskaniu kanałów z
uprawnieniami zapisywane są sesja i lista; odtwarzanie kontynuuje pracę na nowej
odpowiedzi. Nieudane odnowienie nie nadpisuje poprzedniej tożsamości.

To odnowienie już sparowanego konta. HTTP 403 przy pobieraniu nowego kodu
parowania pozostaje odrębnym, nierozwiązanym problemem. Nie pobieramy danych
konta z innych aplikacji. Nie ma potrzeby ręcznego uruchamiania narzędzia przy
kolejnym wystąpieniu tego samego błędu. Nie ma prób odnowienia w pętli.

Narzędzie serwisowe `tools/session_recover.py` pozostaje dostępne. Raport zawiera
tylko status, liczbę kanałów i kody błędów. Tokeny, identyfikatory, odpowiedzi
konta i adresy strumieni nie są wypisywane.

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
