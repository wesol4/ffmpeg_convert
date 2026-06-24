"""Warstwa konfiguracji — tunable receptur FFmpeg w jednym miejscu.

Typowane, zamrożone dataclassy (mypy-checkable, bez zależności zewnętrznych,
bez I/O). Presety, CLI i GUI czytają z `CONFIG`. ZmianaCRF/audio/presetu/
zakresu skali/fps w jednym pliku. Wartości są historycznie dobrane (zgodne
z dotychczasowym hardcoded). Schemat dataclass jest gotowy do ewentualnego
przełożenia na TOML (tomllib) bez zmiany typów.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class H264Config:
    crf: int = 18
    preset: str = "slow"
    pix_fmt: str = "yuv420p"


@dataclass(frozen=True)
class H265Config:
    crf: int = 23
    preset: str = "medium"
    pix_fmt: str = "yuv420p"


@dataclass(frozen=True)
class AudioConfig:
    codec: str = "aac"
    bitrate: str = "192k"            # tryb jakości (1 przebieg)
    twopass_audio_k: int = 128       # tryb docelowego rozmiaru (2 przebiegi), kbit/s


@dataclass(frozen=True)
class EncoderConfig:
    # Stała jakość GPU (skala jak CRF). pix_fmt dla NVENC/AMF (QSV zarządza sam).
    pix_fmt: str = "yuv420p"
    nvenc_preset: str = "p4"
    nvenc_tune: str = "hq"
    qsv_preset: str = "veryslow"
    amf_quality: str = "quality"


@dataclass(frozen=True)
class H264SizeConfig:
    crf_default: int = 23
    crf_min: int = 18
    crf_max: int = 32
    target_mb_default: int = 25


@dataclass(frozen=True)
class ImageConfig:
    jpg_ext: str = "jpg"
    compressed_subdir: str = "compressed"
    split_subdir: str = "SplitGrid"
    scale_snaps: list = field(default_factory=lambda: [10, 25, 50, 75, 90, 100])
    scale_default: int = 50


@dataclass(frozen=True)
class SeqConfig:
    default_fps: int = 24


@dataclass(frozen=True)
class Config:
    h264: H264Config = field(default_factory=H264Config)
    h265: H265Config = field(default_factory=H265Config)
    audio: AudioConfig = field(default_factory=AudioConfig)
    encoder: EncoderConfig = field(default_factory=EncoderConfig)
    h264size: H264SizeConfig = field(default_factory=H264SizeConfig)
    image: ImageConfig = field(default_factory=ImageConfig)
    seq: SeqConfig = field(default_factory=SeqConfig)


CONFIG = Config()
