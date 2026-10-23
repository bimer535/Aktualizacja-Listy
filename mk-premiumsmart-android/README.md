# MK PremiumSmart TV 0.1.0

Pierwsza testowa aplikacja MK na Android TV, bez konta PremiumSmart.
Android 7.0+ (API 24), ARM 32- i 64-bitowy. Pakiet pl.mk.premiumsmart.tv.
Może być zainstalowana obok aplikacji eu.premiumsmart.tv.
Podpisany instalator APK (około 36 MB) został przekazany osobno w czacie.
Publikacja pliku APK na GitHub nie została ukończona. Aktualizacja w aplikacji
będzie dostępna po opublikowaniu APK i update.json; obecnie instalacja jest ręczna.

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
- 19 testów Python: katalog, źródła, języki, stronicowanie, historia,
  ulubione, wznawianie i ukończenie, ustawienia, jawny start źródła, lokalny relay.
- Cztery wektory Java Pow zgodne bit w bit z oryginalnym kodem C MK;
  osobno sprawdzono przerwanie obliczeń.
- Test na żywo bez konta: pobranie 52 pozycji dla rocznika 2026 / Lektor PL,
  dwa warianty Vidara oraz próbka MPEG-TS przez lokalny przekaźnik HTTP aplikacji.
- Nie potwierdzono jeszcze uruchomienia interfejsu, obrazu i dźwięku na Nokii
  ani innym fizycznym urządzeniu Android TV. To wersja do pierwszego testu.

## Dane i połączenia

Konto i hasło nie są zbierane. Katalog używa anonimowych cookies w pamięci.
Historia, ulubione i postęp są w prywatnym katalogu aplikacji. Krótkotrwały
cache weryfikacji źródeł jest zapisywany w prywatnym cache, z uprawnieniami 0600.
Nie ma wspólnego serwera MK, komputera pośredniczącego ani zależności od Enigmy.

Odtwarzacz Media3 łączy się tylko z lokalnym przekaźnikiem 127.0.0.1 na
losowym porcie i z losowym tokenem. Przekaźnik zachowuje nagłówki i sesję źródła,
wybrane audio/wideo oraz względne linki HLS. Pozostałe połączenia są HTTPS.
Sesje i tymczasowe adresy filmów nie są wyświetlane w interfejsie ani raportach.
Kopia chmurowa i przenoszenie danych są wyłączone w manifeście.

## Budowanie i źródła

JDK 17, Android SDK 35 / Build Tools 35.0.0, Python 3.11 i Gradle 8.11.1.
AGP 8.9.2, Chaquopy 16.1.0, PyCryptodome 3.21.0, Media3 1.6.1.

```sh
./gradlew :app:assembleDebug :app:lintDebug
python3 -m unittest discover -s tests -q
```

Ustaw MK_BUILD_PYTHON, jeśli Python 3.11 nie jest w PATH. Dla budowania release:
./gradlew :app:assembleRelease :app:lintRelease, następnie podpisz unsigned APK
własnym kluczem, narzędziem apksigner. Klucz dystrybucyjny MK jest przechowywany
osobno, prywatnie; nie ma go w repozytorium ani archiwum kodu.
Zmiana klucza podpisu uniemożliwia aktualizację wcześniej zainstalowanej aplikacji.

Całość kodu, zasoby, wrapper Gradle, testy i oryginalne referencje są w pliku
MK_PremiumSmart_TV_0.1.0_source.zip. Narzędzia pobrane do budowania nie są
dołączane do źródeł ani do APK, poza runtime Android/Python wymaganym w aplikacji.

GPL-3.0-only dla kodu MK i publicznych adapterów E2i. Licencje zależności w
app/src/main/assets i THIRD_PARTY.txt. Oryginalne referencje i pochodzenie w reference/.
Publiczna baza E2i: e2iplayer-2026.10.18.05; komponenty MK PremiumSmart E2 0.1.1.
Przyspieszony kod Pow.java jest tłumaczeniem własnej implementacji native_pow.c.

Dokumentacja środowiska:
https://chaquo.com/chaquopy/doc/16.1/android.html
https://developer.android.com/media/media3/exoplayer/hello-world
