"""Fast integration boundary checks, without downloading the optional model."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from app import audio_separation as audio, presets, runner
from app.cli import build_parser


class AudioSeparationTests(unittest.TestCase):
    def test_cli_and_preset_share_worker_without_importing_ml(self):
        args = build_parser().parse_args(["video", "--preset", "audio_separate", "film with spaces.mp4"])
        job, = presets.build_video_jobs(args.preset, args.files)
        self.assertEqual(job.cmds[0][-1], str(Path(args.files[0]).resolve()))
        self.assertEqual(Path(job.cmds[0][1]).name, "audio_separation.py")
        self.assertIsNone(job.mkdir)
        self.assertNotIn("torch", sys.modules)

    def test_repeated_runs_preserve_previous_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "movie.mp4"
            first = audio.reserve_output(source)
            sentinel = first / "sfx.wav"
            sentinel.write_bytes(b"original result")
            second = audio.reserve_output(source)
            self.assertEqual(second.name, "movie_AUDIO_002")
            self.assertEqual(sentinel.read_bytes(), b"original result")

    def test_checksum_rejects_missing_or_tampered_model(self):
        with tempfile.TemporaryDirectory() as temp:
            model = Path(temp) / "model"
            self.assertFalse(audio.verified_checkpoint(model))
            model.write_bytes(b"good")
            with patch.object(audio, "MODEL_SHA256", hashlib.sha256(b"good").hexdigest()):
                self.assertTrue(audio.verified_checkpoint(model))
                model.write_bytes(b"tampered")
                self.assertFalse(audio.verified_checkpoint(model))

    def test_silent_input_does_not_install_or_create_output(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "silent.mp4"
            source.touch()
            response = subprocess.CompletedProcess([], 0, stdout=json.dumps({
                "streams": [{"codec_type": "video"}]}))
            with patch.object(audio.subprocess, "run", return_value=response), \
                    patch.object(audio, "ensure_runtime") as install:
                self.assertEqual(audio.main([str(source)]), 1)
                install.assert_not_called()
            self.assertEqual(list(Path(temp).iterdir()), [source])

    def test_failed_download_does_not_publish_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp) / "runtime"
            runtime.mkdir()
            (runtime / "ready.txt").write_text(audio.RUNTIME_VERSION)
            python = runtime / "python"
            python.touch()
            bad = Path(temp) / "bad.ckpt"
            bad.write_bytes(b"untrusted")
            with patch.object(audio, "RUNTIME", runtime), patch.object(audio, "runtime_python", return_value=python):
                with self.assertRaisesRegex(RuntimeError, "suma kontrolna"):
                    audio.ensure_runtime(bad)
            self.assertFalse((runtime / "checkpoint-multi.ckpt").exists())
            self.assertFalse((runtime / "install.lock").exists())
            self.assertFalse((runtime / "checkpoint.download").exists())

    def test_worker_progress_reaches_gui_without_duration(self):
        values = []
        runner._run_cmd([sys.executable, "-c",
                         "import sys; print('progress_fraction=0.42', file=sys.stderr)"],
                        on_percent=values.append)
        self.assertIn(0.42, values)
        self.assertEqual(values[-1], 1.0)
