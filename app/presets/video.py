"""Presety wideo — jedyne źródło receptur FFmpeg dla konwersji wideo.

Buildery zwracają listę Job; uruchamia je app.runner. Stringowe id presetów
są typowane przez VideoPreset (str, Enum) — literówka rzuca ValueError zamiast
cichego pominięcia.
"""
from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path
from typing import TypedDict

from app.core import probe
from app.core.ffmpeg import FFMPEG
from app.core.jobs import Job


class _SimpleSpec(TypedDict):
    label: str
    suffix: str
    ext: str
    args: list


class VideoPreset(StrEnum):
    """Id presetów wideo; StrEnum → `VideoPreset.H264 == "h264"` (kompatybilne
    z argparse choices, bash, dict keys). Literówka → ValueError przy coerce."""
    H264 = "h264"
    H264SIZE = "h264size"
    H265 = "h265"
    DNXHD = "dnxhd"
    DNXHR = "dnxhr"
    PRORES = "prores"
    CINEFORM = "cineform"
    LAST_FRAME = "last_frame"
    FRAMES = "frames"


# Presety o stałej recepturze (jedna komenda, sufix + rozszerzenie).
# Każdy wpis: id -> (etykieta, sufix pliku/podfolderu, rozszerzenie, argumenty
# FFmpeg między "-i SRC" a plikiem wyjściowym).
SIMPLE_VIDEO: dict[VideoPreset, _SimpleSpec] = {
    VideoPreset.H264: dict(
        label="MP4 H.264 (CRF 18)", suffix="H264", ext="mp4",
        args=["-c:v", "libx264", "-crf", "18", "-preset", "slow",
              "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k"],
    ),
    VideoPreset.H265: dict(
        label="MP4 H.265 / HEVC (CRF 23)", suffix="HEVC", ext="mp4",
        args=["-c:v", "libx265", "-crf", "23", "-preset", "medium",
              "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k"],
    ),
    VideoPreset.DNXHD: dict(
        label="DNxHD 1080p (120 Mb/s)", suffix="DNxHD", ext="mov",
        args=["-vf", "scale=1920:1080", "-c:v", "dnxhd", "-b:v", "120M",
              "-pix_fmt", "yuv422p", "-c:a", "pcm_s16le"],
    ),
    VideoPreset.DNXHR: dict(
        label="DNxHR HQ", suffix="DNxHR", ext="mov",
        args=["-c:v", "dnxhd", "-profile:v", "dnxhr_hq", "-pix_fmt", "yuv422p10le",
              "-c:a", "pcm_s16le"],
    ),
    VideoPreset.PRORES: dict(
        label="ProRes 422 HQ", suffix="PR", ext="mov",
        args=["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le",
              "-c:a", "pcm_s16le"],
    ),
    VideoPreset.CINEFORM: dict(
        label="Cineform Q4 (10-bit)", suffix="CF", ext="mov",
        args=["-c:v", "cfhd", "-quality", "4", "-pix_fmt", "yuv422p10le",
              "-c:a", "pcm_s16le"],
    ),
}

# Presety specjalne (wieloprzebiegowe / wieloplikowe) obsługiwane osobno.
SPECIAL_VIDEO = {
    VideoPreset.H264SIZE: "MP4 H.264 (kontrola rozmiaru)",
    VideoPreset.LAST_FRAME: "Ostatnia klatka PNG",
    VideoPreset.FRAMES: "Eksport klatek (+ WAV)",
}

# Kolejność prezentacji w UI (id -> etykieta).
VIDEO_PRESETS = [
    (VideoPreset.H264, SIMPLE_VIDEO[VideoPreset.H264]["label"]),
    (VideoPreset.H264SIZE, SPECIAL_VIDEO[VideoPreset.H264SIZE]),
    (VideoPreset.H265, SIMPLE_VIDEO[VideoPreset.H265]["label"]),
    (VideoPreset.DNXHD, SIMPLE_VIDEO[VideoPreset.DNXHD]["label"]),
    (VideoPreset.DNXHR, SIMPLE_VIDEO[VideoPreset.DNXHR]["label"]),
    (VideoPreset.PRORES, SIMPLE_VIDEO[VideoPreset.PRORES]["label"]),
    (VideoPreset.CINEFORM, SIMPLE_VIDEO[VideoPreset.CINEFORM]["label"]),
    (VideoPreset.LAST_FRAME, SPECIAL_VIDEO[VideoPreset.LAST_FRAME]),
    (VideoPreset.FRAMES, SPECIAL_VIDEO[VideoPreset.FRAMES]),
]


