"""Sekwencja obrazów → wideo oraz spritesheet (flipbook).

Demuxer image2 (niezawodny FPS, pełna liczba klatek) i concat + filtr tile.
Stringowe id formatów typowane przez SeqFormat (str, Enum).
"""
from __future__ import annotations

import re
import shutil
import tempfile
from enum import StrEnum
from pathlib import Path
from typing import TypedDict

from app.core import probe
from app.core.ffmpeg import FFMPEG
from app.core.jobs import Job


class _SeqSpec(TypedDict):
    label: str
    ext: str
    vargs: list
    aargs: list


class SeqFormat(StrEnum):
    H264 = "h264"
    H265 = "h265"
    PRORES = "prores"
    DNXHD = "dnxhd"


SEQ_FORMATS: dict[SeqFormat, _SeqSpec] = {
    SeqFormat.H264: dict(label="MP4 H.264", ext="mp4",
                         vargs=["-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p"],
                         aargs=["-c:a", "aac", "-b:a", "192k"]),
    SeqFormat.H265: dict(label="MP4 H.265", ext="mp4",
                         vargs=["-c:v", "libx265", "-crf", "23", "-preset", "medium", "-pix_fmt", "yuv420p"],
                         aargs=["-c:a", "aac", "-b:a", "192k"]),
    SeqFormat.PRORES: dict(label="ProRes 422 HQ", ext="mov",
                           vargs=["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le"],
                           aargs=["-c:a", "pcm_s16le"]),
    SeqFormat.DNXHD: dict(label="DNxHD 1080p", ext="mov",
                          vargs=["-vf", "scale=1920:1080", "-c:v", "dnxhd", "-b:v", "120M", "-pix_fmt", "yuv422p"],
                          aargs=["-c:a", "pcm_s16le"]),
}


def _natural_key(s: str) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def _seq_stem(name: str) -> str:
    """Bazowa nazwa sekwencji: z nazwy pliku usuwa ogon numeryczny sekwencji.

    Np. 'frame_001' → 'frame', 'render.0001' → 'render', 'clip' → 'clip'.
    """
    s = Path(name).stem
    s = re.sub(r"\.\d{3,}$", "", s)
    s = re.sub(r"_\d{3,}$", "", s)
    return s


def build_seq_job(files: list, *, fps: int = 24, fmt: "SeqFormat | str" = "h264") -> Job:
    """Złóż posortowane obrazy w wideo przez demuxer image2 (niezawodny FPS i
    pełna liczba klatek). Tworzy katalog tymczasowy z symlinkami seq_%05d.ext.
    """
    fmt = SeqFormat(fmt)  # coerce str → enum (ValueError przy literówce)
    spec = SEQ_FORMATS[fmt]
    # Sortowanie naturalne (frame_2 < frame_10), nie leksykalne. resolve() —
    # by nazwa folderu wyjściowego była poprawna także dla ścieżek względnych.
    paths = sorted((Path(f).resolve() for f in files), key=lambda p: _natural_key(p.name))
    if not paths:
        raise ValueError("Brak plików sekwencji.")

    out_dir = paths[0].parent
    name = out_dir.name or "output"
    out_path = out_dir / f"{name}.{spec['ext']}"
    seq_ext = paths[0].suffix.lstrip(".")

    # Katalog tymczasowy z ponumerowanymi symlinkami → image2 demuxer.
    tmp = Path(tempfile.mkdtemp(prefix="ffseq_"))
    for i, p in enumerate(paths, start=1):
        link = tmp / f"seq_{i:05d}.{seq_ext}"
        try:
            link.symlink_to(p.resolve())
        except OSError:
            shutil.copy2(p, link)  # systemy bez symlinków (np. Windows bez uprawnień)

    # Audio o nazwie folderu (wav/mp4) dołączane automatycznie.
    audio = None
    for ext in ("wav", "mp4"):
        cand = out_dir / f"{name}.{ext}"
        if cand.is_file():
            audio = cand
            break

    cmd = [FFMPEG, "-y", "-framerate", str(fps), "-i", str(tmp / f"seq_%05d.{seq_ext}")]
    if audio:
        cmd += ["-i", str(audio), *spec["aargs"], "-shortest"]
    cmd += [*spec["vargs"], str(out_path)]
    label = f"{len(paths)} klatek @ {fps} fps → {out_path.name}"
    if audio:
        label += f" (+ audio {audio.name})"
    return Job(label=label, cmds=[cmd], mkdir=out_dir, cleanup=[tmp],
               duration=len(paths) / fps if fps else None)


def build_flipbook_job(files: list, *, cols: int, rows: int,
                       tile: "tuple | None" = None) -> Job:
    """Złóż posortowane obrazy w spritesheet przez concat + filtr tile.

    tile=(w,h) — opcjonalne skalowanie kafelka przed ułożeniem w siatkę.
    Wyjście: {stem}_flipbook_{cols}x{rows}.png obok pierwszego pliku.
    """
    if cols < 1 or rows < 1:
        raise ValueError("cols i rows muszą być ≥ 1")
    paths = sorted((Path(f).resolve() for f in files),
                   key=lambda p: _natural_key(p.name))
    if not paths:
        raise ValueError("Brak plików sekwencji.")

    out_dir = paths[0].parent
    stem = _seq_stem(paths[0].name) or "flipbook"
    out_path = out_dir / f"{stem}_flipbook_{cols}x{rows}.png"

    src_size = probe.probe_size(paths[0])
    if tile and src_size and tile != src_size:
        vf = f"scale={tile[0]}:{tile[1]},tile={cols}x{rows}"
    else:
        vf = f"tile={cols}x{rows}"

    # concat demuxer: lista plików w tymczasowym pliku tekstowym.
    tmp_list = tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt",
                                           prefix="ffflip_", encoding="utf-8")
    for p in paths:
        tmp_list.write(f"file '{p}'\n")
    tmp_list.close()

    cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", tmp_list.name,
           "-vf", vf, "-frames:v", "1", "-update", "1", str(out_path)]
    return Job(
        label=f"{len(paths)} klatek → {out_path.name} ({cols}×{rows})",
        cmds=[cmd], mkdir=out_dir, cleanup=[Path(tmp_list.name)],
    )