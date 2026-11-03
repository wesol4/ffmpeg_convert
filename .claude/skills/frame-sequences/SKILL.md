---
name: frame-sequences
description: Sekwencje klatek w ffmpeg_convert — wykrywanie z jednej klatki, padding, dziury, kilka sekwencji w folderze, tryb folderów, dopasowanie audio, dopełnianie ciszą i przycinanie, nazwa i ochrona wyniku, fps NTSC, proxy i miniatura. Użyj przy każdej zmianie w app/core/sequences.py, app/presets/sequence.py albo panelu sekwencji.
---

# Sekwencje klatek

Kontrakt: `docs/rewrite/spec.md`, sekcja 5 (SEQ-D, SEQ-A, SEQ-O, SEQ-F, SEQ-C).

## Twarde zasady

1. Wykrywaj **tylko wybraną sekwencję w jej bezpośrednim folderze**: ten sam prefiks i
   rozszerzenie, ta sama rodzina paddingu (także przejście `0999 → 1000`).
2. **Nie zamykaj dziur i nie mieszaj sekwencji.** Brakujące numery zgłaszaj („Brak klatek: 5,
   10–12”), wideo blokuj. Kilka sekwencji w folderze → błąd z prośbą o wybór klatki.
3. **Najpierw pokaż liczbę i zakres**, potem przełączaj z obrazów na wideo; zwykła konwersja
   wybranego obrazu zostaje dostępna.
4. **Audio jest jawne albo dopasowane po nazwie sekwencji / folderu.** Niejednoznaczność →
   wybór pliku. Niepowiązane nagrania nigdy.
5. Krótsze audio **dopełnij ciszą**, dłuższe **przytnij** do N/fps (`-af apad -t <N/fps>`).
6. **Wynik nigdy nie jest wejściem** (ani klatką, ani audio). Istniejący plik o nazwie
   podanej przez użytkownika → błąd, nie nadpisanie.

## Gdzie w kodzie (v0.7)

| element | miejsce |
|---|---|
| tożsamość klatki, wykrywanie, dziury, duplikaty | `app/core/sequences.py`: `frame_identity`, `detect_sequence`, `FrameSequence.require_complete` |
| dopasowanie audio | `app/core/sequences.py::matching_audio` (ffprobe na kandydata) |
| budowa wideo, audio, kolor, proxy, miniatura | `app/presets/sequence.py::build_seq_job` |
| tryb folderów | `build_seq_jobs_from_folders` |
| CLI: jedna klatka → sekwencja | `app/cli.py::cmd_seq` |
| GUI: wykrycie i przełącznik | `app/gui_main_window.py::_detect_selected_sequence`, `_sequence_mode_changed`; `SeqPanel` w `app/gui_panels.py` |

Logika „jedna klatka → nazwa i ścieżka filmu” jest dziś zdublowana w CLI i GUI; w etapie 2
trafia do rdzenia (audit, sekcja 6).

## Jak to działa

- **image2 przez ponumerowane linki**: klatki linkowane do katalogu tymczasowego jako
  `seq_00001.<ext>`… Dzięki temu dowolne nazwy (`%`, spacje, apostrofy), numeracja od 1001 i
  pełna liczba klatek. Na Windows bez uprawnień do linków: kopie. Katalog sprząta runner.
- **fps**: dodatni i skończony; 23,976 / 29,97 / 59,94 / 47,952 / 119,88 → ułamki NTSC (D9,
  etap 2). Długość = N / fps.
- **Audio**: kandydaci `.wav .flac .mp3 .m4a .aac .ogg .aif .aiff` oraz `.mp4 .mov .mkv .webm` z
  dźwiękiem; kolejność: stem = nazwa sekwencji, potem stem = nazwa folderu, audio przed
  kontenerami wideo. `-map 0:v:0 -map 1:a:0`, więc obraz zawsze z sekwencji.
- **Proxy**: `<folder>/<podfolder wariantu>/<nazwa>.<NNNN>.<ext>`, numeracja od 1001, warianty w
  `CONFIG.seq.proxy_variants`.
- **Miniatura**: klatka z połowy nowego filmu, `<nadrzędny>/<nazwa>_thumb.jpg`.
- **Tryb folderów**: jedno zadanie na folder; foldery bez obrazów pomijane.

## Znane błędy do naprawy w etapie 2

A10 (folder miesza luźne obrazy z pojedynczą klatką), A09 (proxy dopisuje do starych klatek),
A13 (23,976 → 2997/125), A04 (sekwencje JPG o nieparzystym wymiarze), A18 (katalog
tymczasowy tworzony przy budowaniu), A28 (proxy nazwane od folderu).

## Testy

`tests/test_sequences.py` (realny ffmpeg: klatki, długość, audio krótsze/dłuższe/wyłączone,
CLI, ochrona wyniku), `tests/test_gui_sequences.py` (offscreen), `tests/test_presets.py::TestSeq*`.

Fixture'y (skill `ffmpeg-verify`):
```bash
V="venv/bin/python scripts/verify_output.py"
$V fixture /tmp/t/shot010 --kind frames --name shot010 --frames 48 --start 1001
$V fixture /tmp/t/shot010/shot010.wav --kind audio --duration 5      # audio do przycięcia
venv/bin/python app/cli.py seq --fps 23.976 /tmp/t/shot010/shot010.1010.png
$V check /tmp/t/shot010/shot010.mp4 --frames 48 --audio 1 --audio-duration 2.002
# po D9 dodatkowo: --fps 24000/1001
rm /tmp/t/shot010/shot010.1005.png                                    # wariant: dziura → błąd
$V fixture /tmp/t/shot010 --kind frames --name other --frames 3       # wariant: druga sekwencja
```

Przypadki do pokrycia przy każdej zmianie: jedna klatka ze środka, padding 0999→1000, dziura,
duplikat numeru (`.png` i `.PNG`), dwie sekwencje w folderze, folder z luźnym obrazem, audio
dokładne / krótsze / dłuższe / niejednoznaczne / film jako audio, istniejący wynik, 23,976.
