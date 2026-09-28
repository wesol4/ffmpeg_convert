"""Windowed entry point with a visible error if GUI startup fails."""
from __future__ import annotations

import os
import importlib
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    # pythonw has no standard streams; libraries must still be able to print.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    try:
        gui_main = importlib.import_module("app.gui").main
        return int(gui_main(sys.argv[1:]))
    except Exception:
        detail = traceback.format_exc()
        try:
            from app.log import setup_logging
            log = setup_logging()
            with log.open("a", encoding="utf-8") as stream:
                stream.write(detail)
            message = f"Nie można uruchomić FFmpeg Convert.\nUruchom ponownie win\\setup.bat.\nLog: {log}"
        except Exception:
            message = "Nie można uruchomić FFmpeg Convert. Uruchom win\\setup.bat.\n" + detail[-1500:]
        if os.name == "nt":
            import ctypes
            getattr(ctypes, "windll").user32.MessageBoxW(None, message, "FFmpeg Convert", 0x10)
        else:
            print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
