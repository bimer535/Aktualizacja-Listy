# MK Ekino E2 0.1.4

Samodzielna wtyczka Enigma2 z Pythonem 3 dla Octagon SF8008 / OpenATV.
Nie wymaga E2iPlayera, jego prywatnego loadera ani modułów PE2I.
Pakiet i katalog instalacji są niezależne od MK Canal+ E2.

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

**Stan dodatkowych źródeł:** podczas sprawdzenia normalnych odnośników Ekino dla
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
żółty: odśwież, niebieski: aktualizacja. INFO/MENU: informacje i licencja. Odtwarzanie przez MoviePlayer.
Nie jest wymagane logowanie do Ekino. Dostępność źródeł zależy od serwisu.

## Instalacja

Na działającej 0.1.3 wybierz niebieski → OK → zainstaluj 0.1.4, a następnie
zrestartuj interfejs Enigma2. Ręcznie: przenieś `MK_Ekino_E2_0.1.4.ipk` do `/tmp` dekodera:

```sh
opkg install /tmp/MK_Ekino_E2_0.1.4.ipk
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

VOE i MixDrop sprawdzono na kontrolowanych odpowiedziach, bez potwierdzenia
rzeczywistego odtwarzania na dekoderze. Nowe oceny porównano z bieżącym HTML Ekino. Testy lokalne obejmują cykl
aktualizacji i błędy sumy kontrolnej, wersji oraz instalatora, obsługę EXIT, odrzucenie starej
weryfikacji, zakresy MP4, HLS, wybraną ścieżkę audio, anulowanie oraz API okien
OpenATV 7.4. Nie zastępują testu nowego pakietu na urządzeniu.

Zachowano poprawki 0.1.1: metoda związana z ekranem w onLayoutFinish, bez kolizji
z dict.items(), odłączanie callbacków przed usunięciem stanu ekranu przez OpenATV.

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
parserMIXDROP i ikona pochodzą z publicznej paczki e2iplayer-2026.10.18.05.zip.
Zachowano komentarze i podziękowania. parserBYSE ma dodatkowo opcjonalny moduł
obliczeniowy, pomiary czasu oraz odnowienie odrzuconej weryfikacji.
Metadane pochodzenia: `reference/SOURCE.json`. Pozostałe części to klient i adaptery MK.
Nie użyto kodu prywatnego PE2I. Runtime kompilatora w module ARM: licencja MIT,
pełny tekst w `src/MKEkinoE2/THIRD_PARTY.txt`.

Archiwum `_source.zip` zawiera źródła C, Pythona, testy, bibliotekę i skrypty budowania.
Zbudowanie biblioteki: zainstaluj `ziglang==0.14.1` w środowisku budowania,
następnie `python3 tools/build_native.py`. Kompilator nie jest potrzebny na dekoderze.
Pakiet: `python3 tools/build_ipk.py`. Testy: `python3 -m unittest discover -s tests -v`
(wymagają gcc oraz PyCryptodome). Sprawdzenie ARM: `python3 tools/check_arm_pow.py`
(wymaga pyelftools i unicorn). Biblioteka jest freestanding, bez zależności od libc.
