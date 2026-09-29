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
    outputs — pliki wynikowe tworzone przez job; usuwane, gdy job się nie powiedzie
              albo zostanie przerwany (niedokończony plik nie udaje gotowego).
    """

    label: str
    cmds: list
    mkdir: Optional[Path] = None
    cleanup: list = field(default_factory=list)
    duration: Optional[float] = None
    outputs: list = field(default_factory=list)


def free_path(path: Path, taken: "set | None" = None) -> Path:
    """Pierwsza wolna nazwa: path, potem name_002, name_003… (plik lub katalog).

    Wyniki nie nadpisują poprzednich konwersji — kolejna wersja dostaje numer.
    taken — nazwy zarezerwowane już w tej samej partii (np. a.mov i a.mp4 → a_H264);
    wybrana nazwa jest do niego dopisywana.
    """
    taken = taken if taken is not None else set()
    for index in range(1, 10000):
        candidate = path if index == 1 else path.with_name(f"{path.stem}_{index:03d}{path.suffix}")
        if not candidate.exists() and candidate not in taken:
            taken.add(candidate)
            return candidate
    raise RuntimeError(f"Brak wolnej nazwy dla {path}")
