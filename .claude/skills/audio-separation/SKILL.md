---
name: audio-separation
description: Lokalna separacja głosu, muzyki i efektów (Bandit v2, ELUATE) w ffmpeg_convert — przypięte wersje, suma kontrolna modelu przed deserializacją, izolowany runtime .audio-runtime/, lock instalacji, wyniki bez nadpisywania. Użyj przy każdej zmianie w app/audio_separation.py, presecie audio_separate albo komendzie audio-setup.
---

# Separacja audio

Kontrakt: `docs/rewrite/spec.md`, sekcja 10 (AUD-01…08).

## Pliki

`app/audio_separation.py` (instalacja runtime + worker), preset `VideoPreset.AUDIO_SEPARATE` w
`app/presets/video.py` (zadanie uruchamia worker konsolowym Pythonem: `console_python()`),
CLI `audio-setup` i `video --preset audio_separate`, testy `tests/test_audio_separation.py`.

## Twarde zasady

1. **Media nie opuszczają komputera.** Sieć tylko przy instalacji (PyPI, PyTorch, Zenodo).
2. **Suma SHA-256 modelu przed deserializacją.** Checkpoint torch zawiera pickle. Pobranie do
   `checkpoint.download`, `verified_checkpoint()`, dopiero potem `replace()` na
   `checkpoint-multi.ckpt`. Nigdy nie wczytuj pliku bez weryfikacji, także przy `--checkpoint`.
3. **Przypięte wersje**: `torch==2.6.0`, `torchaudio==2.6.0` (indeks CPU), `eluate==0.0.3`,
   `MODEL_URL`, `MODEL_SHA256`. Zmiana którejkolwiek → nowa wartość `RUNTIME_VERSION` (wymusza
   reinstalację) i sprawdzenie, że prywatne API ELUATE nadal istnieje
   (`_load_audio`, `_open_stem_writers`, `_demix_streaming`).
4. **Izolacja**: osobny venv w `.audio-runtime/venv`; GUI i CLI nie importują bibliotek ML
   (test sprawdza, że `torch` nie jest w `sys.modules`).
5. **Wyniki bez nadpisywania**: `reserve_output()` tworzy `<stem>_AUDIO`, potem `_002`…
   (`mkdir` bez `exist_ok`). Przy błędzie usuwany jest tylko ten folder.
6. **Wejście sprawdzane przed instalacją**: brak pliku albo brak ścieżki audio → błąd, nic nie
   jest pobierane ani tworzone.
7. Postęp przez linie `progress_fraction=<0..1>` na stderr (runner je rozumie).

## Runtime i lock

- Lokalizacja dziś: `<katalog nad app>/.audio-runtime` (Windows:
  `%LOCALAPPDATA%\FFmpegConvert\.audio-runtime`, Linux: w repo, w `.gitignore`).
  W v2 (D5): katalog danych użytkownika, migracja przez `rename` na tym samym dysku.
- `install.lock` tworzony z `O_EXCL`; po awaryjnym zamknięciu zostaje i wymaga ręcznego usunięcia.
  Plan (A22): PID w locku i wykrywanie martwego procesu.
- Plan (A22): `requirements` z hashami (`pip install --require-hashes -r …`) i przypięte
  zależności przechodnie (numpy, soundfile, pyyaml…).

## Wynik

`speech.wav`, `music.wav`, `sfx.wav`, `background_no_dialogue.wav` (48 kHz / 24 bit, stereo;
tło ściszane tylko wtedy, gdy szczyt przekroczyłby 0,98), `video_without_dialogue.mkv` (obraz kopiowany, tylko gdy
źródło ma obraz), `report.json`. Przetwarzana pierwsza ścieżka audio.

## Testy

Szybkie (bez pobierania modelu, w CI): `venv/bin/python -m pytest -q tests/test_audio_separation.py`.
Pełny test ręczny (kilka GB, wymaga sieci):
```bash
python app/cli.py audio-setup
python app/cli.py video --preset audio_separate krotki_klip_z_mowa.mp4
```
Sprawdź: komplet plików, długości WAV = długość źródła, drugi przebieg tworzy `_AUDIO_002`.
Nie commituj `.audio-runtime/`, modelu ani nagrań.
