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
from app.config import Config, H264Config  # noqa: E402


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


class TestEncoder(unittest.TestCase):
    def test_encoder_enum_compat(self):
        self.assertEqual(presets.Encoder.NVENC, "nvenc")
        self.assertIs(presets.Encoder("qsv"), presets.Encoder.QSV)
        with self.assertRaises(ValueError):
            presets.Encoder("nvidia")  # literówka

    def test_h264_nvenc(self):
        cmd = presets.build_video_jobs("h264", [Path("/d/x.mov")], encoder="nvenc")[0].cmds[0]
        self.assertIn("h264_nvenc", cmd)
        self.assertIn("-cq", cmd)
        self.assertEqual(cmd[cmd.index("-cq") + 1], "18")
        self.assertIn("-b:v", cmd)  # CQ mode → -b:v 0

    def test_h265_nvenc(self):
        cmd = presets.build_video_jobs("h265", [Path("/d/x.mov")], encoder="nvenc")[0].cmds[0]
        self.assertIn("hevc_nvenc", cmd)
        self.assertEqual(cmd[cmd.index("-cq") + 1], "23")

    def test_h264_qsv_no_pix_fmt(self):
        cmd = presets.build_video_jobs("h264", [Path("/d/x.mov")], encoder="qsv")[0].cmds[0]
        self.assertIn("h264_qsv", cmd)
        self.assertIn("-global_quality", cmd)
        self.assertNotIn("-pix_fmt", cmd)  # QSV zarządza pix_fmt sam

    def test_h265_amf_cqp(self):
        cmd = presets.build_video_jobs("h265", [Path("/d/x.mov")], encoder="amf")[0].cmds[0]
        self.assertIn("hevc_amf", cmd)
        self.assertIn("-rc", cmd)
        self.assertEqual(cmd[cmd.index("-rc") + 1], "cqp")
        self.assertEqual(cmd[cmd.index("-qp_i") + 1], "23")

    def test_cpu_is_default(self):
        cmd = presets.build_video_jobs("h264", [Path("/d/x.mov")])[0].cmds[0]
        self.assertIn("libx264", cmd)
        self.assertEqual(cmd[cmd.index("-crf") + 1], "18")

    def test_dnxhd_ignores_encoder(self):
        # DNxHD to kodek montażowy CPU-only — enkoder ignorowany.
        cmd = presets.build_video_jobs("dnxhd", [Path("/d/x.mov")], encoder="nvenc")[0].cmds[0]
        self.assertIn("dnxhd", cmd)
        self.assertNotIn("h264_nvenc", cmd)

    def test_h264size_crf_uses_encoder(self):
        src = Path("/tmp/v.mov")
        job = presets.build_video_jobs("h264size", [src],
                                       size_mode="crf", crf=20, encoder="nvenc")[0]
        cmd = job.cmds[0]
        self.assertIn("h264_nvenc", cmd)
        self.assertEqual(cmd[cmd.index("-cq") + 1], "20")
        self.assertIn("NVENC", job.label)

    def test_h264size_size_mode_forces_cpu(self):
        # tryb docelowego rozmiaru → CPU 2-pass (precyzja), enkoder ignorowany.
        src = Path("/tmp/v.mov")
        with mock.patch("app.core.probe.probe_duration", return_value=10.0), \
             mock.patch("app.core.probe.probe_has_audio", return_value=True):
            job = presets.build_video_jobs("h264size", [src],
                                           size_mode="size", target_mb=25, encoder="nvenc")[0]
        self.assertIn("libx264", job.cmds[0])
        self.assertIn("-pass", job.cmds[0])
        self.assertIn("CPU 2-pass", job.label)


class TestSeqEncoder(unittest.TestCase):
    def test_seq_h264_nvenc(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "f_1.png").touch()
            (d / "f_2.png").touch()
            job = presets.build_seq_job([str(d / "f_1.png"), str(d / "f_2.png")],
                                        fps=24, fmt="h264", encoder="nvenc")
            cmd = job.cmds[0]
            self.assertIn("h264_nvenc", cmd)
            self.assertIn("-cq", cmd)
            self.assertIn("NVENC", job.label)

    def test_seq_prores_ignores_encoder(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "f_1.png").touch()
            job = presets.build_seq_job([str(d / "f_1.png")], fps=30, fmt="prores", encoder="nvenc")
            self.assertNotIn("nvenc", [c.lower() for c in job.cmds[0]])


