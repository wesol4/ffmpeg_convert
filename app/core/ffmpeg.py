"""Stałe FFmpeg, detekcja typu pliku i enkodery sprzętowe (leaf, tylko stdlib)."""
from __future__ import annotations

import shutil
from enum import StrEnum
from pathlib import Path

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

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
