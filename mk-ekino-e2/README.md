# MK Ekino E2 0.2.3

Samodzielna wtyczka Enigma2 z Pythonem 3 dla Octagon SF8008 / OpenATV.
Nie wymaga E2iPlayera, jego prywatnego loadera ani modułów PE2I.
Pakiet i katalog instalacji są niezależne od MK Canal+ E2.

## Zmiany 0.2.3

- HLS jest rozpoznawany po treści #EXTM3U także wtedy, gdy hosting nie podaje
  rozszerzenia .m3u8 ani poprawnego Content-Type. Adresy zasobów w takiej
  playliście są przepisywane na lokalny przekaźnik.
- Lokalne adresy playlist audio/wideo mają rozszerzenie .m3u8. Nie przekazujemy
  nagłówka Range dla znanych playlist, aby nie pobierać ich w urwanych częściach.
- Fragmenty MPEG-TS i MP4 mają prawidłowy typ MIME również przy błędnym typie
  text/css lub image/* zwracanym przez CDN. Czytanie danych używa read1,
  gdy jest dostępne, zamiast czekać na zapełnienie całego bloku 64 KiB.
- Względne adresy wariantów i audio są liczone od adresu playlisty po
  przekierowaniu HTTP. Błąd po rozpoczęciu transmisji nie dopisuje strony HTML
  do fragmentu filmu.
- /tmp/mk_ekino_report.json jest odświeżany podczas odtwarzania. Zawiera
  selected_variant i relay: liczbę żądań, playlist, przesłanych bajtów,
  błędów oraz ostatni HTTP status i typ treści. Nie zapisuje adresów strumieni,
  tokenów ani cookies. RELAY_READY nadal nie oznacza potwierdzenia obrazu.

Sprawdzenie: 89 testów lokalnych, w tym prawdziwe żądania HTTP do przekaźnika
z playlistą bez rozszerzenia, segmentami o błędnym MIME i błędem upstream 403.
Nie potwierdzono obrazu na fizycznym dekoderze; wydanie wymaga próby odbiornika.

## Zmiany 0.2.2

- **Żółty: Lista / kafelki** zamiast odświeżania. W liście otwiera kafelki,
  w kafelkach wraca do listy, zachowując zaznaczoną pozycję. Ustawienie jest
  zapisywane. W menu kategorii żółty ustawia preferencję kolejnej listy filmów.
- Stała podpowiedź **MENU: opcje, ulubione i kontakt**, widoczna także po zmianie
  tekstu statusu. Kafelki mają dodatkową podpowiedź o żółtym i MENU.
- MENU w kafelkach otwiera opcje wybranej pozycji. Zamknięcie opcji lub ekranu
  kontaktu/licencji wraca do kafelków. Odświeżanie listy przeniesiono do MENU.
- Napisy pozostawiono poza tym wydaniem zgodnie z decyzją użytkownika.

Sprawdzenie lokalne: testy GUI, funkcji oglądania i warstw skinu; dodatkowo cykl
żółty → kafelki → żółty → lista z zachowaniem pozycji, MENU z kafelków i powrót
po anulowaniu oraz usunięcie ostatniej pozycji z ulubionych bez podwójnego okna.

## Zmiany 0.2.1

- MENU → **Autor i kontakt**: „Projekt i rozwój wtyczki: MK”, adres
  **bimer55@wp.pl**, wskazówki do zgłoszenia błędu i kod QR otwierający e-mail.
  Kod jest statycznym PNG 264×264, bez pobierania z Internetu. Ponowne generowanie:
  zainstaluj qrcode/Pillow w środowisku budowania i uruchom tools/build_contact_qr.py.
  Biblioteki generatora nie są potrzebne na dekoderze.
- Podczas filmu **OK przełącza pauzę i odtwarzanie**. Obsługa ma priorytet nad
  natywnym unPauseService/toggleShow i wykonuje jedno przełączenie po puszczeniu
  przycisku. Używa natywnego stanu odtwarzacza, więc współpracuje także z osobnym
  przyciskiem PAUSE. Przy pauzie pokazuje pasek odtwarzania.
- INFO nadal otwiera licencję. Informacje o źródłach i autorach kodu GPL zachowano.

Sprawdzono mapowanie make/break OK zgodne z openatv/enigma2 26c24da,
data/keymap.xml oraz InfoBarSeek w InfoBarGenerics.py. Testy obejmują pełne dwa
naciśnięcia OK, przełączenie z pauzy ustawionej innym klawiszem i zamknięcie ekranu
kontaktu podczas dekodowania QR. Obsługa na rzeczywistym pilocie wymaga testu
po instalacji.

## Zmiany 0.2.0

- **Kontynuuj oglądanie** w menu głównym. Pozycja filmu/odcinka zapisywana co
  15 sekund i przy zamknięciu; ponowne otwarcie proponuje wznowienie. Wpisy są
  powiązane z trwałym adresem katalogu, a nie zmieniającym się adresem strumienia.
  Odtwarzacz czeka na możliwość przewijania i potwierdza zmianę pozycji.
  Strumienie bez obsługi seek mogą wymagać odtwarzania od początku.
- **Ulubione** w menu głównym. Na filmie, serialu lub odcinku: MENU → dodaj/usuń
  z ulubionych. Zapis lokalny, bez logowania.
- **Następny odcinek**: po naturalnym zakończeniu odcinka pytanie o uruchomienie
  kolejnego; przechodzi także do następnego sezonu. Podczas odcinka niebieski
  wywołuje tę samą propozycję. Krótkie przerwanie transmisji nie jest uznawane
  za obejrzenie całego odcinka. Na listach obejrzane pozycje oznacza ✓.
- **Domyślny automat**: otwarcie filmu wybiera najpierw player (potem VOE/MIX,
  gdy brak playera), polską ścieżkę i największą dostępną rozdzielczość, następnie
  najwyższy bitrate. Gdy serwer nie opisuje języka, nie zakładamy polskiego audio.
  Wielościeżkowe MP4 dostają dodatkową próbę wyboru polskiego audio w odtwarzaczu.
  Automat nie przełącza sam źródła po błędzie; można wybrać inne z listy.
  MENU → Automat wyłącza automat i przywraca ręczny wybór źródła/jakości.
- **Opcjonalne kafelki**: MENU → Widok. Cztery duże okładki 200×300 z tytułem
  i oceną; ←/→ wybiera pozycję, ↑/↓ lub CH−/CH+ zmienia stronę kafelków,
  OK otwiera, MENU wraca do listy, EXIT do poprzedniej kategorii.
  Maksymalnie dwa pobrania okładek równolegle, w osobnym procesie.
- Widoczne źródła ograniczono do player, VOE i MIX zgodnie z preferencją użytkownika.

Dane są zapisywane w /etc/mk-ekino-e2/library.json (0600). Limit: 100 ulubionych
oraz 200 ostatnich pozycji odtwarzania. Aktualizacja ich nie usuwa. INFO nadal
pokazuje informacje i licencję; niebieski w przeglądarce aktualizuje wtyczkę.
Domyślny widok to lista; włączone kafelki i tryb automatu są zapamiętywane.

Weryfikacja: testy lokalne obejmują trwały zapis, wznowienie i API seek w jednostkach
90 kHz, wybór języka/jakości, EOF i kolejny sezon, oczekiwanie na zamknięcie
starego procesu odtwarzania oraz cykl życia kafelków i pobierania okładek.
API odtwarzacza porównano z openatv/enigma2 26c24da, InfoBar.py i InfoBarGenerics.py.
Nowe funkcje wymagają jeszcze sprawdzenia na rzeczywistym SF8008; testy lokalne
nie potwierdzają obsługi przewijania przez każdy serwer wideo.

## Zmiany 0.1.9

Ukryto Upzone i Wrzucaj na listach źródeł filmów oraz odcinków seriali na prośbę
użytkownika, który potwierdził brak działania także w oryginalnej wtyczce.
Pozostałe źródła, ich kolejność i numeracja odnośników pozostają bez zmian.
Filtrowanie odbywa się przed utworzeniem pozycji menu; kod resolverów zachowano
w archiwum. Narzędzie source_probe pomija dostawców ukrytych na liście źródeł.

## Zmiany 0.1.8

- Dodano próbną obsługę Upzone: przejście ze strony pliku do /embed/,
  odczyt zakodowanego adresu i przekazanie MP4 lub wariantów HLS do dotychczasowego
  odtwarzacza. Wysyłane są nagłówki User-Agent, Referer i Origin odtwarzacza.
- Odczyt adresu działa w Pythonie bez E2iPlayera, zewnętrznego silnika JS i bez
  wykonywania skryptów pobranych ze strony. Zgodność z publicznym dekoderem
  upzonecc.byte sprawdzono w Duktape 2.7 dla wszystkich 256 wartości bajtów
  i czterech przykładowych adresów. Referencje i wektory są w katalogu reference.
- Osobne komunikaty dla blokady dostępu, wyczerpanego darmowego transferu lub
  wymaganego premium oraz nierozpoznanego odtwarzacza. Obsługa nie omija blokady
  ani ograniczenia transferu; nie dodano logowania do konta premium Upzone.
- source_probe.py przyjmuje teraz --providers upzone i nadal sprawdza rzeczywiste
  bajty wideo. Lokalny test sieciowy zatrzymał się na HTTP 403 na stronie Ekino.
  Odtwarzanie Upzone na dekoderze pozostaje niepotwierdzone.
- Użytkownik potwierdził obraz i dźwięk z VOE, MIX oraz player w 0.1.7 na SF8008.

## Zmiany 0.1.7

- Naprawiono TypeError w VOE podczas pobierania manifestu HLS. Metadane adresu
  zawierały listę napisów external_sub_tracks, przekazywaną omyłkowo jako nagłówek
  HTTP. Teraz zapytanie zawiera tylko tekstowe User-Agent, Referer, Origin i Accept;
  informacje o napisach pozostają w metadanych wariantów odtwarzania.
- Test regresji odtwarza ten błąd prawdziwym serializerem nagłówków Python 3.12,
  zarówno dla pustej, jak i niepustej listy napisów. Sprawdza pobranie wariantów
  HLS i zachowanie napisów oraz nagłówków Referer/Origin po poprawce.
- Test użytkownika na SF8008 potwierdził MEDIA_REACHABLE dla MIX (MixDrop) przy
  filmie „Król dopalaczy”: odczytano bajty wideo z serwera. Nie potwierdza to jeszcze
  obrazu i dźwięku w MoviePlayer. MIX można już wybrać na liście źródeł.
- W tym samym teście wrzucaj zwróciło HTTP 521, a shvid nie zwróciło wariantów.
  Obsługa tych przypadków nie została potwierdzona. VOE po poprawce wymaga testu
  na dekoderze. Upzone nadal nie jest obsługiwane.

## Zmiany 0.1.6

- Nowa własna ikona MK Ekino: duże białe MK, turkusowy symbol odtwarzania,
  ciemne tło i niewielkie marginesy. Prawdziwy kolor RGB PNG 256×256, skalowany
  proporcjonalnie z kwadratowego projektu 1254×1254. Zastępuje poprzednią ikonę
  Ekino z odbiciem i dużym pustym obszarem. Rozmiar pola ikony w menu nadal
  zależy od aktywnego skinu OpenATV; nie modyfikujemy globalnego menu wtyczek.
- Okładka w panelu szczegółów powiększona z 136×204 do 200×300 — ponad dwa razy
  większa powierzchnia (2,16×). Panel szczegółów poszerzono, a listę dostosowano
  do pozostałego miejsca. Zachowane proporcje 2:3 i skalowanie do rzeczywistego
  rozmiaru widgetu w aktualnej rozdzielczości.
- Zachowane jawne warstwy 0/1/2 z poprawki 0.1.5. Katalog, źródła i odtwarzanie
  nie otrzymały zmian funkcjonalnych w tym wydaniu.

Nowy znak przygotowano narzędziem generowania obrazów OpenAI. Opis projektu
znajduje się w reference/icon_design.txt. Pełne grafiki mogą być pomniejszane
przez skin; większa rozdzielczość pliku nie wymusza większego pola w menu.

## Zmiany 0.1.5

Naprawiono nakładanie paneli tła na menu i teksty w 0.1.4. Zgłoszony zrzut ekranu
pokazywał licznik 1/5, czyli wczytane menu, ale jego nazwy i nagłówek pozostawały
zasłonięte. OpenATV tworzy elementy additionalWidgets (eLabel) po komponentach
GUIComponent, niezależnie od kolejności zapisanej w skinie. Przy tej samej warstwie
później utworzone tło przykrywało listę i etykiety. Ustawiono jawne warstwy: tła 0,
lista i teksty 1, okładka 2. Pobieranie katalogu i odtwarzanie pozostają bez zmian.

Dodano test układu odtwarzający zasłonięcie w 0.1.4 i sprawdzający, że wszystkie
przecinające się elementy tła pozostają poniżej nazwanych widgetów w 0.1.5.
Na 0.1.4 przyciski w stopce były widoczne, więc aktualizację można otworzyć
niebieskim przyciskiem. Zainstaluj 0.1.5 i uruchom ponownie interfejs Enigma2.

## Zmiany 0.1.4

- Nowy ciemny układ z akcentem turkusowym, czytelniejszą listą, panelem oceny,
  opisu i okładki. Licznik wskazuje zaznaczoną pozycję. Wszystko działa natywnie
  w Enigmie; bez przeglądarki i dodatkowego środowiska odtwarzania.
- Miniatury Ekino pobierane są dopiero po zatrzymaniu zaznaczenia na pozycji,
  w osobnym procesie. Pamięć podręczna w /tmp przechowuje do 64 plików po 256 KiB.
  Brak lub błąd okładki nie blokuje katalogu ani filmu.
- Każda nowa lista rozpoczyna się od pierwszej pozycji. Powrót EXIT przywraca
  zaznaczenie w poprzedniej liście.
- Osobne odnośniki tego samego dostawcy nie są już pomijane; kolejne mają numer.
  Identyfikatory sesji nie są zapisywane, a wybrany odnośnik odtwarzamy po świeżym
  pobraniu strony filmu.
- Poprawiono odczyt spakowanych ciągów JS MixDrop z cytatami oraz zakłóceń VOE,
  zwykłych adresów HLS i nagłówków końcowej domeny. Rozpakowywanie nie wykonuje JS.
- Dodano próbny parser SST/HTML5/Playerjs dla wrzucaj i shvid. Nie jest to gwarancja
  obsługi wszystkich ich odtwarzaczy. Upzone nadal nie jest obsługiwane.

**Stan podczas wydania 0.1.4 (zaktualizowany powyżej w 0.1.7):** podczas sprawdzenia normalnych odnośników Ekino dla
VOE, MixDrop, wrzucaj i shvid serwer zwrócił HTTP 403 / Cloudflare, zanim możliwe
było otwarcie ich odtwarzaczy. Nie potwierdzamy odtwarzania tych źródeł na żywo.
Poprawki parserów sprawdzono na kontrolowanych odpowiedziach. Wtyczka wyświetla
teraz czytelną przyczynę odmowy, zamiast sugerować, że brak jest wariantów filmu.
Działanie może różnić się pomiędzy źródłami, tytułami i połączeniami użytkowników.
W raporcie /tmp/mk_ekino_report.json jest też nazwa wybranego dostawcy.

Nowy wygląd wymaga sprawdzenia na rzeczywistym SF8008. Testy obejmują API okien
OpenATV 7.4, granice elementów skinu, wybór pozycji, obsługę EXIT oraz cykl pobrania
okładki, zmianę zaznaczenia i zamknięcie okna podczas pracy w tle. Biblioteka ARM
przyspieszająca player pozostaje identyczna jak w działającej 0.1.2/0.1.3.

## Zmiany 0.1.3

- EXIT kończy film i wraca do listy Ekino jednym naciśnięciem, również przy widocznym
  pasku odtwarzacza. Obsługa działa przy zwolnieniu przycisku, aby to samo naciśnięcie
  nie cofnęło dodatkowo listy Ekino. STOP nadal działa. Nie zmieniamy globalnych ustawień.
- Niebieski przycisk: sprawdzanie i instalacja aktualizacji z GitHuba. INFO/MENU:
  informacje i licencja. Aktualizacje są sprawdzane tylko na żądanie.
- Oceny Ekino w skali do 10 przy tytułach; liczba głosów w opisie zaznaczonego filmu.
  Brak głosów jest pokazywany jako „brak ocen”. Dane pochodzą z tej samej strony co
  lista, bez dodatkowych zapytań dla każdego filmu. Oceny są aktualizowane po odświeżeniu listy.

## Aktualizacje z pilota

Po pierwszej ręcznej instalacji 0.1.3 kolejne wydania można pobierać niebieskim
przyciskiem. Wtyczka pokazuje wersję i opis zmian, prosi o zgodę na instalację,
pobiera IPK i sprawdza rozmiar, SHA-256, nazwę pakietu oraz wersję. Instaluje przez
opkg i potwierdza wynik w bazie pakietów. Po instalacji proponuje restart interfejsu,
który użytkownik może odłożyć. Podczas instalacji EXIT nie przerywa opkg.
Sprawdzanie i instalacja odbywają się w osobnym procesie.

Manifest: https://raw.githubusercontent.com/bimer535/Aktualizacja-Listy/main/mk-ekino-e2/update.json
Pakiety: https://github.com/bimer535/Aktualizacja-Listy/tree/main/mk-ekino-e2/packages
Źródła każdego wydania są udostępnione w sąsiednim archiwum `_source.zip`.

Autor aktualizacji buduje nowe wydanie z większym numerem wersji przez
`python3 tools/build_ipk.py`. Publikuje IPK i źródła w `mk-ekino-e2/packages/`
oraz wygenerowany `dist/update.json` jako `mk-ekino-e2/update.json` w repozytorium.
Pakiety ze starym numerem wersji pozostają niezmienione. Manifest generuje się
z rzeczywistego pliku IPK, co zapobiega rozbieżności wersji i sumy kontrolnej.

## Zachowane zmiany 0.1.2

- Pierwsza weryfikacja źródła player: opcjonalny moduł ARMv7 wykonuje obliczenia
  zamiast pętli Pythona. Wynik algorytmu pozostaje taki sam. Inne architektury
  i brak zgodnego modułu uruchamiają dotychczasową wersję w Pythonie.
- Weryfikacja przyznana przez źródło jest zachowywana pomiędzy filmami do terminu
  ważności podanego przez serwer, najwyżej 29 minut po odjęciu marginesu. Odmowa
  ponownego użycia powoduje świeżą weryfikację. Nie przedłużamy ważności tokenu.
- STOP i zakończenie filmu zamykają MoviePlayer i wracają do Ekino, zamiast otwierać
  listę nagrań HDD. Użyto `fromMovieSelection=False`; globalne ustawienia nagrań
  pozostają ustawieniami użytkownika.
- Dodano resolvery publicznych źródeł VOE i MixDrop oraz przekazywanie MP4 z obsługą
  zakresów bajtowych. Upzone nadal pokazuje komunikat o braku obsługi.
- Raport zawiera czasy zapytań i obliczeń, co pozwala odróżnić lokalne czekanie od sieci.

## Funkcje

Filmy według kategorii, języka i roku; seriale, sezony i odcinki; wyszukiwanie;
lokalna historia; wybór źródła, języka i jakości z manifestu. Zielony: wyszukaj,
żółty: lista/kafelki, niebieski: aktualizacja. MENU: opcje i odświeżanie. INFO/MENU: informacje i licencja. Odtwarzanie przez MoviePlayer.
Nie jest wymagane logowanie do Ekino. Dostępność źródeł zależy od serwisu.

## Instalacja

W wersji 0.1.3 lub nowszej wybierz niebieski → OK → zainstaluj 0.2.2, a następnie
zrestartuj interfejs Enigma2. Ręcznie: przenieś `MK_Ekino_E2_0.2.2.ipk` do `/tmp` dekodera:

```sh
opkg install /tmp/MK_Ekino_E2_0.2.2.ipk
```

Zrestartuj interfejs Enigma2, otwórz MK Ekino E2 i sprawdź ten sam film ze źródła
player. Sprawdź EXIT podczas filmu, oceny na liście oraz niebieski przycisk aktualizacji.
Pakiet wymaga Python 3, PyCryptodome oraz ctypes. Nie instaluje E2iPlayera.

## Stan sprawdzenia

Użytkownik potwierdził rzeczywiste odtwarzanie filmu z player w 0.1.1 oraz sprawne
odtwarzanie i wyraźne przyspieszenie weryfikacji w 0.1.2 na SF8008.
W 0.1.2 zgodność modułu C z publicznym algorytmem Pythona sprawdzono na wektorach
hasha i wyszukiwaniu wyniku. Zbudowaną bibliotekę ARM sprawdzono w emulatorze ARM.
Lokalny pomiar na komputerze potwierdza przyspieszenie samych obliczeń; nie jest
pomiarem SF8008 ani pełnego czasu otwierania filmu. Nie mamy liczbowego pomiaru porównawczego prywatnego E2i. Sieć i serwer nadal mogą wydłużać pierwszą weryfikację.

Użytkownik potwierdził działanie VOE, MIX i player w 0.1.7 na SF8008.
Użytkownik potwierdził brak poprawnych linków Upzone i brak działania Wrzucaj
także w oryginalnej wtyczce. Oba źródła ukryto w 0.1.9. Nowe oceny porównano z bieżącym HTML Ekino. Testy lokalne obejmują cykl
aktualizacji i błędy sumy kontrolnej, wersji oraz instalatora, obsługę EXIT, odrzucenie starej
weryfikacji, zakresy MP4, HLS, wybraną ścieżkę audio, anulowanie oraz API okien
OpenATV 7.4. Nie zastępują testu nowego pakietu na urządzeniu.

Zachowano poprawki 0.1.1: metoda związana z ekranem w onLayoutFinish, bez kolizji
z dict.items(), odłączanie callbacków przed usunięciem stanu ekranu przez OpenATV.

## Test dodatkowych źródeł na dekoderze

Jeżeli player działa, a inne źródła nie, jednorazowy test można wykonać bez
instalowania nowej wersji wtyczki:

```sh
wget -O /tmp/mk_ekino_source_probe.py https://raw.githubusercontent.com/bimer535/Aktualizacja-Listy/main/mk-ekino-e2/tools/source_probe.py
python3 /tmp/mk_ekino_source_probe.py
```

Test używa zainstalowanych modułów MK Ekino, wyszukuje przykładowy tytuł i bada
widoczne źródła VOE oraz MixDrop (pozostali dostawcy testu są pomijani). Raport `/tmp/mk_ekino_sources_report.json`
zawiera etapy HTTP, nazwy hostów i rozpoznane formaty strony. Nie zapisuje
pełnych adresów źródeł, cookies, kluczy ani kont. Nie zmienia konfiguracji.
Po znalezieniu wariantu wykonuje ograniczony odczyt do 2048 bajtów z serwera
wideo. `MEDIA_REACHABLE` potwierdza dostęp do bajtów wideo; nie jest potwierdzeniem
obrazu i dźwięku w natywnym odtwarzaczu. `BLOCKED` oznacza odmowę na danym etapie.

## Dane i diagnostyka

Historia: `/etc/mk-ekino-e2/history.json`. Krótka weryfikacja źródła:
`/tmp/mk-ekino-access.json`, uprawnienia 0600, plik usuwany przy restarcie dekodera.
Nie udostępniaj tego pliku. Adresy strumieni pozostają w pamięci procesu.
Proces odtwarzania kończy się po zamknięciu filmu. Przekaźnik nasłuchuje wyłącznie
na 127.0.0.1 pod losowym adresem i zachowuje wybraną ścieżkę audio/wideo.

Raport `/tmp/mk_ekino_report.json` zawiera etapy, statusy HTTP i czasy, bez pełnych
adresów strumieni, cookies i odpowiedzi API. `source_metrics.verification.engine`
wskazuje `native_armv7` albo `python`, gdy wykonywano obliczenia. Pusty obiekt
weryfikacji może oznaczać użycie ważnego wyniku z pamięci podręcznej.

## Źródła i licencja

GPL-3.0, pełna treść w `src/MKEkinoE2/LICENSE`. Metody parserBYSE, parserVOESX,
parserMIXDROP, parserSST oraz przepływ Upzone pochodzą z publicznej paczki e2iplayer-2026.10.18.05.zip.
Zachowano komentarze i podziękowania. parserBYSE ma dodatkowo opcjonalny moduł
obliczeniowy, pomiary czasu oraz odnowienie odrzuconej weryfikacji.
Oryginalny przepływ Upzone: `reference/public_upzone_method.txt`; wektory
dekodera: `reference/upzone_vectors.json`. Przeniesiono dekoder do Pythona.
Metadane pochodzenia: `reference/SOURCE.json`. Pozostałe części to klient i adaptery MK.
Nie użyto kodu prywatnego PE2I. Runtime kompilatora w module ARM: licencja MIT,
pełny tekst w `src/MKEkinoE2/THIRD_PARTY.txt`.

Archiwum `_source.zip` zawiera źródła C, Pythona, testy, bibliotekę i skrypty budowania.
Zbudowanie biblioteki: zainstaluj `ziglang==0.14.1` w środowisku budowania,
następnie `python3 tools/build_native.py`. Kompilator nie jest potrzebny na dekoderze.
Pakiet: `python3 tools/build_ipk.py`. Testy: `python3 -m unittest discover -s tests -v`
(wymagają gcc oraz PyCryptodome). Sprawdzenie ARM: `python3 tools/check_arm_pow.py`
(wymaga pyelftools i unicorn). Biblioteka jest freestanding, bez zależności od libc.
