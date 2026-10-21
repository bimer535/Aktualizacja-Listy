# MK Canal+ E2 0.5.2 — test VOD

Pomysł i projekt: **MK**.

Osobny pakiet testowy z katalogiem VOD. Aktualizator zwykłej wersji nadal wskazuje
0.4.0. Po potwierdzeniu filmu i odcinka na dekoderze można opublikować kolejną
wersję dla wszystkich. Nie deklarujemy jeszcze działającego odtwarzania VOD
na koncie użytkownika.

## Wersja 0.5.2: pilot i raport VOD

Podczas oglądania TV **CH+ lub ↑** przełącza na następny kanał, a **CH− lub ↓**
na poprzedni w kolejności listy. Lista zapętla się na końcach. Ekran odtwarzania
pozostaje otwarty; aktualizuje nazwę, jakość i Teraz/Następnie. EXIT kończy oglądanie.
Przy szybkich naciśnięciach wybierany jest ostatni kanał, a poprzedni proces
odtwarzacza kończy pracę przed uruchomieniem nowego. Przyciski kanałów dotyczą TV.
Mapowanie CH+/CH− korzysta z NavigationActions/pageUp/pageDown oficjalnej mapy
OpenATV: https://github.com/openatv/enigma2/blob/master/data/keymap.xml.

Próba VOD w 0.5.1 zakończyła się HTTP 403 przy `vod_playset`. W 0.5.2 również
adapter odtwarzania VOD korzysta ze standardowego nagłówka przeglądarki.
Nie potwierdzono jeszcze, czy rozwiązuje to odmowę HAPI na dekoderze.

Dodatkowa diagnostyka błędu playsetu zapisuje się automatycznie w zwykłym
`/tmp/canal_e2_playback_report.json`, w polu `vod_http_diagnostic`. Zawiera
kod HTTP, format odpowiedzi, rozpoznane nazwy pól, numeryczne kody serwera
i znaczniki słów z komunikatu (np. wzmianka o tokenie lub urządzeniu).
Nie zapisuje treści komunikatów, tokenów konta, adresów ani odpowiedzi licencji.
Sonda `mk_canal_vod_probe.json` jest oddzielnym narzędziem i powstaje dopiero
po ręcznym uruchomieniu; do zwykłej próby filmu nie jest potrzebna.

Testy lokalne obejmują szybkie przełączanie, oba kierunki i zapętlenie listy,
anulowanie podczas przełączania, zmianę po błędzie kanału oraz zachowanie VOD,
nagłówek HTTP i bezpieczne dane błędu w raporcie. Pilot i obraz/dźwięk nowej
wersji wymagają sprawdzenia na rzeczywistym dekoderze.

## Poprawka 0.5.1

Test na SF8008 potwierdził HTTP 403 dla nagłówka User-Agent wtyczki i HTTP 200
z katalogiem dla standardowego nagłówka przeglądarki (filmy i seriale).
Ta wersja używa dokładnie nagłówka zaakceptowanego w teście. Błędy katalogu
pokazują teraz również kod HTTP. Odtwarzanie VOD wymaga osobnego potwierdzenia.

## Instalacja na dotychczasowym SF8008 / OpenATV 7.x

```sh
wget -O /tmp/MK_Canal_E2_0.5.2.ipk https://raw.githubusercontent.com/bimer535/Aktualizacja-Listy/main/mk-canal-e2/packages/MK_Canal_E2_0.5.2.ipk
opkg install /tmp/MK_Canal_E2_0.5.2.ipk
```

Zrestartuj interfejs Enigma2. Sesja CANAL+ i dane dotychczasowej wtyczki
pozostają w `/etc/canal-e2`. Nie potrzeba ponownego parowania, dopóki sesja jest
ważna. Pakiet instaluje się jako aktualizacja tej samej wtyczki.

## Menu i obsługa

- **Telewizja na żywo**: dotychczasowa lista kanałów i Teraz/Następnie.
- **Filmy, Seriale, Dokumentalne, Dzieci, Produkcje oryginalne, Kolekcje, Sport**:
  katalog i kategorie CANAL+, opisy, sezony oraz odcinki.
- **Szukaj**: wyszukiwanie tytułu w bieżącym katalogu CANAL+.
- W katalogu: OK otwiera pozycję; czerwony/EXIT wraca do poprzedniego widoku,
  zielony szuka, żółty odświeża, niebieski/INFO pokazuje opis.
