# MK eKino Vega 0.1.1

Port dla Amazon Fire TV Stick 4K Select z **Vega OS 2.0**. Pakiet ARMv7 `.vpkg`, aplikacja `eu.prostastrona.mkekino`, komponent `eu.prostastrona.mkekino.main`.

Projekt korzysta z wcześniejszego prototypu MK eKino Vega 0.1.0 i tras oraz selektorów katalogu z `mk-ekino-android/packages/MK_Ekino_TV_0.1.2_source.zip` w tym repozytorium (stan bazowy `c7666a7`). Interfejs i adapter WebView są przeznaczone dla Vega; kod Java/Media3 z Androida nie działa bezpośrednio na Vega OS.

## Działanie

- Katalog filmów i seriali, szczegóły, odcinki i strony wskazane przez serwis.
- Wyszukiwanie w katalogu `/search/qf/?q=...` oraz filtrowanie bieżącej listy.
- Ulubione i oznaczanie obejrzanych zapisane w pamięci aplikacji.
- Nawigacja przestrzenna WebView pilotem; Wstecz zamyka odtwarzacz, wraca z odcinka do serialu i z katalogu głównego wychodzi z aplikacji.
- Otwieranie stron źródeł w osobnym WebView z kontrolkami multimedialnymi Vega.
- Błędy HTTP i timeouty; ignorowanie spóźnionych odpowiedzi po zmianie widoku.
- Parsowanie zewnętrznego HTML jako danych, bez wstawiania go do interfejsu przez `innerHTML`. Most sieciowy przyjmuje tylko adresy katalogu `https://ekino.ws`.

## Status sprawdzenia — 29.10.2026

- SDK `2.0.13986`, CLI `1.4.7`, React Native `0.83.0`, WebView `4.0.5`.
- TypeScript: bez błędów.
- 5 testów integracji interfejsu w JSDOM: zaliczone. Pokrywają tytuły/okładki/paginację, wyszukiwanie, wybór źródła/zapis/back, powrót z odcinka, spóźnione odpowiedzi i nieufny HTML.
- `vega project doctor`: wszystkie wymagane kontrole zgodności zaliczone.
- Release ARMv7: zbudowany; `vpt validate`: 0 błędów manifestu.
- Pobranie prawdziwej strony katalogu: HTTP 200, 10 pozycji.
- **Nie wykonano instalacji i testu na fizycznym Sticku. Nie potwierdzono odtwarzania wideo.**

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
vega device launch-app --appName eu.prostastrona.mkekino.main
```

Podpisy i profile instalacyjne obsługuje oficjalny toolchain. W razie odmowy instalacji zachowaj dokładny komunikat urządzenia; nie wyłączaj weryfikacji podpisów. Poprawna walidacja pakietu nie stanowi potwierdzenia instalacji na każdym urządzeniu.

## Dokumentacja producenta

- https://developer.amazon.com/docs/vega/latest/install-vega-sdk
- https://developer.amazon.com/docs/vega/latest/developer-mode
- https://developer.amazon.com/docs/vega/latest/run-apps
- https://developer.amazon.com/docs/vega/latest/vda-over-tcpip
- https://developer.amazon.com/docs/vega/latest/develop-your-app-with-webview

Kod MK: GPL-3.0-only, pełny tekst w `LICENSE`. Biblioteki i narzędzia Amazon mają własne licencje; SDK, klucze i dane logowania nie są częścią repozytorium.
