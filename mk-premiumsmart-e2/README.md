# MK PremiumSmart E2 0.1.0

Samodzielna wtyczka Enigma2 / Python 3 dla Octagon SF8008 i OpenATV 7.x,
oparta na publicznym hoście premiumsmart.eu oraz interfejsie MK Ekino E2 0.2.2.
Osobny pakiet enigma2-plugin-extensions-mkpremiumsmarte2 i katalog MKPremiumSmartE2.
Nie wymaga instalacji E2iPlayera ani MK Ekino. Nie modyfikuje MK Ekino ani MK Canal+.

## Funkcje

- Filmy / seriale → wersja → rocznik → sposób sortowania → tytuły.
- Wersje według oznaczeń serwisu: Lektor PL, Lektor AI, PL, Dubbing, CAM
  oraz Wszystkie wersje. „Lektor PL” nie obejmuje „Lektor AI”. Nie zakładamy,
  że cała oferta jest z polskim lektorem.
- Dokładny rocznik jest filtrowany na serwerze przez publiczny zakres release_date.
  Sortowanie: najnowsze dodane, najnowszy rocznik, ocena, popularność.
- API kanałów nie obsługuje pola language_type (serwer zwraca błąd dla takiego
  filtra). Dlatego filmy są wybierane według wersji primary_video z opisu tytułu,
  z przeglądaniem kolejnych stron. Alternatywna wersja ukryta pod tytułem z inną
  główną wersją może wymagać listy Wszystkie wersje. Przy otwieraniu filmu
  wtyczka dodatkowo wybiera tylko źródła z wybraną wersją.
- Dla seriali wybór wersji jest preferencją źródeł odcinka, gdyż część seriali
  nie ma jednej wersji opisanej na poziomie całego tytułu. Brak wybranej wersji
  jest zgłaszany, bez automatycznej zmiany na inną.
- Sezony, odcinki, następny odcinek (również między sezonami), wyszukiwanie,
  historia, ulubione i kontynuowanie oglądania. Wznawianie zależy od obsługi seek
  przez strumień; pozycja jest zapisywana pod adresem katalogu, a nie strumienia.
- Okładki i oceny z danych serwisu. Lista i cztery duże kafelki.
- Źródła: Byse/Vidara, VOE, MixDrop, StreamTape (bez wykonywania JS) oraz
  bezpośrednie MP4/HLS lub proste HTML5. Odtwarzacze wymagające innych resolverów,
  np. niektóre warianty Abyss/FlyFile, mogą nie zwrócić wariantów. Dostępność
  zależy od serwisu, źródła i sieci. Testy lokalne nie potwierdzają obrazu na TV.

## Pilot

OK w przeglądarce: wybierz. OK w filmie: pauza / wznów. EXIT kończy film
i wraca do wtyczki. Zielony: wyszukaj. Żółty: lista / kafelki. Niebieski
w przeglądarce: aktualizacja; podczas odcinka: następny odcinek.
MENU: opcje, ulubione, odświeżanie, widok, tryb automatyczny, Autor i kontakt.
INFO: informacje i licencja. Kontakt: MK, bimer55@wp.pl, kod QR do e-maila.
Domyślny automat preferuje Lektor PL i Byse oraz najlepszą dostępną jakość.
Można go wyłączyć w MENU i wybierać źródło/jakość ręcznie.

## Instalacja

Pobierz MK_PremiumSmart_E2_0.1.0.ipk do /tmp dekodera:

```sh
opkg install /tmp/MK_PremiumSmart_E2_0.1.0.ipk
```

Uruchom ponownie interfejs Enigma2. Pakiet wymaga enigma2, Python 3, ctypes,
html i PyCryptodome, instalowanych przez zależności opkg. OpenATV 6.4 / Python 2
nie jest obsługiwany. Pakiet zawiera opcjonalną bibliotekę ARMv7; inne
architektury korzystają z implementacji Python, więc weryfikacja może być wolniejsza.

Aktualizacje: https://raw.githubusercontent.com/bimer535/Aktualizacja-Listy/main/mk-premiumsmart-e2/update.json
Dane prywatne wtyczki: /etc/mk-premiumsmart-e2/library.json oraz history.json.
Cookie anonimowej sesji PremiumSmart pozostaje w pamięci procesu. Nie są czytane
pliki kont ani cookies prywatnego E2i. Token przyznanej weryfikacji źródła jest
krótkotrwale przechowywany w /tmp/mk-premiumsmart-access.json (0600).
Nie udostępniaj tego pliku. Raporty nie zawierają pełnych adresów strumieni/cookies.

## Sprawdzenie i ograniczenia

Na żywo potwierdzono dostęp do anonimowego API, działanie roczników 2020 i 2026,
listę filmów oznaczonych Lektor PL oraz pobieranie źródeł tytułu. Próba Byse dla
jednego filmu z 2020 przeszła weryfikację serwera, ale CDN zwrócił stronę HTML
„Site Unavailable” zamiast manifestu. Dla innego filmu Byse i StreamTape nie
zwróciły wariantów. Przyczyna różnicy między sieciami nie została potwierdzona.
To pierwsze wydanie testowe: nie potwierdzono obrazu i dźwięku na rzeczywistym
SF8008. 35 testów lokalnych sprawdza katalog, filtry, interfejs i aktualizator.
Osobno udostępniono tools/probe.py, który sprawdza katalog oraz opcjonalnie
warianty i ograniczony odczyt danych wideo.
MEDIA_REACHABLE oznacza bajty wideo, nie potwierdzenie pracy natywnego odtwarzacza.

```sh
wget -O /tmp/mk_premiumsmart_probe.py https://raw.githubusercontent.com/bimer535/Aktualizacja-Listy/main/mk-premiumsmart-e2/tools/probe.py
python3 /tmp/mk_premiumsmart_probe.py --year 2020 --media
```

Szczegółowy bezpieczny raport: /tmp/mk_premiumsmart_probe.json.

## Źródła i budowanie

GPL-3.0, LICENSE w katalogu wtyczki. Oryginalny publiczny host:
reference/public_hostpremiumsmarteu.py; przepływ API i paginację przepisano
na samodzielnego klienta. Referencje publicznych parserów w reference.
Pochodzenie i sumy: reference/SOURCE.json. Interfejs, wznawianie, ulubione,
aktualizator, cache, przekaźnik oraz adaptery MK pochodzą z MK Ekino E2 0.2.2.
Biblioteka ARM jest identycznym kodem obliczeniowym z osobną nazwą; kod C dołączono.
Nie zawiera prywatnego PE2I ani jego loadera.

Budowanie: python3 tools/build_ipk.py. Testy: python3 -m unittest discover -s tests -v.
Budowanie biblioteki ARM: tools/build_native.py (Zig 0.14.1, tylko w środowisku budowania).
Runtime kompilatora: MIT, THIRD_PARTY.txt. Ikona MK i QR kontaktu wykorzystane
z własnych materiałów MK Ekino; QR to mailto:bimer55@wp.pl.
Pełny kod, testy i referencje są publikowane w sąsiednim pliku _source.zip.
