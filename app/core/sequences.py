"""Read-only detection of numbered frames and matching soundtracks."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from app.core.ffmpeg import kind_of
from app.core.probe import probe_has_audio

AUDIO_EXTS = {".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg", ".aif", ".aiff"}
MEDIA_AUDIO_EXTS = AUDIO_EXTS | {".mp4", ".mov", ".mkv", ".webm"}


def frame_identity(path: Path) -> tuple[str, str, int, int] | None:
    match = re.fullmatch(r"(.*?)([0-9]+)", path.stem)
    if not match or kind_of(path) != "image":
        return None
    prefix, number = match.groups()
    padding = len(number) if number.startswith("0") else 0
    return prefix, path.suffix.lower(), padding, int(number)


@dataclass(frozen=True)
class FrameSequence:
    frames: tuple[Path, ...]
    name: str
    first: int
    last: int
    missing: tuple[str, ...]

    def require_complete(self) -> None:
        if self.missing:
            raise ValueError("Brak klatek: " + ", ".join(self.missing[:8])
                             + ". Uzupełnij sekwencję przed utworzeniem filmu.")


def detect_sequence(frame: Path) -> FrameSequence | None:
    frame = frame.absolute()
    identity = frame_identity(frame)
    if identity is None or not frame.is_file():
        return None
    prefix, extension, padding, _ = identity
    matches = []
    for path in frame.parent.iterdir():
        item = frame_identity(path)
        if not item or not path.is_file() or item[:2] != (prefix, extension):
            continue
        # Same padding family, including sequences crossing 0999 -> 1000.
        digits = len(path.stem) - len(prefix)
        if padding and digits != padding:
            continue
        if not padding and item[2] and len(frame.stem) - len(prefix) != digits:
            continue
        matches.append((item[3], path))
    if len(matches) < 2:
        return None
    matches.sort(key=lambda item: (item[0], item[1].name))
    numbers = [item[0] for item in matches]
    if len(set(numbers)) != len(numbers):
        raise ValueError("Powtarzające się numery klatek — ujednolić nazwy lub rozszerzenia.")
    missing = tuple(str(a + 1) if b == a + 2 else f"{a + 1}–{b - 1}"
                    for a, b in zip(numbers, numbers[1:]) if b > a + 1)
    return FrameSequence(tuple(p for _, p in matches), prefix.rstrip("._- ") or frame.parent.name,
                         numbers[0], numbers[-1], missing)


def matching_audio(frames: list[Path] | tuple[Path, ...], exclude: Path | None = None) -> list[Path]:
    """Prefer sequence-name, then folder-name tracks. Never guess unrelated audio."""
    if not frames:
        return []
    folder = frames[0].parent
    identity = frame_identity(frames[0])
    name = identity[0].rstrip("._- ") if identity else ""
    names = list(dict.fromkeys(n for n in (name, folder.name) if n))
    candidates = sorted((p for p in folder.iterdir()
                         if p.is_file() and p.suffix.lower() in MEDIA_AUDIO_EXTS and p.stem in names
                         and (exclude is None or p.resolve() != exclude.resolve())),
                        key=lambda p: (names.index(p.stem), p.suffix.lower() not in AUDIO_EXTS, p.name))
    return [p for p in candidates if probe_has_audio(p)]
