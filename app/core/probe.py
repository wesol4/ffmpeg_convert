"""Odczyt metadanych przez ffprobe (długość, wymiary, obecność audio)."""
from __future__ import annotations

import json
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.core.ffmpeg import FFMPEG, FFPROBE, Encoder
from app.core.process import subprocess_options


def probe_duration(src: Path) -> Optional[float]:
    """Długość wideo w sekundach (float) lub None, jeśli nie udało się odczytać."""
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(src)],
            check=True, capture_output=True, text=True, encoding="utf-8", errors="replace", **subprocess_options(),
        )
        return float(out.stdout.strip())
    except Exception:
        return None


def probe_size(src: Path) -> Optional[tuple]:
    """Wymiary (width, height) pierwszego strumienia wideo lub None."""
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x",
             str(src)],
            check=True, capture_output=True, text=True, encoding="utf-8", errors="replace", **subprocess_options(),
        )
        w, h = out.stdout.strip().split("x")
        return int(w), int(h)
    except Exception:
        return None


def probe_untagged_hd_yuv(src: Path) -> bool:
    """Czy wideo to YUV HD+ (wys. >= 720) bez zapisanej macierzy (color_space).

    Takie pliki (np. z generatorów AI) są kodowane macierzą 709, ale swscale przy
    dekodowaniu do RGB bez tagu przyjmuje 601 — klatki PNG wychodzą z przesuniętym
    kolorem. Wołający wymusza wtedy in_color_matrix=bt709 (jak odtwarzacze HD).
    """
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=pix_fmt,height,color_space", "-of", "json", str(src)],
            check=True, capture_output=True, text=True, encoding="utf-8", errors="replace", **subprocess_options(),
        )
        stream = json.loads(out.stdout)["streams"][0]
    except Exception:
        return False
    return (str(stream.get("pix_fmt", "")).startswith("yuv")
            and int(stream.get("height") or 0) >= 720
            and stream.get("color_space", "unknown") in ("", "unknown"))


def probe_has_audio(src: Path) -> bool:
    """Czy w pliku jest strumień audio (do estymacji bitrate 2-pass)."""
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0",
             str(src)],
            check=True, capture_output=True, text=True, encoding="utf-8", errors="replace", **subprocess_options(),
        )
        return bool(out.stdout.strip())
    except Exception:
        return False


@lru_cache(maxsize=1)
def available_filters() -> frozenset:
    """Zbiór nazw dostępnych filtrów wideo (`ffmpeg -filters`), cached.

    Pusty zbiór przy braku ffmpeg — wołający traktują to jako „filtr niedostępny".
    Używane do guardowania zscale (zimg) — bez niego EXR→display pipeline jest
    pomijany (graceful), by nie crashować na buildach bez libzimg.
    """
    try:
        out = subprocess.run([FFMPEG, "-hide_banner", "-filters"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace",
                             check=False, **subprocess_options())
    except Exception:
        return frozenset()
    names = set()
    for line in out.stdout.splitlines():
        # Linia filtra: " ...T. name        V->V       opis". Nazwa to 2. token.
        # Pomijamy nagłówek ("Filters:" itd.) bez typowych znaczników flag.
        parts = line.split()
        if len(parts) >= 2 and parts[1].isidentifier():
            names.add(parts[1])
    return frozenset(names)


def has_filter(name: str) -> bool:
    """Czy dany filtr wideo jest dostępny w buildie ffmpeg (np. 'zscale')."""
    return name in available_filters()


def probe_encoders() -> set:
    """Zbiór dostępnych enkoderów (Encoder) na podstawie `ffmpeg -encoders`.

    Zwraca co najmniej {Encoder.CPU}. Sprzętowe (NVENC/QSV/AMF) dodaje, gdy
    ffmpeg zna zarówno h264_*, jak i hevc_* wariant danego dostawcy. Uwaga:
    to oznacza, że ffmpeg jest SKOMPILOWANY z obsługą enkodera — nie gwarantuje
    obecności GPU; brak sprzętu wykryje się dopiero błędem konwersji.
    """
    avail = {Encoder.CPU}
    try:
        out = subprocess.run([FFMPEG, "-hide_banner", "-encoders"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace",
                             check=False, **subprocess_options())
        text = out.stdout
        for enc in Encoder:
            if enc == Encoder.CPU:
                continue
            if f"h264_{enc.value}" in text and f"hevc_{enc.value}" in text:
                avail.add(enc)
    except Exception:
        pass
    return avail
