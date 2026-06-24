# ffmpeg_convert — specyfikacja do ponownego napisania

Dokument opisuje obecny stan projektu na tyle dokładnie, by dało się
zapisać go od zera z zachowaniem funkcji i zachowań. Sekcja
„Uwagi do przebudowy" zbiera słabe punkty obecnej implementacji.

## 1. Cel i zarys

Narzędzie do konwersji wideo i kompresji obrazów przez FFmpeg, dostępne
trzema drogami: **GUI** (PyQt5, drag & drop), **CLI** (skryptowalne), oraz
**menu kontekstowe** menedżera plików (Nemo na Linuksie, Eksplorator na
Windows). Kluczowa zasada architektury: **cała logika konwersji (receptury
FFmpeg) żyje w jednym miejscu** — pakiecie `app/` w Pythonie. Wszystkie
front-endy korzystają ze wspólnego rdzenia, więc dodanie/zmiana presetu
działa od razu wszędzie.

Wymagania środowiska: `ffmpeg` (i `ffprobe`) w PATH, Python 3, PyQt5.
Na Linuksie dodatkowo `zenity` dla front-endów bash.

## 2. Architektura

```
app/presets.py   ← jedyne źródło prawdy: buduje listy Job (komendy FFmpeg)
app/runner.py    ← wykonuje Joby (subprocess, przechwyt błędów, sprzątanie)
app/cli.py       ← front-end wiersza poleceń (video/image/seq/gui)
app/gui.py       ← GUI PyQt5 (drag & drop, panele obrazy/wideo)
linux/           ← akcje Nemo + front-endy bash + install.sh
win/             ← setup.bat (instalator zależności + menu kontekstowe)
```

Rdzeń (`presets` + `runner`) nie zależy od żadnego UI. `cli.py` i `gui.py`
importują go. Zależność cykliczna/ładowania rozwiązana shhem importu:
`if __package__: from . import presets, runner else: sys.path.insert(parent);
import presets; import runner` — dzięki temu moduły działają zarówno jako
pakiet (`python -m app.cli`), jak i samodzielne skrypty (`python app/gui.py`).

## 3. Model danych (`app/presets.py`)

Stałe:
- `FFMPEG`, `FFPROBE` — `shutil.which(...) or "ffmpeg"/"ffprobe"`.
- `IMAGE_EXTS = {.png,.jpg,.jpeg,.exr,.tif,.tiff,.webp}`
- `VIDEO_EXTS = {.mp4,.mov,.mkv,.avi,.webm,.m4v}`
- `kind_of(path)` → `"image" | "video" | "other"` (po rozszerzeniu).

`Job` (dataclass):
- `label: str` — tekst w logu,
- `cmds: list` — lista komend; każda to lista argumentów dla `subprocess`
  (pierwszy element to `ffmpeg`/`ffprobe`/`__copy__`),
- `mkdir: Optional[Path]` — katalog do utworzenia przed startem,
- `cleanup: list` — pliki/katalogi do usunięcia po zakończeniu.

Konwencja: komenda `["__copy__", src, dst]` oznacza kopię bez
przekodowania (`shutil.copy2`) — używana w trybie „zachowaj oryginał".

### 3.1 Presety wideo

`SIMPLE_VIDEO` (id → dict `label/suffix/ext/args`), jedna komenda:
- `h264` — MP4 H.264 CRF 18, suffix `H264`, ext `mp4`,
  args `[-c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p -c:a aac -b:a 192k]`
- `h265` — MP4 H.265/HEVC CRF 23, suffix `HEVC`, ext `mp4`,
  args `[-c:v libx265 -crf 23 -preset medium -pix_fmt yuv420p -c:a aac -b:a 192k]`
- `dnxhd` — DNxHD 1080p 120 Mb/s, suffix `DNxHD`, ext `mov`,
  args `[-vf scale=1920:1080 -c:v dnxhd -b:v 120M -pix_fmt yuv422p -c:a pcm_s16le]`
- `dnxhr` — DNxHR HQ, suffix `DNxHR`, ext `mov`,
  args `[-c:v dnxhd -profile:v dnxhr_hq -pix_fmt yuv422p10le -c:a pcm_s16le]`
