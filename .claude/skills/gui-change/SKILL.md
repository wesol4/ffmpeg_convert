---
name: gui-change
description: Zmiany w GUI ffmpeg_convert (Qt) — architektura okna i paneli, workery w wątkach, polskie teksty, dostępność z klawiatury, test offscreen i zrzut okna do przeglądu. Użyj przy każdej zmianie w app/gui*.py (v2: pakiet gui/), układu, tekstów UI albo stylu.
---

# Zmiana w GUI

Kontrakt: `docs/rewrite/spec.md`, sekcja 8 (GUI-01…14). Wygląd marki: skill `lgc-brand-ui`.
Etap 3 przenosi GUI na **PySide6** (D1) i styl do `app/ui/theme.py`; do tego czasu PyQt5 5.15.

## Mapa (v0.7)

| plik | rola |
|---|---|
| `app/gui.py` | entry point: `QApplication`, styl, `MainWindow`, pliki z argumentów |
| `app/launch.py` | start z menu Windows (`pythonw`): okno błędu z logiem, gdy GUI nie wstanie |
| `app/gui_main_window.py` | `MainWindow`: lista, tryb (obrazy / wideo / sekwencja / foldery), start, log, pasek |
| `app/gui_panels.py` | `ImagePanel`, `VideoPanel`, `SeqPanel`: zbierają opcje i wołają `presets.build_*` |
| `app/gui_widgets.py` | `DropList` (przeciągnij i upuść, podpowiedź) |
| `app/gui_workers.py` | `ConvertWorker`, `UpdateChecker` (`QThread` + sygnały) |
| `app/gui_style.py` | QSS (etap 3: generowany z tokenów) |

## Zasady

1. **GUI nie ma logiki konwersji.** Nazwy wyników, kolizje, walidacja i probe są w rdzeniu;
   panel tylko zbiera parametry. Nowa reguła → rdzeń + test, potem GUI.
2. **Nic blokującego w wątku UI**: żadnego `subprocess`, ffprobe, `iterdir()` po dużych folderach.
   Planowanie i probe w workerze, wynik przez sygnał (A11). Długie zadanie zawsze z „Przerwij”
   (WSP-14).
3. **Nazwy plików jako zwykły tekst**: `QLabel.setTextFormat(Qt.PlainText)`; nigdy HTML z nazwą
   pliku; elementy listy (`QListWidgetItem`) są bezpieczne.
4. **Teksty po polsku**, krótkie i konkretne; bez kropek na przyciskach; „…” tylko na
   przyciskach, które otwierają okno wyboru („Dodaj pliki…”).
5. **Klawiatura**: każda kontrolka osiągalna Tabem w logicznej kolejności; etykieta powiązana
   z polem (`setBuddy`) i mnemonik `&`; widoczny focus (obrys z `lgc-brand-ui`); Enter
   uruchamia główną akcję, Esc przerywa lub zamyka okno dialogowe.
6. **Kompaktowy układ desktopowy**, nie web UI. Liczba klatek, długość, wybór audio i przycisk
   akcji obok siebie, bez przewijania (GUI-07).
7. Okno z systemową ramką albo z pełną obsługą krawędzi, minimalizacji i Snap (A21).

## Test offscreen

```bash
QT_QPA_PLATFORM=offscreen venv/bin/python -m pytest -q tests/test_gui_sequences.py
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p test_gui_sequences.py -v
```
Wzorzec testu: `tests/test_gui_sequences.py` (okno z plikami w katalogu tymczasowym, klik,
sprawdzenie panelu i zadań; worker zastępowany `mock`).

## Zrzut okna do przeglądu

```python
import os; os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication          # etap 3: PySide6
from app.gui_style import APP_STYLE
from app.gui_main_window import MainWindow
app = QApplication([]); app.setStyleSheet(APP_STYLE)
win = MainWindow(); win.resize(760, 840); win.show(); app.processEvents()
win.grab().save("docs/rewrite/screens/pusty.png")
win.add_files([...]); app.processEvents(); win.grab().save("docs/rewrite/screens/wideo.png")
```
Stany do zrzutu (etap 3): pusty, wideo, obrazy, sekwencja, praca, błąd. Rozmiary: 760×840 i
minimalny. Skalowanie: `QT_SCALE_FACTOR=1.5` dla przybliżenia 150%; ostateczna kontrola na
Windows 100% i 150% oraz na Linuksie. Do repo trafiają tylko zrzuty interfejsu, nie media
użytkownika; zrzut obejrzyj, zanim go opiszesz.

## Lista kontrolna

- [ ] logika w rdzeniu, GUI tylko zbiera opcje
- [ ] brak blokowania UI (probe i planowanie w workerze)
- [ ] polskie teksty, bez kropek na przyciskach
- [ ] Tab, buddy, mnemoniki, widoczny focus
- [ ] test offscreen + zrzuty stanów obejrzane
- [ ] `venv/bin/ruff check .` i pełne `pytest`
