# MK eKino Vega 0.1.10 — źródła

Port dla Amazon Fire TV Stick 4K Select z **Vega OS 2.0**. Pakiet ARMv7 `.vpkg`, aplikacja `org.mkapps.ekino`, komponent `org.mkapps.ekino.main`.

Projekt korzysta z wcześniejszego prototypu MK eKino Vega 0.1.0 i tras oraz selektorów katalogu z `mk-ekino-android/packages/MK_Ekino_TV_0.1.2_source.zip` w tym repozytorium (stan bazowy `c7666a7`). Interfejs i adapter WebView są przeznaczone dla Vega; kod Java/Media3 z Androida nie działa bezpośrednio na Vega OS.

## Zmiany w 0.1.10 — oczekuje na kompilację i sprawdzenie

- Poprawka błędu aplikacji: `onError` WebView nie zasłania całego playera i nie wyłącza kursora. Błędy po otwarciu źródła są komunikatem, który nie przechwytuje wejścia. Dotyczy to także błędu HTTP dokumentu; błędy zasobów są logowane bez blokowania strony.
- Dodano kod błędu i nazwę ze stałej listy `ERR_*`, bez zapisywania URL ani surowego opisu. Anulowanie nawigacji `ERR_ABORTED` nie tworzy komunikatu awarii. Odczyt metadanych, `canplay`, `playing` lub poprawne wczytanie dokumentu usuwa poprzedni komunikat strony.
- Log użytkownika 0.1.9: wysłano kliknięcie kursora, odczytano metadane H.264 1920 × 800 i `canplay` z `paused=1`, lecz ekran pokazywał błąd strony. Ten fragment nie zawiera samego zdarzenia `document-error` i nie ustala przyczyny źródłowego błędu.
- Przywrócono pięć wpisów zależności npm do wcześniejszych wartości. Numerowanie poprzednich wydań przypadkowo zmieniło również wersje zależności w pliku blokady; nie odtwarzały one stanu zainstalowanego wcześniej `node_modules`. Podbijanie wersji dotyczy teraz wyłącznie metadanych aplikacji.
- Dodano dwa testy regresji błędów strony i HTTP, zachowania kursora, usuwania komunikatu po `canplay` oraz redakcji szczegółów.
- **Nowe testy, TypeScript i budowa nie zostały uruchomione: środowisko wykonawcze było niedostępne. Nie ma jeszcze gotowego pakietu 0.1.10.** Budowanie musi rozpocząć się od `npm ci`, następnie przejść kontrole, zanim pakiet zostanie zainstalowany.

## Zmiany w 0.1.9

- Zgłoszenie użytkownika 0.1.8: strona zatrzymuje się na oknie „Wznów / Od początku”; przyciski nie są dostępne strzałkami, obrazu i dźwięku brak. Log `playing` z rosnącym czasem nie potwierdził widocznego filmu. To stan HTMLMediaElement, a nie pomiar obrazu na ekranie.
- Dodano ręczny kursor TV, automatycznie włączany na wejściu do zewnętrznego playera. Strzałki przesuwają celownik, OK wysyła natywne `touchstart` i `touchend` przez udokumentowane `WebView.dispatchTouchEvent`. Menu przełącza kursor/nawigację; Wstecz wraca do katalogu. W trybie nawigacji dostępny jest też przycisk „Kursor”.
- Nakładka z własnym fokusem przejmuje strzałki/OK, zamiast polegać na fokusowaniu elementów zewnętrznej strony. Współrzędne celownika są skalowane do widocznego viewportu WebView; brak rozmiaru oznacza widoczny błąd, bez zgadywania pozycji kliknięcia.
- Kliknięcia następują wyłącznie po OK użytkownika. Kod nie wyszukuje ani nie klika samoczynnie „Wznów”, „Od początku” czy potwierdzeń człowieka. Zakończenie dotyku jest wysyłane także przy wyjściu w trakcie kliknięcia. Natywne Play/Pauza nie steruje filmem w trybie kursora, aby użytkownik najpierw obsłużył okno strony.
- Logi `cursor-click` i `cursor-click-failed` nie zawierają treści strony, współrzędnych, URL ani danych osobowych.
- Sprawdzenie obejmuje przeliczanie pozycji, ograniczenie ruchu do ekranu, pojedynczą sekwencję dotyku na OK, zmianę trybu bez odtwarzania renderera i zwolnienie dotyku przy Wstecz. Nie potwierdzono jeszcze działania kursora ani obrazu/dźwięku na fizycznym Sticku.

## Zmiany w 0.1.8

