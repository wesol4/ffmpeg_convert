"""Wspólna logika konwersji koloru EXR (scene-referred linear) → sRGB display.

Używane przez presets.sequence (mp4 + proxy) i presets.image (EXR→JPG), by uniknąć
cyklu importów (sequence importuje _scale_filter z image). Zależy tylko od CONFIG
i probe — bez importów wewnątrz presets.
"""
from __future__ import annotations

from pathlib import Path

from app.config import CONFIG
from app.core import probe

# Opcjonalny nadpisany LUT ACES (np. wyeksportowany z Nuke: ACES 2.0 sRGB Display).
# Ustawiany przez CLI --aces-lut / GUI; pusty = wbudowany aces_ap0_to_srgb.cube.
_user_lut: "Path | None" = None


def set_aces_lut(path) -> None:
    """Nadpisz LUT ACES (AP0 linear → sRGB display). None = wróć do wbudowanego."""
    global _user_lut
    _user_lut = Path(path) if path else None


def lut_path() -> Path:
    """Ścieżka LUT-a 3D: nadpisany (user) lub wbudowany app/luts/aces_ap0_to_srgb.cube."""
    if _user_lut is not None:
        return _user_lut
    return Path(__file__).resolve().parents[1] / "luts" / CONFIG.color.aces_lut


def exr_color_vf(scale: "str | None", color: bool, seq_ext: str, target: str):
    """vf konwertujący EXR (scene-referred linear) → sRGB display dla danego wyjścia.

    target ∈ {"jpg", "png", "mp4"}. scale — wynik _scale_filter() lub None (doklejone
    PRZED konwersją koloru, by skalować w linear). Zwraca (vf, tags, label) lub
    (None, [], "") gdy bez konwersji (nie-EXR / color=False / brak zscale/LUT).

    ACES2065-1 (AP0, domyślnie): macierz AP0→709 przez LUT 3D (zscale nie zna primaries
    AP0) + sRGB OETF, bez filmicznego RRT — wartości >1 i <0 są clipowane. lin709:
    zscale (pin=709) + sRGB OETF (dotychczasowe). Wyjścia: jpg → rgb24 (mjpeg robi
    konsystentną konwersję RGB→YUV 601 + tag JFIF 601); png → rgb48le (16-bit sRGB
    display); mp4 → yuv420p macierzą 709 + tagi 709 (konsystentnie, wymaga zscale).
    """
    if not (color and CONFIG.color.exr_linear and seq_ext.lower() == "exr"):
        return None, [], ""
    cs = CONFIG.color.exr_colorspace
    zscale_ok = probe.has_filter("zscale")
    tag = " (AP0→sRGB)" if cs == "aces2065" else " (linear→sRGB)"

    if cs == "aces2065":
        lp = lut_path()
        if not lp.is_file():
            from app.log import get_logger
            get_logger().warning(
                "Brak LUT-a ACES (%s) — pomijam konwersję koloru EXR.", lp)
            return None, [], ""
        base = f"lut3d=file={lp}"
        if target == "jpg":
            vf = f"{scale},{base},format=rgb24" if scale else f"{base},format=rgb24"
            return vf, list(CONFIG.color.color_tags_jpg), tag
        if target == "png":
            return (f"{scale},{base}" if scale else base), [], tag
        # mp4: LUT (rgb48le sRGB display) -> zscale RGB->yuv420p macierzą 709 (limited).
        if not zscale_ok:
            from app.log import get_logger
            get_logger().warning(
                "mp4 z ACES wymaga zscale (RGB->YUV 709) — pomijam (kolory mp4 mogą być niedokładne).")
        vf = (f"{base},{CONFIG.color.aces_mp4_yuv}" if zscale_ok
              else f"{base},format=yuv420p")
        return vf, list(CONFIG.color.color_tags), tag

    # lin709 (legacy): zscale pin=709 + sRGB OETF, gotowe pipeline'y wg targetu.
    if not zscale_ok:
        from app.log import get_logger
        get_logger().warning(
            "EXR linear→display wymaga filtra zscale (zimg), niedostępnego w tym "
            "buildie ffmpeg — pomijam konwersję koloru (wyjście może być za ciemne).")
        return None, [], ""
    pipelines = {"jpg": CONFIG.color.exr_vf_jpg, "png": CONFIG.color.exr_vf_png16,
                 "mp4": CONFIG.color.exr_vf}
    tags = {"jpg": CONFIG.color.color_tags_jpg, "png": [], "mp4": CONFIG.color.color_tags}
    base = pipelines[target]
    vf = f"{scale},{base}" if scale and target != "mp4" else base
    return vf, list(tags[target]), tag