class TestProbeEncoders(unittest.TestCase):
    def test_detects_nvenc_only(self):
        text = " ..... h264_nvenc   NVIDIA NVENC H.264 encoder\n" \
               " ..... hevc_nvenc   NVIDIA NVENC HEVC encoder\n"
        with mock.patch("app.core.probe.subprocess.run",
                        return_value=mock.MagicMock(stdout=text)):
            avail = presets.probe_encoders()
        self.assertIn(presets.Encoder.CPU, avail)
        self.assertIn(presets.Encoder.NVENC, avail)
        self.assertNotIn(presets.Encoder.QSV, avail)
        self.assertNotIn(presets.Encoder.AMF, avail)

    def test_always_has_cpu_on_failure(self):
        with mock.patch("app.core.probe.subprocess.run", side_effect=RuntimeError):
            avail = presets.probe_encoders()
        self.assertEqual(avail, {presets.Encoder.CPU})


class TestConfig(unittest.TestCase):
    def test_defaults_match_historical_values(self):
        cfg = presets.CONFIG
        self.assertEqual(cfg.h264.crf, 18)
        self.assertEqual(cfg.h265.crf, 23)
        self.assertEqual(cfg.audio.bitrate, "192k")
        self.assertEqual(cfg.audio.twopass_audio_k, 128)
        self.assertEqual(cfg.encoder.nvenc_preset, "p4")
        self.assertEqual(cfg.h264size.crf_default, 23)
        self.assertEqual(cfg.h264size.crf_min, 18)
        self.assertEqual(cfg.h264size.crf_max, 32)
        self.assertEqual(cfg.h264size.target_mb_default, 25)
        self.assertEqual(cfg.image.scale_snaps, [10, 25, 50, 75, 90, 100])
        self.assertEqual(cfg.image.scale_default, 50)
        self.assertEqual(cfg.seq.default_fps, 24)
        self.assertEqual(cfg.seq.thumb_width, 320)
        self.assertEqual(cfg.seq.thumb_ext, "jpg")

    def test_config_drives_recipes(self):
        # Dowód sprzężenia: podmiana CONFIG w video.py zmienia wygenerowaną komendę.
        custom = Config(h264=H264Config(crf=20))
        with mock.patch("app.presets.video.CONFIG", custom):
            cmd = presets.build_video_jobs("h264", [Path("/d/x.mov")])[0].cmds[0]
        self.assertEqual(cmd[cmd.index("-crf") + 1], "20")

    def test_config_is_frozen(self):
        with self.assertRaises(Exception):
            presets.CONFIG.h264.crf = 99  # type: ignore[misc]

    def test_color_config_defaults(self):
        cfg = presets.CONFIG.color
        self.assertTrue(cfg.exr_linear)
        self.assertIn("zscale=tin=linear", cfg.exr_vf)
        self.assertIn("format=yuv420p", cfg.exr_vf)
        self.assertIn("format=rgb24", cfg.exr_vf_jpg)
        # tagi: sRGB trc + BT.709 primaries/matrix, limited (wideo) / full (jpg)
        self.assertIn("-color_range", cfg.color_tags)
        self.assertEqual(cfg.color_tags[cfg.color_tags.index("-color_range") + 1], "tv")
        self.assertEqual(cfg.color_tags_jpg[cfg.color_tags_jpg.index("-color_range") + 1], "pc")


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
        # bitrate wideo = max(50, 25*8192/10*0.95 - 128) = 19328
        self.assertIn("19328k", job.cmds[0])
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
        # bez audio: 25*8192/10*0.95 = 19456 na wideo, pass2 bez -c:a
        self.assertIn("19456k", job.cmds[0])
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

    def test_out_path_override(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "seq").mkdir()
            (d / "seq" / "f_1.png").touch()
            job = presets.build_seq_job([str(d / "seq" / "f_1.png")], fmt="h264",
                                         out_path=d / "custom.mp4")
            self.assertEqual(Path(job.cmds[0][-1]), d / "custom.mp4")


