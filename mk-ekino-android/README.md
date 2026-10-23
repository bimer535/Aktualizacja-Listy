# MK eKino TV 0.1.2

Nowa turkusowa ikona MK eKino. Kod odtwarzania i aktualizacji zachowany z 0.1.1.

# MK Ekino TV 0.1.1

Samodzielna aplikacja na Android TV 7.0+ dla urządzeń ARM 32/64-bit,
np. Nokia 8810. Pakiet: pl.mk.ekino.tv. Może działać obok MK PremiumSmart TV.
Nie wymaga komputera, dekodera Enigma, ServiceApp ani konta eKino.

## Zmiany 0.1.1

- Domyślnie wypełnienie ekranu bez pasów generowanych przez dopasowanie
  proporcji filmu. Zachowuje proporcje, przycina boki obrazu.
- Przycisk Obraz oraz żółty na pilocie podczas filmu przełączają
  Wypełnij / Dopasuj. Dopasuj pokazuje cały kadr. Wybór jest zapisywany.
  Pasy zakodowane bezpośrednio w obrazie filmu mogą nadal być widoczne.
- Aktualizacje z GitHub: MENU → Sprawdź aktualizację lub niebieski.
  Pobieranie z postępem i anulowaniem. Sprawdzamy aplikację, wersję,
  rozmiary i SHA-256 całego APK oraz fragmentów i zgodność podpisu z
  zainstalowaną aplikacją. Instalację zatwierdza użytkownik w Androidzie.
- Plik APK jest publikowany w 51 fragmentach w packages/. Aplikacja pobiera
  je kolejno i zapisuje gotowy APK w prywatnym cache. Fragmenty mają osobne
  sumy kontrolne. Nie wymagają ręcznego łączenia przy aktualizacji w aplikacji.
- Przejście z 0.1.0 wymaga jednorazowej ręcznej instalacji 0.1.1 z czatu;
  stara wersja aktualizatora nie obsługuje plików podzielonych na fragmenty.
  Podpis pozostaje ten sam i dane użytkownika są zachowane.
- 18 testów Python, 10 testów Java (w tym uszkodzone/niepełne fragmenty,
  błędne adresy, suma całego APK i anulowanie), Android Lint bez błędów.
  Użytkownik potwierdził działanie filmów w 0.1.0; nowy tryb obrazu wymaga
  sprawdzenia na urządzeniu.

## Funkcje

- Ten sam katalog i obsługa źródeł co MK Ekino E2 0.2.7.
- Filmy: kategorie, wersja językowa (np. lektor/dubbing/napisy), rocznik,
  stronicowanie, wyszukiwanie i historia wyszukiwania.
- Seriale, sezony, odcinki i propozycja następnego odcinka po zakończeniu.
- Trzy widoczne źródła: Player, VOE, Mix, w tej kolejności.
  Wejście do filmu pokazuje źródła; dopiero OK na źródle uruchamia odtwarzanie.
- Automatyczna najlepsza jakość i polskie audio, opcjonalny ręczny wybór jakości.
- Lista/kafelki, duże okładki, oceny eKino, ulubione, kontynuuj oglądanie.
- Wznawianie od zapisanej pozycji, zakończone filmy usuwane z kontynuowania.
- Własna kwadratowa ikona MK EKINO; w menu bez okładki widoczna jest ikona.
- Informacje i kontakt MK: bimer55@wp.pl.

## Pilot

OK: wybór. Przytrzymanie OK na filmie/serialu: ulubione.
MENU: opcje, jakość, odświeżanie, kontakt i sprawdzanie aktualizacji.
Żółty: lista/kafelki. Niebieski: sprawdź aktualizacje.
W odtwarzaczu OK przy ukrytych kontrolkach: pauza/wznów.
Wstecz/STOP kończy film i wraca do źródeł.
Audio/napisy: wybór dostępnych ścieżek. Niebieski w odcinku: następny odcinek.
Po otwarciu nowej listy zaznaczenie trafia na pierwszą pozycję.

