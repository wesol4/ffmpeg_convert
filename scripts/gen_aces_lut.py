#!/usr/bin/env python3
"""Generator LUT-a 3D: ACES2065-1 (AP0, linear) -> sRGB display (BT.709 + sRGB OETF).

Prosta konwersja (BEZ filmicznego RRT): macierz AP0->lin_709 (z ampas/aces-dev,
z chromatic adaptation Bradford ACES-white -> D65) + sRGB OETF, z clipem [0,1].
Super-white (>1.0) i undershoot (<0) sa clipowane -- to zamierzony, prosty proxy
(bez RRT). Wartosci macierzy sa obliczane tu z primaries (i zgadzaja sie z publikowanymi).

Wyjscie: app/luts/aces_ap0_to_srgb.cube (Resolve/ffmpeg lut3d, rozmiar 33, domena [0,1]).

Uruchomienie:  python3 scripts/gen_aces_lut.py
"""
from __future__ import annotations

from pathlib import Path

# --- primaries (CIE xy) ---
AP0_R, AP0_G, AP0_B = (0.7347, 0.2653), (0.0, 1.0), (0.0001, -0.0770)
ACES_WHITE = (0.32168, 0.33767)              # bialy AP0 (≈ D60)
S_RGB_R, S_RGB_G, S_RGB_B = (0.640, 0.330), (0.300, 0.600), (0.150, 0.060)
D65 = (0.3127, 0.3290)

N = 33  # rozmiar LUT-a (33^3); dokladnosc wystarczajaca dla proxy


def _xy_to_xyz(x: float, y: float) -> tuple:
    return (x / y, 1.0, (1.0 - x - y) / y)


def _mm(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _mv(a, v):
    return [sum(a[i][k] * v[k] for k in range(3)) for i in range(3)]


def _inv(a):
    m = [row[:] + [1.0 if i == j else 0.0 for j in range(3)] for i, row in enumerate(a)]
    for c in range(3):
        p = max(range(c, 3), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        pv = m[c][c]
        m[c] = [x / pv for x in m[c]]
        for r in range(3):
            if r != c and m[r][c] != 0:
                f = m[r][c]
                m[r] = [a - f * b for a, b in zip(m[r], m[c])]
    return [row[3:] for row in m]


def _rgb_to_xyz(r, g, b, w):
    xr, yr, zr = _xy_to_xyz(*r)
    xg, yg, zg = _xy_to_xyz(*g)
    xb, yb, zb = _xy_to_xyz(*b)
    cols = [[xr, xg, xb], [yr, yg, yb], [zr, zg, zb]]
    xw, yw, zw = _xy_to_xyz(*w)
    s = _mv(_inv(cols), [xw, yw, zw])
    return [[cols[i][j] * s[j] for j in range(3)] for i in range(3)]


def _bradford(src_w, dst_w):
    mb = [[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]]
    s = _mv(mb, list(_xy_to_xyz(*src_w)))
    d = _mv(mb, list(_xy_to_xyz(*dst_w)))
    diag = [[d[0] / s[0], 0, 0], [0, d[1] / s[1], 0], [0, 0, d[2] / s[2]]]
    return _mm(_mm(_inv(mb), diag), mb)


def _ap0_to_lin709() -> list:
    m_ap0_xyz = _rgb_to_xyz(AP0_R, AP0_G, AP0_B, ACES_WHITE)
    m_xyz_709 = _inv(_rgb_to_xyz(S_RGB_R, S_RGB_G, S_RGB_B, D65))
    cat = _bradford(ACES_WHITE, D65)
    return _mm(m_xyz_709, _mm(cat, m_ap0_xyz))


def srgb_oetf(l: float) -> float:
    if l <= 0.0:
        return 0.0
    if l <= 0.0031308:
        return 12.92 * l
    return 1.055 * (l ** (1.0 / 2.4)) - 0.055


def main() -> None:
    mat = _ap0_to_lin709()
    # weryfikacja: bialy (1,1,1) -> (1,1,1)
    assert all(abs(v - 1.0) < 1e-6 for v in _mv(mat, [1, 1, 1])), "bialy nie zachowany"
    out = Path(__file__).resolve().parents[1] / "app" / "luts" / "aces_ap0_to_srgb.cube"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = ['TITLE "ACES2065-1 (AP0 linear) -> sRGB display (no RRT)"',
             f"LUT_3D_SIZE {N}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    for bi in range(N):
        for gi in range(N):
            for ri in range(N):  # R zmienia sie najszybciej (konwencja .cube)
                r, g, b = ri / (N - 1), gi / (N - 1), bi / (N - 1)
                lin = _mv(mat, [r, g, b])
                lin = [max(0.0, min(1.0, c)) for c in lin]  # clip (bez RRT)
                out_rgb = [max(0.0, min(1.0, srgb_oetf(c))) for c in lin]
                lines.append(f"{out_rgb[0]:.6f} {out_rgb[1]:.6f} {out_rgb[2]:.6f}")
    out.write_text("\n".join(lines) + "\n")
    print(f"zapisano {out} ({len(lines)} linii, {N}^3 = {N**3} wezlow)")
    print("macierz AP0->lin_709:")
    for row in mat:
        print("  [" + ", ".join(f"{v:+.6f}" for v in row) + "]")


if __name__ == "__main__":
    main()