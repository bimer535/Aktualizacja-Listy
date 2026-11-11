# MK Kino Android TV 0.6.2

- Grafika 12 slajdów na głównej mieści się proporcjonalnie w górnym obszarze ekranu: bez rozciągania i bez kadrowania CENTER_CROP.
- Zdjęcie jest wyświetlane bez przyciemniających nakładek i oddzielnie od tekstu. Nowy loader zachowuje szczegóły obrazów do Full HD, zamiast pomniejszać je do miniatur plakatów.
- Przy braku panoramy pokazywany jest cały pionowy plakat. Jakość zależy też od obrazu dostarczonego przez katalog.
- Sezony i odcinki mają zwięzłe wiersze z pełnymi podpisami. Pojedynczy sezon nie rozciąga zdjęcia na całą szerokość ekranu.
- Stała szerokość plakatów także przy 1–4 wynikach wyszukiwania i w ostatnim rzędzie.
- Powiększana jest tylko grafika zaznaczenia, a nie tekst: podpisy przy lewej krawędzi pozostają w swoich granicach.
- Zachowano rotację co 5 sekund, filtry, podpis aplikacji i aktualizator.

Pakiet pl.mk.ekino.tv, versionCode 16. Instalacja na obecną aplikację.
Sprawdzono kompilację, testy logiki, geometrię siatki i próbkowanie grafiki, podpis APK i integralność paczki.
Nie wykonano testu wizualnego ani odtwarzania na fizycznym Android TV.
