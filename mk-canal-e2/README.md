# MK Canal+ E2

**Pomysł i projekt: MK.** Niezależna wtyczka do kanałów CANAL+ na Enigma2,
z logowaniem kodem i aktualizacją z GitHuba. Każdy użytkownik korzysta ze
swojego abonamentu. W repozytorium nie ma danych logowania ani kluczy DRM.

![Logo MK Canal+ E2](src/CanalE2Test/logo.svg)

## Test filmów i seriali: 0.5.5

Osobny [pakiet testowy VOD 0.5.5](VOD_TEST.md) dodaje katalog, sezony, odcinki,
opisy i wyszukiwanie. Wersja 0.5.5 zachowuje parametry adresu licencji
i dodaje bezpieczny odczyt kodu odmowy HTTP. Test 0.5.4 dotarł do licencji (403);
odtwarzanie filmu nadal wymaga potwierdzenia. Wersja 0.5.4 poprawia wybór wariantów Widevine/DASH
i rozpoznawanie adresów po typie pliku. Smooth Streaming nadal wymaga osobnej
obsługi; odtwarzanie VOD nie jest jeszcze potwierdzone na dekoderze. Wersja 0.5.3 poprawia adresy manifestów z parametrami,
ujednolica nagłówki VOD i rozszerza diagnostykę błędu 503. Wersja 0.5.2 dodaje przełączanie TV przez CH+/CH− i ↑/↓
oraz diagnostykę VOD w zwykłym raporcie. Wersja 0.5.1 poprawia nagłówek HTTP powodujący błąd 403
na SF8008. Katalog sprawdzono na danych CANAL+; odtwarzanie VOD
wymaga jeszcze próby na dekoderze. Automatyczne aktualizacje nadal wskazują
wersję 0.4.0. Instrukcje i ograniczenia znajdują się w podanym dokumencie.

## Instalacja

Pobierz [MK_Canal_E2_0.4.0.ipk](packages/MK_Canal_E2_0.4.0.ipk), skopiuj do `/tmp` i wykonaj:

```sh
opkg update
opkg install /tmp/MK_Canal_E2_0.4.0.ipk
```

Zrestartuj interfejs Enigma2 i otwórz **Wtyczki → MK Canal+ E2**.
Dotychczasowe logowanie z wersji CANAL E2 zostaje zachowane.

Wersja 0.3.3 zachowuje kwadratowe proporcje znaku w standardowym menu
OpenATV (pole ikony 100×40) dzięki przezroczystym marginesom. Wewnątrz
wtyczki logo ma 128×128 zamiast 72×72. Rozmiar ikony w zewnętrznym menu
ogranicza aktywny motyw Enigmy.
Pakiet używa też aktualnych dat plików źródłowych, aby Python po aktualizacji
odświeżył pamięć podręczną i poprawnie odczytał nowy numer wersji.

| Przycisk | Działanie |
| --- | --- |
| OK | Odtwarzanie kanału |
| Zielony | Logowanie kodem na `https://connect.canalplus.com/` |
| Żółty | Odświeżenie listy kanałów |
| Niebieski | Sprawdzenie i instalacja aktualizacji |
| INFO / EPG | Aktualna i następna audycja z informacjami CANAL+ |
| EXIT | Powrót; zatrzymanie odtwarzania |

Pierwsza instalacja wymaga internetu, działających repozytoriów OpenATV
i co najmniej 120 MB wolnego miejsca na przygotowanie odtwarzacza.
Nie wymaga E2iPlayera ani Kodi. Odtwarzacz i biblioteki są przechowywane
w osobnym katalogu; systemowy `exteplayer3` nie jest podmieniany.

## EPG: Teraz / Następnie

Wersja 0.4.0 pokazuje tytuły i godziny aktualnej oraz następnej audycji
w panelu obok listy kanałów. Pasek wskazuje postęp aktualnej audycji.
INFO/EPG otwiera szczegóły i przewijanie. Podczas oglądania OK pokazuje
pasek informacyjny, a INFO/EPG otwiera szczegóły bez zatrzymywania kanału.

