"""Regression scenarios using real FFmpeg outputs, plus discovery edge cases."""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest import mock
import wave
import zlib

from app import presets, runner
from app.cli import main
from app.core.sequences import detect_sequence, matching_audio


def png(path, color=(100, 150, 200)):
    def chunk(kind, data):
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))
    pixels = (b"\0" + bytes(color) * 64) * 48
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!2I5B", 64, 48, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


def wav(path, seconds):
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(48000)
        stream.writeframes(b"\0\0" * int(48000 * seconds))


class SequenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sequence's test ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.frames = []
        for number in range(1001, 1013):
            frame = self.root / f"shot.{number}.png"
            png(frame)
            self.frames.append(frame)

    def clean_job(self, job):
        for path in job.cleanup:
            self.addCleanup(shutil.rmtree, path, True)
        return job

    def test_one_middle_frame_detects_entire_sequence_only(self):
        png(self.root / "other.1001.png")
        png(self.root / "thumbnail.png")
        (self.root / "shot.1013.png").mkdir()
        sequence = detect_sequence(self.frames[5])
        self.assertEqual(sequence.frames, tuple(self.frames))
        self.assertEqual((sequence.first, sequence.last, sequence.name), (1001, 1012, "shot"))
        sequence.require_complete()

    def test_gaps_are_reported_without_allocating_a_huge_range(self):
        png(self.root / "shot.999999999999.png")
        sequence = detect_sequence(self.frames[0])
        with self.assertRaisesRegex(ValueError, "1013"):
            sequence.require_complete()

    def test_padding_transition_works_from_both_ends(self):
        for name in ("pad.0998.png", "pad.0999.png", "pad.1000.png"):
            png(self.root / name)
        a = detect_sequence(self.root / "pad.0998.png")
        b = detect_sequence(self.root / "pad.1000.png")
        self.assertEqual(a.frames, b.frames)
        self.assertEqual(len(a.frames), 3)

    def test_folder_with_multiple_sequences_is_not_silently_mixed(self):
        png(self.root / "other.1001.png")
        png(self.root / "other.1002.png")
        with self.assertRaisesRegex(ValueError, "Kilka sekwencji"):
            presets.build_seq_jobs_from_folders([self.root])

    def test_bad_fps_missing_frame_and_empty_action_fail_before_temp_creation(self):
        with mock.patch("app.presets.sequence.tempfile.mkdtemp") as mkdir:
            for fps in (0, -1, float("nan"), float("inf")):
                with self.assertRaises(ValueError):
                    presets.build_seq_job(self.frames, fps=fps)
            with self.assertRaises(ValueError):
                presets.build_seq_job(self.frames, make_mp4=False)
            with self.assertRaises(ValueError):
                presets.build_seq_job([self.root / "missing.png"])
            mkdir.assert_not_called()

    def test_existing_output_is_preserved(self):
        target = self.root / "result.mp4"
        target.write_bytes(b"previous movie")
        with self.assertRaisesRegex(ValueError, "już istnieje"):
            presets.build_seq_job(self.frames, out_path=target)
        self.assertEqual(target.read_bytes(), b"previous movie")

    def test_ambiguous_audio_requires_explicit_choice(self):
        wav(self.root / "shot.wav", 0.2)
        wav(self.root / f"{self.root.name}.wav", 0.2)
        with self.assertRaisesRegex(ValueError, "kilka ścieżek"):
            presets.build_seq_job(self.frames)
        job = self.clean_job(presets.build_seq_job(self.frames, auto_audio=False))
        self.assertIn("-an", job.cmds[0])

    def test_invalid_audio_and_unrelated_tracks_are_not_selected(self):
        (self.root / "shot.wav").write_bytes(b"not audio")
        wav(self.root / "unrelated.wav", 0.2)
        self.assertEqual(matching_audio(self.frames), [])

    def test_thumbnail_uses_new_sequence_duration_not_existing_movie(self):
        job = self.clean_job(presets.build_seq_job(self.frames, fps=12, thumb_width=100))
        command = job.cmds[-1]
        self.assertEqual(command[command.index("-ss") + 1], "0.500")

    def test_reject_audio_as_output(self):
        target = self.root / "sound.mp4"
        with self.assertRaises(ValueError):
            presets.build_seq_job(self.frames, audio_path=target, out_path=target)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
    def test_short_long_and_disabled_audio_keep_all_video_frames(self):
        for seconds, audio_enabled, mode in ((0.2, True, "crf"), (2, True, "crf"),
                                            (0.2, True, "size"), (0.2, False, "crf")):
            with self.subTest(seconds=seconds, audio=audio_enabled, mode=mode):
                audio = self.root / "custom voice.wav"
                wav(audio, seconds)
                output = self.root / f"movie_{seconds}_{audio_enabled}_{mode}.mp4"
                job = presets.build_seq_job(self.frames, fps=12, out_path=output, auto_audio=False,
                                            audio_path=audio if audio_enabled else None,
                                            size_mode=mode, target_mb=0.05)
                runner.run_job(job)
                self.assertFalse(Path(job.cleanup[0]).exists())
                data = subprocess.check_output([presets.FFPROBE, "-v", "error", "-count_frames",
                    "-show_streams", "-show_format", "-of", "json", str(output)], text=True)
                info = json.loads(data)
                video = next(s for s in info["streams"] if s["codec_type"] == "video")
                self.assertEqual(int(video["nb_read_frames"]), 12)
                self.assertAlmostEqual(float(info["format"]["duration"]), 1, delta=0.05)
                self.assertEqual(any(s["codec_type"] == "audio" for s in info["streams"]), audio_enabled)

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg required")
    def test_cli_single_frame_creates_full_video_and_preserves_existing_result(self):
        with mock.patch("app.cli.setup_logging"):
            self.assertEqual(main(["seq", "--fps", "12", "--no-audio", str(self.frames[5])]), 0)
            output = self.root / "shot.mp4"
            original = output.read_bytes()
            self.assertEqual(main(["seq", "--no-audio", str(self.frames[5])]), 2)
            self.assertEqual(output.read_bytes(), original)

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg required")
    def test_video_used_as_audio_does_not_replace_sequence_picture(self):
        audio_movie = self.root / "voice source.mp4"
        subprocess.run([presets.FFMPEG, "-v", "error", "-f", "lavfi", "-i",
                        "color=red:size=128x96:duration=0.2", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=0.2", "-c:v", "libx264", "-c:a", "aac",
                        str(audio_movie)], check=True)
        output = self.root / "picture.mp4"
        runner.run_job(presets.build_seq_job(self.frames, fps=12, audio_path=audio_movie, out_path=output))
        self.assertEqual(presets.probe_size(output), (64, 48))
        self.assertTrue(presets.probe_has_audio(output))

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg required")
    def test_flipbook_accepts_apostrophes_in_paths(self):
        job = presets.build_flipbook_job(self.frames[:2], cols=2, rows=1)
        runner.run_job(job)
        self.assertTrue(Path(job.cmds[0][-1]).is_file())

    @unittest.skipIf(os.name == "nt", "Windows rejects newlines in filenames")
    def test_flipbook_rejects_newline_in_path(self):
        frame = self.root / "bad\nfile.png"
        png(frame)
        with self.assertRaisesRegex(ValueError, "nowej linii"):
            presets.build_flipbook_job([frame], cols=1, rows=1)
