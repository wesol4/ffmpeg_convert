"""scripts/verify_output.py: fixture'y z lavfi i sprawdzanie wyniku przez ffprobe (realny ffmpeg)."""
import importlib.util
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "verify_output", Path(__file__).resolve().parents[1] / "scripts" / "verify_output.py")
verify = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(verify)


def run(*argv):
    out = StringIO()
    with redirect_stdout(out):
        code = verify.main([str(a) for a in argv])
    return code, out.getvalue()


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class VerifyOutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_odd_ntsc_fixture_passes_exact_checks_and_fails_wrong_ones(self):
        src = self.root / "odd.mp4"
        self.assertEqual(run("fixture", src, "--kind", "video", "--size", "321x181",
                             "--fps", "24000/1001", "--frames", "24")[0], 0)
        code, text = run("check", src, "--frames", "24", "--size", "321x181", "--fps", "24000/1001",
                         "--duration", "1.001", "--audio", "1", "--color", "unknown/-/-/-")
        self.assertEqual(code, 0, text)
        code, text = run("check", src, "--frames", "25", "--fps", "24")
        self.assertEqual(code, 1)
        self.assertEqual(text.count("BŁĄD"), 2)

    def test_fixture_never_overwrites_without_flag(self):
        src = self.root / "a.wav"
        self.assertEqual(run("fixture", src, "--kind", "audio")[0], 0)
        before = src.read_bytes()
        self.assertEqual(run("fixture", src, "--kind", "audio", "--duration", "2")[0], 2)
        self.assertEqual(src.read_bytes(), before)

    def test_rgb_and_709_color_samples(self):
        rgb = self.root / "rgb.mov"
        run("fixture", rgb, "--kind", "rgbvideo", "--pattern", "color", "--size", "64x64",
            "--frames", "1", "--no-audio")
        self.assertEqual(run("sample", rgb, "--expect", "10,98,204", "--tolerance", "0")[0], 0)
        yuv = self.root / "yuv.mp4"
        run("fixture", yuv, "--kind", "video", "--pattern", "color", "--size", "1280x720",
            "--frames", "1", "--no-audio")
        self.assertEqual(run("sample", yuv, "--matrix", "bt709", "--expect", "10,98,204")[0], 0)
        self.assertEqual(run("sample", yuv, "--matrix", "bt601", "--expect", "10,98,204")[0], 1)

    def test_frame_sequence_fixture(self):
        folder = self.root / "seq"
        self.assertEqual(run("fixture", folder, "--kind", "frames", "--frames", "5", "--name", "plate",
                             "--size", "65x33")[0], 0)
        frames = sorted(folder.glob("plate.*.png"))
        self.assertEqual([f.name for f in frames][::4], ["plate.1001.png", "plate.1005.png"])
        self.assertEqual(run("check", frames[0], "--size", "65x33", "--pix-fmt", "rgb24")[0], 0)


if __name__ == "__main__":
    unittest.main()