- W filmie: zielony pauzuje/wznawia, lewo/prawo przewija o 30 sekund,
  OK pokazuje informacje, INFO otwiera opis, EXIT zatrzymuje i wraca.

Katalog jest publiczny; pozycja na liście nie oznacza uprawnienia do odtwarzania.
Dostęp jest sprawdzany dla zalogowanego abonamentu przy uruchomieniu materiału.
Wtyczka nie wykonuje zakupu ani wypożyczenia. Nie odtwarza materiałów z zewnętrznych
aplikacji, do których CANAL+ jedynie odsyła.

Jakość jest ograniczona do 1080p oraz do jakości przyznanej przez usługę, tak jak
w dotychczasowym odtwarzaczu. Obsługiwany jest pojedynczy okres DASH; materiał
z wieloma okresami jest odrzucany, aby nie uruchamiać tylko fragmentu filmu.
Nie dodano zapamiętywania miejsca, synchronizacji profili, napisów, zmiany języka,
ulubionych ani funkcji zakupowych z pełnej aplikacji CANAL+.

## Co zostało sprawdzone

Sprawdzono rzeczywiste publiczne odpowiedzi strony CANAL+ dla filmów, serialu,
sezonu i odcinków. Lokalnie przechodzą 51 testów: normalizacja katalogu, wybór
właściwej strony z danych SSR, nawigacja sezonów, kursory, wyszukiwanie z bieżącej
konfiguracji, błędy, anulowanie zadań i UTF-8, odrębne ścieżki TV/VOD, kontrakt
HAPI na kontrolowanych odpowiedziach oraz dotychczasowe EPG i aktualizacje.

Serwery Hodor/HAPI odmawiają dostępu z hosta deweloperskiego (HTTP 403).
Uwierzytelnione pobranie filmu, licencja VOD, wyszukiwanie i kolejne strony Hodor
oraz obraz/dźwięk, pauza i przewijanie wymagają próby na dekoderze. Testy lokalne
nie są takim potwierdzeniem. Adapter VOD wykorzystuje publicznie opisany protokół
HAPI playset/view; jego zgodność z aktualnym kontem należy dopiero potwierdzić.

## Próba na dekoderze

1. Sprawdź dotychczasowy kanał TV.
2. Wybierz film dostępny w Twoim abonamencie, potem odcinek serialu.
3. Sprawdź obraz, dźwięk, pauzę, przewinięcie i powrót do katalogu.
4. Sprawdź wyszukiwanie i przejście do kolejnej strony kategorii.

Jeżeli VOD nie ruszy, wystarczy raport:

```sh
cat /tmp/canal_e2_playback_report.json
```

Raport zawiera kod błędu i etap `vod_step`; nie zawiera tokenów konta, adresów
strumienia, odpowiedzi licencji ani kluczy DRM. Nie udostępniaj `session.json`,
`live.json` ani logów systemowego odtwarzacza.

Dodatkowa sonda tylko odczytuje strukturę playsetu (nie rozpoczyna filmu ani
licencji):

```sh
wget -O /tmp/mk_canal_vod_probe.py https://raw.githubusercontent.com/bimer535/Aktualizacja-Listy/main/mk-canal-e2/tools/vod_probe.py
python3 /tmp/mk_canal_vod_probe.py
```

Kod katalogu czyta dane `window.REACT_QUERY_STATE` oficjalnej strony, nigdy nie
wykonuje jej JavaScriptu. Obsługuje bieżące `mediaData.linkerData`, `detail`,
`selector` i `episodes`. HTTPS i certyfikaty są weryfikowane. Dane konta trafiają
wyłącznie do wskazanego serwera HAPI, a klucze i media pozostają w pamięci.

Protokół HAPI porównano z publiczną integracją GPL CanalPLUS-VOD 1.7.5.11
(autorzy: mbebe, mariusz89b, hevet). Kod nowego klienta nie importuje Kodi ani
E2iPlayera. Nazwy pól i przepływ playset/view zaimplementowano niezależnie.
Źródłem bieżącego katalogu i konfiguracji adresu HAPI jest oficjalna strona
`https://www.canalplus.com/pl/`.