- Zgłoszony log 0.1.7 potwierdził odczyt metadanych i znalezienie dekodera H.264 dla 1280 × 536, lecz bez `play`/`playing`. Nie dowodzi to prawidłowego dekodowania klatek ani pełnego buforowania filmu.
- Wyłączono wymaganie gestu WebView (`mediaPlaybackRequiresUserAction=false`), które mogło odrzucać próbę Play po asynchronicznym, ręcznym potwierdzeniu na stronie. To hipoteza wynikająca z etapu zatrzymania, nie potwierdzona jeszcze diagnoza na Sticku.
- Dodano natywny przycisk „Play / Pauza” po odczytaniu metadanych oraz obsługę przycisku Play/Pauza pilota. Steruje wyłącznie istniejącym elementem video z metadanymi; nie klika przycisków strony ani potwierdzeń człowieka. Nie zmienia wyglądu i fokusu playera. Wyłączono domyślne sterowanie sesją Kepler, aby nie dublować własnego przełączania Play/Pauza.
- Logi i komunikaty rozróżniają odrzucenie Play (`PLAY_REJECTED_1`: polityka uruchamiania, `_2`: nieobsługiwane źródło, `_3`: anulowanie). Raportują też stan pauzy, czas oraz bufor przed aktualną pozycją jako liczby; nie zapisują URL, tokenów ani treści wyjątków.
- Przy powrocie do katalogu stary renderer jest najpierw odmontowany, a katalog tworzony po 300 ms. Log 0.1.7 pokazał timeout zwykłej nawigacji do katalogu i późniejszy sukces po restarcie widoku; zachowano ekran odzyskiwania oraz potwierdzenie `ui-ready`.
- Sprawdzenie: testy kodu, TypeScript, budowa i walidacja pakietu. Brak potwierdzenia odtwarzania na fizycznym Sticku.

## Zmiany w 0.1.7

- Przy przejściu katalog → player → katalog pozostaje ten sam natywny WebView. Usunięto zmianę klucza React oraz `stopLoading` przy powrocie, aby nie niszczyć powierzchni renderera i nie zatrzymywać nowej nawigacji.
- Katalog sygnalizuje `ui-ready` po zarejestrowaniu własnych funkcji. Wrapper dopiero wtedy uruchamia katalog przez `mkStart`, przekazując stan do odtworzenia. Samo zdarzenie `onLoad` nie jest potwierdzeniem gotowości skryptu. Uruchomienie jest jednokrotne, aby start domyślny nie ścigał się z przywracaniem filtrów.
- Podczas przywracania widoczny jest natywny ekran „Ładowanie katalogu”. Jeżeli katalog nie potwierdzi gotowości w 10 s, pojawiają się „Ponów wczytywanie katalogu” i „Zamknij aplikację”. Wstecz może zamknąć aplikację także bez odpowiedzi WebView.
- Ręczna próba ponowienia zwalnia renderer i tworzy nowy po przerwie w osobnym renderowaniu React. Powrót z Home ponawia wczytywanie tylko wtedy, gdy katalog nie potwierdził gotowości. Nie kasuje danych użytkownika.
- Logi MKPLAY rozróżniają `catalogue-requested`, `catalogue-document-loaded`, `catalogue-ready`, `catalogue-ready-timeout` i `catalogue-restart`; nie zawierają prywatnych danych ani adresów strumienia.
- Zgłoszenie użytkownika: w 0.1.6 natywne Wstecz zostało odebrane, lecz katalog nie wrócił i po Home aplikacja pozostała czarna. Zmiana odpowiada na ten błąd; fizyczne odtworzenie filmu i działanie powierzchni renderera wymagają sprawdzenia na Sticku. Nie potwierdzono przyczyny wcześniejszego błędu samego filmu.

## Zmiany w 0.1.6

- Usunięto automatyczne `video.play()`, wymuszanie kontrolek, pełnego ekranu i fokusu wewnątrz zewnętrznych playerów. Strona dostawcy zachowuje własny przebieg uruchamiania; obserwator raportuje tylko zdarzenia wideo, bez zmiany DOM.
- Włączono cookies zewnętrznych ramek dla sesji playera. Potwierdzenie i Play pozostają ręczną czynnością użytkownika.
- Dodano natywną obsługę Wstecz i Menu przez zdarzenia pilota Kepler, zatrzymanie dokumentu przy powrocie i odrzucanie spóźnionej odpowiedzi resolvera. Nie wymaga to odpowiedzi JavaScript strony źródłowej. Nie zapewnia wyjścia w razie awarii całego procesu aplikacji/systemu.
- Po 45 s bez potwierdzonego `playing` aplikacja pokazuje komunikat i preferuje przycisk powrotu. Nie przerywa samoczynnie wideo: zdarzenia z wewnętrznej ramki innego pochodzenia mogą być niewidoczne dla obserwatora.
- Zgłoszenie użytkownika: 0.1.5 zatrzymuje się na ładowaniu playera i nie pozwala wrócić pilotem. Przyczyna wcześniejszego błędu samego strumienia pozostaje niepotwierdzona. VLC nie jest integrowany ani uruchamiany przez tę aplikację.
- Sprawdzenie obejmuje testy kodu, kompilację i walidację pakietu; nie obejmuje odtwarzania na fizycznym Sticku. To pakiet diagnostyczny i poprawka obsługi zewnętrznego playera, nie deklaracja działającego odtwarzania wszystkich źródeł.

