"""Testy jednostkowe dla app/runner.py.

Używa realnego ffmpeg (generuje mały plik przez lavfi) plus mocków dla
ścieżek błędów. Uruchomienie z repo: python3 -m unittest discover -s tests -v
"""
import logging
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import presets, runner  # noqa: E402
from app.log import LOGGER_NAME, get_logger, logs_dir, setup_logging  # noqa: E402


def _ffmpeg_ok_cmd(out: Path) -> list:
    """Komenda ffmpeg, która generuje 1 klatkę 4x4 (sukces)."""
    return [presets.FFMPEG, "-y", "-f", "lavfi", "-i",
            "color=red:size=4x4:duration=0.1", "-frames:v", "1", str(out)]


def _ffmpeg_fail_cmd() -> list:
    """Komenda ffmpeg, która kończy się błędem (brak źródła)."""
    return [presets.FFMPEG, "-y", "-i", "/nieistnieje/zebr/abc", "-y", "x"]


class TestRunCmd(unittest.TestCase):
    def test_copy(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            src = d / "s.bin"
            src.write_bytes(b"hello")
            dst = d / "d.bin"
            runner._run_cmd(["__copy__", str(src), str(dst)])
            self.assertEqual(dst.read_bytes(), b"hello")

    def test_ffmpeg_success(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "frame.png"
            runner._run_cmd(_ffmpeg_ok_cmd(out))
            self.assertTrue(out.is_file() and out.stat().st_size > 0)

    def test_ffmpeg_failure_raises_with_stderr(self):
        with self.assertRaises(RuntimeError) as ctx:
            runner._run_cmd(_ffmpeg_fail_cmd())
        self.assertIn("ffmpeg", str(ctx.exception).lower())


class TestRunJob(unittest.TestCase):
    def test_mkdir_created(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            out = d / "out" / "sub" / "f.png"
            job = presets.Job(label="t", cmds=[_ffmpeg_ok_cmd(out)],
                              mkdir=out.parent)
            runner.run_job(job)
            self.assertTrue(out.is_file())

    def test_cleanup_runs_even_on_error(self):
        leftover = Path(tempfile.mkdtemp()) / "leftover.log"
        leftover.write_text("x")
        job = presets.Job(label="t", cmds=[_ffmpeg_fail_cmd()],
                          cleanup=[leftover])
        with self.assertRaises(RuntimeError):
            runner.run_job(job)
        self.assertFalse(leftover.exists())

    def test_cleanup_directory(self):
        tmp = Path(tempfile.mkdtemp())
        job = presets.Job(label="t", cmds=[_ffmpeg_ok_cmd(tmp / "f.png")],
                          cleanup=[tmp])
        runner.run_job(job)
        self.assertFalse(tmp.exists())


class TestRunJobs(unittest.TestCase):
    def test_mixed_ok_fail_counts_and_progress(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            ok1 = presets.Job(label="ok1", cmds=[_ffmpeg_ok_cmd(d / "a.png")])
            ok2 = presets.Job(label="ok2", cmds=[_ffmpeg_ok_cmd(d / "b.png")])
            bad = presets.Job(label="bad", cmds=[_ffmpeg_fail_cmd()])
            logs, prog = [], []
            n_ok = runner.run_jobs([ok1, bad, ok2],
                                   on_log=logs.append,
                                   on_progress=lambda c, t: prog.append((c, t)))
            self.assertEqual(n_ok, 2)  # ok1, ok2
            self.assertEqual(len(prog), 3)
            self.assertEqual(prog[-1], (3, 3))
            self.assertTrue(any("BŁĄD" in m for m in logs))
            self.assertTrue(any("OK" in m for m in logs))

    def test_empty_jobs_returns_zero(self):
        self.assertEqual(runner.run_jobs([]), 0)


class TestOutTimeParser(unittest.TestCase):
    def test_out_time_us(self):
        self.assertEqual(runner._out_time_us("frame= 10 out_time_us=2500000"), 2500000)

    def test_out_time_timestamp(self):
        self.assertEqual(runner._out_time_us("out_time=00:00:02.500"), 2_500_000)

    def test_legacy_out_time_ms(self):
        self.assertEqual(runner._out_time_us("out_time_ms=1500000"), 1_500_000)

    def test_no_match(self):
        self.assertIsNone(runner._out_time_us("Press [q] to quit"))


def _make_src_video(path: Path, seconds: float = 3.0):
    """Wygeneruj realne krótkie wideo (do testów postępu)."""
    import subprocess
    subprocess.run([presets.FFMPEG, "-y", "-f", "lavfi", "-i",
                    f"color=blue:size=16x16:duration={seconds}", "-r", "10",
                    str(path)], check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


class TestProgress(unittest.TestCase):
    def test_run_job_reports_progress(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            src = d / "src.mp4"
            _make_src_video(src, 3.0)
            job = presets.build_video_jobs("h264", [src])[0]
            self.assertIsNotNone(job.duration)
            self.assertGreater(job.duration, 2.0)
            self.assertLess(job.duration, 4.0)
            fracs = []
            runner.run_job(job, on_percent=fracs.append)
            self.assertTrue(fracs)                      # coś zgłoszone
            self.assertAlmostEqual(fracs[-1], 1.0, places=2)  # job ukończony
            self.assertLessEqual(max(fracs), 1.0 + 1e-6)
            self.assertGreaterEqual(min(fracs), 0.0)
            # niemalejący
            self.assertEqual(fracs, sorted(fracs))

    def test_run_jobs_overall_progress(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            src = d / "src.mp4"
            _make_src_video(src, 2.0)
            jobs = presets.build_video_jobs("h264", [src])
            overall = []
            runner.run_jobs(jobs, on_percent=overall.append)
            self.assertTrue(overall)
            self.assertAlmostEqual(overall[-1], 1.0, places=2)

    def test_image_job_no_duration_still_completes(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            src = d / "a.png"
            src.write_bytes(b"\x89PNG\r\n\x1a\n")  # fałszywy plik (wystarczy do copy)
            fracs = []
            job = presets.Job(label="t", cmds=[["__copy__", str(src), str(d / "b.png")]],
                              duration=None)
            runner.run_job(job, on_percent=fracs.append)
            self.assertEqual(fracs, [1.0])  # copy → jednorazowo 1.0


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list = []

    def emit(self, record):
        self.records.append(record)


class TestLogFile(unittest.TestCase):
    def tearDown(self):
        # nie zanieczyszczaj innych testów FileHandlerem do usuniętego tmp
        logging.getLogger(LOGGER_NAME).handlers = []
        get_logger()  # przywróć NullHandler

    def test_setup_writes_record(self):
        with tempfile.TemporaryDirectory() as d:
            logfile = setup_logging(logs_root=Path(d))
            log = get_logger()
            log.info("test-marker-123")
            for h in log.handlers:
                h.flush()
            content = logfile.read_text(encoding="utf-8")
        self.assertIn("test-marker-123", content)
        self.assertTrue(logfile.name.endswith(".log"))

    def test_logs_dir_default_under_cache(self):
        p = logs_dir()
        self.assertEqual(p.name, "logs")
        self.assertEqual(p.parent.name, "ffmpeg_convert")


class TestRunnerLogging(unittest.TestCase):
    def test_logs_ok_and_error(self):
        cap = _Capture()
        log = get_logger()
        log.addHandler(cap)
        try:
            with tempfile.TemporaryDirectory() as d:
                d = Path(d)
                ok = presets.Job(label="okjob", cmds=[_ffmpeg_ok_cmd(d / "a.png")])
                bad = presets.Job(label="badjob", cmds=[_ffmpeg_fail_cmd()])
                runner.run_jobs([ok, bad])
        finally:
            log.removeHandler(cap)
        msgs = [r.getMessage() for r in cap.records]
        self.assertTrue(any("OK" in m and "okjob" in m for m in msgs))
        self.assertTrue(any("BŁĄD" in m and "badjob" in m for m in msgs))
        self.assertTrue(any(r.levelno == logging.ERROR for r in cap.records))


if __name__ == "__main__":
    unittest.main()
