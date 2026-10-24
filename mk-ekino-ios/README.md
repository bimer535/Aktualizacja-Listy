# MK eKino iOS — 1.0.3 beta

Niezależne wydanie MK na iPhone i iPad. Autor wydania: **MK**, kontakt **bimer55@wp.pl**. Układ graficzny przeniesiony stylistycznie z epremki.eu eKino, ale osobna identyfikacja MK i przekazana turkusowa ikona. iOS 16+, bundle `pl.mk.ekino.ios`.

## Faktyczny stan

To natywna aplikacja SwiftUI z katalogiem HTML i odtwarzaczem źródłowym w WebKit. Nie jest konwersją APK i nie uruchamia silnika Androida. Wymaga kompilacji Xcode i sprawdzenia na iPhonie. Nie należy traktować samego projektu jako potwierdzenia działania wideo.

Filmy: kategoria → wersja językowa → rocznik → lista/kafelki → szczegóły → wybór źródła. Seriale: sekcje/A–Z → sezon → odcinek. Wyszukiwanie, oceny, ulubione, przechowywany lokalnie postęp oraz następny odcinek. Player, VOE i Mix są wyświetlane; niedziałające wcześniej Upzone i Wrzucaj pominięte.

## Odtwarzanie i różnice wobec Androida

Aplikacja podąża za normalnymi linkami osadzenia i otwiera oficjalny odtwarzacz hostingu w WKWebView. Nie przenosi parserów, obliczeń weryfikacji, deszyfrowania ani serwera relay z Androida. Nie omija CAPTCHA, DRM, logowania ani limitów źródła. Serwis może wymagać interakcji użytkownika. Nie ma gwarancji zgodności każdego hostingu z WebKit. Jakość i napisy wybiera się w kontrolkach dostawcy; aplikacja nie narzuca automatycznie najlepszej jakości ani języka. Reklamy źródła mogą być widoczne.

Postęp i wznowienie działają tylko dla dostępnego elementu HTML5 video w załadowanej ramce. Wideo jest uznawane za uruchomione dopiero po zdarzeniu odtwarzania; wczytanie strony nie jest potwierdzeniem wideo. PIP i AirPlay zależą od możliwości źródła/iOS. Ulubione i historia pozostają na urządzeniu.

## Budowanie bez własnego Maca

Workflow `github/mk-ekino-ios.yml` należy umieścić w `.github/workflows/mk-ekino-ios.yml` repozytorium. Na GitHubie macOS runner generuje projekt przez XcodeGen, uruchamia testy w symulatorze i buduje IPA bez podpisu, do podpisania przez użytkownika. Workflow nie używa konta Apple, certyfikatów ani haseł. Brak publikacji do App Store/TestFlight. Do uruchomienia workflow GitHub musi zezwalać połączeniu na zapis plików workflows.

Alternatywnie na Macu: Xcode + XcodeGen, następnie `bash tools/build-ios.sh`.

## Darmowa instalacja z Windowsa

1. Zainstaluj **AltServer / AltStore Classic** zgodnie z aktualnym poradnikiem: https://faq.altstore.io/altstore-classic/how-to-install-altstore-windows . Nie chodzi o AltStore PAL.
2. Podłącz iPhone do Windowsa i zainstaluj AltStore. Konto Apple wpisujesz lokalnie w AltServer, nigdy w czacie ani w GitHub Secrets.
3. W razie potrzeby włącz Tryb dewelopera na iPhonie.
4. Pobierz ZIP artefaktu `MK_Ekino_iOS_1.0.3` z udanego przebiegu GitHub Actions. Wypakuj IPA, udostępnij do AltStore / dodaj przez zakładkę My Apps (+).
5. AltStore podpisuje aplikację Twoim kontem. Darmowe profile wygasają po 7 dniach; wymagają odświeżania. AltServer musi być dostępny do odnawiania, nie do oglądania filmów.

Aktualizacje wymagają ponownego podpisania i instalacji IPA. iOS nie oferuje tej aplikacji androidowego samodzielnego instalatora APK z GitHuba.

## Licencje

GPL-3.0-only. Natywny port koncepcji katalogu MK eKino / epremki, wcześniejsza baza E2iPlayer; zachowano informację o pochodzeniu. Nie dołączono prywatnego E2iPlayera ani danych konta. SwiftSoup 2.13.9 (MIT), źródła/licencja pobierane przez Swift Package Manager. Ikona dostarczona przez właściciela projektu. Wersja oficjalnie niezwiązana z serwisem eKino.


## Poprawki 1.0.1

Dodatkowe okna WebKit są wyświetlane z paskiem zamknięcia, w konfiguracji dostarczonej przez WebKit (z zachowaniem window.opener i sesji). Dodano dialogi JavaScript alert/confirm/prompt z oznaczeniem domeny, zamykanie i anulowanie przy wyjściu, właściwy Referer ostatniej strony osadzającej oraz diagnostykę dotknięcia i błędów skryptu bez zapisywania adresów/tokenów. Nie automatyzuje ani nie omija weryfikacji człowieka. Zgodność Player na fizycznym iPhonie nadal wymaga testu.


## 1.0.3 — okna reklamowe

Dodatkowe okna i przekierowania głównego odtwarzacza ograniczono do hostów wybranego źródła i jego wrapperów katalogowych. Obce witryny, w tym zgłoszona luugy.com, oraz niesklasyfikowane puste popupy nie otwierają okna nad filmem. Zwykłe zasoby wideo i osadzone ramki nadal są pobierane przez stronę. Nie usuwa to reklam osadzonych bezpośrednio w samym filmie lub odtwarzaczu. Nowe domeny przekierowań niepowiązane z wybranym hostem mogą wymagać aktualizacji adaptera. Poprawka nie omija logowania, CAPTCHA, DRM ani uprawnień źródła.

### 1.0.3
- Resolves ordinary VOE same-film alias redirects before the player host policy is created.
- Stable player status area, inline video and a manual play action for already loaded media.
- Keeps unrelated ad popups blocked; never clicks verification controls.
- Physical iPhone playback still requires verification by the user.
