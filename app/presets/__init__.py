"""Pakiet presetów — re-eksportuje publiczne API dla zgodności wstecz.

`from app import presets` + `presets.build_video_jobs(...)` itd. działają jak
dotąd (cli.py, gui.py, testy). Wewnętrznie logika żyje w podmodułach
video/image/sequence, a model Job i stałe ffmpeg/probe w app.core.
"""
from __future__ import annotations

from app.config import CONFIG, ProxyVariant
from app.core.color import exr_color_vf, set_aces_lut
from app.core.ffmpeg import FFMPEG, FFPROBE, IMAGE_EXTS, VIDEO_EXTS, Encoder, kind_of
from app.core.jobs import Job
from app.core.probe import probe_duration, probe_encoders, probe_has_audio, probe_size
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
    _resolve_proxy_variant,
    _seq_stem,
    build_flipbook_job,
    build_proxy_cmd,
    build_seq_job,
    build_seq_jobs_from_folders,
    build_thumbnail_cmd,
)
from app.presets.video import (
    SIMPLE_VIDEO,
    SPECIAL_VIDEO,
    VIDEO_PRESETS,
    VideoPreset,
    build_video_jobs,
)

__all__ = [
    "FFMPEG", "FFPROBE", "IMAGE_EXTS", "VIDEO_EXTS", "Encoder", "CONFIG", "ProxyVariant",
    "kind_of", "Job",
    "probe_duration", "probe_encoders", "probe_has_audio", "probe_size",
    "exr_color_vf", "set_aces_lut",
    "IMAGE_QUALITY", "_scale_filter", "build_image_jobs", "build_split_jobs",
    "image_target_name",
    "SEQ_FORMATS", "SeqFormat", "_natural_key", "_resolve_proxy_variant", "_seq_stem",
    "build_flipbook_job", "build_proxy_cmd", "build_seq_job", "build_seq_jobs_from_folders",
    "build_thumbnail_cmd",
    "SIMPLE_VIDEO", "SPECIAL_VIDEO", "VIDEO_PRESETS", "VideoPreset",
    "build_video_jobs",
]
