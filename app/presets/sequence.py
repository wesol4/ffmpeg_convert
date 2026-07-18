"""Sekwencja obrazów → wideo oraz spritesheet (flipbook).

Demuxer image2 (niezawodny FPS, pełna liczba klatek) i concat + filtr tile.
Stringowe id formatów typowane przez SeqFormat (str, Enum).
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
from enum import StrEnum
from pathlib import Path
from typing import TypedDict

from app.config import CONFIG, ProxyVariant
from app.core import probe
from app.core.color import exr_color_vf
from app.core.ffmpeg import FFMPEG, Encoder, kind_of
from app.core.jobs import Job
from app.presets.image import _scale_filter
from app.presets.video import VideoPreset, _encoder_codec_vargs


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


def build_seq_job(files: list, *, fps: int = 24, fmt: "SeqFormat | str" = "h264",
                  encoder: "Encoder | str" = "cpu", color: bool = True,
                  out_path: "Path | str | None" = None,
                  make_mp4: bool = True,
                  thumb_width: "int | None" = None, thumb_ext: str = "jpg",
                  proxy_variants: "tuple | list" = (),
                  proxy_start_frame: int = 1001,
                  size_mode: str = "crf",
                  crf: int = CONFIG.h264size.crf_default,
                  target_mb: float = CONFIG.h264size.target_mb_default,
                  colorspace: "str | None" = None,
                  aces_lut: "Path | str | None" = None) -> Job:
    """Złóż posortowane obrazy w wideo przez demuxer image2 (niezawodny FPS i
    pełna liczba klatek). Tworzy katalog tymczasowy z symlinkami seq_%05d.ext.

    out_path — jawna ścieżka wyjściowa mp4/mov (np. w folderze nadrzędnym).
    None = dotychczasowe zachowanie: plik wewnątrz folderu sekwencji,
    nazwany jak folder. Audio nadal szukane w folderze sekwencji (out_dir).

    encoder — wybór enkodera dla formatów h264/h265 (prores/dnxhd CPU-only).

    color — dla sekwencji EXR (scene-referred linear) i formatu h264/h265 nakładaj
    OETF sRGB (iec61966-2-1) + tagi koloru (patrz CONFIG.color), by MP4 nie wychodził
    za ciemny w dekoderach bez color management (Discord, miniatury OS, Nuke). Pomijane
    dla prores/dnxhd (formaty montażowe — grading należy do coloristy). Wymaga filtra
    zscale; przy jego braku wywołanie degraduje do starego zachowania (bez warning).

    make_mp4 — False = pomiń komendę mp4 (samo proxy / miniaturka niedostępna bez mp4).

    thumb_width — gdy podane (>0) i make_mp4, do Joba doklejana jest komenda
    miniaturki (klatka z połowy mp4, skalowana), zapis w folderze nadrzędnym.

    proxy_variants — sekwencje proxy (klucze lub ProxyVariant) generowane obok:
    sekwencja klatek numerowana od proxy_start_frame (standard VFX), w podfolderze
    variant.subdir wewnątrz folderu sekwencji. Nie rusza plików-źródeł.

    size_mode — dla H.264: "crf" (jakość, 1 przebieg) lub "size" (docelowy rozmiar MB,
    CPU 2-pass). Dla pozostałych formatów ignorowane.
    """
    fmt = SeqFormat(fmt)  # coerce str → enum (ValueError przy literówce)
    encoder = Encoder(encoder)
    spec = SEQ_FORMATS[fmt]
    # Sortowanie naturalne (frame_2 < frame_10), nie leksykalne. resolve() —
    # by nazwa folderu wyjściowego była poprawna także dla ścieżek względnych.
    paths = sorted((Path(f).resolve() for f in files), key=lambda p: _natural_key(p.name))
    if not paths:
        raise ValueError("Brak plików sekwencji.")

    out_dir = paths[0].parent
    name = out_dir.name or "output"
    mp4_out = (Path(out_path) if out_path is not None
               else out_dir / f"{name}.{spec['ext']}")
    seq_ext = paths[0].suffix.lstrip(".")
    duration = len(paths) / fps if fps else None

    # Konwersja koloru EXR (linear) → display tylko dla formatów dystrybucyjnych.
    # prores/dnxhd to intermediaty montażowe — tam OETF byłby szkodliwy.
    color_vf: "str | None" = None
    color_tags: list = []
    color_tag = ""
    if (color and CONFIG.color.exr_linear and seq_ext.lower() == "exr"
            and fmt in (SeqFormat.H264, SeqFormat.H265)):
        color_vf, color_tags, color_tag = exr_color_vf(
            None, color, seq_ext, "mp4", colorspace=colorspace, aces_lut=aces_lut)

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

    tmp_pattern = str(tmp / f"seq_%05d.{seq_ext}")
    cmds: list = []
    label = f"{len(paths)} klatek @ {fps} fps"

    # 1) MP4 z klatek (opcjonalnie). Miniaturka wymaga mp4 (seek do połowy mp4).
    if make_mp4:
        if fmt == SeqFormat.H264 and size_mode == "size":
            # Docelowy rozmiar: CPU 2-pass z kontrolą bitrate.
            size_job = _h264_size_seq_job(
                tmp_pattern, mp4_out, fps, len(paths), audio, color_vf, color_tags,
                target_mb, out_dir, tmp,
                colorspace=colorspace, aces_lut=aces_lut,
            )
            cmds.extend(size_job.cmds)
            label += f" → {mp4_out.name} (~{target_mb:g} MB, CPU 2-pass){color_tag}"
        else:
            cmd = [FFMPEG, "-y", "-framerate", str(fps), "-i", tmp_pattern]
            if audio:
                cmd += ["-i", str(audio), *spec["aargs"], "-shortest"]
            if color_vf:
                cmd += ["-vf", color_vf]
            # vargs: dla h264/h265 honoruj enkoder; prores/dnxhd — CPU z SEQ_FORMATS.
            if fmt in (SeqFormat.H264, SeqFormat.H265) and encoder != Encoder.CPU:
                vpreset = VideoPreset.H264 if fmt == SeqFormat.H264 else VideoPreset.H265
                quality = crf if fmt == SeqFormat.H264 else CONFIG.h265.crf
                codec, vargs = _encoder_codec_vargs(vpreset, encoder, quality)
                cmd += ["-c:v", codec, *vargs, *color_tags, str(mp4_out)]
                enc_tag = f" [{encoder.value.upper()}]"
            else:
                if fmt == SeqFormat.H264:
                    # size_mode == "crf" pozwala wybrać własny CRF;
                    # domyślnie używamy klasycznego CRF 18 z CONFIG.h264.
                    vargs = ["-crf", str(crf), "-preset", CONFIG.h264.preset,
                             "-pix_fmt", CONFIG.h264.pix_fmt]
                    cmd += ["-c:v", "libx264", *vargs, *color_tags, str(mp4_out)]
                    enc_tag = ""
                else:
                    cmd += [*spec["vargs"], *color_tags, str(mp4_out)]
                    enc_tag = ""
            cmds.append(cmd)
            label += f" → {mp4_out.name}{enc_tag}{color_tag}"
        if audio:
            label += f" (+ audio {audio.name})"

        if thumb_width:
            thumb = out_dir.parent / f"{name}_thumb.{thumb_ext}"
            cmds.append(build_thumbnail_cmd(mp4_out, thumb, thumb_width, thumb_ext))
            label += f" + miniatura {thumb.name}"
    else:
        label += " (bez mp4)"

    # 2) Proxy — sekwencje klatek numerowane od proxy_start_frame (standard VFX).
    #    Współdzielą tmp (symlinki); podfoldery obok źródeł (nie rusza klatek).
    variants = [_resolve_proxy_variant(v) for v in proxy_variants]
    for v in variants:
        cmds.append(build_proxy_cmd(tmp_pattern, out_dir, name, v,
                                    fps=fps, start_frame=proxy_start_frame,
                                    color=color, seq_ext=seq_ext,
                                    colorspace=colorspace, aces_lut=aces_lut))
        label += f" + proxy {v.subdir}/{name}.{proxy_start_frame}+.{v.ext}"

    return Job(label=label, cmds=cmds, mkdir=out_dir, cleanup=[tmp],
               duration=duration)


def _h264_size_seq_job(tmp_pattern: str, mp4_out: Path, fps: int, frame_count: int,
                       audio: "Path | None", color_vf: "str | None",
                       color_tags: list, target_mb: float,
                       out_dir: Path, tmp: Path,
                       colorspace: "str | None" = None,
                       aces_lut: "Path | str | None" = None) -> Job:
    """CPU 2-pass H.264 dla sekwencji klatek z docelowym rozmiarem w MB.

    Dla sekwencji nie znamy trwania z ffprobe, więc liczymy je z fps i liczby klatek.
    Tryb docelowego rozmiaru zawsze CPU — GPU nie robi precyzyjnego 2-pass.
    """
    duration = frame_count / fps if fps else 0.0
    passlog = str(tmp / "ffmpeg2pass")
    cleanup = [Path(passlog + "-0.log"), Path(passlog + "-0.log.mbtree")]

    if duration <= 0:
        # Fallback: CRF 23, gdy nie można obliczyć długości.
        cmd = [FFMPEG, "-y", "-framerate", str(fps), "-i", tmp_pattern]
        if color_vf:
            cmd += ["-vf", color_vf]
        cmd += ["-c:v", "libx264", "-crf", str(CONFIG.h264size.crf_default),
                "-preset", CONFIG.h264.preset, "-pix_fmt", CONFIG.h264.pix_fmt,
                *color_tags, str(mp4_out)]
        return Job(label=f"{mp4_out.name} (brak fps — CRF fallback)", cmds=[cmd],
                   mkdir=out_dir, cleanup=cleanup)

    audio_k = CONFIG.audio.twopass_audio_k if audio else 0
    total_k = (target_mb * 8192) / duration * (1 - CONFIG.h264size.overhead_pct)
    video_k = max(50, min(int(total_k - audio_k), CONFIG.h264size.max_video_kbps))

    pass1 = [FFMPEG, "-y", "-framerate", str(fps), "-i", tmp_pattern]
    if color_vf:
        pass1 += ["-vf", color_vf]
    pass1 += ["-c:v", "libx264", "-b:v", f"{video_k}k", "-preset", "slow",
                "-pix_fmt", CONFIG.h264.pix_fmt, "-pass", "1",
                "-passlogfile", passlog, "-an", "-f", "null", os.devnull]

    pass2 = [FFMPEG, "-y", "-framerate", str(fps), "-i", tmp_pattern]
    if color_vf:
        pass2 += ["-vf", color_vf]
    pass2 += ["-c:v", "libx264", "-b:v", f"{video_k}k", "-preset", "slow",
               "-pix_fmt", CONFIG.h264.pix_fmt, "-pass", "2",
               "-passlogfile", passlog]
    if audio:
        pass2 += ["-i", str(audio), "-c:a", CONFIG.audio.codec, "-b:a", f"{audio_k}k", "-shortest"]
    else:
        pass2.append("-an")
    pass2 += [*color_tags, str(mp4_out)]

    return Job(
        label=f"{mp4_out.name} (~{target_mb:g} MB, {video_k}k wideo, CPU 2-pass)",
        cmds=[pass1, pass2], mkdir=out_dir, cleanup=cleanup,
        duration=duration,
    )


def build_thumbnail_cmd(src: "Path | str", out_path: "Path | str",
                        width: int, ext: str = "jpg") -> list:
    """Komenda FFmpeg wyciągająca jedną klatkę z połowy filmu i skalująca ją
    do stałej szerokości (proporcje zachowane, wysokość parzysta).

    -ss przed -i = szybki seek (input seek); -frames:v 1 = jedna klatka;
    scale={width}:-2 = szerokość N, wysokość auto zaokrąglona w dół do parzystej.
    Długość źródła z ffprobe; przy braku (None) seekujemy do 0 (pierwsza klatka).
    """
    dur = probe.probe_duration(Path(src)) or 0.0
    mid = dur / 2 if dur else 0.0
    # format=rgb24 na końcu: dekoduje YUV z mp4 (macierz 709 z colr) do RGB, a enkoder
    # mjpeg robi konsystentną konwersję RGB→YUV(601)+tag JFIF 601. Bez tego mjpeg
    # przełąpałby YUV(709) z mp4 i otagował 601 → rozjazd macierzy (patrz exr_vf_jpg).
    return [FFMPEG, "-y", "-loglevel", "error", "-ss", f"{mid:.3f}",
            "-i", str(src), "-frames:v", "1",
            "-vf", f"scale={width}:-2,format=rgb24", str(out_path)]


def _resolve_proxy_variant(v: "ProxyVariant | str") -> ProxyVariant:
    """Str/ProxyVariant → ProxyVariant. Str = klucz szukany w CONFIG.seq.proxy_variants."""
    if isinstance(v, ProxyVariant):
        return v
    for pv in CONFIG.seq.proxy_variants:
        if pv.key == v:
            result: ProxyVariant = pv
            return result
    raise ValueError(f"Nieznany wariant proxy: {v!r}")


def build_proxy_cmd(tmp_pattern: "Path | str", out_dir: "Path | str", stem: str,
                    variant: ProxyVariant, *, fps: int = 24,
                    start_frame: int = 1001, color: bool = True,
                    seq_ext: str = "exr",
                    colorspace: "str | None" = None,
                    aces_lut: "Path | str | None" = None) -> list:
    """Komenda FFmpeg: sekwencja klatek → proxy (sekwencja obrazów numerowana od
    start_frame, standard VFX 1001). Czyta z tmp_pattern (image2 demuxer), zapisuje do
    out_dir/variant.subdir/stem.NNNN.ext. Podfolder jest tu zakładany (ffmpeg image2
    nie tworzy podfolderów wyjściowych).

    Kolor: EXR (scene-referred linear) + color → sRGB display przez exr_color_vf
    (ACES2065-1/AP0 przez LUT 3D lub lin709 przez zscale) — jpg→rgb24 (mjpeg 601),
    png16→rgb48le (16-bit sRGB display). color=False / nie-EXR → sam format
    (jpg: rgb24; png: rgb48le — liniowe wartości zachowane). Patrz CONFIG.color.
    """
    out_dir = Path(out_dir)
    subdir = out_dir / variant.subdir
    subdir.mkdir(parents=True, exist_ok=True)
    pad = CONFIG.seq.proxy_pad
    out_pattern = str(subdir / f"{stem}.%0{pad}d.{variant.ext}")

    scale = _scale_filter(variant.scale_pct)
    target = "png" if variant.ext == "png" else "jpg"
    # EXR (linear) → sRGB display przez exr_color_vf (ACES LUT lub zscale lin709);
    # None = nie-EXR / color=False / brak zscale/LUT → sam format (bez OETF).
    cvf, tags, _label = exr_color_vf(
        scale, color, seq_ext, target, colorspace=colorspace, aces_lut=aces_lut)
    if cvf is None:
        # PNG → rgb48le (16-bit, wartości zachowane). JPG → rgb24 i zostawiamy konwersję
        # RGB→YUV(+tag 601) enkoderowi mjpeg (konsystentne — patrz exr_vf_jpg).
        fmt = "rgb48le" if variant.ext == "png" else "rgb24"
        vf = f"{scale},format={fmt}" if scale else f"format={fmt}"
    else:
        vf = cvf

    cmd = [FFMPEG, "-y", "-loglevel", "error", "-framerate", str(fps),
           "-i", str(tmp_pattern), "-vf", vf]
    if variant.quality is not None:
        cmd += ["-q:v", str(variant.quality)]
    cmd += [*tags, "-start_number", str(start_frame), out_pattern]
    return cmd


def build_seq_jobs_from_folders(folders: list, *, fps: int = 24,
                                fmt: "SeqFormat | str" = "h264",
                                encoder: "Encoder | str" = "cpu",
                                color: bool = True, mp4_in_seq: bool = True,
                                thumb_width: "int | None" = None,
                                thumb_ext: str = "jpg", make_mp4: bool = True,
                                proxy_variants: "tuple | list" = (),
                                proxy_start_frame: int = 1001,
                                size_mode: str = "crf",
                                crf: int = CONFIG.h264size.crf_default,
                                target_mb: float = CONFIG.h264size.target_mb_default,
                                colorspace: "str | None" = None,
                                aces_lut: "Path | str | None" = None) -> list:
    """Batch: jeden Job na folder sekwencji (mp4 + miniaturka + proxy wg wyboru).

    mp4_in_seq — True = mp4 wewnątrz folderu sekwencji (jak build_seq_job);
    False = mp4 w folderze nadrzędnym (razem z miniaturką).

    thumb_width — gdy podane (>0) i make_mp4, do Joba doklejana jest komenda
    miniaturki (klatka z połowy mp4, skalowana) zapisana w folderze nadrzędnym.

    proxy_variants — sekwencje proxy (klucze lub ProxyVariant); sekwencja klatek
    numerowana od proxy_start_frame w podfolderze variant.subdir obok źródeł.

    make_mp4 — False = pomiń mp4 (samo proxy); miniaturka wtedy niedostępna bez mp4.

    size_mode — dla H.264: "crf" lub "size" (docelowy rozmiar MB). Dla pozostałych
    formatów ignorowane.

    Folder bez klatek-obrazów jest pomijany (bez Joba).
    """
    fmt = SeqFormat(fmt)
    spec = SEQ_FORMATS[fmt]
    jobs: list = []
    for folder in folders:
        folder = Path(folder)
        if not folder.is_dir():
            continue
        frames = sorted((p for p in folder.iterdir() if kind_of(p) == "image"),
                        key=lambda p: _natural_key(p.name))
        if not frames:
            continue  # folder bez klatek — pomijamy
        out_path = None if mp4_in_seq else folder.parent / f"{folder.name}.{spec['ext']}"
        jobs.append(build_seq_job(
            [str(f) for f in frames], fps=fps, fmt=fmt, encoder=encoder, color=color,
            out_path=out_path, make_mp4=make_mp4,
            thumb_width=thumb_width, thumb_ext=thumb_ext,
            proxy_variants=proxy_variants, proxy_start_frame=proxy_start_frame,
            size_mode=size_mode, crf=crf, target_mb=target_mb,
            colorspace=colorspace, aces_lut=aces_lut,
        ))
    return jobs


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