import dataclasses  # noqa: E402


def _cfg_with(cs: str):
    """Kopia CONFIG z innym exr_colorspace (frozen dataclass → dataclasses.replace)."""
    return dataclasses.replace(
        presets.CONFIG, color=dataclasses.replace(presets.CONFIG.color, exr_colorspace=cs))


class TestSeqEXRColor(unittest.TestCase):
    """EXR (scene-referred linear) → MP4: konwersja do sRGB display + tagi koloru.

    Domyślnie EXR traktowany jako ACES2065-1 (AP0) → LUT 3D (AP0→709 + sRGB OETF, bez
    RRT); 'lin709' (opt-in) → zscale (pin=709 + sRGB OETF). Tagi: sRGB transfer,
    BT.709 primaries/matrix, zakres limited (tv).
    """

    def _exr_job(self, fmt="h264", color=True, has_zscale=True, encoder="cpu", cs=None):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for n in ("f_1.exr", "f_2.exr"):
                (d / n).touch()
            patches = [mock.patch("app.core.probe.has_filter", return_value=has_zscale)]
            if cs:
                patches.append(mock.patch("app.core.color.CONFIG", _cfg_with(cs)))
            for p in patches:
                p.start()
            try:
                return presets.build_seq_job(
                    [str(d / "f_1.exr"), str(d / "f_2.exr")],
                    fps=24, fmt=fmt, encoder=encoder, color=color)
            finally:
                for p in patches:
                    p.stop()

    def test_exr_h264_aces_lut_pipeline(self):
        job = self._exr_job()
        cmd = job.cmds[0]
        vf = cmd[cmd.index("-vf") + 1]
        self.assertIn("lut3d=", vf)                       # ACES: LUT AP0→709+sRGB
        self.assertIn("zscale", vf)                        # mp4: zscale RGB->YUV 709 po LUT
        self.assertEqual(cmd[cmd.index("-color_trc") + 1], "iec61966-2-1")
        self.assertEqual(cmd[cmd.index("-colorspace") + 1], "bt709")
        self.assertEqual(cmd[cmd.index("-color_range") + 1], "tv")
        self.assertIn("AP0→sRGB", job.label)

    def test_exr_h264_lin709_zscale_pipeline(self):
        job = self._exr_job(cs="lin709")
        vf = job.cmds[0][job.cmds[0].index("-vf") + 1]
        self.assertIn("zscale=tin=linear", vf)            # lin709: zscale pin=709
        self.assertNotIn("lut3d", vf)
        self.assertIn("linear→sRGB", job.label)

    def test_exr_no_color_opt_out(self):
        job = self._exr_job(color=False)
        cmd = job.cmds[0]
        self.assertNotIn("-vf", cmd)
        self.assertNotIn("-color_trc", cmd)
        self.assertNotIn("→sRGB", job.label)

    def test_png_seq_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "f_1.png").touch()
            with mock.patch("app.core.probe.has_filter", return_value=True):
                job = presets.build_seq_job([str(d / "f_1.png")], fmt="h264")
            self.assertNotIn("-vf", job.cmds[0])
            self.assertNotIn("-color_trc", job.cmds[0])

    def test_exr_prores_skips_color(self):
        # ProRes to intermediate montażowy — OETF sRGB byłby szkodliwy.
        job = self._exr_job(fmt="prores")
        cmd = job.cmds[0]
        self.assertNotIn("-vf", cmd)
        self.assertNotIn("-color_trc", cmd)
        self.assertNotIn("→sRGB", job.label)

    def test_exr_aces_mp4_without_zscale_degrades(self):
        # ACES mp4 bez zscale: LUT OK, ale RGB->YUV degraduje do format=yuv420p (swscale).
        job = self._exr_job(has_zscale=False)
        vf = job.cmds[0][job.cmds[0].index("-vf") + 1]
        self.assertIn("lut3d=", vf)
        self.assertNotIn("aces_mp4_yuv", vf)              # bez zscale -> brak segmentu zscale
        self.assertIn("format=yuv420p", vf)

    def test_exr_lin709_without_zscale_degrades(self):
        # lin709 bez zscale -> brak konwersji koloru (degrade).
        job = self._exr_job(has_zscale=False, cs="lin709")
        cmd = job.cmds[0]
        self.assertNotIn("-vf", cmd)
        self.assertNotIn("-color_trc", cmd)

    def test_exr_h265_with_gpu_encoder(self):
        # pipeline koloru łączy się z GPU enkoderem (vf CPU, encode GPU).
        job = self._exr_job(fmt="h265", encoder="nvenc")
        cmd = job.cmds[0]
        self.assertIn("hevc_nvenc", cmd)
        self.assertIn("-vf", cmd)
        self.assertIn("lut3d=", cmd[cmd.index("-vf") + 1])
        self.assertIn("NVENC", job.label)
        self.assertIn("AP0→sRGB", job.label)


