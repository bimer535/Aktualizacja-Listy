# MK PremiumSmart TV 0.1.3

Nowa zielona kwadratowa ikona MK PremiumSmart. Jest to aktualizacja zasobów
podpisanego APK 0.1.2; zachowuje jego odtwarzanie i alternatywny odtwarzacz.
Podpis jest zgodny z poprzednimi wersjami.

Aktualizator pobiera APK w 30 częściach i sprawdza sumy SHA-256. Pełny plik
APK udostępniono osobno do ręcznej instalacji. Numer wersji: 0.1.3, kod: 4.
Zestaw odtwarzający zmianę zasobów: packages/MK_PremiumSmart_TV_0.1.3_icon_update.zip.
Nie zastępuje go starsze archiwum pełnych źródeł 0.1.1.

Poniżej historyczna dokumentacja 0.1.1.

# MK PremiumSmart TV 0.1.1

Pierwsza testowa aplikacja MK na Android TV, bez konta PremiumSmart.
Android 7.0+ (API 24), ARM 32- i 64-bitowy. Pakiet pl.mk.premiumsmart.tv.
Może być zainstalowana obok aplikacji eu.premiumsmart.tv.
Podpisany APK przekazano osobno w czacie. Publikacja APK i manifestu aktualizacji
na GitHub nie jest ukończona; tę wersję należy zainstalować ręcznie na poprzedniej.

## Zmiany 0.1.1

- Natywny transport wideo Media3/OkHttp zamiast przesyłania filmu przez Pythona.
  Obsługa HTTP/2, połączeń wielokrotnego użytku, zakresów bajtów i przewijania MP4.
- Jawny format HLS również dla adresów bez rozszerzenia oraz manifestów/segmentów
  serwowanych przez hosting z nietypowymi końcówkami lub Content-Type.
- Oryginalna playlista HLS pozwala adaptować jakość do łącza i obsługi dekodera.
  Tryb automatyczny ogranicza górną rozdzielczość do najlepszego wybranego wariantu;
  ręczny wybór ogranicza rozdzielczość i preferuje najwyższy obsługiwany bitrate.
- Nagłówki i cookies sesji źródła trafiają do natywnego transportu. Cookies mają
  zachowane ograniczenia domeny, hosta, ścieżki, HTTPS i terminu ważności.
- Bufor docelowy 30–90 sekund, próg startu 3 s i wznowienia po buforowaniu 6 s,
  z limitem docelowym danych 64 MiB. Alternatywny dekoder przy błędzie inicjalizacji.
- Widoczny stan buforowania; komunikaty odtwarzacza zawierają kod błędu i HTTP,
  bez adresów wideo, cookies ani tokenów.
- Archiwum źródeł zawiera również brakujący wcześniej app/build.gradle.

## Funkcje

- Filmy i seriale z tego samego anonimowego API co MK PremiumSmart E2 0.1.1.
- Wersje językowe, roczniki, sortowanie po dacie, ocenie i popularności.
- Sezony i odcinki, wyszukiwanie z historią, okładki i oceny.
- Wybór źródła ręcznie. Samo otwarcie filmu nie uruchamia odtwarzania.
- Te same adaptery źródeł co w E2: Byse, Vidara, VidsST, Abyss, StreamTape,
  VOE i MixDrop, plus proste MP4/HLS. Dostępność zależy od źródła i sieci.
- Najlepsza dostępna jakość i preferencja polskiego audio; opcjonalny ręczny
  wybór wariantu w MENU. Audio i napisy udostępnione przez źródło w odtwarzaczu.
- Lista i kafelki, ulubione, kontynuowanie oglądania, zapamiętywanie pozycji.
- Po zakończeniu odcinka propozycja następnego, również między sezonami.
- Aktualizacja APK z GitHub: kontrola wersji, pakietu, rozmiaru i SHA-256;
  instalację potwierdza użytkownik w systemowym instalatorze Android.
- Kontakt MK: bimer55@wp.pl. Własna ikona MK PremiumSmart.

Nie jest to zmodyfikowane APK innego autora. Przesłane premiumsmart-tv.apk
wykorzystano tylko do sprawdzenia nazwy pakietu, ABI i wymagań systemowych.
Nie skopiowano jego kodu ani nie usuwano ekranu logowania.

## Pilot

OK: wybór. Przytrzymanie OK na filmie/serialu: dodaj lub usuń z ulubionych.
MENU: opcje, jakość, odświeżanie, aktualizacja i kontakt.
Żółty: lista/kafelki. Niebieski: aktualizacja.
W odtwarzaczu OK przy ukrytych kontrolkach: pauza/wznów; widoczne kontrolki
obsługuje się standardowo pilotem. Wstecz/STOP kończy film i wraca do źródeł.
Niebieski podczas odcinka: przejdź do następnego odcinka.
Przycisk Audio/napisy: dostępne ścieżki tego źródła.

