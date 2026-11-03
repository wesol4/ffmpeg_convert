---
name: color-pipeline
description: Zasady koloru w ffmpeg_convert — sRGB vs BT.709, macierze 601/709 i tagi, zakresy tv/pc, 4:2:0 i parzyste wymiary, EXR linear (ACES2065-1 / lin709) → wideo i obrazy, nieotagowane wideo z generatorów AI, ProRes pod Nuke. Użyj przy każdej zmianie filtrów scale/zscale/lut3d, pix_fmt albo tagów koloru.
---

# Kolor

Decyzja D8 (zaakceptowana) i punkty spec: VID-09, VID-17, IMG-07, IMG-11, SEQ-C01…C06.

## Pojęcia, które się mylą

- **sRGB i BT.709 mają te same primaries**, różnią się transferem (krzywą). Konwersja RGB→YUV
  dotyczy **macierzy**, nie primaries.
- **Macierz 601 vs 709**: swscale bez wskazania używa 601 przy RGB→YUV i przy dekodowaniu YUV bez
  tagu. HD+ jest odtwarzane jako 709. Dlatego **zawsze** podawaj `out_color_matrix` /
  `in_color_matrix` i taguj wynik.
- **Zakres**: wideo `tv` (16–235), JPEG/PNG `pc` (0–255). mjpeg zapisuje znacznik JFIF 601 pełny
  zakres, więc do JPG podawaj `format=rgb24` i pozwól enkoderowi zrobić konwersję
  (`ColorConfig.exr_vf_jpg` opisuje dlaczego).
- **4:2:0** wymaga parzystej szerokości i wysokości, **4:2:2** parzystej szerokości.
  Przycinamy 1 px z prawej/dołu (`EVEN_CROP` w `app/presets/sequence.py`, D11), nie skalujemy.

## Reguły (D8)

| źródło → cel | macierz | tagi (space/prim/trc/range) |
|---|---|---|
| RGB/sRGB (PNG, TIFF, RGB w MOV) → MP4 (dystrybucja) | 709, tv | bt709 / bt709 / **iec61966-2-1** / tv |
| RGB/sRGB → ProRes/DNx/Cineform (montaż) | 709, tv | bt709 / bt709 / **bt709** / tv |
| JPG → wideo HD+ | jak RGB (709), nie zostawiać 601 | jak wyżej |
| YUV otagowane → dowolny | bez zmiany macierzy | przenieś tagi |
| YUV bez tagów, wysokość ≥ 720 (generatory AI) | traktuj jak 709 | dopisz 709 |
| wideo → PNG/klatki | dekoduj `scale=in_color_matrix=bt709` dla nieotagowanego HD (`_decode_vf`) | — |
| EXR → MP4 i ProRes/DNx | transformacja do display (poniżej) | jak RGB → cel |
| PNG z alfą → JPG | spłaszcz na białe tło, wpis w logu | — |

Stan v0.7 odbiega w kilku miejscach (A14, A15): presety wideo nie konwertują RGB, `prores_nuke`
taguje bez konwersji, JPG zostaje 601, EXR → ProRes jest surowy. Naprawa w etapie 2.

## EXR (scene-referred linear)

- **ACES2065-1** (AP0): LUT 3D `app/luts/aces_ap0_to_srgb.cube` (macierz AP0→709 + OETF sRGB, bez
  RRT, wartości > 1 obcinane). zscale nie zna primaries AP0, dlatego LUT. Własny LUT (np. z Nuke,
  ACES 2.0 sRGB Display): `--aces-lut` / pole w GUI. LUT generują `scripts/gen_aces_lut.py` i
  `scripts/bake_aces_lut_from_ocio.py`.
- **lin709**: `zscale=tin=linear:min=gbr:pin=709:rin=pc:t=iec61966-2-1:…` (`ColorConfig`).
- **Którą wybrać**: odczyt atrybutu `chromaticities` z nagłówka EXR (AP0 → ACES, Rec.709 →
  lin709); brak atrybutu → ACES2065-1 z widocznym komunikatem (D8c, do zrobienia w etapie 2).
- Bez filtra zscale albo pliku LUT konwersja jest pomijana z ostrzeżeniem w logu
  (`app/core/color.py`); test: `TestSeqEXRColor`, `TestImageEXRColor`.
- Skala przed konwersją koloru (skalowanie w linear).

## ProRes pod Nuke (`prores_nuke`)

`prores_ks -profile:v 3 -pix_fmt yuv422p10le`, tagi bt709/bt709/bt709, `pcm_s24le -ar 48000`.
Tagi muszą odpowiadać danym: źródło RGB lub otagowane inaczej najpierw
`scale=out_color_matrix=bt709:out_range=tv`.

## Gotowe fragmenty filtrów

```text
RGB → YUV 709 (MP4):    crop=trunc(iw/2)*2:trunc(ih/2)*2,scale=out_color_matrix=bt709:out_range=tv,format=yuv420p
RGB → YUV 709 (ProRes): scale=out_color_matrix=bt709:out_range=tv,format=yuv422p10le
nieotagowane HD → PNG:  scale=in_color_matrix=bt709
DNxHD + konwersja:      jedno -vf: scale=1920:1080:out_color_matrix=bt709:out_range=tv,format=yuv422p
```
Dwa `-vf` w jednej komendzie: ffmpeg bierze ostatni. Łącz filtry w jednym łańcuchu
(`_rgb_to_yuv709_vf`).

## Gdzie w kodzie (v0.7)

`app/core/color.py` (EXR → display), `app/config.py::ColorConfig` (filtry, tagi, domyślna
przestrzeń), `app/presets/sequence.py` (`RGB_DISPLAY_EXTS`, `_rgb_to_yuv709_vf`, `EVEN_CROP`),
`app/presets/video.py::_decode_vf`, `app/core/probe.py::probe_untagged_hd_yuv`.

## Weryfikacja

Kolor wzorcowy 10,98,204 (różnica 601/709 największa):
```bash
V="venv/bin/python scripts/verify_output.py"
$V fixture /tmp/t/rgb.mov --kind rgbvideo --pattern color --size 1280x720 --frames 2 --no-audio
# … konwersja …
$V sample wynik.mp4 --matrix auto --expect 10,98,204    # zgodnie z tagami
$V check wynik.mp4 --color bt709/bt709/iec61966-2-1/tv
```
Test w repo: `tests/test_runner.py::TestColorMatrixRealFFmpeg`.
