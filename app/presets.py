#!/usr/bin/env python3
"""Jedyne źródło prawdy dla konwersji FFmpeg.

Tu — i tylko tu — opisane są receptury (argumenty FFmpeg) dla wszystkich
presetów wideo i obrazów. Korzystają z tego zarówno GUI (Linux/Windows),
jak i CLI (menu kontekstowe Nemo / Eksploratora). Dodanie nowego presetu
to zmiana w jednym miejscu, która działa wszędzie.

Funkcje budujące zwracają listę obiektów `Job`; uruchamia je `runner.py`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".exr", ".tif", ".tiff", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def kind_of(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    return "other"


@dataclass
class Job:
    """Pojedyncze zadanie: jedna lub kilka komend FFmpeg do wykonania po kolei.

    label   — opis pokazywany w logu.
    cmds    — lista komend (każda to lista argumentów dla subprocess).
    mkdir   — katalog do utworzenia przed startem (None = nie trzeba).
    cleanup — pliki/katalogi do usunięcia po zakończeniu (np. logi 2-pass,
              tymczasowe symlinki).
    """

    label: str
    cmds: list
    mkdir: Optional[Path] = None
    cleanup: list = field(default_factory=list)


# --------------------------------------------------------------------------
#  Presety wideo o stałej recepturze (jedna komenda, sufix + rozszerzenie).
# --------------------------------------------------------------------------
# Każdy wpis: id -> (etykieta, sufix pliku/podfolderu, rozszerzenie, argumenty
# FFmpeg między "-i SRC" a plikiem wyjściowym).
SIMPLE_VIDEO = {
    "h264": dict(
        label="MP4 H.264 (CRF 18)", suffix="H264", ext="mp4",
        args=["-c:v", "libx264", "-crf", "18", "-preset", "slow",
              "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k"],
    ),
    "h265": dict(
        label="MP4 H.265 / HEVC (CRF 23)", suffix="HEVC", ext="mp4",
        args=["-c:v", "libx265", "-crf", "23", "-preset", "medium",
              "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k"],
    ),
    "dnxhd": dict(
        label="DNxHD 1080p (120 Mb/s)", suffix="DNxHD", ext="mov",
        args=["-vf", "scale=1920:1080", "-c:v", "dnxhd", "-b:v", "120M",
              "-pix_fmt", "yuv422p", "-c:a", "pcm_s16le"],
    ),
    "dnxhr": dict(
        label="DNxHR HQ", suffix="DNxHR", ext="mov",
        args=["-c:v", "dnxhd", "-profile:v", "dnxhr_hq", "-pix_fmt", "yuv422p10le",
              "-c:a", "pcm_s16le"],
    ),
    "prores": dict(
        label="ProRes 422 HQ", suffix="PR", ext="mov",
        args=["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le",
              "-c:a", "pcm_s16le"],
    ),
    "cineform": dict(
        label="Cineform Q4 (10-bit)", suffix="CF", ext="mov",
        args=["-c:v", "cfhd", "-quality", "4", "-pix_fmt", "yuv422p10le",
              "-c:a", "pcm_s16le"],
    ),
}

# Presety specjalne (wieloprzebiegowe / wieloplikowe) obsługiwane osobno.
SPECIAL_VIDEO = {
    "h264size": "MP4 H.264 (kontrola rozmiaru)",
    "last_frame": "Ostatnia klatka PNG",
    "frames": "Eksport klatek (+ WAV)",
}

# Kolejność prezentacji w UI (id -> etykieta).
VIDEO_PRESETS = [
    ("h264", SIMPLE_VIDEO["h264"]["label"]),
    ("h264size", SPECIAL_VIDEO["h264size"]),
    ("h265", SIMPLE_VIDEO["h265"]["label"]),
    ("dnxhd", SIMPLE_VIDEO["dnxhd"]["label"]),
    ("dnxhr", SIMPLE_VIDEO["dnxhr"]["label"]),
    ("prores", SIMPLE_VIDEO["prores"]["label"]),
    ("cineform", SIMPLE_VIDEO["cineform"]["label"]),
    ("last_frame", SPECIAL_VIDEO["last_frame"]),
    ("frames", SPECIAL_VIDEO["frames"]),
]


def probe_duration(src: Path) -> Optional[float]:
    """Długość wideo w sekundach (float) lub None, jeśli nie udało się odczytać."""
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(src)],
            check=True, capture_output=True, text=True,
        )
        return float(out.stdout.strip())
    except Exception:
        return None


def _out_dir(src: Path, suffix: str, batch: bool) -> Path:
    """Przy batchu (>1 plik) zapisujemy do podfolderu, inaczej obok źródła."""
    return (src.parent / suffix) if batch else src.parent


def _h264_size_job(src: Path, base: str, batch: bool,
                   size_mode: str, crf: int, target_mb: float) -> Job:
    """Preset z kontrolą rozmiaru: tryb CRF (1 przebieg) lub MB (2 przebiegi)."""
    out_dir = _out_dir(src, "H264", batch)
    out_path = out_dir / f"{base}_H264.mp4"
    rel = out_path.relative_to(src.parent)

    def crf_fallback(reason: str) -> Job:
        cmd = [FFMPEG, "-y", "-i", str(src), "-c:v", "libx264", "-crf", "23",
               "-preset", "slow", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", str(out_path)]
        return Job(label=f"{src.name} → {rel} ({reason})", cmds=[cmd], mkdir=out_dir)

    if size_mode == "crf":
        cmd = [FFMPEG, "-y", "-i", str(src), "-c:v", "libx264", "-crf", str(crf),
               "-preset", "slow", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", str(out_path)]
        return Job(label=f"{src.name} → {rel} (CRF {crf})", cmds=[cmd], mkdir=out_dir)

    # Tryb docelowego rozmiaru: bitrate wideo liczony z czasu trwania.
    duration = probe_duration(src)
    if not duration or duration <= 0:
        return crf_fallback("nie odczytano długości — CRF 23")

    audio_k = 128
    total_k = (target_mb * 8192) / duration  # MB → kbit/s całości
    video_k = max(50, int(total_k - audio_k))
    passlog = str(out_dir / f"{base}_ffmpeg2pass")
    pass1 = [FFMPEG, "-y", "-i", str(src), "-c:v", "libx264", "-b:v", f"{video_k}k",
             "-preset", "slow", "-pix_fmt", "yuv420p", "-pass", "1",
             "-passlogfile", passlog, "-an", "-f", "null", os.devnull]
    pass2 = [FFMPEG, "-y", "-i", str(src), "-c:v", "libx264", "-b:v", f"{video_k}k",
             "-preset", "slow", "-pix_fmt", "yuv420p", "-pass", "2",
             "-passlogfile", passlog, "-c:a", "aac", "-b:a", f"{audio_k}k", str(out_path)]
    return Job(
        label=f"{src.name} → {rel} (~{target_mb:g} MB, {video_k}k wideo)",
        cmds=[pass1, pass2], mkdir=out_dir,
        cleanup=[Path(passlog + "-0.log"), Path(passlog + "-0.log.mbtree")],
    )


def _frames_job(src: Path, base: str, frames_format: str, with_wav: bool) -> Job:
    """Eksport klatek do podfolderu + opcjonalnie ścieżka audio WAV."""
    fmt = frames_format.lower()
    frames_dir = src.parent / f"{base}_FRAMES"
    pattern = frames_dir / f"{base}_%04d.{fmt}"
    # -fps_mode passthrough: zachowaj dokładnie tyle klatek, ile w źródle.
    cmds = [[FFMPEG, "-y", "-i", str(src), "-fps_mode", "passthrough", str(pattern)]]
    label = f"{src.name} → {frames_dir.name}/ (klatki {fmt.upper()}"
    if with_wav:
        wav_path = frames_dir / f"{base}.wav"
        cmds.append([FFMPEG, "-y", "-i", str(src), "-vn", "-c:a", "pcm_s24le", str(wav_path)])
        label += " + WAV"
    label += ")"
    return Job(label=label, cmds=cmds, mkdir=frames_dir)


def build_video_jobs(preset: str, files, *, size_mode: str = "crf", crf: int = 23,
                     target_mb: float = 25, frames_format: str = "png",
                     frames_with_wav: bool = True) -> list:
    """Zbuduj listę Jobów dla wybranego presetu wideo."""
    files = [Path(f) for f in files]
    batch = len(files) > 1
    jobs = []
    for src in files:
        base = src.stem
        if preset in SIMPLE_VIDEO:
            spec = SIMPLE_VIDEO[preset]
            out_dir = _out_dir(src, spec["suffix"], batch)
            out_path = out_dir / f"{base}_{spec['suffix']}.{spec['ext']}"
            cmd = [FFMPEG, "-y", "-i", str(src), *spec["args"], str(out_path)]
            jobs.append(Job(
                label=f"{src.name} → {out_path.relative_to(src.parent)}",
                cmds=[cmd], mkdir=out_dir,
            ))
        elif preset == "h264size":
            jobs.append(_h264_size_job(src, base, batch, size_mode, crf, target_mb))
        elif preset == "last_frame":
            out_path = src.parent / f"{base}_last.png"
            cmd = [FFMPEG, "-y", "-sseof", "-1", "-i", str(src), "-update", "1", str(out_path)]
            jobs.append(Job(label=f"{src.name} → {out_path.name}", cmds=[cmd], mkdir=src.parent))
        elif preset == "frames":
            jobs.append(_frames_job(src, base, frames_format, frames_with_wav))
        else:
            raise ValueError(f"Nieznany preset wideo: {preset}")
    return jobs


# --------------------------------------------------------------------------
#  Obrazy: kompresja do JPG (q) lub zachowanie oryginału, z opcjonalną
#  zmianą nazwy (numeracja) i wyborem miejsca zapisu.
# --------------------------------------------------------------------------
# Mapowanie etykiet jakości na wartość -q:v FFmpeg (niższa = lepsza).
IMAGE_QUALITY = {2: "Q2 (~94%, najlepsza)", 5: "Q5 (~85%, dobra)",
                 10: "Q10 (~70%, mała waga)", 1: "Bez kompresji (maks. JPG)"}


def image_target_name(path: Path, idx: int, newname: str, keep: bool):
    base = f"{newname}_{idx:03d}" if newname else path.stem
    ext = path.suffix.lstrip(".") if keep else "jpg"
    return base, ext


def build_image_jobs(files, *, quality: Optional[int] = 2, keep: bool = False,
                     newname: str = "", subdir: bool = True) -> list:
    """Joby dla obrazów. quality=None lub keep=True → kopiuj oryginał.

    Inaczej niż dawniej, kompresji do JPG poddajemy DOWOLNY obraz rastrowy
    (nie tylko PNG) — FFmpeg potrafi przekodować każdy z IMAGE_EXTS.
    """
    files = [Path(f) for f in files]
    jobs = []
    idx = 0
    for path in files:
        if kind_of(path) != "image":
            continue
        idx += 1
        base, ext = image_target_name(path, idx, newname, keep)
        out_dir = (path.parent / "compressed") if subdir else path.parent
        out_path = out_dir / f"{base}.{ext}"
        if out_path.resolve() == path.resolve():
            continue  # nie nadpisuj oryginału
        if keep:
            jobs.append(Job(label=f"{path.name} → {out_path.name}",
                            cmds=[["__copy__", str(path), str(out_path)]], mkdir=out_dir))
        else:
            cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", str(path),
                   "-q:v", str(quality), "-vf", "format=yuvj420p", str(out_path)]
            jobs.append(Job(label=f"{path.name} → {out_path.name}", cmds=[cmd], mkdir=out_dir))
    return jobs


# --------------------------------------------------------------------------
#  Sekwencja obrazów → wideo (naprawione: demuxer image2, poprawny FPS,
#  zachowane WSZYSTKIE klatki). Audio o nazwie folderu dołączane automatycznie.
# --------------------------------------------------------------------------
SEQ_FORMATS = {
    "h264": dict(label="MP4 H.264", ext="mp4",
                 vargs=["-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p"],
                 aargs=["-c:a", "aac", "-b:a", "192k"]),
    "h265": dict(label="MP4 H.265", ext="mp4",
                 vargs=["-c:v", "libx265", "-crf", "23", "-preset", "medium", "-pix_fmt", "yuv420p"],
                 aargs=["-c:a", "aac", "-b:a", "192k"]),
    "prores": dict(label="ProRes 422 HQ", ext="mov",
                   vargs=["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le"],
                   aargs=["-c:a", "pcm_s16le"]),
    "dnxhd": dict(label="DNxHD 1080p", ext="mov",
                  vargs=["-vf", "scale=1920:1080", "-c:v", "dnxhd", "-b:v", "120M", "-pix_fmt", "yuv422p"],
                  aargs=["-c:a", "pcm_s16le"]),
}


def build_seq_job(files, *, fps: int = 24, fmt: str = "h264") -> Job:
    """Złóż posortowane obrazy w wideo przez demuxer image2 (niezawodny FPS i
    pełna liczba klatek). Tworzy katalog tymczasowy z symlinkami seq_%05d.ext.
    """
    if fmt not in SEQ_FORMATS:
        raise ValueError(f"Nieznany format sekwencji: {fmt}")
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
    return Job(label=label, cmds=[cmd], mkdir=out_dir, cleanup=[tmp])


def _natural_key(s: str):
    import re
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]
