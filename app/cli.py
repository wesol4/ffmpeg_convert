#!/usr/bin/env python3
"""Wspólny front-end CLI dla konwersji FFmpeg.

Używany przez menu kontekstowe Nemo (Linux) i Eksploratora (Windows) oraz do
skryptowania. Receptury pochodzą wyłącznie z presets.py — to samo źródło, co GUI.

Przykłady:
  cli.py video --preset h264 plik1.mov plik2.mov
  cli.py video --preset h264size --target-mb 25 plik.mov
  cli.py image --quality 2 --name render *.png
  cli.py seq   --fps 24 --format h264 klatka_*.png
  cli.py gui   plik.mov              # otwórz GUI z wczytanymi plikami
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Działaj zarówno jako moduł (python -m app.cli), jak i skrypt (python cli.py).
if __package__:
    from . import presets, runner
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import presets
    import runner


def _existing(files):
    out = [Path(f) for f in files if Path(f).is_file()]
    for f in files:
        if not Path(f).is_file():
            print(f"Pomijam (nie istnieje): {f}", file=sys.stderr)
    return out


def _run(jobs) -> int:
    if not jobs:
        print("Brak zadań do wykonania (sprawdź pliki / ustawienia).", file=sys.stderr)
        return 1
    ok = runner.run_jobs(jobs, on_log=print,
                         on_progress=lambda c, t: print(f"[{c}/{t}]"))
    print(f"=== Gotowe: {ok}/{len(jobs)} ===")
    return 0 if ok == len(jobs) else 2


def cmd_video(a) -> int:
    files = _existing(a.files)
    jobs = presets.build_video_jobs(
        a.preset, files, size_mode=("size" if a.target_mb else "crf"),
        crf=a.crf, target_mb=(a.target_mb or 25),
        frames_format=a.frames_format, frames_with_wav=not a.no_wav,
    )
    return _run(jobs)


def cmd_image(a) -> int:
    files = _existing(a.files)
    keep = a.quality == "keep"
    quality = None if keep else int(a.quality)
    jobs = presets.build_image_jobs(files, quality=quality, keep=keep,
                                    newname=a.name, subdir=not a.beside)
    return _run(jobs)


def cmd_seq(a) -> int:
    files = _existing(a.files)
    return _run([presets.build_seq_job(files, fps=a.fps, fmt=a.format)])


def cmd_gui(a) -> int:
    # Przekaż pliki do GUI (te same receptury, pełna kontrola opcji).
    if __package__:
        from . import gui
    else:
        import gui
    return gui.main(a.files)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ffmpeg-convert", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("video", help="konwersja wideo")
    pv.add_argument("--preset", required=True,
                    choices=[pid for pid, _ in presets.VIDEO_PRESETS])
    pv.add_argument("--crf", type=int, default=23, help="CRF dla presetu h264size (18–32)")
    pv.add_argument("--target-mb", type=float, default=None,
                    help="docelowy rozmiar MB dla h264size (2 przebiegi)")
    pv.add_argument("--frames-format", default="png", choices=["png", "jpg", "exr"])
    pv.add_argument("--no-wav", action="store_true", help="nie eksportuj WAV przy 'frames'")
    pv.add_argument("files", nargs="+")
    pv.set_defaults(func=cmd_video)

    pi = sub.add_parser("image", help="kompresja / zmiana nazwy obrazów")
    pi.add_argument("--quality", default="2", choices=["1", "2", "5", "10", "keep"])
    pi.add_argument("--name", default="", help="nowa nazwa bazowa (numeracja); puste = oryginalne")
    pi.add_argument("--beside", action="store_true", help="zapisz obok oryginału (zamiast podfolderu)")
    pi.add_argument("files", nargs="+")
    pi.set_defaults(func=cmd_image)

    ps = sub.add_parser("seq", help="sekwencja obrazów → wideo")
    ps.add_argument("--fps", type=int, default=24)
    ps.add_argument("--format", default="h264", choices=list(presets.SEQ_FORMATS))
    ps.add_argument("files", nargs="+")
    ps.set_defaults(func=cmd_seq)

    pg = sub.add_parser("gui", help="otwórz GUI z wczytanymi plikami")
    pg.add_argument("files", nargs="*")
    pg.set_defaults(func=cmd_gui)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