- `prores` — ProRes 422 HQ, suffix `PR`, ext `mov`,
  args `[-c:v prores_ks -profile:v 3 -pix_fmt yuv422p10le -c:a pcm_s16le]`
- `cineform` — Cineform Q4 10-bit, suffix `CF`, ext `mov`,
  args `[-c:v cfhd -quality 4 -pix_fmt yuv422p10le -c:a pcm_s16le]`

Dla simple: `out_dir = (src.parent/suffix) if batch else src.parent`
(`batch = len(files)>1`); `out = out_dir/{base}_{suffix}.{ext}`;
`cmd = [ffmpeg -y -i src, *args, out]`.

`SPECIAL_VIDEO` (obsługiwane osobno): `h264size`, `last_frame`, `frames`.

Kolejność w UI (`VIDEO_PRESETS`, lista `(id, label)`):
`h264, h264size, h265, dnxhd, dnxhr, prores, cineform, last_frame, frames`.

#### h264size — kontrola rozmiaru (`_h264_size_job`)
`out_dir = batch ? parent/"H264" : parent`; `out = {base}_H264.mp4`.
- Tryb `crf`: `[ffmpeg -y -i src -c:v libx264 -crf {crf} -preset slow
  -pix_fmt yuv420p -c:a aac -b:a 192k out]`.
- Tryb `size` (docelowy rozmiar MB, 2 przebiegi): `duration =
  probe_duration(src)` przez ffprobe; `audio_k=128`;
  `total_k = target_mb*8192/duration`; `video_k = max(50, int(total_k-audio_k))`;
  `passlog = out_dir/{base}_ffmpeg2pass`;
  pass1 `[-y -i src -c:v libx264 -b:v {video_k}k -preset slow -pix_fmt yuv420p
  -pass 1 -passlogfile passlog -an -f null devnull]`;
  pass2 `[-y -i src -c:v libx264 -b:v {video_k}k -preset slow -pix_fmt yuv420p
  -pass 2 -passlogfile passlog -c:a aac -b:a 128k out]`;
  `cleanup=[passlog-0.log, passlog-0.log.mbtree]`.
- Jeśli `duration` nie do odczytu → fallback CRF 23 (label z powodem).

#### last_frame
`out = {base}_last.png`; `cmd = [ffmpeg -y -sseof -1 -i src -update 1 out]`;
`mkdir = parent`.

#### frames — eksport klatek (+ opcjonalnie WAV)
`frames_dir = parent/{base}_FRAMES`; `pattern = frames_dir/{base}_%04d.{fmt}`
(fmt: png/jpg/exr);
cmd `[ffmpeg -y -i src -fps_mode passthrough pattern]`
(`passthrough` zachowuje dokładnie tyle klatek, co źródło);
jeśli `with_wav` → dołącz `[ffmpeg -y -i src -vn -c:a pcm_s24le
frames_dir/{base}.wav]`; `mkdir = frames_dir`.

`build_video_jobs(preset, files, *, size_mode="crf", crf=23, target_mb=25,
frames_format="png", frames_with_wav=True)`. Nieznany preset → `ValueError`.

### 3.2 Obrazy

`IMAGE_QUALITY = {2:"Q2 (~94%, najlepsza)", 5:"Q5 (~85%, dobra)",
10:"Q10 (~70%, mała waga)", 1:"Bez kompresji (maks. JPG)"}` (mapa na `-q:v`).

`image_target_name(path, idx, newname, keep)`:
- `base = f"{newname}_{idx:03d}" if newname else path.stem`
- `ext = path.suffix.lstrip(".") if keep else "jpg"`

`_scale_filter(scale_pct)`: `None` gdy brak lub `==100`; w p.p.
`p = scale_pct/100`; zwraca `scale=trunc(iw*{p}/2)*2:trunc(ih*{p}/2)*2`
(trunc do parzystych — wymagane przez `yuvj420p`).

`build_image_jobs(files, *, quality=2, keep=False, newname="", subdir=True,
scale_pct=None)`:
- dla każdego pliku `kind_of=="image"`: `idx++`; `base, ext =
  image_target_name`; `out_dir = subdir ? parent/"compressed" : parent`;
  `out = out_dir/{base}.{ext}`; pomiń gdy `out.resolve()==src.resolve()`.