class TestImageEXRColor(unittest.TestCase):
    """EXR → JPG: konwersja linear→display (ACES LUT domyślnie; zscale dla lin709)."""

    def test_exr_to_jpg_aces_lut(self):
        p = Path("/d/a.exr")
        with mock.patch("app.core.probe.has_filter", return_value=True):
            jobs = presets.build_image_jobs([p], quality=2, subdir=True)
        cmd = jobs[0].cmds[0]
        vf = cmd[cmd.index("-vf") + 1]
        self.assertIn("lut3d=", vf)
        self.assertIn("format=rgb24", vf)                 # mjpeg robi konsystentną konwersję 601
        self.assertEqual(cmd[cmd.index("-color_range") + 1], "pc")
        self.assertIn("AP0→sRGB", jobs[0].label)

    def test_exr_to_jpg_lin709_zscale(self):
        p = Path("/d/a.exr")
        with mock.patch("app.core.color.CONFIG", _cfg_with("lin709")), \
             mock.patch("app.core.probe.has_filter", return_value=True):
            jobs = presets.build_image_jobs([p], quality=2, subdir=True)
        vf = jobs[0].cmds[0][jobs[0].cmds[0].index("-vf") + 1]
        self.assertIn("zscale=tin=linear", vf)
        self.assertIn("format=rgb24", vf)
        self.assertIn("linear→sRGB", jobs[0].label)

    def test_exr_no_color_opt_out(self):
        p = Path("/d/a.exr")
        with mock.patch("app.core.probe.has_filter", return_value=True):
            jobs = presets.build_image_jobs([p], quality=2, subdir=True, color=False)
        cmd = jobs[0].cmds[0]
        self.assertEqual(cmd[cmd.index("-vf") + 1], "format=yuvj420p")
        self.assertNotIn("-color_range", cmd)

    def test_png_to_jpg_unchanged(self):
        p = Path("/d/a.png")
        with mock.patch("app.core.probe.has_filter", return_value=True):
            jobs = presets.build_image_jobs([p], quality=2, subdir=True)
        cmd = jobs[0].cmds[0]
        self.assertEqual(cmd[cmd.index("-vf") + 1], "format=yuvj420p")
        self.assertNotIn("-color_range", cmd)

    def test_exr_keep_copies_without_color(self):
        p = Path("/d/a.exr")
        with mock.patch("app.core.probe.has_filter", return_value=True):
            jobs = presets.build_image_jobs([p], quality=2, keep=True, subdir=True)
        # keep → kopia, brak filtra koloru
        self.assertEqual(jobs[0].cmds[0][0], "__copy__")
        self.assertNotIn("→sRGB", jobs[0].label)

    def test_exr_with_scale_prepends_scale(self):
        p = Path("/d/a.exr")
        with mock.patch("app.core.probe.has_filter", return_value=True):
            jobs = presets.build_image_jobs([p], quality=5, scale_pct=50)
        vf = jobs[0].cmds[0][jobs[0].cmds[0].index("-vf") + 1]
        self.assertTrue(vf.startswith("scale=trunc(iw*0.5/2)*2"))
        self.assertIn("lut3d=", vf)                        # scale PRZED LUT (skala w linear)
        self.assertIn("format=rgb24", vf)


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