## Instalacja i pierwsza próba

Pobierz APK na przystawkę Android TV i otwórz w menedżerze plików.
Jeżeli Android poprosi, zezwól temu menedżerowi na instalowanie aplikacji.
Uruchom MK PremiumSmart TV z menu aplikacji. Logowanie nie jest wymagane.

Pierwsza próba: Filmy → Lektor PL → rocznik → sortowanie → film → źródło → OK.
Wypróbuj także Vidara, jeśli inny serwer jest niedostępny.

## Weryfikacja

- Zbudowany podpisany APK release, poprawny podpis v2 i v3; osobny klucz MK.
- Android Lint: 0 błędów. Ostrzeżenia obejmują m.in. teksty wyłącznie po polsku,
  celowy układ poziomy TV i nowsze dostępne wersje bibliotek.
- 24 testy Python: katalog, źródła, języki, stronicowanie, historia,
  ulubione, wznawianie i ukończenie, ustawienia, jawny start źródła, format HLS bez rozszerzenia, przekierowania i deskryptory natywne.
- 3 testy Java: ograniczenia cookies domena/host/ścieżka/HTTPS, segmenty na
  subdomenach oraz wymiana i wygasanie cookies odpowiedzi.
- Cztery wektory Java Pow zgodne bit w bit z oryginalnym kodem C MK;
  osobno sprawdzono przerwanie obliczeń.
- Test na żywo bez konta: pobranie 51 pozycji dla rocznika 2026 / Lektor PL,
  dwa warianty Vidara i próbka MPEG-TS (HTTP 206, 65 536 bajtów).
  VidsST zwracał HTTP 503, a StreamTape stronę Site Unavailable. Abyss
  zwrócił warianty, ale pobranie próbki z tego środowiska otrzymało HTTP 403.
- Użytkownik uruchomił wersję 0.1.0 na Android TV: działał Byse, Abyss klatkował.
  Poprawiona wersja 0.1.1 wymaga ponownego sprawdzenia obrazu i dźwięku na Nokii;
  nie deklarujemy działania niedostępnych serwerów źródeł.

## Dane i połączenia

Konto i hasło nie są zbierane. Katalog używa anonimowych cookies w pamięci.
Historia, ulubione i postęp są w prywatnym katalogu aplikacji. Krótkotrwały
cache weryfikacji źródeł jest zapisywany w prywatnym cache, z uprawnieniami 0600.
Nie ma wspólnego serwera MK, komputera pośredniczącego ani zależności od Enigmy.

Odtwarzacz Media3 pobiera wideo, playlisty i napisy bezpośrednio przez HTTPS
korzystając z OkHttp. Python obsługuje katalog i uzyskanie adresu źródła,
ale nie przenosi bajtów filmu. Natywny klient zachowuje nagłówki źródła oraz
domenowe cookies sesji; są one trzymane wyłącznie w pamięci odtwarzania.
Sesje i tymczasowe adresy filmów nie są wyświetlane w interfejsie ani raportach.
Kopia chmurowa i przenoszenie danych są wyłączone w manifeście.

## Budowanie i źródła

JDK 17, Android SDK 35 / Build Tools 35.0.0, Python 3.11 i Gradle 8.11.1.
AGP 8.9.2, Chaquopy 16.1.0, PyCryptodome 3.21.0, Media3 1.6.1, OkHttp 4.12.0.

```sh
./gradlew :app:assembleRelease :app:testReleaseUnitTest :app:lintRelease
python3 -m unittest discover -s tests -q
```

Ustaw MK_BUILD_PYTHON, jeśli Python 3.11 nie jest w PATH. Dla budowania release:
./gradlew :app:assembleRelease :app:lintRelease, następnie podpisz unsigned APK
własnym kluczem, narzędziem apksigner. Klucz dystrybucyjny MK jest przechowywany
osobno, prywatnie; nie ma go w repozytorium ani archiwum kodu.
Zmiana klucza podpisu uniemożliwia aktualizację wcześniej zainstalowanej aplikacji.

Całość kodu, zasoby, wrapper Gradle, testy i oryginalne referencje są w pliku
MK_PremiumSmart_TV_0.1.1_source.zip. Narzędzia pobrane do budowania nie są
dołączane do źródeł ani do APK, poza runtime Android/Python wymaganym w aplikacji.

GPL-3.0-only dla kodu MK i publicznych adapterów E2i. Licencje zależności w
app/src/main/assets i THIRD_PARTY.txt. Oryginalne referencje i pochodzenie w reference/.
Publiczna baza E2i: e2iplayer-2026.10.18.05; komponenty MK PremiumSmart E2 0.1.1.
Przyspieszony kod Pow.java jest tłumaczeniem własnej implementacji native_pow.c.

Dokumentacja środowiska:
https://chaquo.com/chaquopy/doc/16.1/android.html
https://developer.android.com/media/media3/exoplayer/hello-world
