#!/usr/bin/env python
"""Wypiecz .cube (AP0 linear -> sRGB display) z konfigu OCIO, np. z Nuke ACES 2.0.

Ręczne próbkowanie procesora OCIO (bez Baker/API), by działało niezależnie od wersji
PyOpenColorIO. Wyjście: 3D .cube (format Resolve/ffmpeg lut3d) z domeną pokrywającą
scene-linear (0..DOM_MAX, domyślnie 16 — pokrywa super-white, RRT tonemapuje).

URUCHOMIENIE w Nuke (z licencją), jedną z dróg:
  A) Script Editor w Nuke: wczytaj ten plik i wywołaj bake(<ocio>, <out>).
  B) Terminal (z licencją render): Nuke17.0 -t bake_aces_lut_from_ocio.py <ocio> <out.cube> [DOM_MAX] [SIZE]

Przykład:
  Nuke17.0 -t bake_aces_lut_from_ocio.py \
    ~/software/Nuke17.0v3/plugins/OCIOConfigs/configs/fn-nuke_cg-config-v3.0.0_aces-v2.0_ocio-v2.4.ocio \
    ~/aces2_srgb.cube 16 64

Potem w app:  cli seq --aces-lut ~/aces2_srgb.cube --proxy jpg <folder>
"""
import sys


def bake(ocio_path, out_path, dom_max=16.0, size=64,
         src="ACES2065-1", display="sRGB - Display",
         view="ACES 2.0 - SDR 100 nits (Rec.709)"):
    import PyOpenColorIO as OCIO

    config = OCIO.Config.CreateFromFile(ocio_path)
    dvt = OCIO.DisplayViewTransform()
    dvt.setSrc(src)
    dvt.setDisplay(display)
    dvt.setView(view)
    dvt.setLooksBypass(True)
    proc = config.getProcessor(dvt, OCIO.TRANSFORM_DIR_FORWARD).getDefaultCPUProcessor()

    n = size
    lines = ['TITLE "OCIO: %s -> %s / %s"' % (src, display, view),
             f"LUT_3D_SIZE {n}",
             "DOMAIN_MIN 0 0 0",
             f"DOMAIN_MAX {dom_max} {dom_max} {dom_max}"]
    step = dom_max / (n - 1)
    for bi in range(n):
        for gi in range(n):
            for ri in range(n):  # R zmienia sie najszybciej (konwencja .cube)
                rgb = [ri * step, gi * step, bi * step]
                out = proc.applyRGB(rgb)
                lines.append("%.6f %.6f %.6f" % tuple(max(0.0, min(1.0, c)) for c in out))
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("Zapisano %s (%d^3, domena 0..%g)" % (out_path, n, dom_max))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    ocio_path = sys.argv[1]
    out_path = sys.argv[2]
    dom_max = float(sys.argv[3]) if len(sys.argv) > 3 else 16.0
    size = int(sys.argv[4]) if len(sys.argv) > 4 else 64
    bake(ocio_path, out_path, dom_max, size)
else:
    # importowany w Script Editorze Nuke: wywołaj bake(...)
    pass