class TestSeqBatch(unittest.TestCase):
    """Tryb folderów: jeden mp4 na folder + opcjonalna miniaturka w nadrzędnym."""

    def _make_folder(self, root: Path, name: str, frames=2, ext="png"):
        d = root / name
        d.mkdir()
        for i in range(1, frames + 1):
            (d / f"frame_{i:03d}.{ext}").touch()
        return d

    def test_one_job_per_folder(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            a = self._make_folder(root, "seqA")
            b = self._make_folder(root, "seqB")
            jobs = presets.build_seq_jobs_from_folders([a, b], fps=24, fmt="h264")
            self.assertEqual(len(jobs), 2)
            # mp4 nazwane po folderze, wewnątrz folderu (domyślnie mp4_in_seq)
            outs = [Path(j.cmds[0][-1]) for j in jobs]
            self.assertTrue(any(o.name == "seqA.mp4" and o.parent == a for o in outs))
            self.assertTrue(any(o.name == "seqB.mp4" and o.parent == b for o in outs))

    def test_mp4_in_parent(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            a = self._make_folder(root, "seqA")
            jobs = presets.build_seq_jobs_from_folders([a], mp4_in_seq=False, fmt="h264")
            self.assertEqual(len(jobs), 1)
            out = Path(jobs[0].cmds[0][-1])
            self.assertEqual(out, root / "seqA.mp4")

    def test_thumbnail_appended(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            a = self._make_folder(root, "seqA", frames=2)
            with mock.patch("app.core.probe.probe_duration", return_value=10.0):
                jobs = presets.build_seq_jobs_from_folders(
                    [a], fmt="h264", thumb_width=320)
            self.assertEqual(len(jobs), 1)
            job = jobs[0]
            self.assertEqual(len(job.cmds), 2)  # mp4 + miniaturka
            thumb_cmd = job.cmds[1]
            # seek do połowy (10/2 = 5.000)
            self.assertEqual(thumb_cmd[thumb_cmd.index("-ss") + 1], "5.000")
            self.assertEqual(thumb_cmd[thumb_cmd.index("-frames:v") + 1], "1")
            self.assertEqual(thumb_cmd[thumb_cmd.index("-vf") + 1], "scale=320:-2,format=rgb24")
            # miniaturka w folderze nadrzędnym
            self.assertEqual(Path(thumb_cmd[-1]), root / "seqA_thumb.jpg")
            self.assertIn("miniatura", job.label)

    def test_no_thumb_when_none(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            a = self._make_folder(root, "seqA")
            jobs = presets.build_seq_jobs_from_folders([a], thumb_width=None)
            self.assertEqual(len(jobs[0].cmds), 1)

    def test_skips_empty_folder(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            empty = self._make_folder(root, "empty", frames=0)
            full = self._make_folder(root, "full", frames=2)
            jobs = presets.build_seq_jobs_from_folders([empty, full])
            self.assertEqual(len(jobs), 1)

    def test_skips_nonexistent(self):
        jobs = presets.build_seq_jobs_from_folders([Path("/nie/istnieje/sekk")])
        self.assertEqual(len(jobs), 0)

    def test_build_thumbnail_cmd_mid_seek(self):
        src = Path("/d/clip.mp4")
        out = Path("/d/clip_thumb.jpg")
        with mock.patch("app.core.probe.probe_duration", return_value=8.0):
            cmd = presets.build_thumbnail_cmd(src, out, width=200)
        self.assertEqual(cmd[cmd.index("-ss") + 1], "4.000")
        self.assertEqual(cmd[cmd.index("-vf") + 1], "scale=200:-2,format=rgb24")
        self.assertEqual(cmd[-1], str(out))

    def test_build_thumbnail_cmd_no_duration_seeks_zero(self):
        src = Path("/d/clip.mp4")
        with mock.patch("app.core.probe.probe_duration", return_value=None):
            cmd = presets.build_thumbnail_cmd(src, Path("/d/t.jpg"), width=320)
        self.assertEqual(cmd[cmd.index("-ss") + 1], "0.000")


class TestSeqProxy(unittest.TestCase):
    """Proxy — sekwencje klatek numerowane od 1001 (standard VFX), w podfolderach
    obok źródeł. Komendy doczepiane do tego samego Joba (współdzielą tmp)."""

    def _make_folder(self, root: Path, name: str, frames=2, ext="png"):
        d = root / name
        d.mkdir()
        for i in range(1, frames + 1):
            (d / f"frame_{i:03d}.{ext}").touch()
        return d

    def _proxy_cmd(self, job, subdir):
        """Zwraca komendę proxy wg nazwy podfolderu w ostatnim argumencie."""
        cmds = [c for c in job.cmds if f"/{subdir}/" in c[-1]]
        self.assertEqual(len(cmds), 1, f"oczekiwano 1 komendy proxy {subdir}, jest {len(cmds)}")
        return cmds[0]

    def test_proxy_jpg_appended(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            a = self._make_folder(root, "shot", frames=3)
            jobs = presets.build_seq_jobs_from_folders([a], fmt="h264",
                                                       proxy_variants=["jpg"])
            self.assertEqual(len(jobs), 1)
            job = jobs[0]
            # mp4 + proxy (bez thumb → thumb_width domyślnie None)
            self.assertEqual(len(job.cmds), 2)
            cmd = self._proxy_cmd(job, "proxy_jpg")
            self.assertEqual(cmd[cmd.index("-start_number") + 1], "1001")
            self.assertEqual(cmd[-1], str(a / "proxy_jpg" / "shot.%04d.jpg"))
            self.assertEqual(cmd[cmd.index("-q:v") + 1], "2")
            self.assertIn("proxy", job.label)

    def test_no_proxy_keeps_existing_behavior(self):
        # proxy_variants=() → tylko mp4, jeden cmd (zachowanie dotychczasowe).
        with tempfile.TemporaryDirectory() as root:
            a = self._make_folder(Path(root), "seqA")
            jobs = presets.build_seq_jobs_from_folders([a], fmt="h264")
            self.assertEqual(len(jobs[0].cmds), 1)

    def test_proxy_half_has_scale(self):
        with tempfile.TemporaryDirectory() as root:
            a = self._make_folder(Path(root), "shot")
            jobs = presets.build_seq_jobs_from_folders([a], fmt="h264",
                                                       proxy_variants=["half"])
            cmd = self._proxy_cmd(jobs[0], "proxy_half")
            self.assertIn("scale=", cmd[cmd.index("-vf") + 1])
            self.assertEqual(cmd[-1], str(a / "proxy_half" / "shot.%04d.jpg"))

    def test_proxy_png16_rgb48le(self):
        with tempfile.TemporaryDirectory() as root:
            a = self._make_folder(Path(root), "shot")
            jobs = presets.build_seq_jobs_from_folders([a], fmt="h264",
                                                       proxy_variants=["png16"])
            cmd = self._proxy_cmd(jobs[0], "proxy_png16")
            self.assertIn("rgb48le", cmd[cmd.index("-vf") + 1])
            # PNG nie ma -q:v
            self.assertNotIn("-q:v", cmd)

    def test_no_mp4_with_proxy(self):
        with tempfile.TemporaryDirectory() as root:
            a = self._make_folder(Path(root), "shot")
            jobs = presets.build_seq_jobs_from_folders(
                [a], fmt="h264", make_mp4=False, proxy_variants=["jpg"])
            job = jobs[0]
            # brak komendy mp4 (żaden cmd nie kończy się .mp4) — sam proxy.
            self.assertFalse(any(c[-1].endswith(".mp4") for c in job.cmds))
            self.assertEqual(len(job.cmds), 1)
            self.assertIn("bez mp4", job.label)

    def test_proxy_start_frame_configurable(self):
        with tempfile.TemporaryDirectory() as root:
            a = self._make_folder(Path(root), "shot")
            jobs = presets.build_seq_jobs_from_folders(
                [a], fmt="h264", proxy_variants=["jpg"], proxy_start_frame=1)
            cmd = self._proxy_cmd(jobs[0], "proxy_jpg")
            self.assertEqual(cmd[cmd.index("-start_number") + 1], "1")
            self.assertEqual(cmd[-1], str(a / "proxy_jpg" / "shot.%04d.jpg"))

    def test_proxy_exr_aces_applies_lut(self):
        with tempfile.TemporaryDirectory() as root:
            a = self._make_folder(Path(root), "shot", ext="exr")
            with mock.patch("app.core.probe.has_filter", return_value=True):
                jobs = presets.build_seq_jobs_from_folders(
                    [a], fmt="h264", proxy_variants=["jpg", "png16"])
            jpg = self._proxy_cmd(jobs[0], "proxy_jpg")
            png = self._proxy_cmd(jobs[0], "proxy_png16")
            # ACES (domyślnie): AP0→709+sRGB przez LUT 3D (nie zscale).
            self.assertIn("lut3d=", jpg[jpg.index("-vf") + 1])
            self.assertIn("lut3d=", png[png.index("-vf") + 1])
            self.assertNotIn("zscale", png[png.index("-vf") + 1])  # png bez YUV
            # jpg z konwersją koloru dostaje tagi sRGB
            self.assertIn("-color_trc", jpg)

    def test_proxy_exr_no_color_keeps_linear(self):
        with tempfile.TemporaryDirectory() as root:
            a = self._make_folder(Path(root), "shot", ext="exr")
            jobs = presets.build_seq_jobs_from_folders(
                [a], fmt="h264", color=False, proxy_variants=["png16"])
            cmd = self._proxy_cmd(jobs[0], "proxy_png16")
            vf = cmd[cmd.index("-vf") + 1]
            self.assertNotIn("lut3d", vf)
            self.assertNotIn("zscale", vf)
            self.assertIn("rgb48le", vf)  # liniowe wartości w 16-bit RGB

    def test_multiple_variants(self):
        with tempfile.TemporaryDirectory() as root:
            a = self._make_folder(Path(root), "shot", frames=4)
            jobs = presets.build_seq_jobs_from_folders(
                [a], fmt="h264", proxy_variants=["jpg", "png16", "half"])
            job = jobs[0]
            # mp4 + 3 proxy = 4 cmds
            self.assertEqual(len(job.cmds), 4)
            for sub in ("proxy_jpg", "proxy_png16", "proxy_half"):
                self._proxy_cmd(job, sub)

    def test_proxy_custom_lut_override(self):
        # --aces-lut / picker: własny .cube nadpisuje wbudowany LUT ACES.
        with tempfile.TemporaryDirectory() as root:
            lut = Path(root) / "my_aces.cube"
            lut.write_text("LUT_3D_SIZE 2\n0 0 0\n1 0 0\n0 1 0\n1 1 0\n"
                           "0 0 1\n1 0 1\n0 1 1\n1 1 1\n")
            a = self._make_folder(Path(root), "shot", ext="exr")
            with mock.patch("app.core.probe.has_filter", return_value=True):
                jobs = presets.build_seq_jobs_from_folders(
                    [a], fmt="h264", proxy_variants=["jpg"], aces_lut=str(lut))
            cmd = self._proxy_cmd(jobs[0], "proxy_jpg")
            vf = cmd[cmd.index("-vf") + 1]
            self.assertIn("my_aces.cube", vf)            # nadpisany LUT w vf
            self.assertNotIn("aces_ap0_to_srgb", vf)    # nie wbudowany


class TestSeqStem(unittest.TestCase):
    def test_strip_numeric_tail(self):
        self.assertEqual(presets._seq_stem("frame_001.png"), "frame")
        self.assertEqual(presets._seq_stem("render.0001.png"), "render")
        self.assertEqual(presets._seq_stem("clip.png"), "clip")
        self.assertEqual(presets._seq_stem("frame_1.png"), "frame_1")  # <3 cyfry


if __name__ == "__main__":
    unittest.main()