## Instalacja

Pobierz podpisany MK_Ekino_TV_0.1.1.apk i otwórz go w menedżerze plików
na przystawce Android TV. Zezwól temu menedżerowi na instalowanie aplikacji,
jeśli Android zapyta. Uruchom MK Ekino TV z menu aplikacji.
APK jest udostępniony osobno w czacie; źródła są w tym repozytorium.

Aktualizacje korzystają z osobnego manifestu mk-ekino-android/update.json.
Instalację kolejnego APK zawsze zatwierdza użytkownik w instalatorze Androida.
Manifest wskazuje fragmenty instalatora dostępne w packages/. Użyj wbudowanej
aktualizacji z wersji 0.1.1 lub nowszej. Pierwszą instalację wykonaj APK z czatu.

## Działanie i prywatność

Python obsługuje katalog i adaptery źródeł przeniesione z MK Ekino E2.
AndroidX Media3/OkHttp pobiera film, playlisty i napisy bezpośrednio z hostingu.
Nie przesyłamy wideo przez Pythona, komputer, Enigmę ani serwer MK.
Cookies mają zachowany zakres domeny, ścieżki, HTTPS i termin ważności.
Nie używamy E2iPlayera ani kodu prywatnego loadera. Dane konta nie są zbierane.
Historia, ulubione i postęp są prywatnymi danymi aplikacji; kopia chmurowa
jest wyłączona. Adresy filmów i tokeny nie trafiają do komunikatów błędów.
Dostępność źródeł i wideo zależy od serwisu, sieci oraz dekodera urządzenia.

## Budowanie i sprawdzenie

JDK 17, Android SDK 35 / Build Tools 35.0.0, Python 3.11, Gradle 8.11.1.
AGP 8.9.2, Chaquopy 16.1.0, PyCryptodome 3.21.0, Media3 1.6.1, OkHttp 4.12.0.
Ustaw MK_BUILD_PYTHON, jeżeli python3.11 nie jest w PATH.

```sh
./gradlew :app:assembleRelease :app:testReleaseUnitTest :app:lintRelease
python3 -m unittest discover -s tests -q
```

APK release jest unsigned do chwili podpisania własnym kluczem apksigner.
Klucz MK jest przechowywany osobno, prywatnie; nie ma go w źródłach.
Utrzymanie tego samego podpisu jest konieczne do aktualizacji aplikacji.

Sprawdzenie wydania 0.1.0:
- Release APK zbudowany i podpisany, podpisy v2 i v3 zweryfikowane.
- 18 testów Python oraz 3 testy Java zakończone powodzeniem.
- Android Lint: zero błędów; ostrzeżenia m.in. o orientacji TV, tekstach PL
  i nowszych dostępnych wersjach zależności.
- Cztery wektory Java PoW zgodne z C, przerwanie obliczeń sprawdzone.
- Próba sieciowa bez konta: 37 kategorii, 10 filmów na pierwszej stronie,
  lista źródeł. Próba otwarcia Playera z tego środowiska otrzymała HTTP 403
  na stronie watch, dlatego nie potwierdzono tutaj odtwarzania filmu.

Testy obejmują katalog HTML, filtry, oceny, źródła, następny odcinek, stan
oglądania, nagłówki/cookies natywnego transportu i przekierowania HLS.
Cztery wektory Java PoW są zgodne z oryginalną implementacją C MK.
Fizyczna Nokia 8810 wymaga próby obrazu, dźwięku, pilota i wznowienia.
Nie deklarujemy sprawdzonego odtwarzania filmu na urządzeniu użytkownika.

GPL-3.0-only dla kodu MK i publicznych adapterów E2i. Licencje zależności
w app/src/main/assets oraz THIRD_PARTY.txt. Pochodzenie adapterów w reference/.
Baza: MK Ekino E2 0.2.7 i własny interfejs MK PremiumSmart TV 0.1.1.
