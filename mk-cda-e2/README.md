# MK CDA E2 0.1.0

Osobna wtyczka Enigma2 / Python 3 dla OpenATV 7.x, przygotowana przez MK.
Pakiet: enigma2-plugin-extensions-mkcdae2. Katalog: MKCDAE2.
Nie wymaga E2iPlayera ani pozostałych wtyczek MK.

## Co zawiera

- Domyślnie darmowy katalog CDA, bez konta: filmy, polskie kino, gatunki,
  nowości, sortowanie po ocenie IMDb, dacie premiery i popularności.
- Osobny katalog CDA Premium i wszystkie filmy; płatne tytuły nie stają się
  darmowe po wybraniu tej kategorii. Filtr „Tylko darmowe” pozostaje aktywny
  również przy przechodzeniu na kolejne strony.
- Wyszukiwanie długich materiałów w CDA, historia, ulubione, wznawianie,
  okładki, lista i kafelki. Wyniki wyszukiwania mogą obejmować materiały płatne.
- Odtwarzanie progresywnego MP4 lub HLS przez lokalny przekaźnik i natywny
  odtwarzacz Enigmy. Wybór filmu otwiera pozycję CDA; kolejne OK uruchamia
  pobranie wariantu. Domyślnie wybierana jest najlepsza jakość; ręczny wybór w MENU.
- OK podczas filmu: pauza/wznów. EXIT: zakończ i wróć do wtyczki.
- Żółty: lista/kafelki. Zielony: wyszukaj. Niebieski: aktualizacja.
- MENU: opcje, ulubione, konto CDA, kontakt MK (bimer55@wp.pl).
- Ikona: oryginalne logo CDA, z małym dopiskiem MK; zachowane proporcje.
  Źródło: https://scdn2.cda.pl/img/icon/favicon/favicon-cda-512.svg
  Edytowalny plik reference/cda-mk.svg; instalowana ikona src/MKCDAE2/icon.png.
  Logo CDA należy do CDA; wtyczka jest niezależnym projektem MK.

Ocena IMDb służy do sortowania katalogu przez serwis. Karty filmów nie pokazują
zmyślonych ocen, jeśli strona katalogu nie podaje wartości liczbowej.
Sekcja seriali korzysta z katalogu CDA; osobna nawigacja po sezonach i automatyczny
następny odcinek nie zostały wdrożone w tym wydaniu.

## Opcjonalne logowanie

MENU → Konto CDA → Zaloguj własne konto. Login i maskowane hasło wpisuje się
na dekoderze. Hasło nie jest zapisywane w ustawieniach, raportach ani historii.
Tymczasowe żądanie 0600 jest usuwane przez proces roboczy przed połączeniem.
Sesja trafia do /etc/mk-cda-e2/session.cookies z uprawnieniami 0600.
Stan konta: /etc/mk-cda-e2/account.json, również 0600, bez loginu i hasła.
Wylogowanie usuwa lokalną sesję. Nie udostępniaj pliku sesji innym osobom.

Przepływ logowania sprawdzono testami z przykładowymi odpowiedziami. Nie został
jeszcze potwierdzony na prawdziwym koncie Premium. Jeśli CDA zażąda CAPTCHA
lub weryfikacji przeglądarki, wtyczka wyświetli odpowiedni komunikat. Nie zawiera
obsługi tego etapu. Filmów wymagających DRM ta wersja nie odtwarza, również po
zalogowaniu. Dostępność materiałów może zależeć od kraju i praw do tytułu.

## Instalacja

Pobierz MK_CDA_E2_0.1.0.ipk do /tmp dekodera, następnie:

```sh
opkg update
opkg install /tmp/MK_CDA_E2_0.1.0.ipk
```

Uruchom ponownie interfejs Enigma2. Zależności z feedu: enigma2, python3-core,
python3-html, python3-pillow. Pillow konwertuje okładki WebP na JPEG dla ePicLoad.
Nie trzeba instalować kompilatorów ani pełnego E2i. OpenATV 6.4 / Python 2 nie
jest obsługiwany. Dane biblioteki: /etc/mk-cda-e2/library.json i history.json.
Aktualizacje: https://raw.githubusercontent.com/bimer535/Aktualizacja-Listy/main/mk-cda-e2/update.json

## Walidacja 23.10.2026

41 testów lokalnych: interfejs OpenATV, sterowanie pilotem, katalog i filtry,
paginacja, dekodowanie URL, wybór jakości, logowanie i ochrona danych, aktualizator.
Na żywo, bez logowania: 22 darmowe filmy na pierwszej stronie listy nowości,
22 na kolejnej stronie, bez powtórzeń; 34 pozycje menu gatunków.
Potwierdzono konwersję okładki WebP na JPEG.
Dla darmowego filmu „Zdążyć przed ciszą” pobrano warianty 1080p/720p/480p/360p
oraz próbkę MP4: HTTP 206, video/mp4, prawidłowa sygnatura ftyp.
Potwierdzenie bajtów wideo nie jest testem obrazu i dźwięku na rzeczywistym SF8008.

Diagnostyka na dekoderze (bez ujawniania adresów strumieni lub sesji):

```sh
wget -O /tmp/mk_cda_probe.py https://raw.githubusercontent.com/bimer535/Aktualizacja-Listy/main/mk-cda-e2/tools/probe.py
python3 /tmp/mk_cda_probe.py --media
```

Raport: /tmp/mk_cda_probe.json. Opcjonalnie --url https://www.cda.pl/video/ID.

## Kod i licencja

GPL-3.0; LICENSE i NOTICE.txt w pakiecie. Publiczna baza: hostcdapl.py i metoda
parserCDA z e2iplayer-2026.10.18.05. Oryginały i pochodzenie w reference/.
Samodzielny interfejs i elementy MK na bazie MK PremiumSmart E2 0.1.1.
Nie czyta kont, sesji ani kodu prywatnego E2i.
Źródła w sąsiednim pliku MK_CDA_E2_0.1.0_source.zip.

Budowanie: python3 tools/build_ipk.py. Testy: python3 -m unittest discover -s tests -q.
