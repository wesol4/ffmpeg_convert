"""Pakiet presetów — re-eksportuje publiczne API dla zgodności wstecz.

`from app import presets` + `presets.build_video_jobs(...)` itd. działają jak
dotąd (cli.py, gui.py, testy). Wewnętrznie logika żyje w podmodułach
video/image/sequence, a model Job i stałe ffmpeg/probe w app.core.
"""
from __future__ import annotations

from app.core.ffmpeg import FFMPEG, FFPROBE, IMAGE_EXTS, VIDEO_EXTS, kind_of
from app.core.jobs import Job
from app.core.probe import probe_duration, probe_has_audio, probe_size
from app.presets.image import (
    IMAGE_QUALITY,
    _scale_filter,
    build_image_jobs,
    build_split_jobs,
    image_target_name,
)
from app.presets.sequence import (
    SEQ_FORMATS,
    SeqFormat,
    _natural_key,
    _seq_stem,
    build_flipbook_job,
    build_seq_job,
)
from app.presets.video import (
    SIMPLE_VIDEO,
    SPECIAL_VIDEO,
    VIDEO_PRESETS,
    VideoPreset,
    build_video_jobs,
)

__all__ = [
    "FFMPEG", "FFPROBE", "IMAGE_EXTS", "VIDEO_EXTS", "kind_of", "Job",
    "probe_duration", "probe_has_audio", "probe_size",
    "IMAGE_QUALITY", "_scale_filter", "build_image_jobs", "build_split_jobs",
    "image_target_name",
    "SEQ_FORMATS", "SeqFormat", "_natural_key", "_seq_stem",
    "build_flipbook_job", "build_seq_job",
    "SIMPLE_VIDEO", "SPECIAL_VIDEO", "VIDEO_PRESETS", "VideoPreset",
    "build_video_jobs",
]