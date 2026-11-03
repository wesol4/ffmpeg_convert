---
name: ffmpeg-verify
description: Weryfikacja wyniku FFmpeg przez ffprobe (klatki, długość, kodek, pix_fmt, tagi koloru, audio, rozmiar, kolor piksela) i generowanie fixture'ów z lavfi skryptem scripts/verify_output.py. Użyj przy każdej zmianie strumieni, liczby klatek, długości, kodeków lub koloru oraz przy pisaniu testów na realnym ffmpeg.
---

# Weryfikacja wyniku FFmpeg

Zasada z `CLAUDE.md`: testuj faktyczny plik wynikowy, nie tylko listę argumentów.
Narzędzie: `scripts/verify_output.py` (stdlib; test: `tests/test_verify_output.py`).
Fixture'y twórz w katalogu tymczasowym, **nigdy w repo**.

## Komendy

```bash
V="venv/bin/python scripts/verify_output.py"
$V fixture /tmp/t/src.mp4 --kind video --size 1281x721 --fps 24000/1001 --frames 48
$V check out.mp4 --frames 48 --fps 24000/1001 --codec h264 --pix-fmt yuv420p \
   --color bt709/bt709/iec61966-2-1/tv --audio 1 --audio-duration 2.002
$V probe out.mp4            # pełny raport JSON
$V sample out.mp4 --matrix bt709 --expect 10,98,204   # kolor środka kadru, tolerancja 3
```

Kody: `check`/`sample` → 0 zgodne, 1 niezgodne, 2 błąd odczytu.

## Co i jak sprawdzać

| cecha | flaga | uwaga |
|---|---|---|
| liczba klatek | `--frames` | `-count_packets`, bez dekodowania |
| długość obrazu | `--duration` (±`--tolerance`, domyślnie 0,05 s) | długość strumienia wideo; długość kontenera bywa dłuższa o priming AAC (~5 ms) |
| fps | `--fps 24000/1001` | porównanie ułamków; 23,976 zapisane jako 2997/125 to błąd (A13) |
| kodek, pix_fmt, wymiar | `--codec`, `--pix-fmt`, `--size` | |
| tagi koloru | `--color space/prim/trc/range` | `-` pomija pole; brak tagu = `unknown` |
| audio | `--audio N`, `--audio-codec`, `--audio-rate`, `--audio-duration` | `--audio 0` = brak ścieżki |
| rozmiar | `--max-mb`, `--min-mb` | 1 MB = 10^6 B |
| kolor | `sample --matrix bt709|bt601|auto` | dekoduj tak, jak zrobi to odtwarzacz; `auto` = wg tagów |

## Fixture'y

| scenariusz | polecenie |
|---|---|
| wideo HD bez tagów (jak z generatora AI) | `fixture x.mp4 --kind video --size 1280x720` (macierz 709, bez tagów) |
| to samo z tagami 709 | `… --tag-709` |
| nieparzyste wymiary | `--size 1281x721` (lavfi sam zaokrągla, skrypt skaluje do dokładnego) |
| dokładna liczba klatek NTSC | `--fps 24000/1001 --frames 48` (samo `--duration 2` da 47) |
| bez audio | `--no-audio` |
| źródło RGB (PNG w MOV) | `--kind rgbvideo` (`.mov`) |
| kolor wzorcowy | `--pattern color --color 0x0A62CC` (różnica 601/709 jest tu największa) |
| trudny materiał (bitrate, 2-pass) | `--pattern noise` |
| sekwencja klatek | `fixture dir --kind frames --frame-format png|jpg|tif|exr --frames 12 --name shot --start 1001` |
| dziura w sekwencji | jak wyżej, potem usuń jedną klatkę |
| audio dłuższe / krótsze | `fixture a.wav --kind audio --duration 5` |
| kilka ścieżek audio | ręcznie: `ffmpeg -f lavfi -i testsrc2=d=1 -f lavfi -i sine=f=300:d=1 -f lavfi -i sine=f=600:d=1 -map 0 -map 1 -map 2 -c:v libx264 -c:a aac multi.mkv` |

Wymiary: trzymaj ≤ 640×360 i ≤ 2 s. Wyjątek: testy macierzy koloru dla HD wymagają wysokości
≥ 720, bo program traktuje nieotagowane HD jako 709 (`probe_untagged_hd_yuv`).

## W testach

```python
spec = importlib.util.spec_from_file_location("verify_output", ROOT / "scripts/verify_output.py")
```
Wzorzec: `tests/test_verify_output.py`. Testy z ffmpeg oznaczaj
`@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")`.

## Oczekiwane wyniki presetów (v0.7, źródło 8-bit z AAC)

| preset | kodek / pix_fmt | audio |
|---|---|---|
| h264, h264size, h264_20m | h264 / yuv420p | aac (20m: 128 kb/s) |
| h265 | hevc / yuv420p | aac |
| dnxhd | dnxhd / yuv422p, 1920×1080 | pcm_s16le |
| dnxhr | po naprawie (D10): dnxhd profil HQX / yuv422p10le | pcm_s16le |
| prores | prores / yuv422p10le | pcm_s16le |
| prores_nuke | prores / yuv422p10le, tagi bt709/bt709/bt709 | pcm_s24le 48000 |
| cineform | cfhd / yuv422p10le | pcm_s16le |
| last_frame | png / rgb24, 1 klatka | — |
| frames | N plików = N klatek źródła; WAV pcm_s24le | |

Wyniki pierwszego audytu: `docs/rewrite/audit.md`, sekcja 2.
