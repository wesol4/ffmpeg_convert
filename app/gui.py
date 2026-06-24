#!/usr/bin/env python3
"""GUI (PyQt5) — entry-point.

Logika interfejsu żyje w app.gui_* (style, widgets, panels, workers,
main_window); konwersja w app.presets + app.runner (te same receptury co CLI).

Uruchamialny jako skrypt (python app/gui.py, pythonw …\\app\\gui.py z menu
Windows) i jako moduł (python -m app.gui) — bootstrap dodaje rodzica app/.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Bootstrap: rodzic app/ na sys.path → absolutne importy `from app…` działają
# w obu trybach uruchomienia (skrypt i -m).
_PARENT = Path(__file__).resolve().parents[1]
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

from app import presets  # noqa: E402
from app.gui_main_window import MainWindow  # noqa: E402
from app.log import get_logger, setup_logging  # noqa: E402
from app.gui_panels import ImagePanel, VideoPanel  # noqa: E402
from app.gui_style import APP_STYLE, ICON  # noqa: E402
from app.gui_widgets import DropList  # noqa: E402
from app.gui_workers import ConvertWorker  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

# Re-eksport dla zgodności wstecz (from app import gui; gui.MainWindow()).
__all__ = ["main", "MainWindow", "ImagePanel", "VideoPanel", "DropList",
           "ConvertWorker", "APP_STYLE", "ICON"]


def main(files=None) -> int:
    setup_logging()
    log = get_logger()
    # Guard na przestarzałą kopię app/: stary, płaski presets.py (sprzed
    # refaktoru pakietowego) przykrywa nowy pakiet app/presets/ — wtedy brakuje
    # presets.VideoPreset i GUI cicho traci m.in. suwak h264size. Wybij się
    # czytelnym komunikatem zamiast półdziałającego okna.
    if not hasattr(presets, "VideoPreset"):
        log.error("niezgodny rdzeń app/ — brak presets.VideoPreset (stary presets.py?)")
        print("BŁĄD: niezgodna wersja rdzenia app/ — brak presets.VideoPreset.\n"
              "Przekopiuj cały folder app/ na nowo (stary presets.py przykrywa "
              "pakiet presets/). Uruchom win\\setup.bat i wybierz 3 (Skopiuj app\\).",
              file=sys.stderr)
        return 1
    log.info("GUI start, files=%d", len(files or []))
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)
    win = MainWindow()
    if files:
        win.add_files([Path(f) for f in files])
    win.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
