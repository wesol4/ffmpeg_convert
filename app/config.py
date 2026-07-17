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
class ProxyVariant:
    """Jeden wariant proxy — sekwencja klatek numerowana od proxy_start_frame.

    Standard VFX: klatki numerowane od 1001 (zapas na ujemne handle, brak problemów
    z minimalnymi wartościami). Każdy wariant to osobny podfolder obok źródła.

    key       — identyfikator (CLI --proxy, GUI checkbox).
    label     — etykieta w UI.
    ext       — rozszerzenie wyjścia (jpg/png).
    subdir    — podfolder w folderze sekwencji (np. 'proxy_jpg').
    scale_pct  — procent skali (100 = pełny rozmiar; 50 = połowa).
    quality   — -q:v dla jpg (None dla png — bezstratny).
    """
    key: str
    label: str
    ext: str
    subdir: str
    scale_pct: int = 100
    quality: "int | None" = 2


@dataclass(frozen=True)
class SeqConfig:
    default_fps: int = 24
    # Miniaturka z gotowego mp4 sekwencji: klatka z połowy filmu, skalowana do
    # stałej szerokości (proporcje zachowane), zapisana w folderze nadrzędnym.
    thumb_width: int = 320
    thumb_ext: str = "jpg"
    # Proxy — sekwencje klatek numerowane od 1001 (standard VFX).
    proxy_start_frame: int = 1001
    proxy_pad: int = 4                 # cyfr w numerze klatki (%04d → 1001..9999)
    # Domyślne warianty proxy (UI/CLI pokazuje je jako wybór; użytkownik zaznacza).
    proxy_variants: tuple = field(default_factory=lambda: (
        ProxyVariant("jpg", "Proxy JPG (8-bit, pełny)", "jpg", "proxy_jpg",
                     scale_pct=100, quality=2),
        ProxyVariant("png16", "Proxy PNG 16-bit (pełny)", "png", "proxy_png16",
                     scale_pct=100, quality=None),
        ProxyVariant("half", "Proxy JPEG ½ rozmiaru (50%)", "jpg", "proxy_half",
                     scale_pct=50, quality=5),
    ))


@dataclass(frozen=True)
class ColorConfig:
    # EXR jest scene-referred linear. Bez OETF wyjście jest za ciemne w dekoderach
    # bez pełnego color management (Discord, miniatury OS): liniowe wartości traktowane
    # są jak gotowe do wyświetlenia, więc średnie tony zapadają się. Pipeline nakłada
    # OETF sRGB (iec61966-2-1, linear→display) i taguje plik sRGB, by Nuke (który dla
    # JPG/PNG 8-bit zakłada sRGB) oraz thumbnailery/tag-aware playery zgadzały się z
    # playerem. Wymaga filtra zscale (zimg).
    #
    # tin/min/pin/rin — wejście zakładamy jako linear RGB (matrix gbr), primaries 709,
    # pełny zakres (EXR jest [0..∞], pc). t=iec61966-2-1 (sRGB OETF), m/p=709 (primaries
    # sRGB == BT.709); r=tv+yuv420p dla wideo, r=pc+yuvj420p dla JPG. Wartości >1.0
    # (super-white) są clipowane do bieli display — standard dla SDR; tonemap to osobna,
    # kreatywna decyzja (tu niezastosowany).
    exr_linear: bool = True
    # Której przestrzeni zakładamy, że jest EXR (scene-referred linear):
    #   "aces2065" — ACES2065-1 (primaries AP0, linear). Standard VFX. Konwersja AP0->709
    #                przez LUT 3D (zscale nie zna primaries AP0) + sRGB OETF, bez RRT.
    #   "lin709"   — linear BT.709 (np. render w linear sRGB). Konwersja przez zscale
    #                (pin=709) + sRGB OETF (dotychczasowe zachowanie).
    exr_colorspace: str = "aces2065"
    aces_lut: str = "aces_ap0_to_srgb.cube"   # plik w app/luts/ (AP0 linear -> sRGB display)
    exr_vf: str = ("zscale=tin=linear:min=gbr:pin=709:rin=pc:"
                   "t=iec61966-2-1:m=709:p=709:r=tv,format=yuv420p")
    # JPG: zscale wydaje rgb24 (sam transfer sRGB, BEZ macierzy YUV), a enkoder mjpeg
    # robi konwersję RGB→YUV macierzą 601 i taguje JFIT jako 601 — konsystentnie. Gdyby
    # zscale wyprodukował yuvj420p z m=709, mjpeg i tak otagowałby JFIF jako 601 → rozjazd
    # macierzy (709 encode vs 601 tag) i przekłamania kolorów w czytnikach honorujących
    # tag (Nuke, ffplay). r=pc → pełny zakres (yuvj420p). Wymaga zscale.
    exr_vf_jpg: str = ("zscale=tin=linear:min=gbr:pin=709:rin=pc:"
                       "t=iec61966-2-1:p=709:r=pc,format=rgb24")
    # Proxy PNG 16-bit: zscale → display sRGB pełny zakres, następnie ffmpeg format
    # do rgb48le (PNG i tak zapisuje big-endian → ffprobe zgłasza rgb48be; to poprawne
    # 16-bit PNG). Drugi format=rgb48le to ffmpeg-owy filtr format wymuszający LE.
    exr_vf_png16: str = ("zscale=tin=linear:min=gbr:pin=709:rin=pc:"
                         "t=iec61966-2-1:m=709:p=709:r=pc,format=rgb48,format=rgb48le")
    # ACES: po LUT (sRGB display, rgb48le pełny zakres) -> yuv420p macierzą 709 (limited),
    # z identycznym transferem (tin=t=iec61966-2-1) — sama konwersja RGB->YUV do mp4.
    # Wymaga zscale; bez niej mp4 z ACES degraduje (swscale używa macierzy domyślnej).
    aces_mp4_yuv: str = ("zscale=tin=iec61966-2-1:min=gbr:pin=709:rin=pc:"
                         "t=iec61966-2-1:m=709:p=709:r=tv,format=yuv420p")
    color_tags: tuple = ("-color_primaries", "bt709", "-color_trc", "iec61966-2-1",
                         "-colorspace", "bt709", "-color_range", "tv")
    color_tags_jpg: tuple = ("-color_primaries", "bt709", "-color_trc", "iec61966-2-1",
                             "-colorspace", "bt709", "-color_range", "pc")


@dataclass(frozen=True)
class Config:
    h264: H264Config = field(default_factory=H264Config)
    h265: H265Config = field(default_factory=H265Config)
    audio: AudioConfig = field(default_factory=AudioConfig)
    encoder: EncoderConfig = field(default_factory=EncoderConfig)
    h264size: H264SizeConfig = field(default_factory=H264SizeConfig)
    image: ImageConfig = field(default_factory=ImageConfig)
    seq: SeqConfig = field(default_factory=SeqConfig)
    color: ColorConfig = field(default_factory=ColorConfig)


CONFIG = Config()
