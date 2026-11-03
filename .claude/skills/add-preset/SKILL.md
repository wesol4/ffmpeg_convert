---
name: add-preset
description: Dodanie lub zmiana presetu konwersji (wideo, format sekwencji, obrazy) w ffmpeg_convert — od receptury przez CONFIG, CLI, GUI i filtr enkoderów po test na realnym ffmpeg i README. Użyj przy każdej zmianie argumentów ffmpeg w presetach.
---

# Dodanie presetu

Kontrakt: `docs/rewrite/spec.md` (sekcje VID, SEQ-F, IMG). Nowy preset = nowy punkt w spec.
Ścieżki poniżej dotyczą v0.7 (`app/`); po etapie 2 rdzeń przechodzi do `src/ffmpeg_convert/` (D5),
kolejność kroków zostaje.

## 1. Receptura

- Wideo: `app/presets/video.py`
  - id w `VideoPreset` (StrEnum, wartość = id w CLI);
  - jedna komenda → wpis w `SIMPLE_VIDEO` (`label`, `suffix`, `ext`, `args`);
  - kilka komend / probe → funkcja `_<id>_job(src, base, batch, …) -> Job`, etykieta w
    `SPECIAL_VIDEO`, gałąź w `build_video_jobs`;
  - pozycja w `VIDEO_PRESETS` = kolejność w GUI.
- Format sekwencji: `SeqFormat` + `SEQ_FORMATS` w `app/presets/sequence.py`.
- Obrazy: `build_image_jobs` w `app/presets/image.py`.

Zasady receptury:
- lista argumentów, bez shella; wynik przez `_out_dir()` (batch → podfolder `<sufiks>/`);
- **nie dodawaj nowego `-y` do pliku wynikowego** (WSP-03, D7); po etapie 2 nadpisywaniem
  zarządza rdzeń, nie preset;
- kodeki 4:2:0 / 4:2:2: parzyste wymiary przez przycięcie 1 px (WSP-11, D11; dziś `EVEN_CROP`
  w `sequence.py`);
- kolor: tagi zgodne z faktyczną macierzą, reguła dystrybucja vs montaż → skill `color-pipeline`;
- `%` w części dosłownej wzorca `image2` → `%%` (WSP-10);
- każde `probe.*` to osobny proces ffprobe: nie dokładaj kolejnych wywołań na plik bez potrzeby.

## 2. CONFIG

Wartości do strojenia (CRF, preset kodera, bitrate, limity) w `app/config.py` (zamrożone
dataclassy), receptura czyta z `CONFIG`. Zmiana domyślnej wartości → aktualizacja
`tests/test_presets.py::TestConfig`.

## 3. CLI

`--preset` bierze wartości z `VideoPreset` automatycznie. Nowa opcja → `build_parser()` i
`cmd_video()` w `app/cli.py`. Opcja, której preset nie używa, ma dać ostrzeżenie (D14).

## 4. GUI

`VideoPanel` (`app/gui_panels.py`) tworzy radio z `VIDEO_PRESETS`. Opcje presetu: własny
`QGroupBox` + widoczność w `_toggle_option_boxes()`. Teksty po polsku, krótkie, bez kropek na
przyciskach. Zmiany układu → skill `gui-change`.

## 5. Enkodery GPU

Tylko jeśli preset to H.264/H.265: parametry w `_encoder_codec_vargs()` (`video.py`), gałąź w
`build_video_jobs`, widoczność `encoder_box` w `_toggle_option_boxes()`. Presety montażowe i
2-pass ignorują enkoder (VID-14). `probe_encoders()` sprawdza tylko kompilację ffmpeg (A20).

## 6. Testy

1. Komenda jako lista: `tests/test_presets.py` (dokładne porównanie listy argumentów).
2. Realny ffmpeg (skill `ffmpeg-verify`): fixture → `runner.run_job()` → ffprobe.

```python
src = tmp / "src.mp4"
verify.main(["fixture", str(src), "--kind", "video", "--size", "1281x721",
             "--fps", "24000/1001", "--frames", "24"])
job, = presets.build_video_jobs("nowy_preset", [src])
runner.run_job(job)
out = Path(job.cmds[-1][-1])
assert verify.main(["check", str(out), "--frames", "24", "--fps", "24000/1001",
                    "--codec", "…", "--pix-fmt", "…", "--audio", "1"]) == 0
```

Minimum przypadków: zwykłe 1080p, nieparzyste wymiary, 23,976, bez audio, źródło RGB
(`--kind rgbvideo`), batch z dwoma plikami o tym samym stem.

## 7. Dokumentacja

README → „Presety wideo” (jedna linia: zastosowanie, kodek, sufiks, id CLI); `spec.md` → nowy
punkt VID-xx; `CHANGELOG.md` → „Dodane”.

## Lista kontrolna

- [ ] receptura + id + kolejność w UI
- [ ] wartości w CONFIG
- [ ] CLI (opcje, ostrzeżenia)
- [ ] GUI (opcje, widoczność, polskie etykiety)
- [ ] enkodery (albo jawnie CPU-only)
- [ ] test listy argumentów + test realnego ffmpeg (6 przypadków)
- [ ] README, spec, CHANGELOG
- [ ] `venv/bin/ruff check . && venv/bin/mypy app && venv/bin/python -m pytest -q`
