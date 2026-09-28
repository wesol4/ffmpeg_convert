"""Optional, isolated CPU runtime for Bandit v2 dialogue/music/effects separation.

No media is uploaded. The pinned ELUATE private streaming API is intentional:
its public API does not export all three stems. Verify the checkpoint before
ELUATE loads it (torch checkpoint contains pickle data).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import venv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.ffmpeg import FFMPEG, FFPROBE  # noqa: E402
from app.core.process import subprocess_options  # noqa: E402

RUNTIME = ROOT / ".audio-runtime"
MODEL_URL = "https://zenodo.org/records/12701995/files/checkpoint-multi.ckpt?download=1"
MODEL_SHA256 = "abcfccf65446752a057f4a302c941479a54b7560ebf8d7bca039d2ea98e64cfc"
RUNTIME_VERSION = "eluate-0.0.3-torch-2.6.0-cpu-v1"


def runtime_python() -> Path:
    return RUNTIME / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def verified_checkpoint(path: Path) -> bool:
    if not path.is_file():
        return False
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() == MODEL_SHA256


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, stdin=subprocess.DEVNULL, stdout=sys.stderr, **subprocess_options())


def ensure_runtime(seed_checkpoint: Path | None = None) -> None:
    """Install once; interrupted installs are retried, concurrent installs fail clearly."""
    RUNTIME.mkdir(parents=True, exist_ok=True)
    checkpoint = RUNTIME / "checkpoint-multi.ckpt"
    marker = RUNTIME / "ready.txt"
    if (runtime_python().is_file() and marker.is_file()
            and marker.read_text() == RUNTIME_VERSION and verified_checkpoint(checkpoint)):
        return
    lock = RUNTIME / "install.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise RuntimeError(f"Instalacja audio już trwa. Po przerwaniu instalacji usuń {lock} i ponów.") from None
    os.close(fd)
    try:
        print("Przygotowanie lokalnej separacji audio (jednorazowe pobieranie bibliotek i modelu)…",
              file=sys.stderr, flush=True)
        if not marker.is_file() or marker.read_text() != RUNTIME_VERSION or not runtime_python().is_file():
            venv.EnvBuilder(with_pip=True).create(RUNTIME / "venv")
            python = str(runtime_python())
            run([python, "-m", "pip", "install", "--no-cache-dir", "torch==2.6.0", "torchaudio==2.6.0",
                 "--index-url", "https://download.pytorch.org/whl/cpu"])
            run([python, "-m", "pip", "install", "--no-cache-dir", "eluate==0.0.3"])
        if not verified_checkpoint(checkpoint):
            partial = RUNTIME / "checkpoint.download"
            try:
                if seed_checkpoint is not None:
                    shutil.copyfile(seed_checkpoint, partial)
                else:
                    with urllib.request.urlopen(MODEL_URL, timeout=120) as response, partial.open("wb") as dest:
                        shutil.copyfileobj(response, dest)
                if not verified_checkpoint(partial):
                    raise RuntimeError("Niepoprawna suma kontrolna modelu. Ponów instalację audio.")
                partial.replace(checkpoint)
            finally:
                partial.unlink(missing_ok=True)
        marker.write_text(RUNTIME_VERSION)
    finally:
        lock.unlink(missing_ok=True)


def inspect_source(source: Path) -> bool:
    """Reject silent/missing inputs before installing anything; return video presence."""
    if not source.is_file():
        raise ValueError(f"Nie ma pliku: {source}")
    result = subprocess.run([FFPROBE, "-v", "error", "-show_streams", "-of", "json", str(source)],
                            check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
                            **subprocess_options())
    streams = json.loads(result.stdout).get("streams", [])
    if not any(s.get("codec_type") == "audio" for s in streams):
        raise ValueError("Plik nie ma ścieżki audio do separacji.")
    return any(s.get("codec_type") == "video" for s in streams)


def reserve_output(source: Path) -> Path:
    for index in range(1, 10000):
        suffix = "" if index == 1 else f"_{index:03d}"
        folder = source.parent / f"{source.stem}_AUDIO{suffix}"
        try:
            folder.mkdir()
            return folder
        except FileExistsError:
            continue
    raise RuntimeError("Brak wolnej nazwy katalogu wynikowego.")


def progress(fraction: float) -> None:
    print(f"progress_fraction={fraction:.6f}", file=sys.stderr, flush=True)


def separate(source: Path) -> Path:
    has_video = inspect_source(source)
    checkpoint = RUNTIME / "checkpoint-multi.ckpt"
    if not verified_checkpoint(checkpoint):
        raise RuntimeError("Brak zweryfikowanego modelu; uruchom audio-setup.")
    # Lazy imports keep optional ML dependencies out of GUI, CLI and normal conversions.
    torch = importlib.import_module("torch")
    sf = importlib.import_module("soundfile")
    np = importlib.import_module("numpy")
    yaml = importlib.import_module("yaml")
    eluate = importlib.import_module("eluate")
    separator_type = importlib.import_module("eluate.core.separator").BanditSeparator
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    torch.set_num_interop_threads(2)
    output = reserve_output(source)
    start = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix=".work-", dir=output) as temp:
            work = Path(temp)
            original = work / "original.wav"
            run([FFMPEG, "-v", "error", "-nostdin", "-n", "-i", str(source), "-map", "0:a:0",
                 "-vn", "-ar", "48000", "-ac", "2", "-c:a", "pcm_f32le", str(original)])
            progress(0.05)
            if eluate.__file__ is None:
                raise RuntimeError("Niepełna instalacja ELUATE; ponów instalację audio.")
            config = yaml.safe_load((Path(eluate.__file__).parent / "configs/bandit_v2.yaml").read_text())
            config["inference"]["batch_size"] = 1
            config_path = work / "config.yaml"
            config_path.write_text(yaml.safe_dump(config))
            separator = separator_type(config_path=config_path, checkpoint_path=checkpoint,
                                       device=torch.device("cpu"))
            mix = separator._load_audio(original)
            paths, writers = separator._open_stem_writers(work, mix.shape[0])
            try:
                separator._demix_streaming(mix, writers, lambda p: progress(0.05 + 0.8 * p))
            finally:
                for writer in writers.values():
                    writer.close()
            # Process WAVs in blocks to avoid extra full-length arrays in memory.
            for name, path in paths.items():
                with sf.SoundFile(path) as reader, sf.SoundFile(
                        output / f"{name}.wav", "w", samplerate=reader.samplerate,
                        channels=reader.channels, subtype="PCM_24") as writer:
                    for block in reader.blocks(blocksize=65536, dtype="float32", always_2d=True):
                        writer.write(np.clip(block, -1.0, 1.0))
            peak = 0.0
            with sf.SoundFile(paths["music"]) as music, sf.SoundFile(paths["sfx"]) as sfx:
                for block in music.blocks(blocksize=65536, dtype="float32", always_2d=True):
                    bed = block + sfx.read(len(block), dtype="float32", always_2d=True)
                    peak = max(peak, float(np.max(np.abs(bed))))
                gain = min(1.0, 0.98 / max(peak, 1e-9))
                music.seek(0)
                sfx.seek(0)
                with sf.SoundFile(output / "background_no_dialogue.wav", "w", samplerate=music.samplerate,
                                  channels=music.channels, subtype="PCM_24") as writer:
                    for block in music.blocks(blocksize=65536, dtype="float32", always_2d=True):
                        writer.write((block + sfx.read(len(block), dtype="float32", always_2d=True)) * gain)
            progress(0.95)
            if has_video:
                # Matroska supports the source codecs without recompressing the picture.
                run([FFMPEG, "-v", "error", "-nostdin", "-n", "-i", str(source), "-i",
                     str(output / "background_no_dialogue.wav"), "-map", "0:v:0", "-map", "1:a:0",
                     "-c:v", "copy", "-c:a", "pcm_s24le", "-shortest", str(output / "video_without_dialogue.mkv")])
        (output / "report.json").write_text(json.dumps({
            "source": str(source), "model": "Bandit v2 multilingual", "software": "eluate 0.0.3",
            "checkpoint_sha256": MODEL_SHA256, "device": "cpu", "credits_used": 0,
            "processing_seconds": round(time.monotonic() - start, 2), "background_gain": gain,
            "input_audio_stream": 0,
        }, indent=2), encoding="utf-8")
    except BaseException:
        # Only our exclusively created directory is removed; previous runs stay intact.
        shutil.rmtree(output)
        raise
    print(f"Gotowe: {output}", file=sys.stderr, flush=True)
    progress(1.0)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, nargs="?")
    parser.add_argument("--setup", action="store_true")
    parser.add_argument("--checkpoint", type=Path, help="lokalna kopia modelu przy instalacji")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.setup:
            ensure_runtime(args.checkpoint)
            return 0
        if args.source is None:
            parser.error("podaj plik źródłowy lub --setup")
        source = args.source.resolve()
        if args.worker:
            separate(source)
        else:
            inspect_source(source)
            ensure_runtime()
            run([str(runtime_python()), str(Path(__file__).resolve()), "--worker", str(source)])
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        print(f"Błąd separacji audio: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
