#!/usr/bin/env python3
"""Weryfikacja wyniku FFmpeg przez ffprobe i fixture'y z lavfi (tylko stdlib).

Komendy:
  probe   PLIK                 raport JSON (klatki, długość, kodek, pix_fmt, tagi koloru, audio)
  check   PLIK [oczekiwania]   porównanie z oczekiwaniami; kod 1 przy niezgodności
  sample  PLIK                 kolor środka kadru (R G B) po dekodowaniu wskazaną macierzą
  fixture WYJŚCIE --kind …     plik testowy z lavfi (wideo, wideo RGB, audio, sekwencja klatek)

Przykłady:
  scripts/verify_output.py fixture /tmp/t/src.mp4 --kind video --size 1281x721 --fps 24000/1001 --duration 2
  scripts/verify_output.py check out.mp4 --frames 48 --codec h264 --pix-fmt yuv420p \
      --fps 24000/1001 --color bt709/bt709/-/tv --audio 1 --audio-duration 2.002
  scripts/verify_output.py sample out.mp4 --matrix bt709 --expect 10,98,204

Narzędzia: zmienne FFMPEG / FFPROBE albo ffmpeg / ffprobe z PATH. Fixture'y twórz poza repo.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = os.environ.get("FFPROBE") or shutil.which("ffprobe") or "ffprobe"
COLOR_KEYS = ("color_space", "color_primaries", "color_transfer", "color_range")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _float(value: Any) -> float | None:
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def probe(path: Path) -> dict[str, Any]:
    """Raport o pliku. Klatki liczone przez -count_packets (szybko, bez dekodowania)."""
    result = _run([FFPROBE, "-v", "error", "-count_packets", "-show_streams", "-show_format",
                   "-of", "json", str(path)])
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe nie odczytał {path}: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    fmt = data.get("format", {})
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    report: dict[str, Any] = {
        "file": str(path),
        "bytes": int(fmt.get("size") or path.stat().st_size),
        "format": fmt.get("format_name"),
        "format_duration": _float(fmt.get("duration")),
        "video": None,
        "audio": [],
    }
    if video:
        report["video"] = {
            "codec": video.get("codec_name"),
            "profile": video.get("profile"),
            "size": f"{video.get('width')}x{video.get('height')}",
            "pix_fmt": video.get("pix_fmt"),
            "fps": video.get("r_frame_rate"),
            "avg_fps": video.get("avg_frame_rate"),
            "frames": int(video["nb_read_packets"]) if video.get("nb_read_packets") else None,
            "duration": _float(video.get("duration")) or report["format_duration"],
            "color": {key: video.get(key, "unknown") for key in COLOR_KEYS},
        }
    for stream in audio:
        report["audio"].append({
            "codec": stream.get("codec_name"),
            "sample_rate": int(stream.get("sample_rate") or 0),
            "channels": stream.get("channels"),
            "duration": _float(stream.get("duration")) or report["format_duration"],
        })
    return report


def check(report: dict[str, Any], args: argparse.Namespace) -> list[tuple[str, str, str, bool]]:
    """Lista (nazwa, oczekiwane, faktyczne, ok) dla podanych oczekiwań."""
    rows: list[tuple[str, str, str, bool]] = []
    video = report["video"] or {}
    audio = report["audio"]
    tol = args.tolerance

    def add(name: str, expected: Any, actual: Any, ok: bool) -> None:
        rows.append((name, str(expected), str(actual), ok))

    if args.frames is not None:
        add("klatki", args.frames, video.get("frames"), video.get("frames") == args.frames)
    if args.duration is not None:
        actual = video.get("duration")
        add("długość wideo [s]", f"{args.duration}±{tol}", actual,
            actual is not None and abs(actual - args.duration) <= tol)
    if args.codec:
        add("kodek", args.codec, video.get("codec"), video.get("codec") == args.codec)
    if args.pix_fmt:
        add("pix_fmt", args.pix_fmt, video.get("pix_fmt"), video.get("pix_fmt") == args.pix_fmt)
    if args.size:
        add("wymiar", args.size, video.get("size"), video.get("size") == args.size)
    if args.fps:
        actual = video.get("fps") or "0/1"
        add("r_frame_rate", args.fps, actual, Fraction(actual) == Fraction(args.fps))
    if args.color:
        expected = args.color.split("/")
        if len(expected) != 4:
            raise SystemExit("--color: podaj space/primaries/transfer/range, '-' pomija część")
        actual_color = video.get("color", {})
        for key, want in zip(COLOR_KEYS, expected):
            if want != "-":
                got = actual_color.get(key, "unknown")
                add(key, want, got, got == want)
    if args.audio is not None:
        add("ścieżki audio", args.audio, len(audio), len(audio) == args.audio)
    if args.audio_codec:
        got = audio[0]["codec"] if audio else None
        add("kodek audio", args.audio_codec, got, got == args.audio_codec)
    if args.audio_rate:
        got = audio[0]["sample_rate"] if audio else None
        add("próbkowanie audio", args.audio_rate, got, got == args.audio_rate)
    if args.audio_duration is not None:
        got = audio[0]["duration"] if audio else None
        add("długość audio [s]", f"{args.audio_duration}±{tol}", got,
            got is not None and abs(got - args.audio_duration) <= tol)
    megabytes = report["bytes"] / 1e6
    if args.max_mb is not None:
        add("rozmiar ≤ [MB]", args.max_mb, f"{megabytes:.3f}", megabytes <= args.max_mb)
    if args.min_mb is not None:
        add("rozmiar ≥ [MB]", args.min_mb, f"{megabytes:.3f}", megabytes >= args.min_mb)
    return rows


def sample(path: Path, matrix: str, rng: str) -> tuple[int, int, int]:
    """Kolor środkowych 2×2 px po dekodowaniu do RGB (jak odtwarzacz z daną macierzą)."""
    parts = ["scale=out_range=full:flags=accurate_rnd+full_chroma_int"]
    if matrix != "auto":
        parts[0] += f":in_color_matrix={matrix}"
    if rng != "auto":
        parts[0] += f":in_range={rng}"
    vf = f"{parts[0]},crop=2:2,format=rgb24"
    result = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-frames:v", "1", "-vf", vf,
                             "-f", "rawvideo", "-"], capture_output=True)
    if result.returncode != 0 or len(result.stdout) < 3:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip() or "brak klatki")
    r, g, b = result.stdout[:3]
    return r, g, b


def _source_filter(pattern: str, size: str, fps: str, duration: float, color: str, pix: str) -> str:
    """Źródło lavfi w RGB (dokładny kolor), także o nieparzystych wymiarach."""
    width, height = (int(v) for v in size.lower().split("x"))
    even = (width + width % 2, height + height % 2)  # testsrc2/color zaokrąglają do parzystych
    if pattern == "color":
        src = f"color=c={color}:s={even[0]}x{even[1]}:r={fps}:d={duration}"
    else:
        src = f"testsrc2=s={even[0]}x{even[1]}:r={fps}:d={duration}"
    src += f",format={pix}"  # bez tego color/testsrc2 przechodzą przez YUV i tracą dokładność
    if pattern == "noise":
        src += ",noise=alls=20:allf=t"
    if (width, height) != even:
        src += f",scale={width}:{height}"
    return src


def fixture(out: Path, args: argparse.Namespace) -> list[Path]:
    """Utwórz plik testowy. Zwraca utworzone pliki. Nie nadpisuje bez --overwrite."""
    target = out / f"{args.name}.{args.start:04d}.{args.frame_format}" if args.kind == "frames" else out
    if target.exists() and not args.overwrite:
        raise RuntimeError(f"{target} już istnieje (użyj --overwrite)")
    out.parent.mkdir(parents=True, exist_ok=True)
    duration = args.duration
    limit: list[str] = []
    if args.frames:  # dokładna liczba klatek; lavfi z samym d= zaokrągla w dół (2 s @ 23,976 = 47)
        duration = float(args.frames / Fraction(args.fps))
        limit = ["-frames:v", str(args.frames)]
    base = [FFMPEG, "-v", "error", "-y"]
    audio_src = f"sine=f=440:r=48000:d={duration:.6f}"
    if args.kind == "audio":
        _checked([*base, "-f", "lavfi", "-i", audio_src, str(out)])
        return [out]
    pix = "gbrpf32le" if args.kind == "frames" and args.frame_format == "exr" else "rgb24"
    src = _source_filter(args.pattern, args.size, args.fps, duration + 1 if limit else duration, args.color, pix)
    if args.kind == "frames":
        out.mkdir(parents=True, exist_ok=True)
        pattern = out / f"{args.name}.%04d.{args.frame_format}"
        extra = {"exr": ["-c:v", "exr"], "jpg": ["-pix_fmt", "yuvj420p", "-q:v", "2"]}.get(args.frame_format, [])
        _checked([*base, "-f", "lavfi", "-i", src, *limit, *extra,
                  "-start_number", str(args.start), str(pattern)])
        return sorted(out.glob(f"{args.name}.*.{args.frame_format}"))
    cmd = [*base, "-f", "lavfi", "-i", src]
    if args.audio:
        cmd += ["-f", "lavfi", "-i", audio_src]
    cmd += limit
    if args.kind == "rgbvideo":
        cmd += ["-c:v", "png", "-pix_fmt", "rgb24"]
    else:
        odd = any(int(v) % 2 for v in args.size.lower().split("x"))
        pix = "yuv444p" if odd else "yuv420p"
        cmd += ["-vf", f"scale=out_color_matrix=bt709:out_range=tv,format={pix}",
                "-c:v", "libx264", "-crf", "16", "-preset", "veryfast"]
        if args.tag_709:
            cmd += ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                    "-color_range", "tv"]
    if args.audio:
        cmd += ["-c:a", "pcm_s16le" if out.suffix.lower() == ".mov" else "aac", "-shortest"]
    _checked([*cmd, str(out)])
    return [out]


def _checked(cmd: list[str]) -> None:
    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg: {result.stderr.strip()}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("probe", help="raport JSON")
    p.add_argument("file", type=Path)

    c = sub.add_parser("check", help="porównaj z oczekiwaniami")
    c.add_argument("file", type=Path)
    c.add_argument("--frames", type=int)
    c.add_argument("--duration", type=float, help="długość ścieżki wideo w sekundach")
    c.add_argument("--tolerance", type=float, default=0.05, help="tolerancja długości [s]")
    c.add_argument("--codec")
    c.add_argument("--pix-fmt")
    c.add_argument("--size", help="WxH")
    c.add_argument("--fps", help="r_frame_rate, np. 24000/1001")
    c.add_argument("--color", help="space/primaries/transfer/range, '-' pomija; brak tagu = unknown")
    c.add_argument("--audio", type=int, help="liczba ścieżek audio")
    c.add_argument("--audio-codec")
    c.add_argument("--audio-rate", type=int)
    c.add_argument("--audio-duration", type=float)
    c.add_argument("--max-mb", type=float, help="maks. rozmiar pliku, 1 MB = 10^6 B")
    c.add_argument("--min-mb", type=float)
    c.add_argument("--json", action="store_true", help="wynik jako JSON")

    s = sub.add_parser("sample", help="kolor środka kadru")
    s.add_argument("file", type=Path)
    s.add_argument("--matrix", default="auto", choices=["auto", "bt709", "bt601", "bt2020"])
    s.add_argument("--range", dest="rng", default="auto", choices=["auto", "tv", "pc"])
    s.add_argument("--expect", help="R,G,B; kod 1 gdy różnica > --tolerance")
    s.add_argument("--tolerance", type=int, default=3)

    f = sub.add_parser("fixture", help="plik testowy z lavfi")
    f.add_argument("out", type=Path, help="plik albo folder (dla --kind frames)")
    f.add_argument("--kind", required=True, choices=["video", "rgbvideo", "audio", "frames"])
    f.add_argument("--pattern", default="testsrc2", choices=["testsrc2", "color", "noise"])
    f.add_argument("--color", default="0x0A62CC", help="kolor dla --pattern color")
    f.add_argument("--size", default="320x180", help="WxH, także nieparzyste")
    f.add_argument("--fps", default="24", help="np. 24, 25, 24000/1001")
    f.add_argument("--duration", type=float, default=1.0)
    f.add_argument("--frames", type=int, help="dokładna liczba klatek (zamiast --duration)")
    f.add_argument("--audio", action=argparse.BooleanOptionalAction, default=True)
    f.add_argument("--tag-709", action="store_true", help="zapisz tagi bt709 (domyślnie wideo bez tagów)")
    f.add_argument("--frame-format", default="png", choices=["png", "jpg", "tif", "exr"])
    f.add_argument("--name", default="shot", help="prefiks klatek")
    f.add_argument("--start", type=int, default=1001, help="numer pierwszej klatki")
    f.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "probe":
            print(json.dumps(probe(args.file), indent=2, ensure_ascii=False))
            return 0
        if args.command == "check":
            rows = check(probe(args.file), args)
            if not rows:
                raise SystemExit("check: podaj co najmniej jedno oczekiwanie")
            if args.json:
                print(json.dumps([dict(zip(("check", "expected", "actual", "ok"), r)) for r in rows],
                                 ensure_ascii=False, indent=2))
            else:
                for name, want, got, ok in rows:
                    print(f"{'OK  ' if ok else 'BŁĄD'}  {name}: oczekiwane {want}, jest {got}")
            return 0 if all(r[3] for r in rows) else 1
        if args.command == "sample":
            rgb = sample(args.file, args.matrix, args.rng)
            print(*rgb)
            if args.expect:
                expected = [int(v) for v in args.expect.split(",")]
                return 0 if all(abs(a - b) <= args.tolerance for a, b in zip(rgb, expected)) else 1
            return 0
        created = fixture(args.out, args)
        print("\n".join(str(p) for p in created) if len(created) < 5
              else f"{len(created)} plików: {created[0].name} … {created[-1].name}")
        return 0
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"Błąd: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
