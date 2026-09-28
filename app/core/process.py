"""Portable subprocess defaults for a Windows pythonw GUI and console workers."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def console_python() -> str:
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        return str(executable.with_name("python.exe"))
    return str(executable)


def subprocess_options() -> dict:
    # Console workers keep real stdout/stderr handles, without flashing a window.
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)} if os.name == "nt" else {}
