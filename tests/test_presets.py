"""Testy jednostkowe dla app/presets.py (komendy jako listy argumentów).

Uruchomienie z repo:  python3 -m unittest discover -s tests -v
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Repo root na sys.path, by `from app import …` działał niezależnie od CWD.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import presets  # noqa: E402


class TestKindOf(unittest.TestCase):
    def test_image_exts(self):
        for ext in (".png", ".jpg", ".jpeg", ".exr", ".tif", ".tiff", ".webp"):
            self.assertEqual(presets.kind_of(Path(f"a{ext}")), "image")

    def test_video_exts(self):
        for ext in (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"):
            self.assertEqual(presets.kind_of(Path(f"a{ext}")), "video")

    def test_other(self):
        self.assertEqual(presets.kind_of(Path("a.txt")), "other")
        self.assertEqual(presets.kind_of(Path("noext")), "other")


class TestEnums(unittest.TestCase):
    def test_video_preset_str_compat(self):
        # str-Enum: równość ze stringiem i coerce z id.
        self.assertEqual(presets.VideoPreset.H264, "h264")
        self.assertIs(presets.VideoPreset("h264"), presets.VideoPreset.H264)

    def test_video_preset_typo_raises(self):
        with self.assertRaises(ValueError):
            presets.VideoPreset("h246")  # literówka → ValueError, nie ciche pominięcie

    def test_seq_format_str_compat(self):
        self.assertEqual(presets.SeqFormat.PRORES, "prores")
        self.assertIs(presets.SeqFormat("h265"), presets.SeqFormat.H265)

    def test_build_accepts_enum_and_str(self):
        src = Path("/tmp/x.mov")
        jobs_str = presets.build_video_jobs("h264", [src])
        jobs_enum = presets.build_video_jobs(presets.VideoPreset.H264, [src])
        self.assertEqual(jobs_str[0].cmds[0], jobs_enum[0].cmds[0])


class TestSimpleVideo(unittest.TestCase):
    def _job_cmd(self, jobs):
        self.assertEqual(len(jobs), 1)
        return jobs[0].cmds[0]

    def test_h264_single(self):
        src = Path("/tmp/movie.mov")
        jobs = presets.build_video_jobs("h264", [src])
        cmd = self._job_cmd(jobs)
        expected = [presets.FFMPEG, "-y", "-i", str(src),
                    "-c:v", "libx264", "-crf", "18", "-preset", "slow",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    str(src.parent / "movie_H264.mp4")]
        self.assertEqual(cmd, expected)

    def test_h265_batch_writes_to_subfolder(self):
        a, b = Path("/d/a.mov"), Path("/d/b.mov")
        jobs = presets.build_video_jobs("h265", [a, b])
        # batch (>1) → podfolder HEVC obok źródła
        for j, src in zip(jobs, (a, b)):
            out = src.parent / "HEVC" / f"{src.stem}_HEVC.mp4"
            self.assertEqual(j.cmds[0][-1], str(out))
            self.assertEqual(j.mkdir, src.parent / "HEVC")

    def test_prores_and_cineform_codecs(self):
        for pid, codec in (("prores", "prores_ks"), ("cineform", "cfhd")):
            jobs = presets.build_video_jobs(pid, [Path("/d/x.mov")])
            self.assertIn(codec, jobs[0].cmds[0])


class TestH264Size(unittest.TestCase):
    def test_crf_mode(self):
        src = Path("/tmp/v.mov")
        jobs = presets.build_video_jobs("h264size", [src],
                                        size_mode="crf", crf=20)
        cmd = jobs[0].cmds[0]
        self.assertEqual(len(jobs[0].cmds), 1)
        self.assertIn("-crf", cmd)
        self.assertEqual(cmd[cmd.index("-crf") + 1], "20")
        self.assertIn("CRF 20", jobs[0].label)

    def test_size_mode_two_pass(self):
        src = Path("/tmp/v.mov")
        with mock.patch("app.core.probe.probe_duration", return_value=10.0), \
             mock.patch("app.core.probe.probe_has_audio", return_value=True):
            jobs = presets.build_video_jobs("h264size", [src],
                                            size_mode="size", target_mb=25)
        job = jobs[0]
        self.assertEqual(len(job.cmds), 2)  # pass1, pass2
        self.assertIn("-pass", job.cmds[0])
        self.assertEqual(job.cmds[0][job.cmds[0].index("-pass") + 1], "1")
        self.assertEqual(job.cmds[1][job.cmds[1].index("-pass") + 1], "2")
        self.assertIn("-an", job.cmds[0])  # pass1 bez audio
        self.assertIn(os.devnull, job.cmds[0])  # wyjście pass1 → null
        # bitrate wideo = max(50, 25*8192/10 - 128) = 20352
        self.assertIn("20352k", job.cmds[0])
        # pass2 koduje audio (128k)
        self.assertIn("-c:a", job.cmds[1])
        self.assertIn("128k", job.cmds[1])
        # cleanup logi 2-pass
        cleanup_names = [Path(p).name for p in job.cleanup]
        self.assertTrue(any("ffmpeg2pass" in n for n in cleanup_names))

    def test_size_mode_no_audio_no_audio_reserve(self):
        src = Path("/tmp/v.mov")
        with mock.patch("app.core.probe.probe_duration", return_value=10.0), \
             mock.patch("app.core.probe.probe_has_audio", return_value=False):
            jobs = presets.build_video_jobs("h264size", [src],
                                            size_mode="size", target_mb=25)
        job = jobs[0]
        # bez audio: całe 25*8192/10 = 20480 na wideo, pass2 bez -c:a
        self.assertIn("20480k", job.cmds[0])
        self.assertNotIn("-c:a", job.cmds[1])

    def test_size_mode_falls_back_when_no_duration(self):
        src = Path("/tmp/v.mov")
        with mock.patch("app.core.probe.probe_duration", return_value=None):
            jobs = presets.build_video_jobs("h264size", [src],
                                            size_mode="size", target_mb=25)
        self.assertEqual(len(jobs[0].cmds), 1)  # fallback CRF (1 przebieg)
        self.assertIn("-crf", jobs[0].cmds[0])


class TestSpecialVideo(unittest.TestCase):
    def test_last_frame(self):
        src = Path("/d/clip.mov")
        jobs = presets.build_video_jobs("last_frame", [src])
        cmd = jobs[0].cmds[0]
        self.assertEqual(cmd[:4], [presets.FFMPEG, "-y", "-sseof", "-1"])
        self.assertEqual(cmd[-1], str(src.parent / "clip_last.png"))

    def test_frames_with_wav(self):
        src = Path("/d/clip.mov")
        jobs = presets.build_video_jobs("frames", [src],
                                        frames_format="png",
                                        frames_with_wav=True)
        self.assertEqual(len(jobs[0].cmds), 2)  # klatki + wav
        self.assertIn("-fps_mode", jobs[0].cmds[0])
        self.assertTrue(jobs[0].cmds[0][-1].endswith("clip_%04d.png"))
        self.assertIn("pcm_s24le", jobs[0].cmds[1])

    def test_frames_no_wav(self):
        src = Path("/d/clip.mov")
        jobs = presets.build_video_jobs("frames", [src],
                                        frames_with_wav=False)
        self.assertEqual(len(jobs[0].cmds), 1)

    def test_unknown_preset_raises(self):
        with self.assertRaises(ValueError):
            presets.build_video_jobs("nope", [Path("/d/x.mov")])


class TestImages(unittest.TestCase):
    def test_compress_default(self):
        p = Path("/d/a.png")
        jobs = presets.build_image_jobs([p], quality=2, subdir=True)
        cmd = jobs[0].cmds[0]
        self.assertIn("-q:v", cmd)
        self.assertEqual(cmd[cmd.index("-q:v") + 1], "2")
        self.assertEqual(cmd[cmd.index("-vf") + 1], "format=yuvj420p")
        self.assertEqual(cmd[-1], str(p.parent / "compressed" / "a.jpg"))

    def test_keep_copies(self):
        p = Path("/d/a.png")
        jobs = presets.build_image_jobs([p], keep=True, subdir=True)
        self.assertEqual(jobs[0].cmds[0][0], "__copy__")
        # zachowaj oryginalne rozszerzenie
        self.assertTrue(jobs[0].cmds[0][2].endswith("a.png"))

    def test_scale_filter_in_vf(self):
        p = Path("/d/a.png")
        jobs = presets.build_image_jobs([p], quality=5, scale_pct=50)
        vf = jobs[0].cmds[0][jobs[0].cmds[0].index("-vf") + 1]
        self.assertIn("scale=trunc(iw*0.5/2)*2", vf)
        self.assertIn("format=yuvj420p", vf)

    def test_rename_numbering(self):
        files = [Path("/d/x.png"), Path("/d/y.png")]
        jobs = presets.build_image_jobs(files, quality=2, newname="render")
        self.assertTrue(jobs[0].cmds[0][-1].endswith("render_001.jpg"))
        self.assertTrue(jobs[1].cmds[0][-1].endswith("render_002.jpg"))

    def test_skip_non_image(self):
        jobs = presets.build_image_jobs([Path("/d/a.txt"), Path("/d/a.png")])
        self.assertEqual(len(jobs), 1)

    def test_skip_overwrite_original(self):
        # keep + obok + bez zmiany nazwy → cel == źródło → pomijamy
        p = Path("/d/a.png")
        jobs = presets.build_image_jobs([p], keep=True, subdir=False)
        self.assertEqual(len(jobs), 0)


class TestImageHelpers(unittest.TestCase):
    def test_image_target_name(self):
        self.assertEqual(
            presets.image_target_name(Path("a.png"), 5, "r", False), ("r_005", "jpg"))
        self.assertEqual(
            presets.image_target_name(Path("a.png"), 5, "r", True), ("r_005", "png"))
        self.assertEqual(
            presets.image_target_name(Path("foo.tif"), 1, "", True), ("foo", "tif"))

    def test_scale_filter(self):
        self.assertIsNone(presets._scale_filter(None))
        self.assertIsNone(presets._scale_filter(100))
        self.assertEqual(
            presets._scale_filter(50), "scale=trunc(iw*0.5/2)*2:trunc(ih*0.5/2)*2")
        self.assertEqual(
            presets._scale_filter(200), "scale=trunc(iw*2.0/2)*2:trunc(ih*2.0/2)*2")


class TestSeq(unittest.TestCase):
    def test_natural_sort(self):
        names = ["frame_10.png", "frame_2.png", "frame_1.png"]
        ordered = sorted(names, key=presets._natural_key)
        self.assertEqual(ordered, ["frame_1.png", "frame_2.png", "frame_10.png"])

    def test_build_seq_job_cmd_and_audio(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            # puste pliki wystarczą (symlinki nie wymagają istnienia źródła)
            for n in ("frame_2.png", "frame_10.png", "frame_1.png"):
                (d / n).touch()
            # audio o nazwie folderu
            (d / f"{d.name}.wav").touch()
            files = [str(d / "frame_2.png"), str(d / "frame_10.png"),
                     str(d / "frame_1.png")]
            job = presets.build_seq_job(files, fps=24, fmt="h264")
            cmd = job.cmds[0]
            self.assertIn("-framerate", cmd)
            self.assertEqual(cmd[cmd.index("-framerate") + 1], "24")
            self.assertIn("seq_%05d.png", cmd[cmd.index("-i") + 1])
            self.assertIn("-shortest", cmd)  # audio doklejone
            self.assertTrue(job.label.startswith("3 klatek @ 24 fps"))
            self.assertEqual(len(job.cleanup), 1)  # katalog tymczasowy

    def test_build_seq_job_no_audio(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "f_1.png").touch()
            job = presets.build_seq_job([str(d / "f_1.png")], fps=30, fmt="prores")
            self.assertNotIn("-shortest", job.cmds[0])
            self.assertTrue(job.cmds[0][-1].endswith(f"{d.name}.mov"))

    def test_unknown_seq_format_raises(self):
        with self.assertRaises(ValueError):
            presets.build_seq_job([Path("/d/a.png")], fmt="nope")


def _make_png(path: Path, size: str = "8x8", color: str = "red"):
    """Wygeneruj realny mały PNG przez lavfi (do testów split/flipbook)."""
    import subprocess
    subprocess.run([presets.FFMPEG, "-y", "-f", "lavfi", "-i",
                    f"color={color}:size={size}", "-frames:v", "1", str(path)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class TestSplit(unittest.TestCase):
    def test_grid_2x2_crops_and_naming(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            src = d / "img.png"
            _make_png(src, "8x8")
            jobs = presets.build_split_jobs([src], cols=2, rows=2, subdir=True)
            self.assertEqual(len(jobs), 1)
            job = jobs[0]
            self.assertEqual(len(job.cmds), 4)  # 2x2 = 4 kafelki
            self.assertEqual(job.mkdir, d / "SplitGrid")
            # crop=4:4:ox:oy (8/2=4; ostatnia kolumna/wiersz dostaje resztę 4)
            vfs = [c[c.index("-vf") + 1] for c in job.cmds]
            self.assertIn("crop=4:4:0:0", vfs)
            self.assertIn("crop=4:4:4:4", vfs)
            outs = [c[-1] for c in job.cmds]
            self.assertTrue(all(o.startswith(str(d / "SplitGrid" / "img_")) for o in outs))

    def test_rejects_bad_grid(self):
        with self.assertRaises(ValueError):
            presets.build_split_jobs([Path("/d/a.png")], cols=0, rows=2)

    def test_skips_non_image(self):
        jobs = presets.build_split_jobs([Path("/d/a.txt")], cols=2, rows=2)
        self.assertEqual(len(jobs), 0)


class TestFlipbook(unittest.TestCase):
    def test_cmd_and_real_output(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for n in ("frame_1.png", "frame_2.png"):
                _make_png(d / n, "8x8")
            files = [str(d / "frame_1.png"), str(d / "frame_2.png")]
            job = presets.build_flipbook_job(files, cols=2, rows=1)
            cmd = job.cmds[0]
            self.assertIn("-f", cmd)
            self.assertEqual(cmd[cmd.index("-f") + 1], "concat")
            self.assertEqual(cmd[cmd.index("-vf") + 1], "tile=2x1")
            self.assertTrue(cmd[-1].endswith("_flipbook_2x1.png"))
            # realne wykonanie → plik istnieje
            import app.runner as runner
            runner.run_job(job)
            self.assertTrue(Path(cmd[-1]).is_file())

    def test_tile_scaling(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            _make_png(d / "f_1.png", "8x8")
            _make_png(d / "f_2.png", "8x8")
            job = presets.build_flipbook_job(
                [str(d / "f_1.png"), str(d / "f_2.png")],
                cols=2, rows=1, tile=(4, 4))
            self.assertEqual(job.cmds[0][job.cmds[0].index("-vf") + 1],
                             "scale=4:4,tile=2x1")

    def test_rejects_bad_grid(self):
        with self.assertRaises(ValueError):
            presets.build_flipbook_job([Path("/d/a.png")], cols=0, rows=1)


class TestSeqStem(unittest.TestCase):
    def test_strip_numeric_tail(self):
        self.assertEqual(presets._seq_stem("frame_001.png"), "frame")
        self.assertEqual(presets._seq_stem("render.0001.png"), "render")
        self.assertEqual(presets._seq_stem("clip.png"), "clip")
        self.assertEqual(presets._seq_stem("frame_1.png"), "frame_1")  # <3 cyfry


if __name__ == "__main__":
    unittest.main()