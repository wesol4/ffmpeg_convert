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

Uruchom **`win\setup.bat`** (dwukrotne kliknięcie, działa na „gołym”
Windowsie 11, bez wymagań wstępnych). Menu instalatora:

- **1) Sprawdź zależności** — raport: Python, PyQt5, ffmpeg
  (obecne / brak).
- **2) Zainstaluj brakujące** — najpierw `winget`, a gdy go brak lub
  zawiedzie — fallback na ręczne pobranie (`curl`) i instalację.
  Instaluje Pythona (per-user, z dopisaniem do PATH), `pip install
  PyQt5` oraz ffmpeg (rozpakowanie zip + dopisanie `bin` do user PATH).
  Wszystko bez uprawnień administratora.
- **3) Skopiuj `app\`** — do `%USERPROFILE%\scripts\app\`
  (źródłem jest folder `app\` z repo, obok `win\`).
- **4) Dodaj menu kontekstowe** — rejestruje pozycje z typem
  `REG_EXPAND_SZ`, więc `%USERPROFILE%` rozwija się w locie dla każdego
  użytkownika. Wideo przypinane jest do konkretnych rozszerzeń
  (`.mp4` / `.mov` / `.mkv`), a nie do ogólnej kategorii `video`
  (tej bywa wypinanej przez zewnętrzne odtwarzacze).
- **5) Usuń menu kontekstowe** — odwraca wpisy z punktu 4.

Na czystym systemie: wybierz kolejno **2 → 3 → 4**, po czym kliknij
prawym na plik wideo lub obraz → **Konwertuj … (FFmpeg)…** (Eksplorator
może wymagać restartu / wylogowania, aby zobaczyć nowy PATH i menu).

> Uwaga techniczna: instalatorem jest `.bat`, a nie `.reg`, bo klasyczne
> wartości `REG_SZ` nie rozwijają zmiennych środowiskowych — system
> szukałby dosłownie folderu `%USERPROFILE%`. `setup.bat` używa
> `REG_EXPAND_SZ`, co rozwiązuje ten problem.

### Aktualizacja

Nadpisz folder `scripts\app\` nową wersją z repozytorium, po czym w
`win\setup.bat` wybierz ponownie **3** (i ewentualnie **4** — wpisy
rejestru wskazują na ten sam folder, więc zwykle nie trzeba).

---

## Testy

Testy rdzenia (`app/presets/`, `app/runner.py`) w `tests/` — `unittest`
(stdlib, bez zależności); `runner` testowany na realnym `ffmpeg`. CI
(GitHub Actions) uruchamia `ruff` + `mypy` + `pytest` przy każdym
pushu/PR do mastera (`.github/workflows/ci.yml`).

[![CI](https://github.com/wesol4/ffmpeg_convert/actions/workflows/ci.yml/badge.svg)](https://github.com/wesol4/ffmpeg_convert/actions/workflows/ci.yml)

```bash
ruff check . && mypy app && pytest -q          # to, co odpala CI
python3 -m unittest discover -s tests -v        # lokalnie bez zależności
```

---

## Presety wideo

- **MP4 H.264 (CRF 18)** — wysoka jakość, dobra kompatybilność.
- **MP4 H.264 (kontrola rozmiaru)** — CRF lub docelowy rozmiar w MB
  (2 przebiegi).
- **MP4 H.265 / HEVC (CRF 23)** — mniejszy rozmiar niż H.264.

### Enkodery sprzętowe (GPU)

Dla **H.264 / H.265** (i „kontroli rozmiaru" w trybie CRF) można wybrać
enkoder: `cpu` (domyślnie, libx264/libx265), `nvenc` (NVIDIA),
`qsv` (Intel QuickSync), `amf` (AMD) — 10–30× szybsza konwersja. Dostępne
opcje są filtrowane przez `ffmpeg -encoders` (CPU zawsze). CLI: `--encoder`;
GUI: lista „Enkoder wideo" (ukryta dla kodeków montażowych CPU-only).
Tryb docelowego rozmiaru MB zawsze używa CPU 2-pass (precyzja rozmiaru).

```bash
python3 app/cli.py video --preset h264 --encoder nvenc plik.mov
```
- **DNxHD 1080p (120 Mb/s)** — edycja, format Avid.
- **DNxHR HQ** — edycja, format Avid (dowolna rozdzielczość).
- **ProRes 422 HQ** — edycja, format Apple.
- **Cineform Q4 (10-bit)** — edycja, format GoPro.
- **Ostatnia klatka PNG** — wyciągnięcie ostatniej klatki.
- **Eksport klatek (+ WAV)** — sekwencja klatek (PNG/JPG/EXR)
  i opcjonalnie audio.