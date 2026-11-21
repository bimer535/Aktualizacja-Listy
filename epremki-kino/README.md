# Aktualizacje Epremki kino

Windows od 0.6.12 i Android od 1.0.4 sprawdzają plik `epremki-kino/update.json` na gałęzi main po wybraniu „Sprawdź aktualizację”.

1. Zbuduj nową wersję. Dla Androida zwiększ versionCode i podpisz APK tym samym kluczem.
2. W GitHub Releases opublikuj osobny tag dla platformy. Dla Windows użyj `epremki-pc-X.Y.Z` z plikiem `Epremki_kino_PC_X.Y.Z.exe`. Dla Androida użyj `epremki-android-X.Y.Z` z plikiem `Epremki_kino_Android_X.Y.Z.apk`.
3. Po opublikowaniu sprawdź pobieranie pliku i wylicz SHA-256. Zaktualizuj tylko odpowiednią sekcję update.json, wpisując wersję, sumę SHA-256 małymi literami oraz dla Androida rzeczywisty versionCode.
4. Uruchom sprawdzanie w poprzedniej wersji Epremki i przetestuj instalację. Windows wymaga możliwości zapisu w folderze przenośnego EXE, a Android potwierdzenia instalacji przez system.

Repozytorium zawiera konfigurację wydań. Użytkownik importuje prywatne playlisty na własnym urządzeniu.
