# ffmpeg_convert

Konwersja wideo i kompresja obrazów przez menu kontekstowe oraz GUI
(drag & drop).

**Wymagania:** FFmpeg + ffprobe, Python 3.12 i PyQt5 (instalator Windows przygotowuje je automatycznie).

---

## Architektura

Cała logika konwersji (receptury FFmpeg) żyje w **jednym miejscu** —
pakiecie `app/` w Pythonie. Korzystają z niej wszystkie front-endy,
więc dodanie lub zmiana presetu działa od razu wszędzie
(Linux, Windows, GUI, CLI).

- **`app/presets/`** — jedyne źródło prawdy. Pakiet: `video.py`,
  `image.py`, `sequence.py` budują komendy FFmpeg; `core/` (`jobs`,
  `ffmpeg`, `probe`) trzyma model `Job`, stałe i detekcję.
- **`app/config.py`** — typowana konfiguracja (frozen dataclass `CONFIG`):
  CRF, preset, pix_fmt, audio bitrate, enkodery, zakres h264size, skala
  obrazów, fps. Tunable w jednym miejscu; presety/CLI/GUI czytają z `CONFIG`.
- **`app/log.py`** — logging diagnostyczny: dzienny plik
  `…/ffmpeg_convert/logs/YYYY-MM-DD.log` (`XDG_CACHE_HOME`/`Caches`/
  `%LOCALAPPDATA%`). UI-log (widget GUI / stdout CLI) nienaruszony.
- **`app/update.py`** — sprawdzanie aktualizacji (GitHub `releases/latest`,
  stdlib `urllib`); CLI `update`, GUI Pomoc → Sprawdź aktualizacje…
  Wymaga opublikowanego release'u/tagu; bez cichego auto-pull (tylko powiadomienie).
  Wersja: `app.__version__`.
- **`app/runner.py`** — uruchamia zadania (subprocess, stream stderr,
  realny postęp, przechwyt błędów, sprzątanie).
- **`app/cli.py`** — front-end wiersza poleceń
  (`video` / `image` / `seq` / `split` / `flipbook` / `gui`).
- **`app/gui.py`** — entry-point GUI (uruchamialny jako skrypt:
  `python app/gui.py` / `pythonw …\app\gui.py` z menu Windows).
  Interfejs rozbity na `app/gui_*.py`: `gui_main_window`, `gui_panels`,
  `gui_widgets`, `gui_workers`, `gui_style`.

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

## Windows 10/11 x64

Pobierz **całe repozytorium**, rozpakuj je i uruchom **`win\setup.vbs`**.
Instalator otwiera zwykłe okno Windows: przyciski, wskaźnik pracy i szczegóły błędów.
Przycisk **Zainstaluj / aktualizuj** przygotowuje również Python 3.12 64-bit przez
`winget`, jeśli go brakuje. Nie trzeba mieć Pythona, żeby otworzyć okno instalatora. Gdy `winget` jest niedostępny, zainstaluj App Installer ze sklepu
Microsoft lub Python 3.12 ręcznie z python.org i uruchom instalator ponownie.

W oknie instalatora dostępne są przyciski:

1. **Zainstaluj / aktualizuj** — sprawdza FFmpeg i ffprobe, instaluje brakujące
   narzędzia przez `winget`, tworzy własne środowisko z PyQt5, kopiuje aplikację,
   dodaje skrót do menu Start i menu kontekstowe plików oraz folderów.
2. **Uruchom aplikację**.
3. **Zainstaluj separację audio** — opcjonalny lokalny model; kilka GB miejsca.
   Można też wybrać separację w aplikacji, aby zainstalować model przy pierwszym użyciu.
4. **Usuń menu kontekstowe** — aplikacja i model pozostają na dysku.
5. **Diagnostyka** — pokazuje używany interpreter, narzędzia i stan PyQt5.
6. **Zamknij** — aktywny po zakończeniu operacji.

Długie operacje działają w tle, a ich komunikaty trafiają do pola szczegółów.
Przycisk **Kopiuj szczegóły** ułatwia przekazanie błędu. `setup.bat` pozostaje
zgodnym wstecznie skrótem; aby nie pojawiła się nawet krótko konsola, użyj `setup.vbs`.
Jeśli firma blokuje Windows Script Host, można uruchomić `setup.ps1` przez PowerShell.
Polityka wykonywania jest ustawiana tylko dla procesu instalatora, bez trwałych zmian systemu.

Instalacja jest dla bieżącego użytkownika w `%LOCALAPPDATA%\FFmpegConvert`.
Środowisko aplikacji i model są niezależne od systemowego PyQt5.
Zapisane ścieżki do Pythona, FFmpeg i ffprobe pozwalają uruchamiać skrót również
z Eksploratora, który nie odświeżył jeszcze PATH.

Na Windows 11 pozycja **FFmpeg Convert…** może być pod **Pokaż więcej opcji**.
Menu obejmuje filmy, PNG/JPG/EXR/TIFF/WebP i foldery sekwencji. Wybierz jedną
klatkę, aby wykryć całą sekwencję; wiele plików dodaj wewnątrz aplikacji lub
przeciągnij na jej okno. Klipy, audio i brakujące klatki obsługuje ten sam rdzeń co na Linuxie.

