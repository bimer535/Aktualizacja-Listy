# MK PremiumSmart E2 0.1.3

## Zmiany 0.1.3 — przewijanie OpenPLi / OpenATV

- Lewo/prawo na kółku oraz krótki ⏪/⏩: skok o 10 sekund. Długie ⏪/⏩: skok o 60 sekund.
- Bez wywoływania nieobsługiwanego trybu x2/x4 w ServiceApp; własny kontekst klawiszy niezależny od map OpenPLi i OpenATV, bez podwójnego skoku przy naciśnięciu i puszczeniu kółka.
- Szybkie kolejne naciśnięcia kumulują skoki mimo opóźnionego odczytu pozycji. Ograniczenie do początku i sekundy przed końcem zapobiega zatrzymaniu ServiceApp.
- Pauza pozostaje pauzą; ręczny skok przerywa ponawiane automatyczne wznowienie. OK/pauza, EXIT i cyfry zachowują obsługę.
- Gdy usługa nie udostępnia seek albo odrzuca komendę, pojawia się krótki komunikat, bez awarii interfejsu. Nie można zagwarantować seek dla serwera, który go nie obsługuje.
- PremiumSmart: zgodny konstruktor MoviePlayer również dla OpenPLi (pominięcie fromMovieSelection, gdy nie jest obsługiwane).
- Weryfikacja lokalna: testy usług i map klawiszy OpenPLi 9.2/OpenATV; test fizycznych dekoderów wymaga potwierdzenia użytkownika.


Wersja 0.1.1: kwadratowa ikona z napisem MK PremiumSmart oraz czytelna informacja
„Wybierz film lub serial — tutaj pojawi się okładka” w pustym polu okładki w menu.
Film otwiera listę źródeł i czeka na OK. Naprawiono rozpoznawanie Vidary (własne
API StreamUp zamiast Byse), dodano parsery VidsST i Abyss oraz komunikaty o błędach
połączenia i niedostępności serwera. Zapisane ustawienie automatu dotyczy teraz
wyłącznie wyboru jakości po ręcznym wskazaniu źródła.

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
- Źródła: Byse, Vidara/StreamUp, VidsST, Abyss, VOE, MixDrop, StreamTape
  (bez wykonywania JS) oraz bezpośrednie MP4/HLS lub proste HTML5.
  Odtwarzacze wymagające innych resolverów, np. FlyFile, mogą nie zwrócić wariantów. Dostępność
  zależy od serwisu, źródła i sieci. Testy lokalne nie potwierdzają obrazu na TV.

## Pilot

OK w przeglądarce: wybierz. OK w filmie: pauza / wznów. EXIT kończy film
i wraca do wtyczki. Zielony: wyszukaj. Żółty: lista / kafelki. Niebieski
w przeglądarce: aktualizacja; podczas odcinka: następny odcinek.
MENU: opcje, ulubione, odświeżanie, widok, tryb automatyczny, Autor i kontakt.
INFO: informacje i licencja. Kontakt: MK, bimer55@wp.pl, kod QR do e-maila.
Źródła są uporządkowane z preferencją Lektor PL i Byse. Film rusza dopiero po OK
na źródle. Domyślnie wybierana jest najlepsza dostępna jakość i polska ścieżka;
w MENU można włączyć ręczny wybór języka i jakości.

## Instalacja

Pobierz MK_PremiumSmart_E2_0.1.1.ipk do /tmp dekodera:

```sh
opkg install /tmp/MK_PremiumSmart_E2_0.1.1.ipk
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
SF8008. 39 testów lokalnych sprawdza katalog, filtry, interfejs i aktualizator.
Osobno udostępniono tools/probe.py, który sprawdza katalog oraz opcjonalnie
warianty i ograniczony odczyt danych wideo.
MEDIA_REACHABLE oznacza bajty wideo, nie potwierdzenie pracy natywnego odtwarzacza.

Weryfikacja 0.1.1 dla „Łączy nas krew” (id 1195929): Vidara zwróciła dwa
warianty HLS; ograniczony odczyt segmentu potwierdził MPEG-TS, HTTP 206.
VidsST zwrócił HTTP 503, StreamTape stronę „Site Unavailable”. Abyss udostępnił
dane odtwarzacza, ale próba odczytu wideo zakończyła się HTTP 403. Są to wyniki
z sieci testowej; dostępność na dekoderze może być inna. Film z Byse działa
według potwierdzenia użytkownika. Nie zmieniono parsera Byse.

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
Runtime kompilatora: MIT, THIRD_PARTY.txt. Ikona MK PremiumSmart powstała przez
edycję własnej ikony MK w narzędziu imagegen: zastąpienie napisu EKINO dwoma
wierszami PREMIUM i SMART, z zachowaniem MK, turkusowego przycisku i ramki.
Plik ikony: src/MKPremiumSmartE2/icon.png. QR to mailto:bimer55@wp.pl.
Pełny kod, testy i referencje są publikowane w sąsiednim pliku _source.zip.

### 0.1.2
Nowa ikona MK z zachowaniem kwadratowych proporcji; bez zmian w odtwarzaniu.



## 0.1.4 — widoczna oś czasu na OpenATV i OpenPLi

Pasek przewijania z czasem docelowym, długością i rzeczywistą pozycją. Kółko lewo/prawo: skoki -10/+10 s. Przyciski << i >>: wybór pozycji na osi czasu w tempie x2/x4/x8/x16/x32/x64; OK lub PLAY zatwierdza i wznawia film. Bez przyspieszonego podglądu obrazu. Zrestartuj interfejs Enigma2 po aktualizacji.

Podczas wyboru pozycji film jest wstrzymany. Tempo dotyczy przesuwania znacznika na osi czasu; aplikacja wysyła żądanie zmiany pozycji po zatwierdzeniu. Pozwala to uniknąć wielu równoczesnych żądań segmentów HLS. Pasek pokazuje osobno czas docelowy i czas zgłoszony przez odtwarzacz, także podczas buforowania. Wskaźnik znika 5 sekund po skoku lub zatwierdzeniu. Skórka paska skaluje się do rozdzielczości interfejsu.

Testy automatyczne obejmują mapy klawiszy obu obrazów, tempo/zmianę kierunku, granice filmu, zatwierdzanie, pauzę, błędy usługi i zamknięcie ekranu. Nie wykonano testu na fizycznym dekoderze.