def _out_dir(src: Path, suffix: str, batch: bool) -> Path:
    """Przy batchu (>1 plik) zapisujemy do podfolderu, inaczej obok źródła."""
    return (src.parent / suffix) if batch else src.parent


def _h264_size_job(src: Path, base: str, batch: bool,
                   size_mode: str, crf: int, target_mb: float) -> Job:
    """Preset z kontrolą rozmiaru: tryb CRF (1 przebieg) lub MB (2 przebiegi)."""
    out_dir = _out_dir(src, "H264", batch)
    out_path = out_dir / f"{base}_H264.mp4"
    rel = out_path.relative_to(src.parent)
    dur = probe.probe_duration(src)

    def crf_fallback(reason: str) -> Job:
        cmd = [FFMPEG, "-y", "-i", str(src), "-c:v", "libx264", "-crf", "23",
               "-preset", "slow", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", str(out_path)]
        return Job(label=f"{src.name} → {rel} ({reason})", cmds=[cmd],
                   mkdir=out_dir, duration=dur)

    if size_mode == "crf":
        cmd = [FFMPEG, "-y", "-i", str(src), "-c:v", "libx264", "-crf", str(crf),
               "-preset", "slow", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", str(out_path)]
        return Job(label=f"{src.name} → {rel} (CRF {crf})", cmds=[cmd],
                   mkdir=out_dir, duration=dur)

    # Tryb docelowego rozmiaru: bitrate wideo liczony z czasu trwania.
    if not dur or dur <= 0:
        return crf_fallback("nie odczytano długości — CRF 23")

    has_audio = probe.probe_has_audio(src)
    audio_k = 128 if has_audio else 0
    total_k = (target_mb * 8192) / dur  # MB → kbit/s całości
    video_k = max(50, int(total_k - audio_k))
    passlog = str(out_dir / f"{base}_ffmpeg2pass")
    pass1 = [FFMPEG, "-y", "-i", str(src), "-c:v", "libx264", "-b:v", f"{video_k}k",
             "-preset", "slow", "-pix_fmt", "yuv420p", "-pass", "1",
             "-passlogfile", passlog, "-an", "-f", "null", os.devnull]
    pass2 = [FFMPEG, "-y", "-i", str(src), "-c:v", "libx264", "-b:v", f"{video_k}k",
             "-preset", "slow", "-pix_fmt", "yuv420p", "-pass", "2",
             "-passlogfile", passlog]
    if has_audio:
        pass2 += ["-c:a", "aac", "-b:a", f"{audio_k}k"]
    pass2.append(str(out_path))
    return Job(
        label=f"{src.name} → {rel} (~{target_mb:g} MB, {video_k}k wideo)",
        cmds=[pass1, pass2], mkdir=out_dir, duration=dur,
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
    return Job(label=label, cmds=cmds, mkdir=frames_dir, duration=probe.probe_duration(src))


def build_video_jobs(preset: "VideoPreset | str", files: list, *, size_mode: str = "crf",
                     crf: int = 23, target_mb: float = 25, frames_format: str = "png",
                     frames_with_wav: bool = True) -> list:
    """Zbuduj listę Jobów dla wybranego presetu wideo."""
    preset = VideoPreset(preset)  # coerce str → enum (ValueError przy literówce)
    files = [Path(f) for f in files]
    batch = len(files) > 1
    jobs: list = []
    for src in files:
        base = src.stem
        if preset in SIMPLE_VIDEO:
            spec = SIMPLE_VIDEO[preset]
            out_dir = _out_dir(src, spec["suffix"], batch)
            out_path = out_dir / f"{base}_{spec['suffix']}.{spec['ext']}"
            cmd = [FFMPEG, "-y", "-i", str(src), *spec["args"], str(out_path)]
            jobs.append(Job(
                label=f"{src.name} → {out_path.relative_to(src.parent)}",
                cmds=[cmd], mkdir=out_dir, duration=probe.probe_duration(src),
            ))
        elif preset == VideoPreset.H264SIZE:
            jobs.append(_h264_size_job(src, base, batch, size_mode, crf, target_mb))
        elif preset == VideoPreset.LAST_FRAME:
            out_path = src.parent / f"{base}_last.png"
            cmd = [FFMPEG, "-y", "-sseof", "-1", "-i", str(src), "-update", "1", str(out_path)]
            jobs.append(Job(label=f"{src.name} → {out_path.name}", cmds=[cmd],
                            mkdir=src.parent, duration=probe.probe_duration(src)))
        elif preset == VideoPreset.FRAMES:
            jobs.append(_frames_job(src, base, frames_format, frames_with_wav))
        else:  # nie powinno się zdarzyć (enum wyczerpuje przypadki)
            raise ValueError(f"Nieobsługiwany preset wideo: {preset}")
    return jobs
