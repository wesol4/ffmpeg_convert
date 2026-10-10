"""Desktop smoke scenarios; runnable with system Python + PyQt5, skipped in headless CI without Qt."""
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from app.gui_main_window import MainWindow
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PyQt5 required")
class GuiSequenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.frames = [self.root / f"render.{n:04d}.png" for n in range(1001, 1005)]
        for frame in self.frames:
            frame.touch()
        self.window = MainWindow()
        self.addCleanup(self.window.close)

    def test_middle_frame_offers_video_without_changing_image_mode(self):
        self.window.add_files([self.frames[2]])
        self.assertFalse(self.window.sequence_btn.isHidden())
        self.assertIs(self.window.stack.currentWidget(), self.window.image_panel)
        self.window.sequence_btn.click()
        self.assertIs(self.window.stack.currentWidget(), self.window.seq_panel)
        panel = self.window.seq_panel
        self.assertEqual(panel.frames, self.frames)
        panel.fps.setValue(23.976)
        panel.thumb_chk.setChecked(False)
        job, = panel.build_jobs()
        self.addCleanup(shutil.rmtree, job.cleanup[0], True)
        self.assertIn("23.976", job.cmds[0])
        self.assertEqual(Path(job.cmds[0][-1]), self.root / "render.mp4")
        self.window.sequence_btn.click()
        self.assertIs(self.window.stack.currentWidget(), self.window.image_panel)
        self.assertEqual(self.window.files, [self.frames[2]])

    def test_gap_shows_reason_and_disables_video_choice(self):
        self.frames[1].unlink()
        self.window.add_files([self.frames[0]])
        self.assertFalse(self.window.sequence_btn.isEnabled())
        self.assertIn("1002", self.window.sequence_notice.text())

    def test_explicit_audio_needs_file_and_detects_deleted_frames(self):
        self.window.add_files([self.frames[0]])
        self.window.sequence_btn.click()
        panel = self.window.seq_panel
        panel.audio_mode.setCurrentIndex(2)
        with self.assertRaisesRegex(ValueError, "Wskaż plik audio"):
            panel.build_jobs()
        panel.audio_mode.setCurrentIndex(1)
        self.frames[-1].unlink()
        with self.assertRaisesRegex(ValueError, "zmieniła"):
            panel.build_jobs()

    def test_close_and_file_changes_are_blocked_during_conversion(self):
        self.window.add_files([self.frames[0]])
        worker = mock.Mock()
        worker.isRunning.return_value = True
        self.window.worker = worker
        question = "app.gui_main_window.QMessageBox.question"
        # „Nie”: okno zostaje, konwersja trwa.
        with mock.patch(question, return_value=QMessageBox.No):
            event = mock.Mock()
            self.window.closeEvent(event)
        event.ignore.assert_called_once()
        worker.cancel.assert_not_called()
        # „Tak”: konwersja jest przerywana, okno zamknie się po jej zakończeniu.
        with mock.patch(question, return_value=QMessageBox.Yes):
            event = mock.Mock()
            self.window.closeEvent(event)
        event.ignore.assert_called_once()
        worker.cancel.assert_called_once()
        self.window.clear_files()
        self.assertEqual(self.window.files, [self.frames[0]])
        self.window.worker = None

    def test_completion_reports_failures(self):
        self.window._on_done(0, 1)
        self.assertIn("0/1", self.window.log.toPlainText())
