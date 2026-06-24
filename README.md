# ffmpeg_convert

Konwersja wideo i kompresja obrazów przez menu kontekstowe oraz GUI
(drag & drop).

**Wymagania:** `ffmpeg` w PATH, `python3` + `PyQt5`.

---

## Architektura

Cała logika konwersji (receptury FFmpeg) żyje w **jednym miejscu** —
pakiecie `app/` w Pythonie. Korzystają z niej wszystkie front-endy,
więc dodanie lub zmiana presetu działa od razu wszędzie
(Linux, Windows, GUI, CLI).

- **`app/presets.py`** — jedyne źródło prawdy. Buduje komendy FFmpeg
  dla każdego presetu (wideo, obrazy, sekwencja klatek → wideo).
- **`app/runner.py`** — uruchamia zadania (subprocess, przechwyt
  błędów, sprzątanie plików tymczasowych).
- **`app/cli.py`** — front-end wiersza poleceń
  (`video` / `image` / `seq` / `gui`). Wołany przez menu Nemo
  i Eksploratora.
- **`app/gui.py`** — GUI PyQt5 z drag & drop. Importuje `presets`
  + `runner`.

### Przykłady CLI

```bash
python3 app/cli.py video --preset h264 plik.mov
```

```bash
python3 app/cli.py video --preset h264size --target-mb 25 plik.mov
```

```bash
python3 app/cli.py image --quality 2 --name render *.png
```

```bash
python3 app/cli.py seq --fps 24 --format h264 klatka_*.png
```

```bash
python3 app/cli.py gui plik.mov   # otwórz GUI z wczytanym plikiem
```

---

## Linux (Nemo)

### Instalacja

```bash
git clone <url> ~/git/ffmpeg_convert
bash ~/git/ffmpeg_convert/linux/install.sh
```

Instalator zainstaluje zależności (`ffmpeg`, `zenity`,
`python3-pyqt5`), podepnie narzędzia, skopiuje akcje Nemo (rozwijając
ścieżki do bieżącego użytkownika), doda skrót **„FFmpeg Convert”**
do menu i zrestartuje Nemo.

### Menu kontekstowe Nemo

- **Konwertuj wideo (FFmpeg)** — otwiera GUI z zaznaczonym wideo.
- **Kompresuj / zmień nazwę obrazów** — otwiera GUI z zaznaczonymi
  obrazami.
- **Utwórz wideo z klatek** — Zenity (FPS + format) → wspólne CLI
  `seq`.
- **Split Image (Grid)** — podział obrazu na siatkę X×Y.
- **Make Flipbook (Spritesheet)** — spritesheet z zaznaczonych klatek.

### Aplikacja GUI

Okno z drag & drop dla obrazów i wideo: automatyczne rozpoznanie typu
plików, wszystkie presety, podgląd nazw na żywo, log i pasek postępu.

```bash
python3 ~/git/ffmpeg_convert/app/gui.py
```

---

## Windows (menu kontekstowe Eksploratora)

### Instalacja

1. Zainstaluj **Python 3** (z dodaniem do PATH) i **PyQt5**:
   `pip install PyQt5`. Upewnij się, że `ffmpeg.exe` jest w PATH
   (po dodaniu do zmiennych środowiskowych wymagany jest restart,
   żeby Eksplorator wczytał nowy PATH).
2. Skopiuj folder `app\` do `%USERPROFILE%\scripts\app\`
   (czyli `C:\Users\<TwojaNazwa>\scripts\app\`).
3. Uruchom **`win\install.bat`** — rejestruje pozycje menu z typem
   `REG_EXPAND_SZ`, więc `%USERPROFILE%` rozwija się dla każdego
   użytkownika bez edycji skryptu. Wideo przypinane jest do konkretnych
   rozszerzeń (`.mp4` / `.mov` / `.mkv`), a nie do ogólnej kategorii
   `video` (tej bywa wypinanej przez zewnętrzne odtwarzacze).
4. Kliknij prawym na plik wideo lub obraz → **Konwertuj … (FFmpeg)…**
   — otworzy się GUI. (Eksplorator może wymagać restartu, aby pokazać
   nowe wpisy.)

Odinstalowanie: `win\uninstall.bat`.

> Uwaga techniczna: nie używamy pliku `.reg` do dwukliku, bo klasyczne
> wartości `REG_SZ` nie rozwijają zmiennych środowiskowych — system
> szukałby dosłownie folderu `%USERPROFILE%`. `install.bat` używa
> `REG_EXPAND_SZ`, co rozwiązuje ten problem.

### Aktualizacja

Nadpisz folder `scripts\app\` nową wersją z repozytorium
(`install.bat` ponawiać nie trzeba — wpisy rejestru wskazują na ten
sam folder).

---

## Presety wideo

- **MP4 H.264 (CRF 18)** — wysoka jakość, dobra kompatybilność.
- **MP4 H.264 (kontrola rozmiaru)** — CRF lub docelowy rozmiar w MB
  (2 przebiegi).
- **MP4 H.265 / HEVC (CRF 23)** — mniejszy rozmiar niż H.264.
- **DNxHD 1080p (120 Mb/s)** — edycja, format Avid.
- **DNxHR HQ** — edycja, format Avid (dowolna rozdzielczość).
- **ProRes 422 HQ** — edycja, format Apple.
- **Cineform Q4 (10-bit)** — edycja, format GoPro.
- **Ostatnia klatka PNG** — wyciągnięcie ostatniej klatki.
- **Eksport klatek (+ WAV)** — sekwencja klatek (PNG/JPG/EXR)
  i opcjonalnie audio.