Źródłem są bezpośrednio metadane CANAL+ używane przez ich odtwarzacz:
`https://secure-webtv-static.canal-plus.com/metadata/cppol/all/v2.2/globalchannels.json`.
Dopasowanie odbywa się po identyfikatorze kanału, a nie po podobnej nazwie.
Pokazywany jest oryginalny podtytuł/opis, jeśli źródło go dostarcza. Test na
dekoderze potwierdził tytuły, podtytuły i czasy; dłuższych opisów w pokazanej
odpowiedzi nie było. Wtyczka nie dopisuje brakujących opisów.

Odczyt odbywa się w osobnym procesie. Pamięć podręczna w `/tmp/mk-canal-epg.json`
zawiera najwyżej dwie audycje na kanał i jest odświeżana po maksymalnie dwóch
minutach lub przy zmianie audycji. Godziny korzystają ze strefy czasowej dekodera.
Brak EPG nie blokuje odtwarzania. Nie wymaga dodatkowego konta ani komputera.

## Aktualizacje

Wersja 0.3.3 rozpoznaje poprawne statusy `opkg`, w tym `install user installed`
i `install hold,user installed`. Nadal odrzuca niewłaściwą wersję, błędy
instalatora, stan niepełnej instalacji oraz flagę `reinstreq`.

Przy przejściu z 0.3.0–0.3.2 starszy, już uruchomiony aktualizator może jeszcze
wyświetlić `installed_version_not_confirmed` po pomyślnej instalacji. Zrestartuj
interfejs Enigma2 i sprawdź numer w nagłówku wtyczki. Jeśli widnieje 0.3.3,
nowa wersja jest wczytana. Jeśli numer pozostał starszy, sprawdź wynik
`opkg status enigma2-plugin-extensions-canale2test` przed dalszą instalacją.

Niebieski przycisk odczytuje [update.json](update.json). Jeśli pojawi się
nowsza wersja, zielony przycisk w ekranie aktualizacji rozpoczyna instalację.
Weryfikowane są adres projektu HTTPS, rozmiar, SHA256, nazwa i wersja pakietu
oraz zakres instalowanych plików. Aktualizator sprawdza wynik `opkg` i proponuje
restart interfejsu. Nie instaluje samoczynnie i nie usuwa zapisanej sesji.

Publikacja kolejnej wersji:

```sh
python3 tools/build_release.py --version 0.4.1 --notes "Opis zmian dla użytkowników"
```

Następnie dodaj zmienione źródła, nowy IPK w `packages/` i `update.json`
do **jednego commita** i wyślij do gałęzi `main`. Zawsze zwiększaj wersję.
Nie nadpisuj starszego pliku IPK; pozostaw go do ewentualnego powrotu.
Nie publikuj plików z `/etc/canal-e2` ani cache dekodera.

## Stan testów i ograniczenia

Obraz i dźwięk wersji 0.1.2 zostały potwierdzone przez użytkownika na
Octagon SF8008 / OpenATV / Python 3.12. Nowe logowanie i aktualizacja mają
testy lokalne; wymagają jeszcze próby na dekoderze. Instalacji na czystym
obrazie i innych modelach nie potwierdzono. Obecny odtwarzacz jest ARMv7.
Jakość jest wybierana zgodnie z otrzymaną licencją; 1080p nie jest gwarantowane.
EPG obejmuje wyłącznie aktualną i następną audycję; nowy interfejs wymaga
jeszcze próby na dekoderze. Nie ma automatycznego odnowienia sesji ani obsługi
zmiany kluczy w trakcie długiego odtwarzania. Logowanie można ponowić zielonym przyciskiem.

## Źródła i licencja

Kod wtyczki znajduje się w `src/CanalE2Test`, licencja GPL-2.0 w
[LICENSE](src/CanalE2Test/LICENSE). Prosty znak graficzny MK ma źródło SVG
w tym samym katalogu. Publiczne zależności są pobierane w czasie uruchamiania,
nie są dołączone do IPK:

- [tools_cenc / archivczsk-doplnky](https://github.com/archivczsk/archivczsk-doplnky),
  commit `0adcaead1cc7b3688ee72627f6810a2453794fd7` — publiczna obsługa licencji.
- [exteplayer3](https://github.com/skyjet18/exteplayer3),
  commit `00aaa894db78a5c71c325d7cab1ea9ba5855024d` — odtwarzacz 183 ARMv7.
- [FFmpeg skyjet18](https://github.com/skyjet18/FFmpeg) — biblioteki pakietu odtwarzacza.

Zależności zachowują własne prawa autorskie i licencje.
