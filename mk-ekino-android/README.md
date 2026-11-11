# MK Kino 0.6.2

Aktualna wersja: **0.6.2**, numer kompilacji **16**, pakiet `pl.mk.ekino.tv`.

Grafika banera jest dopasowana proporcjonalnie do górnego obszaru ekranu, bez przycinania CENTER_CROP, rozciągania i przyciemniających nakładek. Osobny loader zachowuje więcej szczegółów niż miniatury plakatów. Przy braku panoramy wyświetlany jest cały pionowy plakat. Pozostaje rotacja do 12 slajdów co 5 sekund.

Sezony i odcinki mają kompaktowe wiersze wyboru. Stała szerokość plakatów zapobiega rozciąganiu pojedynczego wyniku na całą szerokość ekranu. Powiększana jest tylko grafika zaznaczenia; podpisy przy lewej krawędzi pozostają na miejscu.

## Aktualizacja

Wybierz **MENU → Sprawdź aktualizację → Pobierz**, a następnie zatwierdź instalację w Androidzie. Instaluj na obecną aplikację, bez jej odinstalowywania. Nazwy części zachowują wzór wymagany przez dotychczasowy aktualizator: `MK_Ekino_TV_0.6.2.apk.partNNN`.

Sprawdzono kompilację Android API 35/D8, 36 testów z regresjami geometrii siatki i próbkowania obrazu, podpis APK v2 i zgodność certyfikatu oraz integralność paczki. Biblioteki odtwarzania i pakiet Pythona pozostały niezmienione. Rozmiar APK: 37985823 bajtów, SHA-256: `cf5385a5731c900f42ffb734f14d63353ca92826726f145f583c8887241f28c8`. Nie wykonano testu wizualnego ani odtwarzania na fizycznym Android TV.

[Opis zmian 0.6.2](RELEASE_0.6.2.md). Kontakt: bimer535@wp.pl.

---

## Dokumentacja poprzednich wydań

# MK Kino 0.6.1

Aktualna wersja: **0.6.1**, numer kompilacji **15**, pakiet `pl.mk.ekino.tv`.

Poprawiono rysowanie przewijanych kafelków i opisów pod menu oraz filtrami, równą poświatę wokół zaznaczenia i podwójny rocznik na plakatach. Nie przenoszono interfejsu aplikacji PremiumSmart.

## Aktualizacja

Wybierz **MENU → Sprawdź aktualizację → Pobierz**, potem potwierdź instalację w Androidzie. Nie odinstalowuj poprzedniej wersji. Serwer używa nazw `MK_Ekino_TV_0.6.1.apk.partNNN`, wymaganych przez dotychczasowy aktualizator. Wcześniejszy błąd sprawdzania wersji 0.6.0 powodowały niezgodne nazwy plików; poprawiono je również dla tamtego wydania.

Sprawdzono 36 testów, kompilację Android API 35/D8, podpis APK v2 i zgodność certyfikatu, integralność ZIP i niezmienność bibliotek odtwarzania. Rozmiar APK: 37982227 bajtów, SHA-256: `d12389706af6d799c1bd247cc4d671c802cf8b913966a514b0993784676dd57b`. Nie wykonano testu wizualnego ani odtwarzania na fizycznym Android TV.

[Opis zmian 0.6.1](RELEASE_0.6.1.md). Kontakt: bimer535@wp.pl.

---

## Dokumentacja poprzednich wydań

# MK Kino 0.6.0

Aktualna wersja: **0.6.0**, numer kompilacji **14**, pakiet `pl.mk.ekino.tv`.

Nowy wygląd z niebieskim neonem: grafika na pełnym ekranie, baner zmieniany co 5 sekund, przewijane półki kategorii, odświeżony wybór źródeł i niebieskie akcenty odtwarzacza. Zachowany anonimowy katalog bez logowania.

## Aktualizacja

W aplikacji wybierz **MENU → Sprawdź aktualizację → Pobierz** lub użyj niebieskiego przycisku pilota. Wersje obsługujące sprawdzanie przy starcie mogą również wyświetlić propozycję aktualizacji po uruchomieniu.

