"""Logging diagnostyczny — dzienny plik w katalogu cache (platformowo).

UI-log (widget GUI / stdout w CLI) pozostaje nienaruszony (on_log w runnerze);
to warstwa plikowa dla diagnostyki i zgłoszeń błędów. Bez wywołania
setup_logging() logger ma NullHandler (bezpieczny w bibliotece/testach).
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import date
from pathlib import Path

LOGGER_NAME = "ffmpeg_convert"


def logs_dir() -> Path:
    """Katalog na logi wg platformy: XDG cache (Linux), Caches (macOS),
    %LOCALAPPDATA% (Windows). Tworzy drzewo przy setup_logging."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache"))
    return base / "ffmpeg_convert" / "logs"


def get_logger() -> logging.Logger:
    """Logger 'ffmpeg_convert' z NullHandler, gdy nie skonfigurowano pliku."""
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def setup_logging(level: int = logging.INFO, logs_root: Path | None = None) -> Path:
    """Podłącz dzienny FileHandler; zwraca ścieżkę pliku logu.

    Idempotentna: ponowne wywołanie zastępuje poprzednie handlery (bez duplikatów).
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.handlers = []  # zastąp (NullHandler ewentualnie)
    root = logs_root or logs_dir()
    root.mkdir(parents=True, exist_ok=True)
    logfile = root / f"{date.today().isoformat()}.log"
    fh = logging.FileHandler(logfile, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)
    return logfile
