#!/usr/bin/env python3
"""Wspólny front-end CLI dla konwersji FFmpeg.

Używany przez menu kontekstowe Nemo (Linux) i Eksploratora (Windows) oraz do
skryptowania. Receptury pochodzą wyłącznie z presets.py — to samo źródło, co GUI.

Przykłady:
  cli.py video --preset h264 plik1.mov plik2.mov
  cli.py video --preset h264size --target-mb 25 plik.mov
  cli.py image --quality 2 --name render *.png
  cli.py seq   --fps 24 --format h264 klatka_*.png
  cli.py seq   --fps 24 --format h264 --target-mb 45 klatka_*.png
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
                                    scale_pct=a.scale, color=not a.no_color,
                                    colorspace=a.exr_colorspace,
                                    aces_lut=a.aces_lut)
    return _run(jobs)


def cmd_seq(a) -> int:
    # Katalogi jako argumenty → tryb batch: jeden mp4 na folder (+ opcjonalnie
    # miniaturka i proxy). Luźne pliki → dotychczasowy pojedynczy mp4 z sekwencji.
    dirs = [Path(f) for f in a.files if Path(f).is_dir()]
    loose = [f for f in a.files if not Path(f).is_dir()]
    # Miniaturka wymaga mp4 — gdy --no-mp4, ignorujemy --thumb z ostrzeżeniem.
    thumb = a.thumb if (a.thumb and not a.no_mp4) else None
    if a.thumb and a.no_mp4:
        print("--thumb wymaga mp4 (miniaturka = klatka z mp4); ignoruję --thumb.",
              file=sys.stderr)
    size_mode = "size" if a.target_mb else "crf"
    if dirs and loose:
        raise ValueError("Wybierz foldery albo pliki klatek — nie oba typy jednocześnie.")
    if dirs and a.output:
        raise ValueError("--output działa dla klatek; dla folderów użyj --mp4-in-parent.")
    if any(not Path(f).exists() for f in a.files):
        raise ValueError("Brakuje wybranych klatek lub folderów. Sprawdź ścieżki.")
    if dirs:
        jobs = presets.build_seq_jobs_from_folders(
            dirs, fps=a.fps, fmt=a.format, encoder=a.encoder,
            color=not a.no_color, mp4_in_seq=not a.mp4_in_parent,
            audio_path=a.audio, auto_audio=not a.no_audio,
            thumb_width=thumb, make_mp4=not a.no_mp4,
            proxy_variants=(a.proxy or []), proxy_start_frame=a.proxy_start,
            size_mode=size_mode, crf=a.crf,
            target_mb=(a.target_mb or presets.CONFIG.h264size.target_mb_default),
            colorspace=a.exr_colorspace, aces_lut=a.aces_lut)
        return _run(jobs)
    files = _existing(loose)
    output = a.output
    if len(files) == 1 and not a.selected_only:
        from app.core.sequences import detect_sequence
        sequence = detect_sequence(files[0])
        if sequence is not None:
            sequence.require_complete()
            files = list(sequence.frames)
            if output is None:
                folder = files[0].parent.parent if a.mp4_in_parent else files[0].parent
                output = folder / f"{sequence.name}.{presets.SEQ_FORMATS[a.format]['ext']}"
            print(f"Wykryto {len(files)} klatek: {sequence.first}–{sequence.last}")
    return _run([presets.build_seq_job(
        files, fps=a.fps, fmt=a.format, encoder=a.encoder, color=not a.no_color,
        out_path=output, audio_path=a.audio, auto_audio=not a.no_audio,
        make_mp4=not a.no_mp4, proxy_variants=(a.proxy or []),
        proxy_start_frame=a.proxy_start,
        size_mode=size_mode, crf=a.crf,
        target_mb=(a.target_mb or presets.CONFIG.h264size.target_mb_default),
        colorspace=a.exr_colorspace, aces_lut=a.aces_lut)])


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


def cmd_audio_setup(a) -> int:
    from app.audio_separation import main as audio_main
    return audio_main(["--setup"])


def cmd_update(a) -> int:
    from app import __version__
    from app.update import check_for_updates
    log = get_logger()
    _, latest, msg = check_for_updates(__version__)
    print(msg)
    log.info("update check: latest=%s", latest)
    return 0


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
    pi.add_argument("--no-color", action="store_true",
                    help="nie nakładaj OETF dla EXR (linear) — zostaw surowe wartości")
    pi.add_argument("--exr-colorspace", default=None,
                    choices=["aces2065", "lin709"],
                    help="przestrzeń EXR: aces2065 (domyślnie) lub lin709")
    pi.add_argument("--aces-lut", default=None,
                    help="własny LUT ACES (.cube) zamiast wbudowanego")
    pi.add_argument("files", nargs="+")
    pi.set_defaults(func=cmd_image)

    ps = sub.add_parser("seq", help="sekwencja obrazów → wideo / proxy")
    ps.add_argument("--fps", type=float, default=presets.CONFIG.seq.default_fps)
    audio = ps.add_mutually_exclusive_group()
    audio.add_argument("--audio", type=Path, help="plik audio zamiast automatycznego dopasowania")
    audio.add_argument("--no-audio", action="store_true", help="utwórz film bez dźwięku")
    ps.add_argument("--selected-only", action="store_true", help="nie szukaj pozostałych klatek pojedynczego pliku")
    ps.add_argument("--output", type=Path, help="nazwa pliku wynikowego (tryb klatek)")
    ps.add_argument("--format", default="h264", choices=[f.value for f in presets.SeqFormat])
    ps.add_argument("--encoder", default="cpu", choices=[e.value for e in presets.Encoder],
                    help="enkoder dla h264/h265: cpu / nvenc / qsv / amf")
    ps.add_argument("--target-mb", type=float, default=None,
                    help="dla H.264: docelowy rozmiar pliku w MB (CPU 2-pass); zamiast CRF")
    ps.add_argument("--crf", type=int, default=presets.CONFIG.h264size.crf_default,
                    help="dla H.264 w trybie CRF (gdy nie podano --target-mb)")
    ps.add_argument("--no-color", action="store_true",
                    help="dla sekwencji EXR nie nakładaj OETF sRGB (linear→display)")
    ps.add_argument("--mp4-in-parent", action="store_true",
                    help="tryb folderów: zapisz mp4 w folderze nadrzędnym (zamiast w folderze sekwencji)")
    ps.add_argument("--thumb", type=int, default=0,
                    help="tryb folderów: szerokość miniaturki w px (0 = wyłączone); "
                         "klatka z połowy mp4, zapis w folderze nadrzędnym")
    ps.add_argument("--no-mp4", action="store_true",
                    help="pomiń mp4 — generuj tylko proxy (miniaturka wymaga mp4)")
    ps.add_argument("--proxy", action="append", default=None,
                    choices=[v.key for v in presets.CONFIG.seq.proxy_variants],
                    help="generuj sekwencję proxy (klatki numerowane od --proxy-start); "
                         "powtarzaj per wariant: jpg / png16 / half")
    ps.add_argument("--proxy-start", type=int,
                    default=presets.CONFIG.seq.proxy_start_frame,
                    help="początkowy numer klatki proxy (standard VFX: 1001)")
    ps.add_argument("--exr-colorspace", default=None,
                    choices=["aces2065", "lin709"],
                    help="przestrzeń EXR: aces2065 (domyślnie) lub lin709")
    ps.add_argument("--aces-lut", default=None,
                    help="własny LUT ACES (.cube) zamiast wbudowanego — np. wyeksportowany "
                         "z Nuke 'sRGB Display' (ACES 2.0); wejście AP0 linear -> sRGB display")
    ps.add_argument("files", nargs="+")
    ps.set_defaults(func=cmd_seq)

    pg = sub.add_parser("gui", help="otwórz GUI z wczytanymi plikami")
    pg.add_argument("files", nargs="*")
    pg.set_defaults(func=cmd_gui)

    pa = sub.add_parser("audio-setup", help="zainstaluj lokalną separację głosu, muzyki i SFX")
    pa.set_defaults(func=cmd_audio_setup)

    pu = sub.add_parser("update", help="sprawdź dostępność nowej wersji")
    pu.set_defaults(func=cmd_update)

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
    try:
        return args.func(args)
    except (ValueError, OSError) as exc:
        print(f"Błąd: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
