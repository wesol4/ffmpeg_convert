#!/usr/bin/env python3
"""Jedno okno: przeciągnij pliki (obrazy lub wideo) i skonwertuj je przez FFmpeg."""
import shutil
import subprocess
import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QFileDialog, QFrame, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QProgressBar,
    QPushButton, QRadioButton, QStackedWidget, QVBoxLayout, QWidget,
)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".exr", ".tif", ".tiff", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
ICON = {"image": "🖼", "video": "🎬"}

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

ACCENT = "#34d399"

APP_STYLE = """
* { font-family: "Inter", "Ubuntu", "Segoe UI", sans-serif; }

QWidget {
    background-color: #0f1622;
    color: #e7ebf3;
    font-size: 13px;
}

QLabel#Title {
    font-size: 22px;
    font-weight: 700;
    color: #f2f5fa;
}
QLabel#Subtitle {
    font-size: 13px;
    color: #8a96ab;
}

QFrame#Card, QGroupBox {
    background-color: #161f30;
    border: 1px solid #283248;
    border-radius: 14px;
}
QGroupBox {
    margin-top: 16px;
    padding: 18px 14px 14px 14px;
    font-weight: 600;
    color: #e7ebf3;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    top: 4px;
    padding: 0 6px;
    color: #8a96ab;
    font-weight: 600;
    font-size: 12px;
}

QListWidget, QLineEdit, QComboBox, QPlainTextEdit {
    background-color: #121a29;
    border: 1px solid #283248;
    border-radius: 10px;
    padding: 8px;
    color: #e7ebf3;
    selection-background-color: #1c3a32;
    selection-color: #d8fff0;
}
QListWidget[empty="true"] {
    border: 2px dashed #34495f;
    color: #5d6b80;
}
QListWidget::item {
    padding: 4px 2px;
    border-radius: 6px;
}
QListWidget::item:selected {
    background-color: #1c3a32;
    color: #d8fff0;
}

QPushButton {
    border: none;
    border-radius: 9px;
    padding: 9px 20px;
    font-weight: 600;
}
QPushButton#Primary {
    background-color: #34d399;
    color: #07291d;
}
QPushButton#Primary:hover   { background-color: #4ee0ac; }
QPushButton#Primary:pressed { background-color: #22b67f; }
QPushButton#Primary:disabled { background-color: #283248; color: #5d6b80; }

QPushButton#Secondary {
    background-color: #1c2638;
    color: #e7ebf3;
    border: 1px solid #2c3850;
}
QPushButton#Secondary:hover   { background-color: #243049; }
QPushButton#Secondary:pressed { background-color: #1a2336; }

QRadioButton, QCheckBox {
    spacing: 10px;
    padding: 3px 0;
    color: #e7ebf3;
}
QRadioButton::indicator, QCheckBox::indicator {
    width: 17px;
    height: 17px;
    border-radius: 9px;
    border: 1.5px solid #3b4863;
    background: #121a29;
}
QRadioButton::indicator:checked {
    border: 5px solid #34d399;
    background: #121a29;
}
QCheckBox::indicator { border-radius: 5px; }
QCheckBox::indicator:checked {
    border: 1.5px solid #34d399;
    background: #34d399;
}

QProgressBar {
    border: none;
    border-radius: 6px;
    background-color: #1c2638;
    height: 10px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: #34d399;
    border-radius: 6px;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #2c3850;
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #3b4a68; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

VIDEO_PRESETS = [
    "MP4 H.264 (CRF 18)",
    "MP4 H.265 / HEVC (CRF 23)",
    "DNxHD 1080p",
    "ProRes 422 HQ",
    "Cineform Q4 (10-bit)",
    "Ostatnia klatka PNG",
    "Eksport klatek + WAV",
]

VIDEO_SUFFIX = {
    "MP4 H.264 (CRF 18)": ("H264", "mp4"),
    "MP4 H.265 / HEVC (CRF 23)": ("HEVC", "mp4"),
    "DNxHD 1080p": ("DNxHD", "mov"),
    "ProRes 422 HQ": ("PR", "mov"),
    "Cineform Q4 (10-bit)": ("CF", "mov"),
}


def kind_of(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    return "other"


class DropList(QListWidget):
    filesDropped = pyqtSignal(list)
    PLACEHOLDER = "Przeciągnij i upuść pliki tutaj\n(obrazy lub wideo)"

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setMinimumHeight(150)
        self.setFrameShape(QFrame.NoFrame)
        self.setProperty("empty", True)

    def _refresh_empty_state(self):
        empty = self.count() == 0
        if self.property("empty") != empty:
            self.setProperty("empty", empty)
            self.style().unpolish(self)
            self.style().polish(self)
        self.viewport().update()

    def addItem(self, item):
        super().addItem(item)
        self._refresh_empty_state()

    def clear(self):
        super().clear()
        self._refresh_empty_state()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.count() == 0:
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QColor("#5d6b80"))
            font = painter.font()
            font.setPointSize(11)
            painter.setFont(font)
            painter.drawText(self.viewport().rect(), Qt.AlignCenter, self.PLACEHOLDER)
            painter.end()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        paths = [p for p in paths if p.is_file()]
        if paths:
            self.filesDropped.emit(paths)
        event.acceptProposedAction()


class ImagePanel(QWidget):
    def __init__(self):
        super().__init__()
        self.files = []
        layout = QVBoxLayout(self)

        quality_box = QGroupBox("Jakość JPG")
        qlay = QVBoxLayout(quality_box)
        self.quality_group = QButtonGroup(self)
        self.rb_q2 = QRadioButton("Q2  (~94%, najlepsza)")
        self.rb_q5 = QRadioButton("Q5  (~85%, dobra)")
        self.rb_q10 = QRadioButton("Q10 (~70%, mała waga)")
        self.rb_nocomp = QRadioButton("Bez kompresji (maks. jakość JPG)")
        self.rb_keep = QRadioButton("Zachowaj oryginał (bez konwersji, np. PNG/EXR)")
        self.rb_q2.setChecked(True)
        for rb in (self.rb_q2, self.rb_q5, self.rb_q10, self.rb_nocomp, self.rb_keep):
            self.quality_group.addButton(rb)
            qlay.addWidget(rb)
            rb.toggled.connect(self._update_preview)
        layout.addWidget(quality_box)

        rename_box = QGroupBox("Zmiana nazwy")
        rlay = QVBoxLayout(rename_box)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nowa nazwa bazowa (puste = zachowaj oryginalne nazwy)")
        self.name_edit.textChanged.connect(self._update_preview)
        rlay.addWidget(self.name_edit)
        rlay.addWidget(QLabel("Podgląd nazw (na żywo):"))
        self.preview_list = QListWidget()
        self.preview_list.setMaximumHeight(110)
        rlay.addWidget(self.preview_list)
        layout.addWidget(rename_box)

        out_box = QGroupBox("Gdzie zapisać")
        olay = QVBoxLayout(out_box)
        self.out_group = QButtonGroup(self)
        self.rb_subdir = QRadioButton("W podfolderze 'compressed'")
        self.rb_beside = QRadioButton("Obok oryginału")
        self.rb_subdir.setChecked(True)
        for rb in (self.rb_subdir, self.rb_beside):
            self.out_group.addButton(rb)
            olay.addWidget(rb)
        layout.addWidget(out_box)

        layout.addStretch()

    def set_files(self, files):
        self.files = files
        self._update_preview()

    def _matches(self, path: Path) -> bool:
        if self.rb_keep.isChecked():
            return True
        return path.suffix.lower() == ".png"

    def _quality(self):
        if self.rb_q2.isChecked():
            return 2
        if self.rb_q5.isChecked():
            return 5
        if self.rb_q10.isChecked():
            return 10
        if self.rb_nocomp.isChecked():
            return 1
        return None  # Zachowaj oryginał

    def _target_name(self, path: Path, idx: int):
        newname = self.name_edit.text().strip()
        base = f"{newname}_{idx:03d}" if newname else path.stem
        ext = path.suffix.lstrip(".") if self.rb_keep.isChecked() else "jpg"
        return base, ext

    def _update_preview(self):
        self.preview_list.clear()
        idx = 0
        for path in self.files:
            if not self._matches(path):
                continue
            idx += 1
            base, ext = self._target_name(path, idx)
            self.preview_list.addItem(f"{path.name}  →  {base}.{ext}")

    def build_jobs(self):
        """list[(src, out_path, ('copy', None) | ('encode', q))]"""
        jobs = []
        keep = self.rb_keep.isChecked()
        q = self._quality()
        subdir = self.rb_subdir.isChecked()
        idx = 0
        for path in self.files:
            if not self._matches(path):
                continue
            idx += 1
            base, ext = self._target_name(path, idx)
            out_dir = (path.parent / "compressed") if subdir else path.parent
            out_path = out_dir / f"{base}.{ext}"
            if out_path.resolve() == path.resolve():
                continue
            jobs.append((path, out_path, ("copy", None) if keep else ("encode", q)))
        return jobs


class VideoPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.files = []
        layout = QVBoxLayout(self)

        preset_box = QGroupBox("Preset konwersji")
        play = QVBoxLayout(preset_box)
        self.preset_group = QButtonGroup(self)
        self.preset_buttons = {}
        for i, name in enumerate(VIDEO_PRESETS):
            rb = QRadioButton(name)
            if i == 0:
                rb.setChecked(True)
            rb.toggled.connect(self._toggle_frames_box)
            self.preset_group.addButton(rb)
            self.preset_buttons[name] = rb
            play.addWidget(rb)
        layout.addWidget(preset_box)

        self.frames_box = QGroupBox("Format klatek (dla eksportu klatek + WAV)")
        flay = QHBoxLayout(self.frames_box)
        flay.addWidget(QLabel("Format:"))
        self.frames_format = QComboBox()
        self.frames_format.addItems(["PNG", "JPG", "EXR"])
        flay.addWidget(self.frames_format)
        flay.addStretch()
        self.frames_box.setVisible(False)
        layout.addWidget(self.frames_box)

        layout.addStretch()

    def _toggle_frames_box(self):
        self.frames_box.setVisible(self.preset_buttons["Eksport klatek + WAV"].isChecked())

    def set_files(self, files):
        self.files = files

    def _selected_preset(self):
        for name, rb in self.preset_buttons.items():
            if rb.isChecked():
                return name
        return None

    def _encode_cmd(self, preset, src: Path, out_path: Path):
        common = [FFMPEG, "-y", "-i", str(src)]
        if preset == "MP4 H.264 (CRF 18)":
            return common + ["-c:v", "libx264", "-crf", "18", "-preset", "slow",
                             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(out_path)]
        if preset == "MP4 H.265 / HEVC (CRF 23)":
            return common + ["-c:v", "libx265", "-crf", "23", "-preset", "medium",
                             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(out_path)]
        if preset == "DNxHD 1080p":
            return common + ["-vf", "scale=1920:1080", "-c:v", "dnxhd", "-b:v", "120M",
                             "-pix_fmt", "yuv422p", "-c:a", "pcm_s16le", str(out_path)]
        if preset == "ProRes 422 HQ":
            return common + ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le",
                             "-c:a", "pcm_s16le", str(out_path)]
        if preset == "Cineform Q4 (10-bit)":
            return common + ["-c:v", "cfhd", "-quality", "4", "-pix_fmt", "yuv422p10le",
                             "-c:a", "pcm_s16le", str(out_path)]
        raise ValueError(preset)

    def build_jobs(self):
        """list[dict(label, cmds, mkdir_target)]"""
        preset = self._selected_preset()
        batch = len(self.files) > 1
        jobs = []

        for src in self.files:
            base = src.stem

            if preset in VIDEO_SUFFIX:
                suf, ext = VIDEO_SUFFIX[preset]
                out_dir = (src.parent / suf) if batch else src.parent
                out_path = out_dir / f"{base}_{suf}.{ext}"
                jobs.append({
                    "label": f"{src.name} → {out_path.relative_to(src.parent)}",
                    "cmds": [self._encode_cmd(preset, src, out_path)],
                    "mkdir_target": out_path.parent,
                })

            elif preset == "Ostatnia klatka PNG":
                out_path = src.parent / f"{base}_last.png"
                cmd = [FFMPEG, "-y", "-sseof", "-1", "-i", str(src), "-update", "1", str(out_path)]
                jobs.append({
                    "label": f"{src.name} → {out_path.name}",
                    "cmds": [cmd],
                    "mkdir_target": out_path.parent,
                })

            elif preset == "Eksport klatek + WAV":
                fmt = self.frames_format.currentText().lower()
                frames_dir = src.parent / base
                pattern = frames_dir / f"{base}_%04d.{fmt}"
                wav_path = frames_dir / f"{base}.wav"
                cmd1 = [FFMPEG, "-y", "-i", str(src), str(pattern)]
                cmd2 = [FFMPEG, "-y", "-i", str(src), "-vn", "-acodec", "pcm_s24le", str(wav_path)]
                jobs.append({
                    "label": f"{src.name} → {frames_dir.name}/ (klatki {fmt.upper()} + WAV)",
                    "cmds": [cmd1, cmd2],
                    "mkdir_target": frames_dir,
                })

        return jobs


class ConvertWorker(QThread):
    log = pyqtSignal(str)
    progress = pyqtSignal(int, int)
    done = pyqtSignal()

    def __init__(self, mode, jobs):
        super().__init__()
        self.mode = mode
        self.jobs = jobs

    def run(self):
        total = len(self.jobs)
        for i, job in enumerate(self.jobs, start=1):
            try:
                if self.mode == "image":
                    src, out_path, (action, q) = job
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    if action == "copy":
                        shutil.copy2(src, out_path)
                    else:
                        cmd = [FFMPEG, "-y", "-i", str(src), "-q:v", str(q),
                               "-vf", "format=yuvj420p", str(out_path), "-loglevel", "error"]
                        subprocess.run(cmd, check=True)
                    self.log.emit(f"OK:  {src.name}  →  {out_path.name}")
                else:
                    job["mkdir_target"].mkdir(parents=True, exist_ok=True)
                    for cmd in job["cmds"]:
                        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.log.emit(f"OK:  {job['label']}")
            except Exception as exc:
                self.log.emit(f"BŁĄD: {exc}")
            self.progress.emit(i, total)
        self.done.emit()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FFmpeg Convert")
        self.resize(760, 840)
        self.files = []
        self.kind = None
        self.worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        header = QVBoxLayout()
        header.setSpacing(2)
        title = QLabel("FFmpeg Convert")
        title.setObjectName("Title")
        subtitle = QLabel("Przeciągnij obrazy lub wideo i przekonwertuj je jednym kliknięciem")
        subtitle.setObjectName("Subtitle")
        header.addWidget(title)
        header.addWidget(subtitle)
        layout.addLayout(header)

        self.drop_list = DropList()
        self.drop_list.filesDropped.connect(self.add_files)
        layout.addWidget(self.drop_list)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        add_btn = QPushButton("Dodaj pliki…")
        add_btn.setObjectName("Secondary")
        add_btn.clicked.connect(self.choose_files)
        clear_btn = QPushButton("Wyczyść listę")
        clear_btn.setObjectName("Secondary")
        clear_btn.clicked.connect(self.clear_files)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.stack = QStackedWidget()
        self.empty_page = QLabel("Dodaj pliki, aby zobaczyć opcje konwersji.")
        self.empty_page.setObjectName("Subtitle")
        self.empty_page.setAlignment(Qt.AlignCenter)
        self.image_panel = ImagePanel()
        self.video_panel = VideoPanel()
        self.stack.addWidget(self.empty_page)
        self.stack.addWidget(self.image_panel)
        self.stack.addWidget(self.video_panel)
        layout.addWidget(self.stack)

        action_row = QHBoxLayout()
        action_row.setSpacing(14)
        self.convert_btn = QPushButton("Konwertuj")
        self.convert_btn.setObjectName("Primary")
        self.convert_btn.setEnabled(False)
        self.convert_btn.clicked.connect(self.start_conversion)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(False)
        action_row.addWidget(self.convert_btn)
        action_row.addWidget(self.progress, 1)
        layout.addLayout(action_row)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(140)
        self.log.setPlaceholderText("Tu pojawi się log konwersji…")
        layout.addWidget(self.log)

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Wybierz pliki")
        if paths:
            self.add_files([Path(p) for p in paths])

    def clear_files(self):
        self.files = []
        self.kind = None
        self.drop_list.clear()
        self.log.clear()
        self.stack.setCurrentWidget(self.empty_page)
        self.convert_btn.setEnabled(False)

    def add_files(self, paths):
        for p in paths:
            k = kind_of(p)
            if k == "other":
                self.log.appendPlainText(f"Pomijam (nieobsługiwany format): {p.name}")
                continue
            if self.kind is None:
                self.kind = k
            elif k != self.kind:
                self.log.appendPlainText(
                    f"Pomijam (inny typ niż reszta listy — wyczyść listę, by zmienić tryb): {p.name}")
                continue
            if p in self.files:
                continue
            self.files.append(p)
            self.drop_list.addItem(QListWidgetItem(f"{ICON[k]}   {p}"))

        if not self.files:
            return

        if self.kind == "image":
            self.image_panel.set_files(self.files)
            self.stack.setCurrentWidget(self.image_panel)
        else:
            self.video_panel.set_files(self.files)
            self.stack.setCurrentWidget(self.video_panel)

        self.convert_btn.setEnabled(True)

    def start_conversion(self):
        self.log.clear()
        if self.kind == "image":
            jobs = self.image_panel.build_jobs()
        else:
            jobs = self.video_panel.build_jobs()

        if not jobs:
            self.log.appendPlainText("Brak plików do przetworzenia (sprawdź ustawienia / filtr formatów).")
            return

        self.convert_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setMaximum(len(jobs))
        self.progress.setValue(0)

        self.worker = ConvertWorker(self.kind, jobs)
        self.worker.log.connect(self.log.appendPlainText)
        self.worker.progress.connect(lambda cur, _total: self.progress.setValue(cur))
        self.worker.done.connect(self._on_done)
        self.worker.start()

    def _on_done(self):
        self.convert_btn.setEnabled(True)
        self.log.appendPlainText("=== Gotowe ===")


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
