# FFmpeg Convert

Desktopowe narzędzie do konwersji wideo, kompresji obrazów, sekwencji klatek, splitu/flipbooka i
lokalnej separacji audio. Python 3.12, Qt (PyQt5; od etapu 3 PySide6), FFmpeg/ffprobe. GUI, CLI,
menu kontekstowe Nemo i Windows. Teksty UI po polsku. Kompaktowy układ desktopowy, bez web UI.

Trwa przepisanie v2: kontrakt `docs/rewrite/spec.md`, decyzje `docs/rewrite/decisions.md`
(wszystkie rekomendacje zaakceptowane), błędy `docs/rewrite/audit.md`. Procedury: `.claude/skills/`.

## Mapa architektury (v0.7; w v2 → `src/ffmpeg_convert/`, D5)

| miejsce | rola |
|---|---|
| `app/core/` | `jobs` (model `Job`), `ffmpeg` (narzędzia, typy plików, enkodery), `probe`, `sequences` (wykrywanie klatek i audio, tylko odczyt), `color` (EXR → display), `process` |
| `app/presets/` | receptury wspólne dla GUI i CLI: `video`, `image`, `sequence`; zwracają `Job` |
| `app/config.py` | `CONFIG`: wartości receptur |
| `app/runner.py` | wykonanie list argumentów, postęp, sprzątanie |
| `app/cli.py` | CLI: `video`, `image`, `seq`, `split`, `flipbook`, `gui`, `audio-setup`, `update` |
| `app/gui*.py`, `app/launch.py` | GUI (okno, panele, workery, styl), start z menu Windows |
| `app/audio_separation.py` | opcjonalny izolowany model CPU |
| `linux/`, `win/` | akcje Nemo i `install.sh`; instalator Windows |
| `scripts/verify_output.py` | weryfikacja wyniku przez ffprobe i fixture'y z lavfi |

## Twarde zasady (bezpieczeństwo i dane)

- Procesy tylko jako listy argumentów, bez shella.
- Nazwy w listach concat escapowane; nazwa z newline odrzucana. `%` w nazwach nie może trafić
  do wzorca `image2` bez escapowania.
- Nazwy plików w Qt wyłącznie jako zwykły tekst.
- Suma kontrolna modelu sprawdzana przed deserializacją; media użytkownika nigdy nie są wysyłane.
- Wynik nigdy nie jest wejściem; brak cichego nadpisywania; brak częściowych wyników po błędzie.
- Nie mieszaj sekwencji i nie zamykaj dziur; audio jawne albo dopasowane po nazwie.
- Sprzątaj wyłącznie zasoby tymczasowe utworzone przez bieżące zadanie.
- Nie commituj mediów, modeli, runtime'u (`.audio-runtime/`) ani `venv/`.
- GUI i CLI zachowują się tak samo; logika konwersji tylko w rdzeniu.

## Walidacja

```sh
venv/bin/ruff check .
venv/bin/mypy app
QT_QPA_PLATFORM=offscreen venv/bin/python -m pytest -q
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p test_gui_sequences.py -v
```

Testy GUI wymagają biblioteki Qt w wybranym interpreterze (PySide6 na Linuksie także `libegl1`).
Zmiany strumieni, klatek, długości, kodeków i koloru sprawdzaj na realnym pliku
(`scripts/verify_output.py`, skill `ffmpeg-verify`).
