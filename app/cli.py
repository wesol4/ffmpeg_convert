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
import sys
from pathlib import Path

# Działaj zarówno jako moduł (python -m app.cli), jak i skrypt
# (python app/cli.py) — bootstrap dodaje rodzica app/ do sys.path, by
# absolutne importy `from app import …` działały w obu trybach.
_PARENT = Path(__file__).resolve().parents[1]
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))
from app import presets, runner  # noqa: E402
from app.log import get_logger, setup_logging  # noqa: E402


def _existing(files) -> list:
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
        crf=a.crf, target_mb=(a.target_mb or presets.CONFIG.h264size.target_mb_default),
        frames_format=a.frames_format, frames_with_wav=not a.no_wav,
        encoder=a.encoder,
    )
    return _run(jobs)


def cmd_image(a) -> int:
    files = _existing(a.files)
    keep = a.quality == "keep"
    quality = None if keep else int(a.quality)
    jobs = presets.build_image_jobs(files, quality=quality, keep=keep,
                                    newname=a.name, subdir=not a.beside,
                                    scale_pct=a.scale)
    return _run(jobs)


def cmd_seq(a) -> int:
    files = _existing(a.files)
    return _run([presets.build_seq_job(files, fps=a.fps, fmt=a.format, encoder=a.encoder)])


def cmd_split(a) -> int:
    files = _existing(a.files)
    # Domyślnie: podfolder SplitGrid tylko przy wielu plikach (jak dawniej);
    # --beside wymusza zapis obok oryginału.
    subdir = (not a.beside) and len(files) > 1
    return _run(presets.build_split_jobs(files, cols=a.cols, rows=a.rows,
                                         subdir=subdir))


def cmd_flipbook(a) -> int:
    files = _existing(a.files)
    tile = None
    if a.tile:
        try:
            w, h = a.tile.lower().split("x")
            tile = (int(w), int(h))
        except ValueError:
            print(f"Niepoprawny --tile (oczekiwano WxH, np. 128x128): {a.tile}",
                  file=sys.stderr)
            return 1
    return _run([presets.build_flipbook_job(files, cols=a.cols, rows=a.rows,
                                            tile=tile)])


def cmd_gui(a) -> int:
    # Przekaż pliki do GUI (te same receptury, pełna kontrola opcji).
    from app import gui
    return gui.main(a.files)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ffmpeg-convert", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("video", help="konwersja wideo")
    pv.add_argument("--preset", required=True,
                    choices=[p.value for p in presets.VideoPreset])
    pv.add_argument("--crf", type=int, default=presets.CONFIG.h264size.crf_default,
                    help="CRF dla presetu h264size (18–32)")
    pv.add_argument("--target-mb", type=float, default=None,
                    help="docelowy rozmiar MB dla h264size (2 przebiegi)")
    pv.add_argument("--frames-format", default="png", choices=["png", "jpg", "exr"])
    pv.add_argument("--no-wav", action="store_true", help="nie eksportuj WAV przy 'frames'")
    pv.add_argument("--encoder", default="cpu", choices=[e.value for e in presets.Encoder],
                    help="enkoder wideo: cpu (domyślnie) / nvenc / qsv / amf (dla H.264/H.265)")
    pv.add_argument("files", nargs="+")
    pv.set_defaults(func=cmd_video)

    pi = sub.add_parser("image", help="kompresja / zmiana nazwy obrazów")
    pi.add_argument("--quality", default="2", choices=["1", "2", "5", "10", "keep"])
    pi.add_argument("--name", default="", help="nowa nazwa bazowa (numeracja); puste = oryginalne")
    pi.add_argument("--beside", action="store_true", help="zapisz obok oryginału (zamiast podfolderu)")
    pi.add_argument("--scale", type=float, default=None,
                    help="skaluj obrazy procentowo, np. 50 = połowa wymiarów (100 = bez zmian)")
    pi.add_argument("files", nargs="+")
    pi.set_defaults(func=cmd_image)

    ps = sub.add_parser("seq", help="sekwencja obrazów → wideo")
    ps.add_argument("--fps", type=int, default=presets.CONFIG.seq.default_fps)
    ps.add_argument("--format", default="h264", choices=[f.value for f in presets.SeqFormat])
    ps.add_argument("--encoder", default="cpu", choices=[e.value for e in presets.Encoder],
                    help="enkoder dla h264/h265: cpu / nvenc / qsv / amf")
    ps.add_argument("files", nargs="+")
    ps.set_defaults(func=cmd_seq)

    pg = sub.add_parser("gui", help="otwórz GUI z wczytanymi plikami")
    pg.add_argument("files", nargs="*")
    pg.set_defaults(func=cmd_gui)

    pspl = sub.add_parser("split", help="podział obrazu na siatkę X×Y")
    pspl.add_argument("--cols", type=int, required=True, help="liczba części w poziomie")
    pspl.add_argument("--rows", type=int, required=True, help="liczba części w pionie")
    pspl.add_argument("--beside", action="store_true", help="zapisz obok oryginału (zamiast podfolderu)")
    pspl.add_argument("files", nargs="+")
    pspl.set_defaults(func=cmd_split)

    pfl = sub.add_parser("flipbook", help="spritesheet z klatek (concat + tile)")
    pfl.add_argument("--cols", type=int, required=True, help="kolumny siatki")
    pfl.add_argument("--rows", type=int, required=True, help="wiersze siatki")
    pfl.add_argument("--tile", default=None, help="rozdzielczość kafelka WxH (np. 128x128)")
    pfl.add_argument("files", nargs="+")
    pfl.set_defaults(func=cmd_flipbook)

    return p


def main(argv=None) -> int:
    setup_logging()
    log = get_logger()
    args = build_parser().parse_args(argv)
    log.info("CLI: %s %s", args.cmd, " ".join(getattr(args, "files", []) or []))
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
