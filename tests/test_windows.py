"""Portable Windows setup tests; real registry/runtime checks run on Windows CI."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from app.core import process
from app.core.ffmpeg import tool_path
from app import presets, runner

spec = importlib.util.spec_from_file_location("windows_setup", Path(__file__).resolve().parents[1] / "win/setup.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class WindowsPortabilityTests(unittest.TestCase):
    def test_installer_actions_dispatch_without_interactive_input(self):
        with patch.object(setup, "install") as install:
            setup.perform_action("install")
            install.assert_called_once()
        with patch.object(setup, "check_installed"), patch.object(setup, "run") as run:
            setup.perform_action("audio")
            self.assertEqual(run.call_args.args[0][-1], "audio-setup")
        with self.assertRaises(ValueError):
            setup.perform_action("invalid")

    @unittest.skipUnless(os.name == "nt", "real Windows needed")
    def test_windowed_installer_starts_without_python_dependencies(self):
        script = Path(__file__).resolve().parents[1] / "win/setup.ps1"
        subprocess.run(["powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass",
                        "-File", str(script), "-SmokeTest"], check=True, timeout=30,
                       capture_output=True, text=True)

    def test_pythonw_gui_uses_console_worker(self):
        with patch.object(sys, "executable", str(Path("Python folder") / "pythonw.exe")):
            self.assertEqual(Path(process.console_python()).name, "python.exe")
            job, = presets.build_video_jobs("audio_separate", ["movie.mp4"])
            self.assertEqual(Path(job.cmds[0][0]).name, "python.exe")

    def test_background_window_flag_is_windows_only(self):
        with patch.object(process.os, "name", "nt"):
            self.assertEqual(process.subprocess_options(), {"creationflags": 0x08000000})
        with patch.object(process.os, "name", "posix"):
            self.assertEqual(process.subprocess_options(), {})

    def test_invalid_stderr_bytes_do_not_break_conversion(self):
        runner._run_cmd([sys.executable, "-c", "import os; os.write(2,b'\\xff\\xfe diagnostic\\n')"])

    def test_configured_tools_work_without_path_and_fall_back_if_moved(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            tool = folder / "narzędzia ze spacją" / "ffprobe.exe"
            tool.parent.mkdir()
            tool.touch()
            config = folder / "windows-tools.json"
            config.write_text(json.dumps({"ffprobe": str(tool)}))
            self.assertEqual(tool_path("ffprobe", config), str(tool))
            tool.unlink()
            with patch("app.core.ffmpeg.shutil.which", return_value="fallback"):
                self.assertEqual(tool_path("ffprobe", config), "fallback")

    def test_menu_command_quotes_both_program_and_selection(self):
        with patch.object(setup, "INSTALL", Path("Profil O'Neil & !") / "FFmpeg Convert"):
            command = setup.menu_command()
            self.assertTrue(command.startswith('"'))
            self.assertTrue(command.endswith('"%1"'))
            self.assertIn('pythonw.exe" "', command)
            self.assertNotIn("cmd /c", command)

    def test_menu_covers_exr_and_directories(self):
        self.assertTrue(any(r"\.exr\shell" in key for key in setup.menu_keys()))
        self.assertTrue(any(r"\Directory\shell" in key for key in setup.menu_keys()))

    def test_update_removes_stale_app_modules_and_preserves_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            for filename in ("launch.py", "gui.py", "cli.py", "presets/sequence.py", "audio_separation.py"):
                path = source / filename
                path.parent.mkdir(exist_ok=True)
                path.write_text("# new app\n")
            target = root / "install/app"
            target.mkdir(parents=True)
            (target / "presets.py").write_text("# stale module\n")
            model = target.parent / ".audio-runtime"
            model.mkdir()
            (model / "checkpoint").write_bytes(b"keep model")
            setup.copy_app(source, target)
            self.assertFalse((target / "presets.py").exists())
            self.assertTrue((target / "presets/sequence.py").is_file())
            self.assertEqual((model / "checkpoint").read_bytes(), b"keep model")

    def test_incomplete_update_preserves_old_app(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "app"
            target.mkdir()
            (target / "gui.py").write_text("# keep\n")
            with self.assertRaises(RuntimeError):
                setup.copy_app(root / "missing source", target)
            self.assertEqual((target / "gui.py").read_text(), "# keep\n")

    def test_sequence_falls_back_to_copies_without_symlink_privilege(self):
        with tempfile.TemporaryDirectory() as temp:
            frame = Path(temp) / "klatka.1001.png"
            frame.write_bytes(b"frame bytes")
            with patch.object(Path, "symlink_to", side_effect=OSError("Privilege not held")):
                job = presets.build_seq_job([frame], auto_audio=False)
            try:
                staged = Path(job.cleanup[0]) / "seq_00001.png"
                self.assertFalse(staged.is_symlink())
                self.assertEqual(staged.read_bytes(), frame.read_bytes())
            finally:
                shutil.rmtree(job.cleanup[0])

    @unittest.skipUnless(os.name == "nt", "real Windows needed")
    def test_real_registry_registration_and_removal_in_isolated_key(self):
        import winreg
        import uuid
        base = rf"Software\FFmpegConvertTests\{uuid.uuid4()}"
        with patch.object(setup, "REG_BASE", base):
            try:
                setup.register_menu()
                for key in setup.menu_keys():
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key + r"\command") as handle:
                        self.assertEqual(winreg.QueryValueEx(handle, "")[0], setup.menu_command())
                    setup.delete_menu_key(key)
            finally:
                def remove_tree(key):
                    try:
                        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_ALL_ACCESS) as handle:
                            children = []
                            for index in range(winreg.QueryInfoKey(handle)[0]):
                                children.append(winreg.EnumKey(handle, index))
                        for child in children:
                            remove_tree(key + "\\" + child)
                        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
                    except FileNotFoundError:
                        pass
                remove_tree(base)

    @unittest.skipUnless(os.name == "nt", "real Windows needed")
    def test_pythonw_entry_point_and_gui_import(self):
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "started.txt"
            script = Path(temp) / "smoke.py"
            script.write_text(
                "import os,sys\n"
                "os.environ['QT_QPA_PLATFORM']='offscreen'\n"
                f"sys.path.insert(0,{str(Path(__file__).resolve().parents[1])!r})\n"
                "from PyQt5.QtCore import QTimer\n"
                "from PyQt5.QtWidgets import QApplication\n"
                "from app.launch import main\n"
                "from pathlib import Path\n"
                "app=QApplication([])\n"
                "QTimer.singleShot(200,app.quit)\n"
                "code=main()\n"
                f"Path({str(output)!r}).write_text(str(code))\n", encoding="utf-8")
            subprocess.run([str(pythonw), str(script)], check=True, timeout=30)
            self.assertEqual(output.read_text(), "0")