## Zmiany w 0.1.5

- Poprawka regresji nawigacji zgłoszonej w 0.1.4. Przy wejściu do playera tworzony jest świeży natywny WebView z preferowanym fokusem TV; przy powrocie powstaje widok katalogu i przywracany jest jego stan. W danym momencie pozostaje jeden pełnowymiarowy WebView.
- Nieprzetwarzający jeszcze filmu element video nie przejmuje fokusu przycisku hosta. Fokus przechodzi na video dopiero po zdarzeniu `playing`.
- Potwierdzenie człowieka pozostaje ręcznym działaniem użytkownika. Kod nie klika elementów weryfikacji ani nie obchodzi ich zabezpieczeń.
- To poprawka regresji fokusu, nie potwierdzenie rozwiązania wcześniejszego błędu odtwarzania. Próba filmu na fizycznym Sticku nadal jest potrzebna; zachowano komunikaty MEDIA_ERR i logi MKPLAY.

## Zmiany w 0.1.4

- Jeden, stale zamontowany WebView o pełnym rozmiarze. Katalog i player zmieniają dokument w tej samej powierzchni; nie ma drugiego renderera ani ukrywania katalogu przez rozmiar 0 × 0.
- Przywracanie wybranych filtrów, strony i szczegółów filmu po powrocie z playera. Odpowiedzi poprzedniego dokumentu nie trafiają do nowego widoku.
- Widoczne komunikaty HTMLMediaElement (MEDIA_ERR_1–4) i odrzuconego Play. Logi `[MKPLAY]` zawierają wyłącznie etap i kody stanów, bez URL strumienia, cookies i tokenów.
- Zmiana odpowiada na zgłoszone logi Chromium o utracie kontekstu GPU. Logi zawierały również udane wyświetlenie klatki po powrocie na pierwszy plan; nie dowodzą, że GPU był jedyną przyczyną problemu.
- **Nie potwierdzono odtwarzania na fizycznym Sticku. To poprawka przełączania widoków i diagnostyki, a nie potwierdzenie kompletnego portu resolverów czy playera Androida/Enigmy.**

## Zmiany w 0.1.3

- Wybór gatunku, wersji językowej (np. Lektor, Napisy, Dubbing) i roku z publicznego katalogu. Filtry łączą się w zapytaniu do serwera, resetują paginację i można je wyczyścić.
- Etykiety języka/jakości przy źródłach, jeśli serwis je udostępnia.
- Wybór źródła przechodzi przez publiczny link/iframe strony pośredniej do rzeczywistego playera. Bezpośredni MP4/HLS otwierany jest w kontrolowanym elemencie video w kontekście strony źródłowej (Referer); pozostałe źródła uruchamiają zwykły embed dostawcy z próbą automatycznego odtwarzania.
- Anulowanie otwierania źródła przy powrocie do katalogu, limit czasu i wykrywanie zapętlonych przekierowań.
- Nie wykonuje własnego obchodzenia CAPTCHA, DRM ani ograniczeń konta. Nie jest pełnym portem resolverów Pythona ani natywnego playera Media3.

## Działanie

- Katalog filmów i seriali, szczegóły, odcinki i strony wskazane przez serwis.
- Wyszukiwanie w katalogu `/search/qf/?q=...` oraz filtrowanie bieżącej listy.
- Ulubione i oznaczanie obejrzanych zapisane w pamięci aplikacji.
- Nawigacja przestrzenna WebView pilotem; Wstecz zamyka odtwarzacz, wraca z odcinka do serialu i z katalogu głównego wychodzi z aplikacji.
- Otwieranie stron źródeł w jednym WebView; zewnętrzny player zachowuje własne kontrolki.
- Błędy HTTP i timeouty; ignorowanie spóźnionych odpowiedzi po zmianie widoku.
- Parsowanie zewnętrznego HTML jako danych, bez wstawiania go do interfejsu przez `innerHTML`. Most sieciowy przyjmuje tylko adresy katalogu `https://ekino.ws`.

## Ostatnie ukończone sprawdzenie — 0.1.9, 30.10.2026

