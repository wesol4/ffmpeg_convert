"""Presety obrazów — kompresja do JPG (q) lub zachowanie oryginału, z opcjonalną
zmianą nazwy (numeracja), wyborem miejsca zapisu, skalowaniem i podziałem na siatkę.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.config import CONFIG
from app.core import probe
from app.core.ffmpeg import FFMPEG, kind_of
from app.core.jobs import Job

# Mapowanie etykiet jakości na wartość -q:v FFmpeg (niższa = lepsza).
IMAGE_QUALITY = {2: "Q2 (~94%, najlepsza)", 5: "Q5 (~85%, dobra)",
                 10: "Q10 (~70%, mała waga)", 1: "Bez kompresji (maks. JPG)"}


def image_target_name(path: Path, idx: int, newname: str, keep: bool) -> tuple:
    base = f"{newname}_{idx:03d}" if newname else path.stem
    ext = path.suffix.lstrip(".") if keep else CONFIG.image.jpg_ext
    return base, ext


def _scale_filter(scale_pct: Optional[float]) -> Optional[str]:
    """Wyrażenie filtra FFmpeg skalujące o dany procent, lub None gdy brak.

    trunc(.../2)*2 zaokrągla wymiary w dół do parzystych — yuvj420p tego wymaga.
    """
    if not scale_pct or scale_pct == 100:
        return None
    p = scale_pct / 100
    return f"scale=trunc(iw*{p}/2)*2:trunc(ih*{p}/2)*2"


def build_image_jobs(files: list, *, quality: Optional[int] = 2, keep: bool = False,
                     newname: str = "", subdir: bool = True,
                     scale_pct: Optional[float] = None, color: bool = True,
                     colorspace: Optional[str] = None,
                     aces_lut: "Path | str | None" = None) -> list:
    """Joby dla obrazów. quality=None lub keep=True → kopiuj oryginał.

    Kompresji do JPG poddajemy DOWOLNY obraz rastrowy (nie tylko PNG) — FFmpeg
    potrafi przekodować każdy z IMAGE_EXTS.

    scale_pct — opcjonalne skalowanie procentowe (np. 50 = połowa wymiarów),
    stosowane tylko przy przekodowaniu (nie przy „zachowaj oryginał").

    color — dla EXR (scene-referred linear) nakładaj OETF sRGB (iec61966-2-1) + tagi
    koloru (CONFIG.color), by JPG nie wyszedł za ciemny w dekoderach bez color
    management (Nuke zakłada sRGB dla JPG 8-bit). Wymaga zscale; bez niego degrade
    do zwykłego format=yuvj420p.
    """
    files = [Path(f) for f in files]
    jobs: list = []
    idx = 0
    scale = _scale_filter(scale_pct)
    for path in files:
        if kind_of(path) != "image":
            continue
        idx += 1
        base, ext = image_target_name(path, idx, newname, keep)
        out_dir = (path.parent / CONFIG.image.compressed_subdir) if subdir else path.parent
        out_path = out_dir / f"{base}.{ext}"
        if out_path.resolve() == path.resolve():
            continue  # nie nadpisuj oryginału
        if keep:
            jobs.append(Job(label=f"{path.name} → {out_path.name}",
                            cmds=[["__copy__", str(path), str(out_path)]], mkdir=out_dir))
        else:
            # EXR (linear) → sRGB display przez exr_color_vf (ACES LUT lub zscale lin709);
            # None = nie-EXR / color=False / brak zscale(LUT) → sam format=yuvj420p.
            from app.core.color import exr_color_vf
            cvf, extra, color_tag = exr_color_vf(
                scale, color, path.suffix.lstrip("."), "jpg",
                colorspace=colorspace, aces_lut=aces_lut)
            if cvf is None:
                vf = "format=yuvj420p" if not scale else f"{scale},format=yuvj420p"
                extra, color_tag = [], ""
            else:
                vf = cvf
            cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", str(path),
                   "-q:v", str(quality), "-vf", vf, *extra, str(out_path)]
            tag = f" (skala {scale_pct:g}%)" if scale else ""
            jobs.append(Job(label=f"{path.name} → {out_path.name}{tag}{color_tag}",
                            cmds=[cmd], mkdir=out_dir))
    return jobs


def build_split_jobs(files: list, *, cols: int, rows: int, subdir: bool = True) -> list:
    """Podziel każdy obraz na siatkę cols×rows przez filtr crop.

    Ostatnia kolumna/wiersz dostaje resztę (żeby nie gubić pikseli przy
    dzieleniu). Przy subdir=True zapis do podfolderu 'SplitGrid'.
    """
    if cols < 1 or rows < 1:
        raise ValueError("cols i rows muszą być ≥ 1")
    jobs: list = []
    for path in [Path(f) for f in files]:
        if kind_of(path) != "image":
            continue
        size = probe.probe_size(path)
        if not size:
            continue  # ffprobe nie odczytał wymiarów — pomijamy
        w, h = size
        tw, th = w // cols, h // rows
        out_dir = (path.parent / CONFIG.image.split_subdir) if subdir else path.parent
        cmds = []
        for y in range(rows):
            for x in range(cols):
                cw = (w - x * tw) if x == cols - 1 else tw
                ch = (h - y * th) if y == rows - 1 else th
                out = out_dir / f"{path.stem}_{y}_{x}.png"
                cmds.append([FFMPEG, "-y", "-loglevel", "error", "-i", str(path),
                             "-vf", f"crop={cw}:{ch}:{x * tw}:{y * th}", str(out)])
        jobs.append(Job(
            label=f"{path.name} → {out_dir.name}/ ({cols}×{rows})",
            cmds=cmds, mkdir=out_dir,
        ))
    return jobs