### Aktualizacja starszej instalacji

Pobierz nową kopię repozytorium, zamknij aplikację i kliknij **Zainstaluj / aktualizuj** w `win\setup.vbs`.
Instalator podmieni komplet modułów aplikacji, zachowując lokalny model audio.
Stare wpisy menu wskazujące `scripts\app\gui.py` zostaną zastąpione nowymi.
Stary folder `%USERPROFILE%\scripts\app` nie jest usuwany.
Przy błędzie uruchomienia pojawi się komunikat z lokalizacją logu.

### Sprawdzanie na Windows

```powershell
py -3.12 -m pip install pytest ruff mypy PyQt5==5.15.11
py -3.12 -m pytest -q
py -3.12 -m ruff check .
py -3.12 -m mypy app
```

CI ma osobne zadania Linux/Windows. Testy Windows obejmują m.in. wpisy rejestru
w izolowanym kluczu testowym i uruchomienie GUI przez `pythonw.exe`.

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

## Separacja głosu, muzyki i efektów

W zakładce wideo wybierz **Separacja audio — głos / muzyka / SFX**, dodaj film
i uruchom konwersję. Bandit v2 multilingual (ELUATE 0.0.3) działa lokalnie na CPU;
nie wysyła filmu i nie zużywa kredytów. Pierwsze uruchomienie automatycznie instaluje
biblioteki oraz model w `.audio-runtime/` obok aplikacji. Wymaga internetu,
kilku GB wolnego miejsca, Pythona 3.12 z `venv` i zapisu w katalogu aplikacji.
Kolejne uruchomienia działają offline. Istniejące konwersje nie wymagają tego modelu.

```sh
python3 app/cli.py audio-setup  # opcjonalna instalacja przed pierwszym użyciem
python3 app/cli.py video --preset audio_separate film.mp4
```

Wyniki trafiają obok źródła do `film_AUDIO/` (następnie `_002`, `_003`, bez nadpisywania):

- `speech.wav` — głos;
- `music.wav` — muzyka;
- `sfx.wav` — efekty;
- `background_no_dialogue.wav` — muzyka i efekty bez głosu;
- `video_without_dialogue.mkv` — obraz kopiowany bez rekompresji, tło bez głosu;
- `report.json` — model, czas przetwarzania, koszt: 0 kredytów.

WAV: stereo 48 kHz / 24 bit. Separowana jest pierwsza ścieżka audio filmu.
W edytorze wycisz oryginalny dźwięk, ustaw `background_no_dialogue.wav` na początku
filmu i dodaj nowego lektora na osobnej ścieżce. Do samych efektów użyj `sfx.wav`.
Skuteczność separacji zależy od nagrania; możliwe są resztki mowy lub utrata części efektów.
Długie nagrania wymagają więcej RAM (model wczytuje całe audio wejściowe).

Model: [Bandit v2 multilingual](https://zenodo.org/records/12701995).
Suma SHA-256 modelu jest sprawdzana przed wczytaniem. Wersje PyTorch 2.6.0 i ELUATE
0.0.3 są przypięte, ponieważ eksport trzech ścieżek korzysta z wewnętrznego API ELUATE.
Po błędzie instalację można ponowić; po awaryjnym zamknięciu procesu usuń pozostały
`.audio-runtime/install.lock`, upewniając się, że żadna instalacja już nie trwa.

## Jedna klatka → film z całej sekwencji

Dodaj dowolną klatkę, np. `shot.1050.exr`. Program pokaże wykrytą sekwencję,
liczbę i zakres klatek oraz przycisk **Utwórz wideo z całej sekwencji**.
Zwykła konwersja wybranego obrazu pozostaje dostępna; tryb wideo włącza się
dopiero po kliknięciu przycisku. Można wrócić do obrazów bez ponownego dodawania plików.

Ustaw FPS (także 23,976), nazwę filmu, format i dźwięk:

- dopasuj audio po nazwie sekwencji lub folderu;
- wskaż własny plik audio albo film zawierający dźwięk;
- utwórz film bez audio.

Krótka ścieżka jest uzupełniana ciszą, długa przycinana do długości obrazu.
Nie są dołączane przypadkowe nagrania z folderu. Kilka pasujących ścieżek wymaga
wskazania jednej. Istniejący plik wynikowy jest chroniony przed nadpisaniem.
Brakujące numery klatek są zgłaszane; program nie skraca samowolnie osi czasu.
Jeśli folder zawiera kilka sekwencji, wybierz klatkę z właściwej zamiast całego folderu.

CLI też wykrywa sekwencję po podaniu pojedynczej klatki:

```sh
python3 app/cli.py seq --fps 23.976 shot.1050.exr
python3 app/cli.py seq --fps 24 --audio lektor.wav --output reklama.mp4 shot.1050.exr
python3 app/cli.py seq --no-audio shot.1050.exr
python3 app/cli.py seq --selected-only shot.1050.exr  # tylko wskazana klatka
```

Zasady pracy z projektem i lokalne polecenia sprawdzające: [CLAUDE.md](CLAUDE.md).