- `keep=True` (lub `quality=None`) → Job kopiujący `["__copy__", src, out]`.
- inaczej: `vf = scale ? f"{scale},format=yuvj420p" : "format=yuvj420p"`;
  cmd `[ffmpeg -y -loglevel error -i src -q:v {quality} -vf {vf} out]`.
  Skalowanie stosowane tylko przy przekodowaniu (nie przy „keep").
- Kompresji do JPG poddawany DOWOLNY obraz rastrowy z `IMAGE_EXTS`.

### 3.3 Sekwencja obrazów → wideo (`build_seq_job`)

`SEQ_FORMATS` (id → `label/ext/vargs/aargs`):
- `h264` mp4, vargs `[-c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p]`,
  aargs `[-c:a aac -b:a 192k]`
- `h265` mp4, `[-c:v libx265 -crf 23 -preset medium -pix_fmt yuv420p]`,
  `[-c:a aac -b:a 192k]`
- `prores` mov, `[-c:v prores_ks -profile:v 3 -pix_fmt yuv422p10le]`,
  `[-c:a pcm_s16le]`
- `dnxhd` mov, `[-vf scale=1920:1080 -c:v dnxhd -b:v 120M -pix_fmt yuv422p]`,
  `[-c:a pcm_s16le]`

`build_seq_job(files, *, fps=24, fmt="h264")`:
- naturalne sortowanie (`_natural_key`: split po cyfrach, cyfry jako int)
  rozwiązanych ścieżek; `out_dir = paths[0].parent`;
  `name = out_dir.name or "output"`; `out = out_dir/{name}.{ext}`;
  `seq_ext = paths[0].suffix.lstrip(".")`.
- tymczasowy katalog (`tempfile.mkdtemp("ffseq_")`) z symlinkami
  `seq_{i:05d}.{seq_ext}` → źródło (fallback `shutil.copy2` przy braku
  obsługi symlinków, np. Windows bez uprawnień) — dla demuxera `image2`
  (niezawodny FPS i pełna liczba klatek).
- audio o nazwie folderu: `out_dir/{name}.wav` lub `.mp4` jeśli istnieje.
- cmd `[ffmpeg -y -framerate {fps} -i tmp/seq_%05d.{seq_ext}]` + (audio?
  `[-i audio, *aargs, -shortest]`) + `[*vargs, out]`; `cleanup=[tmp]`.

## 4. Wykonanie (`app/runner.py`)

- `_run_cmd(cmd)`: jeśli `cmd[0]=="__copy__"` → `shutil.copy2`; inaczej
  `subprocess.run(cmd, check=False, stdout=DEVNULL, stderr=PIPE, text=)`.
  Przy `returncode!=0` → `RuntimeError` z ogonem (ostatnie 5 linii stderr).
- `run_job(job)`: `mkdir(parents=True, exist_ok=True)` → komendy po kolei
  (błąd przerywa job) → `finally` cleanup (`rmtree` dla katalogu,
  `unlink(missing_ok=True)` dla pliku).
- `run_jobs(jobs, on_log=None, on_progress=None)`: iteruje joby, liczy OK;
  wyjątek pojedynczego joba jest łapany i logowany (nie przerywa batcha);
  `on_log("OK: …" / "BŁĄD: …")`, `on_progress(cur, total)`; zwraca liczbę OK.

## 5. CLI (`app/cli.py`)

Subkomendy (`argparse`, `required=True`):
- `video --preset {id} [--crf N] [--target-mb MB] [--frames-format png|jpg|exr]
  [--no-wav] files+` — preset z `VIDEO_PRESETS`.
- `image [--quality 1|2|5|10|keep] [--name NAZWA] [--beside] [--scale PCT]
  files+`.
- `seq [--fps N] [--format h264|h265|prores|dnxhd] files+`.
- `gui [files*]` → uruchamia `gui.main(files)`.

`_existing(files)` filtruje istniejące pliki (brakujące loguje na stderr).
`_run(jobs)`: jeśli brak jobów → komunikat + exit 1; uruchamia `run_jobs`
z `on_log=print`, `on_progress=lambda c,t: print(f"[{c}/{t}]")`; drukuje
`=== Gotowe: {ok}/{len} ===`; exit 0 jeśli wszystkie OK, inaczej 2.

## 6. GUI (`app/gui.py`, PyQt5)

Ciemny motyw (`APP_STYLE`, zielony akcent `#34d399`). Struktura:
- `DropList(QListWidget)` — drag & drop, placeholder rysowany gdy pusta,
  sygnał `filesDropped(list)`, stan „empty" zmienia styl (przerywana ramka).
- `MainWindow`: nagłówek, przewijalny środek (`QScrollArea`) z `DropList` +
  przyciski „Dodaj pliki…"/„Wyczyść listę" + `QStackedWidget`
  (empty/image/video), dół: „Konwertuj" + pasek postępu, oraz log
  (`QPlainTextEdit`). Rozmiar okna ograniczony do dostępnego ekranu.
- `add_files(paths)`: narzuca **jeden typ mediów na listę** (image xor video);
  pliki innego typu i duplikaty są pomijane z logiem; ikona `🖼`/`🎬`.
- `ImagePanel`:
  - jakość: radio Q2 / Q5 / Q10 / Bez kompresji (q=1) / Zachowaj oryginał.
  - zmiana nazwy: `QLineEdit` + podgląd na żywo (3 pierwsze + ostatni,
    lub ≤4 linii).
  - miejsce zapisu: podfolder `compressed` / obok oryginału.
  - zmiana wielkości: checkbox + `QSpinBox`(1–800, dom. 50) + `QSlider`
    przyciągający do `SNAP=[10,25,50,75,90,100]`; grupa wyłączona przy
    „zachowaj oryginał".
  - `build_jobs()` → `presets.build_image_jobs(...)`.
- `VideoPanel`:
  - radio presetów z `VIDEO_PRESETS` (pierwszy zaznaczony).
  - `frames_box` (format PNG/JPG/EXR + „Eksportuj WAV") widoczny tylko dla `frames`.
  - `size_box` (suwak CRF 18–32 dom. 23 z opisem jakości / docelowy MB
    1–100000 dom. 25) widoczny tylko dla `h264size`.
  - `build_jobs()` → `presets.build_video_jobs(...)`.
- `ConvertWorker(QThread)`: woła `runner.run_jobs` z sygnałami
  `log/progress/done` — konwersja poza wątkiem UI.
- `start_conversion`: buduje joby, wyłącza przycisk, pasek `max=len(jobs)`,
  `value=0`; `_on_done` przywraca przycisk + „=== Gotowe ===".

`main(files=None)`: `QApplication`, `setStyleSheet`, `MainWindow`, ew.
`add_files`, `exec_`.

## 7. Integracja Linux (Nemo)

`linux/install.sh`:
- sprawdza zależności (`ffmpeg`, `zenity`, PyQt5) → `sudo apt install`
  brakujących;
- symlinki `*.sh` (oprócz `install.sh`) do `~/.local/bin`;
- `chmod +x app/cli.py app/gui.py`;
- kopiuje `*.nemo_action` do `~/.local/share/nemo/actions` rozwijając
  placeholdery: `__HOME__`→`$HOME`, `__GUI__`→`python3 $APP_DIR/gui.py`,
  `__CLI__`→`python3 $APP_DIR/cli.py`;
- tworzy wpis `.desktop` `ffmpeg-convert-gui.desktop`; restartuje Nemo.

Akcje Nemo (Selection=Any, lista rozszerzeń):
- `VideoConvert` → GUI (`__GUI__ %F`), exts wideo.
- `CompressImages` → GUI, exts obrazów.
- `ImagesToVideo` → `gnome-terminal … images_to_video.sh` (Terminal=true).
- `ImageSplit` → `split_image.sh`.
- `MakeFlipbook` → `make_flipbook.sh`.

Front-endy bash (cienkie; konwersję robi wspólny rdzeń):
- `images_to_video.sh`: zenity wybiera FPS (24/25/30/60) i format
  (h264/h265/prores/dnxhd) → `cli.py seq`.
- `make_flipbook.sh`: auto-siatka (cols z {8,16,32,64} min. pustych),
  ffprobe wymiar kafelka, zenity forms (kolumny/wiersze/kafelek), ffmpeg
  concat demuxer + filtr `tile` → PNG spritesheet
  `{stem}_flipbook_{cols}x{rows}.png`; log do `/tmp`.
- `split_image.sh`: zenity forms (X×Y), per obraz ffprobe wymiar + filtr
  `crop` → `{base}_{y}_{x}.png`; przy >1 pliku do podfolderu `SplitGrid`.

> Uwaga: flipbook i split to logika ffmpeg **poza** rdzeniem `app/`
> (skrypty bash) — jedyny wyjątek od „jedno źródło prawdy".

## 8. Integracja Windows (`win/setup.bat`)

Jeden `.bat` (podwójny klik, działa na „gołym" Win11), menu 1–6:
1. Sprawdź zależności (Python, PyQt5, ffmpeg).
2. Zainstaluj brakujące — **hybryda**: najpierw `winget`
   (`Python.Python.3.12 --scope user`, `Gyan.FFmpeg`), a gdy brak/błąd —
   fallback ręczny: `curl` pobiera instalator Pythona
   (`/passive InstallAllUsers=0 PrependPath=1 Include_pip=1`) oraz zip ffmpeg
   (gyan essentials) → `Expand-Archive` do `%USERPROFILE%\ffmpeg` →
   znajdź `bin\ffmpeg.exe` → dopisz do user PATH przez
   `[Environment]::SetEnvironmentVariable` (NIE `setx` — obcina >1024 zn.);
   `pip install --user PyQt5`. Wszystko per-user, bez admina.
   Po instalacji odświeża PATH sesji z rejestru.
3. Kopia `app\` → `%USERPROFILE%\scripts\app\` (`robocopy`).
4. Dodaj menu: `reg add … /t REG_EXPAND_SZ` z
   `pythonw "%USERPROFILE%\scripts\app\gui.py" "%1"` dla
   `SystemFileAssociations\.mp4/.mov/.mkv` oraz `image`.
5. Usuń menu: `reg delete`.
6. Wyjście.

Detekcja Pythona odfiltrowuje skrót-alias Sklepu Windows (wymaga linii
zaczynającej się od „Python " na stdout). Wideo przypinane do konkretnych
rozszerzeń (nie do ogólnej kategorii `video`, którą wypinają odtwarzacze).
Wartości `REG_EXPAND_SZ` rozwijają `%USERPROFILE%` w locie.

### 8.1 Pułapki Windows — diagnoza (historyczna, ku pamięci przy przebudowie)

Trzy problemy napotkane na Windowsie 11, które determinują obecny kształt
instalatora. Każdy ma swoje „dlaczego" — warto je znać, by nie powtórzyć
błędu przy ponownym pisaniu:

1. **Brak FFmpeg w PATH (WinError 2 z `subprocess`).** Pythonowy
   `subprocess` nie znajduje `ffmpeg.exe`, bo Windows nie ma go w PATH —
   nawet jeśli binarka leży na dysku. Rozwiązanie: dopisać folder z
   `ffmpeg.exe` do zmiennych środowiskowych PATH; po zmianie PATH potrzebny
   jest restart, by Eksplorator/przeszukiwanie w tle wczytało nowe ścieżki.
   `setup.bat` robi to automatycznie (instaluje ffmpeg i dopisuje `bin` do
   user PATH przez `[Environment]::SetEnvironmentVariable`). W rewrite:
   nadal instaluj ffmpeg i modyfikuj user PATH; pamiętaj o komunikacie
   „wymaga restartu Eksploratora/wylogowania".

2. **Ślepe menu — `%USERPROFILE%` w REG_SZ.** Pierwotny `.reg` używał
   `%USERPROFILE%\scripts\app\gui.py` w wartości `@=`. Klucze rejestru typu
   `REG_SZ` (zwykły ciąg) **nie rozwijają zmiennych środowiskowych w locie**
   — system szukał dosłownie folderu o nazwie `%USERPROFILE%` zamiast
   `C:\Users\wesol`. Rozwiązanie: albo ścieżka absolutna na sztywno (w
   składni `.reg` z podwójnymi ukośnikami `\\`, np.
   `C:\\Users\\wesol\\scripts\\app\\gui.py`), albo typ `REG_EXPAND_SZ`
   (rozwija `%USERPROFILE%` przy wywołaniu). Wybrano `REG_EXPAND_SZ` —
   działa dla każdego użytkownika bez edycji. W rewrite: nigdy nie
   polegaj na `%VAR%` w `REG_SZ`; używaj `REG_EXPAND_SZ` (`reg add /t
   REG_EXPAND_SZ`).

3. **Brak opcji dla MP4 (przejęte kategorie Windows).** Menu pojawiało się
   dla obrazów, ale nie dla wideo, bo użyto ogólnej grupy
   `SystemFileAssociations\video`. Zewnętrzne odtwarzacze i kodeki
   „przejmują" konkretne formaty (np. `.mp4`), wypinając je z domyślnej
   ogólnej kategorii wideo — wtedy akcja przypisana do kategorii nie działa
   dla tych rozszerzeń. Rozwiązanie: ominąć ogólną kategorię i przypisać
   akcje bezpośrednio do twardych rozszerzeń — osobne klucze
   `SystemFileAssociations\.mp4`, `\.mov`, `\.mkv`. W rewrite: przypinaj
   menu do konkretnych rozszerzeń, nie do kategorii `video`/`image`;
   kategoria `image` działa, bo rzadziej przejmowana, ale dla spójności
   rozważ jawne rozszerzenia obrazów też.

## 9. Zachowania i przypadki brzegowe (do zachować)

- **Batch (>1 plik)** wideo → zapis do podfolderu nazwanego sufiksem
  presetu; pojedynczy plik → obok źródła. Obrazy → podfolder `compressed`
  (chyba że „obok").
- **Nie nadpisuj oryginału** (obrazy: pomiń gdy `out==src`).
- **Jeden typ mediów na sesję GUI** (zmieszane typy są pomijane z logiem).
- **Błąd joba nie przerywa batcha**; liczone OK/total.
- **Skalowanie obrazów** tylko przy przekodowaniu, wymiary parzyste.
- **Sekwencja** zachowuje pełną liczbę klatek i stabilny FPS (image2 +
  ponumerowane symlinki); audio folderu doklejane automatycznie.
- **h264size** przy braku długości → fallback CRF 23.
- **Sprzątanie** 2-pass logów i katalogów tymczasowych (zawsze, nawet
  przy błędzie).
- Klasyczne menu Windows uruchamia komendę raz na każdy zaznaczony plik.

## 10. Uwagi do przebudowy (słabe punkty / decyzje)

- **Brak testów** w repo — przy przebudowie warto dodać testy jednostkowe
  dla `presets` (komendy jako listy arg łatwo porównać) i `runner` (mock
  subprocess). Obecnie weryfikacja tylko ręczna.
- **Presety hard-coded** w dictach Pythona — można je wydzielić do danych
  (YAML/TOML), by edytować bez kodu; obecnie zmiana = edycja `presets.py`.
- **Logika ffmpeg poza rdzeniem**: `make_flipbook.sh` i `split_image.sh`
  dublują receptury w bashu zamiast korzystać z `app/`. Przy przebudowie
  warto dodać preset `flipbook`/`split` do `presets.py` i uczynić skrypty
  bash cienkimi front-endami (jak `images_to_video.sh`).
- **Brak postępu wewnątrz joba**: `runner` suppressuje stdout i czyta
  stderr dopiero po zakończeniu (ostatnie 5 linii). Pasek postępu GUI
  liczy tylko ukończone joby. Przebudowa: strumieniować stderr i parsować
  `out_time`/`frame=` dla realnego % (zwłaszcza przy 2-pass i dużych
  plikach).
- **2-pass bitrate** w `h264size` szacuje z długości i stałego audio
  128 k; niedokładne dla krótkich klipów / zmiennego bitrate.
- **`ffprobe`-zależności**: `probe_duration` oraz sekwencja/split/flipbook
  wymagają ffprobe obok ffmpeg.
- **Import shim** — konieczny tylko dlatego, że moduły mogą być uruchamiane
  jako skrypty i jako pakiet. Przebudowa: ustalić jeden tryb (np. zawsze
  `python -m app.…`) i uprosić importy.
- **Windows: winget `--scope user`** bywa ignorowany przez niektóre
  manifesty → możliwy prompt UAC; fallback ręczny łata większość.
- **Brak i18n** — teksty UI/logów po polsku, zakodowane.
- **Brak obsługi błędów wejścia** w GUI (np. usunięty plik mid-sesji).