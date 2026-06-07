# ffmpeg_convert

Skrypty do konwersji wideo i kompresji obrazów przez menu kontekstowe.

**Wymagania:** `ffmpeg` zainstalowany i dostępny w PATH.

---

## Linux (Nemo)

### Instalacja

```bash
# 1. Sklonuj repozytorium
git clone <url> ~/git/ffmpeg_convert

# 2. Uruchom skrypt instalacyjny
bash ~/git/ffmpeg_convert/linux/install.sh
```

Skrypt automatycznie zainstaluje brakujące zależności (`ffmpeg`, `zenity`), stworzy symlinki w `~/.local/bin/`, skopiuje akcje Nemo i zrestartuje menedżer plików.

Dzięki symlinkowi każda zmiana w repozytorium jest od razu widoczna w systemie — bez ponownej instalacji.

### Skrypty

| Plik | Opis |
|------|------|
| `convert_video.sh` | Konwersja wideo (H.264, H.265, DNxHD, ProRes, klatki, WAV) |
| `compress_images.sh` | Kompresja PNG → JPG (wybór jakości Q2/Q5/Q10) |

---

## Windows (menu kontekstowe Eksploratora)

### Instalacja

1. Skopiuj `convert_video.ps1` do folderu `C:\Users\<TwojaNazwa>\scripts\`
   - Utwórz folder `scripts` jeśli nie istnieje
2. Kliknij dwukrotnie `convert_menu.reg` → potwierdź dodanie do rejestru
3. Gotowe — kliknij prawym przyciskiem na plik wideo → **Konwertuj wideo ▶**

### Aktualizacja skryptu

Nadpisz `convert_video.ps1` w folderze `scripts\` nową wersją z repozytorium.

### Presety dostępne w menu

| Preset | Opis |
|--------|------|
| MP4 H.264 (CRF 18) | Wysoka jakość, dobra kompatybilność |
| MP4 H.265 / HEVC (CRF 23) | Mniejszy rozmiar niż H.264 |
| DNxHD 1080p (120 Mb/s) | Edycja — format Avid |
| DNxHR HQ 4K | Edycja 4K — format Avid |
| ProRes 422 HQ | Edycja — format Apple |
| Cineform Q4 (10-bit) | Edycja — format GoPro |
| Klatki PNG / JPEG / EXR | Eksport sekwencji klatek |
| Ostatnia klatka PNG | Wyciągnięcie ostatniej klatki |
| Eksport klatek + WAV | Sekwencja klatek i audio osobno |
| Wybierz z GUI… | Interaktywny wybór presetu |
