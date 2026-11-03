# Audyt ffmpeg_convert v0.7.0 (etap 0)

Stan: commit `b0ee032` (gałąź robocza `claude/new-session-hw35j9`). Audyt bez zmian w kodzie.
Środowisko: Linux, Python 3.12.3, FFmpeg 6.1.1 (Ubuntu, z `libzimg`, `libx264`, `libx265`),
PyQt5 5.15.11 / Qt 5.15.14, Qt offscreen. Fixture'y generowane przez `lavfi`
(`testsrc2`, `sine`, `color`) w katalogu tymczasowym, poza repo. Żadne media nie trafiły do repo.

> **Brakuje materiałów marki.** W repo nie ma `docs/brand/the_cut_v2.pdf` ani mastera logo (SVG).
> Etap 0 oparłem na wartościach z promptu. Przed etapem 3 potrzebuję obu plików.

Spis: [1. Narzędzia](#1-narzędzia) · [2. Realne przebiegi FFmpeg](#2-realne-przebiegi-ffmpeg) ·
[3. Błędy i ryzyka](#3-błędy-i-ryzyka) · [4. Lista kontrolna z promptu](#4-lista-kontrolna-z-promptu) ·
[5. Martwy kod](#5-martwy-kod) · [6. Duplikacje i wycieki logiki](#6-duplikacje-gui--cli-i-wycieki-logiki-z-presets) ·
[7. Testy i CI](#7-testy-i-ci) · [8. Co zachować](#8-co-działa-dobrze-i-warto-zachować)

---

## 1. Narzędzia

| narzędzie | wynik | uwagi |
|---|---|---|
| `ruff check .` | **0 błędów** | zestaw `E,F,W`; reguły E3xx (puste linie) są w ruff tylko w preview, stąd brak uwag np. do `app/core/ffmpeg.py:8` |
| `mypy app` | **0 błędów** (18 plików) | wykluczone `app/gui*.py` i `app/cli.py`: ok. 1560 linii (≈40% kodu aplikacji) bez sprawdzania typów |
| `pytest -q` (offscreen, PyQt5) | **156 passed, 3 skipped, 13 subtests**, 72,9 s | pominięte 3 testy wymagające prawdziwego Windows; `test_h264_20m_no_second_over_limit` zajmuje 64,7 s (89% czasu) |

Zielone testy nie oznaczają poprawności: kilka krytycznych błędów z sekcji 3 nie ma testów,
a test postępu przechodzi mimo niedziałającego postępu (A05).

## 2. Realne przebiegi FFmpeg

Każdy wiersz: `presets.build_*()` → `runner.run_job()` → `ffprobe -count_packets`.

### 2.1 Presety wideo, źródło 1920×1080, 24 fps, 2 s, AAC (48 klatek)

| preset | wynik | kodek / pix_fmt | klatki | długość | tagi koloru (space/prim/trc/range) | audio |
|---|---|---|---|---|---|---|
| h264 | OK | h264 / yuv420p | 48 | 2,005 | brak | aac |
| h265 | OK | hevc / yuv420p | 48 | 2,005 | -/-/-/tv | aac |
| dnxhd | OK | dnxhd / yuv422p | 48 | 2,005 | bt709/-/-/tv | pcm_s16le |
| **dnxhr** | **BŁĄD** | `pixel format is incompatible with DNxHR LB/SQ/HQ profile`, zostaje plik 0 B | | | | |
| prores | OK | prores / yuv422p10le | 48 | 2,005 | brak | pcm_s16le |
| prores_nuke | OK | prores / yuv422p10le | 48 | 2,005 | bt709/bt709/bt709/- | pcm_s24le 48 kHz |
| cineform | OK | cfhd / yuv422p10le | 48 | 2,005 | brak | pcm_s16le |
| h264size CRF | OK | h264 / yuv420p | 48 | 2,005 | brak | aac |
| h264size 1 MB | OK | h264 / yuv420p | 48 | 2,005 | brak | aac |
| last_frame | OK | png / rgb24 | 1 | | | |
| frames PNG + WAV | OK | 48 plików PNG | 48 | | | WAV pcm_s24le 2,005 s |

Liczba klatek zgadza się ze źródłem. Długość 2,005 s wynika z primingu AAC; ścieżka wideo ma 2,000 s.
Źródło 23,976 (`24000/1001`, 23 klatki) → h264: 23 klatki, `r_frame_rate=24000/1001`, poprawnie.

### 2.2 Nieparzyste wymiary (prawdziwe 1281×721; `testsrc2` sam zaokrągla do parzystych)

| wejście → wyjście | wynik |
|---|---|
| wideo → h264, h265, cineform, h264size (CRF i MB), h264_20m | **BŁĄD** (`Conversion failed!`), zostaje plik 0 B |
| wideo → prores, prores_nuke | OK 1281×721 |
| wideo → dnxhd | OK, ale skalowane do 1920×1080 |
| sekwencja PNG / TIFF → h264 | OK, przycięte do 1280×720 (`EVEN_CROP`) |
| **sekwencja JPG → h264** | **BŁĄD**, zostaje plik 0 B (przycinanie działa tylko dla PNG/TIFF) |
| sekwencja JPG/PNG/TIFF → prores | OK 1281×721 |

### 2.3 Sekwencje (PNG 48 klatek, fps i audio)

| scenariusz | klatki | długość | r_frame_rate | audio |
|---|---|---|---|---|
| fps 24 | 48 | 2,000 | 24/1 | — |
| **fps 23,976** | 48 | 2,002 | **2997/125** (powinno być 24000/1001) | — |
| 23,976 + audio 0,5 s (h264 / prores) | 48 | 2,002 | 2997/125 | dopełnione ciszą do 2,002 s |
| 23,976 + audio 5 s (h264 / prores) | 48 | 2,002 | 2997/125 | przycięte do 2,002 s |
| EXR (ACES i lin709) → h264 | 12/12 | | | tagi bt709/iec61966-2-1 |
| EXR → prores + proxy PNG16 | 12/12, 12 plików proxy | | | proxy nazwane od folderu (`exrseq.1001.png`), nie od sekwencji (`plate`) |

Dopasowanie audio, dopełnianie ciszą i przycinanie działają zgodnie z `CLAUDE.md`.

### 2.4 Kolor

| scenariusz | wynik (kolor wzorcowy 10,98,204, dekodowany macierzą 709) |
|---|---|
| sekwencja PNG → h264 / prores (test w repo) | poprawny, tagi 709 |
| **źródło RGB (PNG w MOV) → h264 / prores** | **(0,93,208)**: macierz 601, brak tagów |
| **źródło RGB → prores_nuke** | **(0,93,208)** z tagami bt709: plik źle opisany (601 w środku, 709 w tagach) |
| sekwencja JPG → h264 | wynik otagowany `bt470bg` (601), spójny, ale inny niż ścieżka PNG (709) |
| nieotagowane HD → last_frame/frames | poprawny (test w repo) |

### 2.5 Docelowy rozmiar (h264size, 2 przebiegi)

| źródło | cel | wynik | odchyłka |
|---|---|---|---|
| 1080p testsrc2 3 s + AAC | 1 MB | 1,038 MB | **+3,8%** (przekroczony) |
| 1080p testsrc2 10 s + AAC | 2 MB | 1,934 MB | −3,3% |
| 1080p testsrc2 30 s + AAC | 5 MB | 4,718 MB | −5,6% |
| 720p szum 10 s + AAC | 4 MB | 3,855 MB | −3,6% |
| 720p szum 2 s + AAC | 1 MB | 2,667 MB | **+167%** (cel nieosiągalny przy QP 51, brak ostrzeżenia) |
| 720p szum 1 s + AAC | 20 MB | 5,654 MB | **−72%** (limit `max_video_kbps` po cichu nadpisuje cel) |

### 2.6 Zachowania przekrojowe

| sprawdzenie | wynik |
|---|---|
| postęp `on_percent` przy 6 s kodowania h264 | **1 wywołanie, wartość 1.0**: brak postępu w trakcie joba |
| istniejący `over_H264.mp4` (9 B) przed konwersją | **nadpisany bez pytania** |
| batch `clip.mov` + `clip.mp4` → h264 | **oba do `H264/clip_H264.mp4`**, drugi nadpisuje pierwszy |
| obrazy `a.png` + `a.jpg` → kompresja | **oba do `compressed/a.jpg`** |
| eksport klatek z wideo bez audio (WAV domyślnie włączony) | **job BŁĄD**, 24 klatki już zapisane |
| eksport 48 klatek, potem ten sam plik skrócony do 24 | **48 plików w folderze**: stare klatki zmieszane z nowymi |
| folder `cover.png` + `frame_0001.png` → wideo | **2-klatkowe wideo**: ciche mieszanie |
| `promo 50%.mp4` → frames | **BŁĄD** (`%` traktowany jak wzorzec) |
| `logo 100%d.png` → kompresja | **wynik `logo 1001.jpg`**: zła nazwa bez ostrzeżenia |
| budowanie joba sekwencji/flipbooka/proxy bez uruchomienia | tworzy `ffseq_*`, `ffflip_*.txt` w `/tmp` i podfolder proxy |
| sekwencja z brakującą klatką (CLI, plik i folder) | exit 2, `Brak klatek: 5…`: poprawnie |
| flipbook 10 klatek, siatka 2×2 | 4 klatki, reszta pominięta bez ostrzeżenia |
| ścieżka z `'` i `\` w flipbooku (concat) | OK, escaping poprawny |
| źródło z 2 ścieżkami audio → h264/prores | wynik ma 1 ścieżkę |
| `MainWindow()` | 0,49 s, **8× `ffmpeg -encoders`** w wątku UI |
| `build_jobs` dla 20 plików (h264 / last_frame) w wątku UI | 1,1 s / 2,3 s (20 / 40 wywołań ffprobe, lokalny SSD, bez timeoutu) |

---

## 3. Błędy i ryzyka

Priorytety: **K** krytyczny (utrata danych, niedziałająca funkcja), **W** wysoki (błędny wynik
lub blokada pracy), **Ś** średni, **N** niski. Etap 2 naprawia wszystkie K i W.

### Krytyczne

**A01 · K · Preset DNxHR HQ nigdy nie działa**
`app/presets/video.py:96-100`. Profil `dnxhr_hq` jest 8-bitowy, a receptura wymusza
`yuv422p10le`. Dowód: 2.1. Naprawa: `dnxhr_hq` + `yuv422p` albo `dnxhr_hqx` + `yuv422p10le`
(decyzja D10), plus test na realnym ffmpeg dla każdego presetu.

**A02 · K · Ciche nadpisywanie istniejących plików**
`-y` w `app/presets/video.py:167,176,191,194,224,226,248,253,283,293,304`,
`app/presets/image.py:82,114`, `app/presets/sequence.py:315,359,411,523`; `__copy__`
(`app/runner.py:57-58`) robi `copy2` na istniejący cel. Ochronę ma tylko MP4 sekwencji
(`sequence.py:167-168`, `-n`). Dowód: 2.6. Naprawa: jedna polityka w rdzeniu (D7):
wynik nigdy nie nadpisuje istniejącego pliku, zapis do `*.part` i atomowe `rename` na końcu.

**A03 · K · Kolizje nazw w batchu nadpisują własne wyniki**
`app/presets/video.py:145-147,160-161,280` (ścieżka wyjścia tylko z `stem`, więc `clip.mov`
i `clip.mp4` dostają ten sam plik i ten sam `passlog`, `video.py:190,223`);
`app/presets/image.py:62-66` (`a.png` + `a.jpg` → `a.jpg`; pomijany jest tylko przypadek
wynik == źródło). Naprawa: planowanie ścieżek wyjścia dla całego batcha przed startem,
wykrycie duplikatów i sufiks `_002` albo błąd walidacji przed uruchomieniem.

### Wysokie

**A04 · W · Nieparzyste wymiary wywalają H.264/H.265/Cineform**
`app/presets/video.py:41,167-170,191-196,220-222,283` (brak przycinania),
`app/presets/sequence.py:194-201` (`EVEN_CROP` tylko razem z `color_vf`, czyli tylko PNG/TIFF/EXR z
konwersją koloru; JPG, WebP i EXR bez konwersji koloru odpadają). Dowód: 2.2. Naprawa: wspólny
krok „wymiary zgodne z chroma subsampling” w budowaniu filtrów (przycięcie 1 px, D11) dla
każdego kodeka 4:2:0/4:2:2 i każdego źródła.

**A05 · W · Postęp w trakcie zadania nie działa**
`app/runner.py:30-47,80-82` parsuje `out_time*=`, ale żadna komenda nie dostaje
`-progress pipe:…`, a domyślne statystyki ffmpeg mają format `time=`. Pasek przeskakuje
tylko po zakończeniu komendy. `tests/test_runner.py:124-140` przechodzi, bo sprawdza tylko
monotoniczność i końcowe 1.0. Naprawa: `-progress pipe:1 -nostats` w runnerze (nie w
presetach), parsowanie `out_time_us` i `frame=`, postęp 2-pass ważony per przebieg, test
wymagający kilku wartości pośrednich.

**A06 · W · Brak anulowania**
`app/gui_workers.py:13-28` nie ma metody stop; `app/gui_main_window.py:328-332` blokuje
zamknięcie okna w trakcie pracy; `app/runner.py:62-66` nie udostępnia procesu. Jedyne wyjście
to zabicie aplikacji, a wtedy zostaje częściowy plik (A07). Naprawa: token anulowania w
runnerze, `terminate()` → po czasie `kill()`, usunięcie `*.part`, w GUI przycisk „Przerwij”
i pytanie przy zamykaniu okna.

**A07 · W · Po błędzie zostaje częściowy albo pusty plik wynikowy**
`app/runner.py:99-117` sprząta tylko `job.cleanup`, a wynik i utworzony folder zostają.
FFmpeg tworzy plik 0 B już przy błędzie inicjalizacji enkodera (2.1, 2.2). Dla sekwencji to
blokuje ponowienie: `sequence.py:167-168` zgłasza „Plik wynikowy już istnieje” na pustym pliku
z nieudanej próby. Naprawa: zapis do `*.part` w docelowym folderze, rename po sukcesie,
usuwanie `*.part` i pustych folderów utworzonych przez job.

**A08 · W · Eksport klatek z WAV pada na wideo bez audio**
`app/presets/video.py:251-254`; WAV jest domyślnie zaznaczony (`app/gui_panels.py:555-556`).
Druga komenda kończy się błędem, job jest liczony jako nieudany, klatki już zapisane.
Naprawa: `probe` przy planowaniu i pominięcie WAV z informacją w logu (albo `-map 0:a:0?`).

**A09 · W · Eksport klatek i proxy do istniejącego folderu miesza stare klatki z nowymi**
`app/presets/video.py:245-249` (`_FRAMES/`), `app/presets/sequence.py:391-416` (proxy, `-y`).
Krótszy eksport zostawia klatki z poprzedniego (2.6: 48 plików zamiast 24). To łamie zasadę
„nie mieszaj sekwencji”. Naprawa: nowy folder wynikowy z sufiksem (jak w separacji audio),
albo błąd, gdy folder nie jest pusty.

**A10 · W · Tryb folderu miesza obrazy spoza sekwencji**
`app/presets/sequence.py:459-471`: jedna numerowana klatka i luźne obrazy (`cover.png`,
`frame_0001.png`) dają wideo ze wszystkich obrazów folderu. Naprawa: tryb folderu przyjmuje
dokładnie jedną sekwencję; luźne obrazy bez numeracji tylko po jawnym wyborze plików.

**A11 · W · Blokowanie wątku UI i probe bez timeoutu**
`app/gui_main_window.py:298-302` (`build_jobs` w wątku UI: ffprobe na każdy plik, 1,1–2,3 s
na 20 plików na lokalnym dysku; na dysku sieciowym lub z antywirusem dużo dłużej);
`app/gui_panels.py:100-103,614-617` (`probe_encoders()` w pętli, 8 uruchomień `ffmpeg -encoders`
przy starcie, bez cache); `app/gui_panels.py:296-304` i `app/gui_main_window.py:233-247`
(`detect_sequence`/`matching_audio` z ffprobe w UI). `app/core/probe.py:17,30,50,66,86,116`:
`subprocess.run` bez `timeout`, więc zawieszony ffprobe zawiesza GUI. Naprawa: planowanie i
probe w workerze, cache probe per plik (mtime+rozmiar), `timeout`, jedno `ffprobe -show_streams
-show_format` na plik zamiast 2–3 wywołań.

### Średnie

**A12 · Ś · `%` w nazwach plików**
`app/presets/video.py:246` (wzorzec klatek z nazwy źródła), `app/presets/image.py:82,113-115`
(wyjście obrazu traktowane przez muxer `image2` jak wzorzec), `app/presets/sequence.py:395`
(proxy z nazwy folderu). Dowód: 2.6. Naprawa: `%` → `%%` w części dosłownej wzorca, a dla
pojedynczych obrazów `-update 1` lub `-frames:v 1` z jawnym `-f image2`.

**A13 · Ś · 23,976 zapisywane jako 2997/125**
`app/presets/sequence.py:229,302,315,322` (`f"{fps:g}"`), `:411` (`str(fps)`),
`app/gui_panels.py:38-41`, `app/cli.py:203`. Programy montażowe widzą niestandardowy timebase;
dryf względem 24000/1001 to ok. 0,09 s na godzinę. To samo dotyczy 29,97 i 59,94. Naprawa (D9):
mapowanie 23,976/29,97/59,94/47,952/119,88 na ułamki NTSC, przechowywanie fps jako `Fraction`.

**A14 · Ś · Kolor dla źródeł RGB i źle otagowany prores_nuke**
`app/presets/video.py:80-117`: presety wideo nie wybierają macierzy dla źródeł RGB (PNG/QTRLE
w MOV, nagrania ekranu), więc wynik ma macierz 601 bez tagów i przesunięty kolor (2.4).
`video.py:106-111` (prores_nuke) dopisuje tagi bt709 bez konwersji, więc dla źródła RGB plik
deklaruje 709 a zawiera 601. Ogólnie H.264/H.265/ProRes nie dostają tagów, więc odtwarzacz
zgaduje. Naprawa: probe `pix_fmt`/`color_space` i jawne `scale=out_color_matrix=…` + tagi
zgodne z faktyczną macierzą (skill `color-pipeline`).

**A15 · Ś · Niespójna polityka tagów i założeń koloru**
PNG/TIFF → wideo dostaje `trc=iec61966-2-1` (`app/config.py:160-163`, `sequence.py:194-198`),
prores_nuke dostaje `trc=bt709`, sekwencja JPG wychodzi jako 601 (2.4). EXR → ProRes/DNxHD
trafia jako surowe wartości liniowe bez tagów (`sequence.py:185-193`). Domyślne założenie EXR to
ACES2065-1 (`config.py:139`), a wiele EXR z Blendera i generatorów to linear Rec.709/sRGB, które
wtedy wyjdą z błędnym kolorem. Decyzja D8.

**A16 · Ś · Docelowy rozmiar: przekroczenia, cichy limit, niejasne MB**
`app/presets/video.py:181-204`, `app/presets/sequence.py:285-342`, `app/config.py:46-54`.
Krótkie klipy przekraczają cel (3 s: +3,8%). `target_mb * 8192` przy `k`=1000 w ffmpeg daje
w praktyce 1,024 × 0,95 celu w MB (10^6). `max_video_kbps=25000` po cichu nadpisuje cel
użytkownika (1 s / 20 MB → 5,6 MB). Cel nieosiągalny przy QP 51 daje +167% bez ostrzeżenia.
Nikt nie sprawdza rozmiaru wyniku. Etykieta fallbacku „CRF 23” jest zapisana na sztywno
(`video.py:183`). Naprawa: MB = 10^6 B (jasno w UI), audio i kontener liczone z probe, VBV
(`-maxrate`/`-bufsize`) dla krótkich klipów, ostrzeżenie o limicie, weryfikacja rozmiaru po
pass 2 i komunikat, gdy cel przekroczony.

**A17 · Ś · DNxHD 1080p rozciąga obraz i ignoruje fps**
`app/presets/video.py:91-95`, `app/presets/sequence.py:51-53`: `scale=1920:1080` zniekształca
źródła inne niż 16:9 (1080×1920 → 1920×1080, 2.1). Stałe 120 Mb/s: FFmpeg 6.1 przyjął 24/25/29,97,
ale tabela profili Avid to 115 Mb/s przy 23,976/24, 120 przy 25 i 145 przy 29,97, więc możliwe
problemy z importem do Avida. Naprawa (D10): skalowanie z zachowaniem proporcji i `pad`, bitrate
z tabeli według fps, odrzucenie nieobsługiwanych fps z komunikatem.

**A18 · Ś · Zasoby tymczasowe tworzone przy budowaniu joba**
`app/presets/sequence.py:204-211` (katalog `ffseq_*` z linkami), `:393` (`mkdir` folderu proxy),
`:516-521` (`ffflip_*.txt`). Job zbudowany, ale nieuruchomiony (błąd po budowie, podgląd,
anulowanie) zostawia śmieci. Builder nie jest czystą funkcją. Naprawa: job opisuje zasoby
deklaratywnie, a runner je tworzy i sprząta.

**A19 · Ś · Gubienie ścieżek audio i strumieni**
`app/presets/video.py:283,293`: brak `-map`, ffmpeg wybiera jedną ścieżkę audio (2.6),
gubi timecode i dodatkowe ścieżki. Dla formatów montażowych to utrata danych. Decyzja D12.

**A20 · Ś · Filtrowanie enkoderów GPU sprawdza tylko kompilację**
`app/core/probe.py:106-127`: NVENC/QSV/AMF są widoczne, gdy ffmpeg jest z nimi zbudowany,
nawet bez karty (np. Gyan na każdym PC ma NVENC/AMF/QSV). Błąd wychodzi dopiero w trakcie
konwersji. Brak cache (8 wywołań przy starcie). Naprawa: krótki test kodowania
(`-f lavfi -i color -frames:v 1 -c:v h264_nvenc -f null -`) w tle, wynik w cache na sesję.

**A21 · Ś · Okno bez ramki i niewidoczny focus**
`app/gui_main_window.py:25-27,349-362`: `FramelessWindowHint` usuwa minimalizację, maksymalizację,
zmianę rozmiaru krawędzią, Snap w Windows i przesuwanie z klawiatury. `app/gui_style.py:6-68`
nie ma ani jednej reguły `:focus`, a przyciski mają `border: none`, więc focus z klawiatury jest
niewidoczny. Etykiety nie mają `setBuddy` ani mnemoników. Naprawa w etapie 3: systemowa ramka
(albo pełna obsługa krawędzi i Snap), czerwony obrys focusu, buddy i skróty.

**A22 · Ś · Instalacja separacji audio**
`app/audio_separation.py:71-73`: `pip install` bez `--require-hashes`; zależności przechodnie
(numpy, soundfile, pyyaml…) nieprzypięte, więc instalacja za rok może dać inny zestaw albo błąd.
`:59-63`: lock po awarii wymaga ręcznego usunięcia. `:23,30`: runtime liczony od położenia kodu
(`ROOT/.audio-runtime`), co przestanie działać po zmianie struktury pakietu (D5). Naprawa: plik
`requirements` z hashami, lock z PID i wykrywaniem martwego procesu, runtime w katalogu danych
użytkownika z migracją.

**A23 · Ś · Brak pliku licencji przy zależności GPL**
W repo nie ma `LICENSE`, a PyQt5 jest na GPLv3 (lub licencji komercyjnej). Dystrybucja
instalatora z PyQt5 wymaga licencji zgodnej z GPL. Decyzja D1/D13.

**A24 · Ś · Instalator Linux**
`linux/install.sh:45-48`: `$HOME`/`$APP_DIR` wstawiane do `sed` bez escapowania (`&`, `|`);
`:47,61`: ścieżki w `Exec=` bez cudzysłowów (spacje w ścieżce psują akcje); `:21` tylko `apt` i
`sudo`; `:71` `nemo -q` zamyka otwarte okna Nemo bez pytania; systemowe PyQt5 na Linuxie i venv
na Windows to dwa różne środowiska; brak deinstalacji; brak akcji Nemo dla folderów (Windows ją
ma). `linux/images_to_video.sh` nie jest podpięty pod żadną akcję (sekcja 5).

**A25 · Ś · Luki w testach i CI**
Szczegóły w sekcji 7.

### Niskie

| ID | problem | miejsce |
|---|---|---|
| A26 | po konwersji przycisk sekwencji wraca do stanu aktywnego mimo dziur | `app/gui_main_window.py:323` |
| A27 | flipbook pomija klatki ponad `cols×rows` bez ostrzeżenia | `app/presets/sequence.py:523-524` |
| A28 | proxy nazwane od folderu, film od sekwencji (`exrseq.1001.png` vs `plate`) | `app/presets/sequence.py:161,272` |
| A29 | sekwencja H.264 domyślnie CRF 23, preset wideo H.264 CRF 18; `crf 18` w `SEQ_FORMATS` martwe; H.265 w sekwencji ignoruje CRF | `sequence.py:43,240,245-251`, `cli.py:214`, `gui_panels.py:121-122` |
| A30 | PNG z alfą → JPG bierze kolor spod przezroczystości (może być czarny lub przypadkowy) | `app/presets/image.py:78` |
| A31 | kod wyjścia 2 oznacza naraz częściowy błąd, błąd walidacji i błąd argparse | `app/cli.py:46,275-277` |
| A32 | `log.clear()` przy starcie konwersji kasuje komunikaty o pominiętych plikach; lista z 1 plikiem ma poziomy pasek, który zasłania ścieżkę | `app/gui_main_window.py:270,219` |
| A33 | „Bez kompresji (maks. JPG)” to nadal stratne `-q:v 1` | `app/presets/image.py:15-16`, `app/gui_panels.py:371` |
| A34 | cyrylica w docstringu („каждого”), zdublowany docstring | `app/update.py:20`, `app/core/color.py:16-17` |
| A35 | `REWRITE.md` opisuje nieaktualny stan (płaski `presets.py`, menu `setup.bat`, „brak testów”, CRF 18 i `-shortest` w sekwencji) | `REWRITE.md` |
| A36 | split EXR → PNG i eksport klatek do EXR bez transformacji koloru | `app/presets/image.py:90-120`, `app/presets/video.py:242-249` |
| A37 | Windows: przy zaznaczeniu wielu plików pozycja menu znika (`MultiSelectModel=Single`); „Usuń menu” nie usuwa skrótu z menu Start; brak pełnej deinstalacji | `win/setup.py:141,213-216` |
| A38 | `ImageConfig.scale_snaps` to `list` w zamrożonej dataclass (mutowalny) | `app/config.py:72` |
| A39 | `stderr` przycinany do 5 linii; przy domyślnym logu właściwa przyczyna bywa wyżej niż „Conversion failed!” | `app/runner.py:67,90` |

---

## 4. Lista kontrolna z promptu

| obszar | stan | odwołania |
|---|---|---|
| liczba klatek i długość po konwersji | ✅ zgodne dla wszystkich działających presetów i sekwencji (2.1, 2.3) | brak testu per preset (A25) |
| dopasowanie audio do sekwencji | ✅ nazwa sekwencji → nazwa folderu, niejednoznaczność = błąd, wynik wykluczony, cisza/przycięcie działa. ❌ tryb folderu miesza obrazy | A10 |
| 23,976 | ❌ 2997/125 zamiast 24000/1001 | A13 |
| tagi BT.709 | ⚠️ poprawne dla sekwencji PNG/TIFF; brak dla presetów wideo; prores_nuke źle opisany dla RGB; niespójne trc | A14, A15 |
| nieparzyste wymiary | ❌ H.264/H.265/Cineform/2-pass z wideo, sekwencje JPG/WebP | A04 |
| 2-pass „target MB” | ⚠️ ±4% na typowym materiale, przekroczenia na krótkich klipach, cichy limit | A16 |
| filtrowanie enkoderów GPU | ⚠️ tylko kompilacja, bez sprawdzenia sprzętu, bez cache | A20, A11 |
| escaping nazw w concat | ✅ `'` i `\` poprawne, newline odrzucany (`sequence.py:513-520`). ❌ `%` w muxerze `image2` | A12 |
| sprzątanie plików tymczasowych | ⚠️ `finally` w runnerze działa, 2-pass nie zostawia logów; zasoby tworzone przy budowie; częściowe wyniki zostają | A07, A18 |
| ochrona przed nadpisaniem | ❌ tylko MP4 sekwencji | A02, A03, A09 |
| blokowanie UI | ⚠️ konwersja w `QThread`; planowanie i probe w wątku UI | A11 |
| progress | ❌ tylko po komendzie | A05 |
| anulowanie | ❌ brak | A06 |

---

## 5. Martwy kod

| element | gdzie | uwagi |
|---|---|---|
| `args` presetów H.264/H.265 w `SIMPLE_VIDEO` | `app/presets/video.py:81-90` | komenda budowana przez `_encoder_codec_vargs`; z wpisu używane są tylko etykieta i sufiks |
| `vargs` H.264 w `SEQ_FORMATS` (CRF 18) | `app/presets/sequence.py:42-44` | ścieżka CPU nadpisuje je wartością `crf` |
| fallback „brak fps” w `_h264_size_seq_job` | `app/presets/sequence.py:300-309` | nieosiągalny: fps jest walidowany wcześniej |
| `dpx` w `RGB_DISPLAY_EXTS` | `app/presets/sequence.py:59` | `kind_of` nie akceptuje `.dpx` (`app/core/ffmpeg.py:25`) |
| `cleanup` z `_h264_size_seq_job` | `app/presets/sequence.py:221-226` | ignorowany (passlog leży w `tmp`, sprzątanym osobno) |
| zdublowany docstring | `app/core/color.py:16` | |
| strażnik „stary `presets.py`” | `app/gui.py:42-48` | dotyczy instalacji sprzed refaktoru pakietu |
| `linux/images_to_video.sh` | | żadna akcja Nemo go nie wywołuje, a `install.sh` linkuje go do `~/.local/bin` |
| shim importu `sys.path` | `app/cli.py:24-27`, `app/gui.py:17-19`, `app/launch.py:10`, `app/audio_separation.py:23-25` | zniknie przy `src/` layout (D5) |
| re-eksport prywatnych nazw | `app/presets/__init__.py:14-32` | `_scale_filter`, `_natural_key`, `_seq_stem`, `_resolve_proxy_variant` używane tylko w testach |
| `IMAGE_QUALITY` | `app/presets/image.py:15-16` | GUI ma własne etykiety (`gui_panels.py:368-372`), CLI własne `choices` |

---

## 6. Duplikacje GUI ↔ CLI i wycieki logiki z `presets/`

**Logika, która powinna być w rdzeniu, a jest w front-endach:**

1. **Wyznaczanie pełnej sekwencji i nazwy filmu z jednej klatki**: dwie implementacje.
   CLI: `app/cli.py:102-111` (nazwa = `sequence.name`, folder nadrzędny przy `--mp4-in-parent`).
   GUI: `app/gui_panels.py:339-351` (ponowna detekcja, `require_complete`, walidacja nazwy, ścieżka).
   GUI waliduje nazwę (`/`, `\`, newline), CLI nie.
2. **Walidacja wejścia `seq`** (foldery xor pliki, `--output` tylko dla klatek, istnienie ścieżek):
   tylko w CLI (`app/cli.py:83-88`).
3. **Reguła podfolderu przy split** (`len(files) > 1`): tylko w CLI (`app/cli.py:126`).
4. **Wybór trybu rozmiaru**: CLI z obecności `--target-mb` (`cli.py:52`), GUI z radia
   (`gui_panels.py:319,681`). Różne domyślne CRF dla sekwencji i wideo (A29).
5. **Filtrowanie plików niedostępnych i „jeden typ mediów”**: tylko w GUI
   (`gui_main_window.py:188-231,269-293`); CLI tylko pomija nieistniejące (`cli.py:31-36`).
6. **Wybór trybu (obrazy / wideo / sekwencja / foldery)**: w GUI (`gui_main_window.py:201-229,295-297`).

**Niespójne opcje:**

| opcja | CLI | GUI |
|---|---|---|
| własny LUT ACES dla obrazów | `image --aces-lut` | brak |
| wyłączenie konwersji koloru EXR | `--no-color` (image, seq) | brak |
| tylko wskazana klatka | `seq --selected-only` | brak (zawsze cała sekwencja) |
| pełna ścieżka wyniku sekwencji | `seq --output` | tylko nazwa |
| split, flipbook | tak | brak |
| enkoder dla ProRes/DNxHD w sekwencji | ignorowany | widoczny, ale bez efektu (`gui_panels.py:91-106`) |

**Duplikacje wewnątrz GUI:** etykiety CRF (`gui_panels.py:239-246` i `643-650`), etykiety
enkoderów (`94-103` i `608-617`), grupa „Kontrola rozmiaru” (`108-147` i `562-601`), grupa
„Colorspace EXR” (`202-215` i `437-451`), wywołania `detect_sequence` 3–4 razy na jedną akcję
(`gui_main_window.py:235,252`, `gui_panels.py:296,340`).

**Mieszanie warstw:** buildery w `presets/` robią I/O (probe, mkdtemp, mkdir: A11, A18) i
decydują o politykach (nadpisywanie, nazwy, foldery). W v2 planowanie (nazwy, kolizje,
polityka nadpisywania, probe) i budowanie argumentów powinny być rozdzielone.

---

## 7. Testy i CI

- **Fałszywa pewność:** test postępu (A05).
- **Brak testów na realnym ffmpeg** dla: dnxhr (A01), cineform, h265, prores_nuke, h264size
  2-pass na wideo, frames bez audio (A08), nieparzystych wymiarów (A04), `%` w nazwach (A12),
  23,976 (A13), kolizji i nadpisywania (A02, A03), mieszania folderów (A10), wielu ścieżek audio.
- **Czas:** `h264_20m` na 1080p z szumem, preset `slow`, 64,7 s. Ten sam warunek można
  sprawdzić na 640×360 w kilka sekund.
- **mypy** pomija GUI i CLI.
- **CI** (`.github/workflows/ci.yml`): uruchamia się tylko dla `master` (push) i PR do
  `master`, więc gałąź przepisania bez PR nie jest testowana; `ruff` i `mypy` bez przypiętych
  wersji (nowa wersja może nagle zepsuć CI); brak cache pip; brak zrzutów okna.
- **Testy Windows** (3) uruchamiają się tylko na prawdziwym Windows w CI.

## 8. Co działa dobrze i warto zachować

- Argumenty jako listy, bez shella. Na Windows `CREATE_NO_WINDOW` dla workerów konsolowych.
- Detekcja sekwencji: padding (także przejście 0999 → 1000), dziury raportowane bez alokacji
  zakresu, duplikaty numerów jako błąd, tylko bezpośredni folder.
- Audio sekwencji: nazwa sekwencji → nazwa folderu, wykluczenie wyniku, jawny wybór przy
  niejednoznaczności, `apad` + `-t` (cisza i przycięcie).
- Escaping concat i odrzucanie newline.
- Separacja audio: suma SHA-256 przed deserializacją, wyłączny folder wyniku z sufiksem,
  `rmtree` tylko własnego folderu, izolowany venv, brak wysyłania mediów.
- Instalator Windows: staging + backup przy aktualizacji, ścieżki narzędzi zapisane w
  `windows-tools.json`, polecenie menu z cudzysłowami, PowerShell bez wstawiania ścieżek do kodu.
- `h264_20m`: twardy limit w każdym oknie 1 s, zweryfikowany testem.
- Etykiety Qt z nazwami plików jako `PlainText`.
