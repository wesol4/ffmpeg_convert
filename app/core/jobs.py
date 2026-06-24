"""Model zadania konwersji — wspólny dla presets i runnera (leaf, tylko stdlib)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Job:
    """Pojedyncze zadanie: jedna lub kilka komend FFmpeg do wykonania po kolei.

    label   — opis pokazywany w logu.
    cmds    — lista komend (każda to lista argumentów dla subprocess).
    mkdir   — katalog do utworzenia przed startem (None = nie trzeba).
    cleanup — pliki/katalogi do usunięcia po zakończeniu (np. logi 2-pass,
              tymczasowe symlinki).
    duration — długość źródła w sekundach; dla realnego postępu w runnerze.
    """

    label: str
    cmds: list
    mkdir: Optional[Path] = None
    cleanup: list = field(default_factory=list)
    duration: Optional[float] = None
