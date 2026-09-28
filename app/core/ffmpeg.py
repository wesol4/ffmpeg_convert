"""Stałe FFmpeg, detekcja typu pliku i enkodery sprzętowe (leaf, tylko stdlib)."""
from __future__ import annotations

import json
import shutil
from enum import StrEnum
from pathlib import Path

def tool_path(name: str, config: Path | None = None) -> str:
    """Use installer-recorded absolute paths, then PATH (also on source checkouts)."""
    config = config or Path(__file__).resolve().parents[2] / "windows-tools.json"
    try:
        saved = json.loads(config.read_text(encoding="utf-8"))
        value = saved.get(name)
        if isinstance(value, str) and Path(value).is_file():
            return value
    except (OSError, ValueError, AttributeError):
        pass
    return shutil.which(name) or name


FFMPEG = tool_path("ffmpeg")
FFPROBE = tool_path("ffprobe")

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".exr", ".tif", ".tiff", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


class Encoder(StrEnum):
    """Enkoder wideo. CPU = programowy (libx264/libx265); pozostałe = sprzętowe.

    NVENC (NVIDIA), QSV (Intel QuickSync), AMF (AMD). StrEnum → `Encoder.NVENC
    == "nvenc"` (kompatybilne z argparse/bash/dict). Dostępność zależy od GPU
    i buildu ffmpeg — sprawdza probe_encoders().
    """
    CPU = "cpu"
    NVENC = "nvenc"
    QSV = "qsv"
    AMF = "amf"


def kind_of(path: Path) -> str:
    """Zwraca 'image' | 'video' | 'other' na podstawie rozszerzenia."""
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    return "other"