Aplikacja pobiera i łączy 58 części APK, sprawdza ich rozmiary i sumy SHA-256 oraz podpis instalatora. Instalację zatwierdź w systemie Android. Instaluj na obecną aplikację, bez jej odinstalowywania, aby zachować dane.

Sprawdzono integralność ZIP i podpis APK v2, zgodność certyfikatu z wydaniem 0.3.1, identyfikator pakietu oraz numer wersji. APK ma 37982320 bajtów, SHA-256: `b4349c0ca8591e0c0bd83787a447f29c5d01d3a662b9662b8be36f3ac90351e2`. Testu na fizycznym Android TV nie wykonano.

[Opis zmian](RELEASE_0.6.0.md)

Kontakt: bimer535@wp.pl.

---

## Dokumentacja wcześniejszych wydań

# MK Kino 0.3.1

Aktualna wersja: **0.3.1**, numer kompilacji **10**, pakiet `pl.mk.ekino.tv`.

## Oceny Filmweb

Oceny eKino są wyłączone, również przy wczytywaniu starszych ulubionych. Nowe oceny pochodzą wyłącznie z Filmwebu: średnia użytkowników oraz liczba głosów. Dopasowanie sprawdza tytuł lub tytuł oryginalny, dokładny rok i typ produkcji. Niejednoznaczne wyniki pozostają bez oceny.

Oceny są pobierane w tle i zapisywane lokalnie. Kafelki oraz panel opisu uzupełniają wynik bez przeładowania strony i zmiany zaznaczenia. Niedostępność Filmwebu nie blokuje katalogu. Działanie nowego interfejsu pilotem wymaga jeszcze sprawdzenia na fizycznym Android TV.

Walidacja: 25 testów lokalnych, prawidłowe dopasowanie i pobranie ocen dla 13 rzeczywistych filmów (w tym różnych roczników Diuny), odrzucenie niezgodnego rocznika, weryfikacja podpisu APK i niezmienionych bibliotek odtwarzania.

## Aktualizacja

W MK Kino wybierz **MENU → Sprawdź aktualizację** lub naciśnij **niebieski przycisk** pilota. Aplikacja pobierze i połączy 57 części, zweryfikuje sumy SHA-256 i podpis, a następnie otworzy instalator Androida. Instaluj na obecną aplikację bez odinstalowywania, aby zachować dane.

[Źródła wersji 0.3.1](packages/MK_Kino_Android_TV_0.3.1_SOURCE.zip). Instrukcja budowania znajduje się w README archiwum. Klucz podpisujący jest przechowywany osobno i nie jest publikowany.

Kontakt: bimer535@wp.pl.

---

## Wcześniejsze wydania

# MK Kino 0.3.0

Aktualna wersja na Android TV: **0.3.0**, numer kompilacji **9**, pakiet `pl.mk.ekino.tv`.

## Aktualizacja

W MK Kino wybierz **MENU → Sprawdź aktualizację** lub użyj **niebieskiego przycisku** pilota. Aplikacja pobierze i połączy 54 części APK oraz sprawdzi ich rozmiary, sumy SHA-256 i podpis instalatora. Zatwierdź instalację w Androidzie. Instaluj na obecną aplikację, bez jej odinstalowywania, aby zachować dane.

## Nowe filtry filmów

Cztery niezależne przyciski: **Gatunek**, **Język**, **Rok**, **Sortowanie**. Ustawienia są zapisywane; zmiana jednego filtra nie zeruje pozostałych. Gatunek, język i rok dotyczą obu katalogów. Sortowanie A–Z i według rocznika porządkuje aktualnie pobraną stronę. Filtr roku zawęża cały katalog.

Sprawdzone: 8 testów logiki katalogów i filtrów, podpis APK, zgodność spakowanych modułów ze źródłami. Obsługa nowego paska pilotem wymaga jeszcze sprawdzenia na fizycznym Android TV.

Kontakt: bimer535@wp.pl.

---

## Historia i opis wcześniejszych wydań

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
- Informacje i kontakt MK: bimer535@wp.pl.

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
