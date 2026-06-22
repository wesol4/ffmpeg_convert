# ffmpeg_convert

Konwersja wideo i kompresja obrazów przez menu kontekstowe oraz GUI (drag & drop).

**Wymagania:** `ffmpeg` w PATH, `python3` + `PyQt5`.

## Architektura

Cała logika konwersji (receptury FFmpeg) żyje w **jednym miejscu** — pakiecie
`app/` w Pythonie. Korzystają z niej wszystkie front-endy, więc dodanie czy
zmiana presetu działa od razu wszędzie (Linux, Windows, GUI, CLI).

| Plik | Rola |
|------|------|
| `app/presets.py` | **Jedyne źródło prawdy** — buduje komendy FFmpeg dla każdego presetu (wideo, obrazy, sekwencja klatek → wideo). |
| `app/runner.py` | Uruchamia zadania (subprocess, przechwyt błędów, sprzątanie plików tymczasowych). |
| `app/cli.py` | Front-end wiersza poleceń (`video` / `image` / `seq` / `gui`). Wołany przez menu Nemo i Eksploratora. |
| `app/gui.py` | GUI PyQt5 z drag & drop. Importuje `presets` + `runner`. |

```bash
# przykłady CLI
python3 app/cli.py video --preset h264 plik.mov
python3 app/cli.py video --preset h264size --target-mb 25 plik.mov
python3 app/cli.py image --quality 2 --name render *.png
python3 app/cli.py seq   --fps 24 --format h264 klatka_*.png
python3 app/cli.py gui   plik.mov          # otwórz GUI z wczytanym plikiem
```

---

## Linux (Nemo)

### Instalacja

```bash
git clone <url> ~/git/ffmpeg_convert
bash ~/git/ffmpeg_convert/linux/install.sh
```

Instalator zainstaluje zależności (`ffmpeg`, `zenity`, `python3-pyqt5`), podepnie
narzędzia, skopiuje akcje Nemo (rozwijając ścieżki do bieżącego użytkownika),
doda skrót **„FFmpeg Convert”** do menu i zrestartuje Nemo.

### Menu kontekstowe Nemo

| Akcja | Co robi |
|-------|---------|
| Konwertuj wideo (FFmpeg) | Otwiera GUI z zaznaczonym wideo |
| Kompresuj / zmień nazwę obrazów | Otwiera GUI z zaznaczonymi obrazami |
| Utwórz wideo z klatek | Zenity (FPS + format) → wspólne CLI `seq` |
| Split Image (Grid) | Podział obrazu na siatkę X×Y |
| Make Flipbook (Spritesheet) | Spritesheet z zaznaczonych klatek |

### Aplikacja GUI

Okno z drag & drop dla obrazów i wideo: automatyczne rozpoznanie typu plików,
wszystkie presety, podgląd nazw na żywo, log i pasek postępu. Uruchomienie:

```bash
python3 ~/git/ffmpeg_convert/app/gui.py
```

---

## Windows (menu kontekstowe Eksploratora)

### Instalacja

1. Zainstaluj **Python 3** (z dodaniem do PATH) i **PyQt5**: `pip install PyQt5`.
   Upewnij się, że `ffmpeg.exe` jest w PATH.
2. Skopiuj folder `app\` do `C:\Users\<TwojaNazwa>\scripts\app\`.
3. Kliknij dwukrotnie `win\convert_menu.reg` → potwierdź dodanie do rejestru.
4. Kliknij prawym na plik wideo lub obraz → **Konwertuj … (FFmpeg)…** — otworzy się GUI.

### Aktualizacja

Nadpisz folder `scripts\app\` nową wersją z repozytorium.

---

## Presety wideo

| Preset | Opis |
|--------|------|
| MP4 H.264 (CRF 18) | Wysoka jakość, dobra kompatybilność |
| MP4 H.264 (kontrola rozmiaru) | CRF lub docelowy rozmiar w MB (2 przebiegi) |
| MP4 H.265 / HEVC (CRF 23) | Mniejszy rozmiar niż H.264 |
| DNxHD 1080p (120 Mb/s) | Edycja — format Avid |
| DNxHR HQ | Edycja — format Avid (dowolna rozdzielczość) |
| ProRes 422 HQ | Edycja — format Apple |
| Cineform Q4 (10-bit) | Edycja — format GoPro |
| Ostatnia klatka PNG | Wyciągnięcie ostatniej klatki |
| Eksport klatek (+ WAV) | Sekwencja klatek (PNG/JPG/EXR) i opcjonalnie audio |