- SDK `2.0.13986`, CLI `1.4.7`, React Native `0.83.0`, WebView `4.0.5`.
- TypeScript: bez błędów.
- 25 testów katalogu, filtrów i adaptera odtwarzania: zaliczone. Pokrywają tytuły/okładki/paginację, wyszukiwanie, wybór źródła/zapis/back, powrót z odcinka, spóźnione odpowiedzi i nieufny HTML.
- `vega project doctor`: wszystkie wymagane kontrole zgodności zaliczone.
- Release ARMv7: zbudowany; `vpt validate`: 0 błędów manifestu.
- Pobranie prawdziwej strony katalogu: HTTP 200, 10 pozycji.
- **Użytkownik zainstalował i uruchomił aplikację na Sticku. Wersje 0.1.3–0.1.5 nie odtworzyły wskazanego filmu poprawnie. Wersja 0.1.6 nie przywróciła katalogu po wyjściu z playera. Wersja 0.1.7 odczytała metadane H.264, lecz nie potwierdziła odtwarzania; zwykły powrót do katalogu zakończył się timeoutem. Wersja 0.1.8 zgłosiła `playing`, ale użytkownik widział nieobsługiwalne pilotem okno wznowienia, bez obrazu i dźwięku. Wersja 0.1.9 nadal nie uruchomiła filmu: po kliknięciu widoczny był błąd strony, mimo późniejszych metadanych i canplay.**
- Próba pobrania aktualnego katalogu w środowisku budowania 30.10: HTTP 403. Testy nowych filtrów i rozwiązywania źródeł wykorzystują lokalne przykłady oparte na publicznym parserze Enigma2; nie stanowią potwierdzenia działania każdego dostawcy.

## Ograniczenia

Odtwarzanie odbywa się w WebView zewnętrznego serwisu. Dostępność, logowanie, reklamy, formaty wideo i ograniczenia serwisów pozostają zależne od tych serwisów. Aplikacja nie omija CAPTCHA, DRM ani zabezpieczeń dostępu. Nie wymaga własnego konta MK.

To nie jest pełna kopia funkcji APK: brak natywnego Media3, automatycznego aktualizatora APK, zapisu pozycji w zewnętrznym odtwarzaczu i natywnego menu wyboru audio/napisów. Kod źródeł z Androida nie jest uruchamiany wewnątrz Vega.

## Budowanie

Oficjalny SDK działa na Ubuntu/macOS. Amazon nie deklaruje wsparcia Windows/WSL. Zainstaluj wersję przypiętą w `.vega-version`, Node.js 20+ i ustaw Vega CLI w PATH.

```bash
vega sdk install 2.0.13986
vega sdk use 2.0.13986
bash build_on_ubuntu.sh
```

Wynik: `build/armv7-release/mk-ekino-vega_armv7.vpkg`. `npm run build:app` pakuje również JavaScript; nie polegaj na przebudowie wyłącznie części natywnej po zmianie `src/App.tsx`.

## Aktywacja urządzenia

Na Sticku: Ustawienia → My Fire TV → Developer Options → Developer Mode → Continue. Kod aktywacyjny ma ograniczony czas ważności.

Na komputerze Ubuntu/macOS:

```bash
vega devmode login
# Zaloguj się na konto Amazon Developer i zatwierdź uprawnienia w przeglądarce.
vega devmode enable-device --code AKTUALNY_KOD_Z_TELEWIZORA
```

Po aktywacji Stick uruchamia się ponownie. W celu instalacji komputer musi mieć połączenie z urządzeniem przez USB albo znajdować się w tej samej sieci. Dla sieci wybierz na Sticku Connection Mode → TCP/IP → port 5555; nie przekierowuj tego portu do Internetu.

## Instalacja

```bash
# USB, dokładnie jedno urządzenie:
bash install_on_fire_tv.sh build/armv7-release/mk-ekino-vega_armv7.vpkg

# Sieć lokalna, adres zastąp adresem swojego Sticka:
bash install_on_fire_tv.sh build/armv7-release/mk-ekino-vega_armv7.vpkg 192.168.1.100:5555
```

Można też wykonać bez skryptu:

```bash
vega device install-app --packagePath build/armv7-release/mk-ekino-vega_armv7.vpkg
vega device launch-app --appName org.mkapps.ekino.main
```

Podpisy i profile instalacyjne obsługuje oficjalny toolchain. W razie odmowy instalacji zachowaj dokładny komunikat urządzenia; nie wyłączaj weryfikacji podpisów. Poprawna walidacja pakietu nie stanowi potwierdzenia instalacji na każdym urządzeniu.

## Dokumentacja producenta

- https://developer.amazon.com/docs/vega/latest/install-vega-sdk
- https://developer.amazon.com/docs/vega/latest/developer-mode
- https://developer.amazon.com/docs/vega/latest/run-apps
- https://developer.amazon.com/docs/vega/latest/vda-over-tcpip
- https://developer.amazon.com/docs/vega/latest/develop-your-app-with-webview

Kod MK: GPL-3.0-only, pełny tekst w `LICENSE`. Biblioteki i narzędzia Amazon mają własne licencje; SDK, klucze i dane logowania nie są częścią repozytorium.
