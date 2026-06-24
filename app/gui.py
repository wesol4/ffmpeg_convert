#!/usr/bin/env python3
"""GUI (PyQt5): przeciągnij pliki (obrazy lub wideo) i skonwertuj je przez FFmpeg.

Cała logika konwersji pochodzi z presets.py + runner.py — to samo źródło, co CLI.
Ten moduł to wyłącznie warstwa interfejsu.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit,
    QProgressBar, QPushButton, QRadioButton, QScrollArea, QSlider, QSpinBox,
    QStackedWidget, QVBoxLayout, QWidget,
)

if __package__:
    from . import presets, runner
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import presets
    import runner

ICON = {"image": "🖼", "video": "🎬"}

APP_STYLE = """
* { font-family: "Inter", "Ubuntu", "Segoe UI", sans-serif; }

QWidget { background-color: #0f1622; color: #e7ebf3; font-size: 13px; }

QLabel#Title { font-size: 22px; font-weight: 700; color: #f2f5fa; }
QLabel#Subtitle { font-size: 13px; color: #8a96ab; }

QFrame#Card, QGroupBox {
    background-color: #161f30; border: 1px solid #283248; border-radius: 14px;
}
QGroupBox {
    margin-top: 16px; padding: 18px 14px 14px 14px; font-weight: 600; color: #e7ebf3;
}
QGroupBox::title {
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 16px; top: 4px; padding: 0 6px; color: #8a96ab; font-weight: 600; font-size: 12px;
}

QListWidget, QLineEdit, QComboBox, QPlainTextEdit {
    background-color: #121a29; border: 1px solid #283248; border-radius: 10px;
    padding: 8px; color: #e7ebf3; selection-background-color: #1c3a32; selection-color: #d8fff0;
}
QListWidget[empty="true"] { border: 2px dashed #34495f; color: #5d6b80; }
QListWidget::item { padding: 4px 2px; border-radius: 6px; }
QListWidget::item:selected { background-color: #1c3a32; color: #d8fff0; }

QPushButton { border: none; border-radius: 9px; padding: 9px 20px; font-weight: 600; }
QPushButton#Primary { background-color: #34d399; color: #07291d; }
QPushButton#Primary:hover   { background-color: #4ee0ac; }
QPushButton#Primary:pressed { background-color: #22b67f; }
QPushButton#Primary:disabled { background-color: #283248; color: #5d6b80; }
QPushButton#Secondary {
    background-color: #1c2638; color: #e7ebf3; border: 1px solid #2c3850;
}
QPushButton#Secondary:hover   { background-color: #243049; }
QPushButton#Secondary:pressed { background-color: #1a2336; }

QRadioButton, QCheckBox { spacing: 10px; padding: 3px 0; color: #e7ebf3; }
QRadioButton::indicator, QCheckBox::indicator {
    width: 17px; height: 17px; border-radius: 9px; border: 1.5px solid #3b4863; background: #121a29;
}
QRadioButton::indicator:checked { border: 5px solid #34d399; background: #121a29; }
QCheckBox::indicator { border-radius: 5px; }
QCheckBox::indicator:checked { border: 1.5px solid #34d399; background: #34d399; }

QProgressBar {
    border: none; border-radius: 6px; background-color: #1c2638; height: 10px;
    text-align: center; color: transparent;
}
QProgressBar::chunk { background-color: #34d399; border-radius: 6px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #2c3850; border-radius: 5px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #3b4a68; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


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
    # Wartości, do których „przyciąga" suwak skali (procent oryginału).
    # Suwak kończy na 100% — większe wartości można wpisać ręcznie w polu.
    SNAP = [10, 25, 50, 75, 90, 100]

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

        scale_box = QGroupBox("Zmiana wielkości (procentowo)")
        sclay = QVBoxLayout(scale_box)
        row = QHBoxLayout()
        self.scale_chk = QCheckBox("Skaluj do")
        self.scale_chk.toggled.connect(self._update_preview)
        row.addWidget(self.scale_chk)
        self.scale_pct = QSpinBox()
        self.scale_pct.setRange(1, 800)
        self.scale_pct.setValue(50)
        self.scale_pct.setSuffix(" %")
        self.scale_pct.valueChanged.connect(self._on_scale_spin)
        row.addWidget(self.scale_pct)
        row.addWidget(QLabel("oryginału"))
        row.addStretch()
        sclay.addLayout(row)

        # Suwak przyciągający do zdefiniowanych wartości — zakres to indeks
        # listy SNAP, więc każdy „klik" ląduje dokładnie na jednej z nich.
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setRange(0, len(self.SNAP) - 1)
        self.scale_slider.setValue(self._snap_index(50))
        self.scale_slider.setTickPosition(QSlider.TicksBelow)
        self.scale_slider.setTickInterval(1)
        self.scale_slider.setSingleStep(1)
        self.scale_slider.valueChanged.connect(self._on_scale_slider)
        sclay.addWidget(self.scale_slider)

        layout.addWidget(scale_box)
        self.scale_box = scale_box
        # Skalowanie sensowne tylko przy przekodowaniu — przy „zachowaj oryginał"
        # kopiujemy plik 1:1, więc wyłączamy tę grupę.
        self.rb_keep.toggled.connect(self._toggle_scale)
        self._toggle_scale()

        layout.addStretch()

    def set_files(self, files):
        self.files = files
        self._update_preview()

    def _keep(self):
        return self.rb_keep.isChecked()

    def _toggle_scale(self):
        self.scale_box.setEnabled(not self.rb_keep.isChecked())

    def _snap_index(self, value):
        """Indeks najbliższej wartości z SNAP — do ustawienia suwaka."""
        return min(range(len(self.SNAP)),
                   key=lambda i: abs(self.SNAP[i] - value))

    def _on_scale_slider(self, idx):
        """Suwak → pole: ustaw dokładną wartość przyciągniętą (bez pętli zwrotnej)."""
        self.scale_pct.blockSignals(True)
        self.scale_pct.setValue(self.SNAP[idx])
        self.scale_pct.blockSignals(False)
        self._update_preview()

    def _on_scale_spin(self, value):
        """Pole → suwak: przyciągnij do najbliższej wartości z SNAP (cicho)."""
        self.scale_slider.blockSignals(True)
        self.scale_slider.setValue(self._snap_index(value))
        self.scale_slider.blockSignals(False)
        self._update_preview()

    def _scale_pct(self):
        return self.scale_pct.value() if self.scale_chk.isChecked() else None

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

    def _update_preview(self):
        self.preview_list.clear()
        keep = self._keep()
        newname = self.name_edit.text().strip()
        lines = []
        idx = 0
        for path in self.files:
            if presets.kind_of(path) != "image":
                continue
            idx += 1
            base, ext = presets.image_target_name(path, idx, newname, keep)
            lines.append(f"{path.name}  →  {base}.{ext}")

        # Przy wielu plikach pokazujemy próbkę: 3 pierwsze + ostatni.
        if len(lines) <= 4:
            preview = lines
        else:
            preview = lines[:3] + [f"… (jeszcze {len(lines) - 4} plików) …", lines[-1]]
        for line in preview:
            self.preview_list.addItem(line)

    def build_jobs(self):
        keep = self._keep()
        return presets.build_image_jobs(
            self.files, quality=self._quality(), keep=keep,
            newname=self.name_edit.text().strip(), subdir=self.rb_subdir.isChecked(),
            scale_pct=self._scale_pct(),
        )


class VideoPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.files = []
        layout = QVBoxLayout(self)

        preset_box = QGroupBox("Preset konwersji")
        play = QVBoxLayout(preset_box)
        self.preset_group = QButtonGroup(self)
        self.preset_buttons = {}  # id -> radiobutton
        for i, (pid, label) in enumerate(presets.VIDEO_PRESETS):
            rb = QRadioButton(label)
            if i == 0:
                rb.setChecked(True)
            rb.toggled.connect(self._toggle_option_boxes)
            self.preset_group.addButton(rb)
            self.preset_buttons[pid] = rb
            play.addWidget(rb)
        layout.addWidget(preset_box)

        self.frames_box = QGroupBox("Eksport klatek")
        flay = QHBoxLayout(self.frames_box)
        flay.addWidget(QLabel("Format:"))
        self.frames_format = QComboBox()
        self.frames_format.addItems(["PNG", "JPG", "EXR"])
        flay.addWidget(self.frames_format)
        self.frames_wav = QCheckBox("Eksportuj też WAV")
        self.frames_wav.setChecked(True)
        flay.addWidget(self.frames_wav)
        flay.addStretch()
        self.frames_box.setVisible(False)
        layout.addWidget(self.frames_box)

        # Opcje dla presetu "h264size".
        self.size_box = QGroupBox("Kontrola rozmiaru / kompresji (H.264)")
        slay = QVBoxLayout(self.size_box)
        self.size_mode_group = QButtonGroup(self)

        self.rb_crf = QRadioButton("Jakość (CRF) — jeden przebieg")
        self.rb_crf.setChecked(True)
        self.size_mode_group.addButton(self.rb_crf)
        slay.addWidget(self.rb_crf)

        crf_row = QHBoxLayout()
        crf_row.addSpacing(28)
        self.crf_slider = QSlider(Qt.Horizontal)
        self.crf_slider.setRange(18, 32)
        self.crf_slider.setValue(23)
        self.crf_label = QLabel()
        self.crf_label.setMinimumWidth(150)
        self.crf_slider.valueChanged.connect(self._update_crf_label)
        crf_row.addWidget(self.crf_slider, 1)
        crf_row.addWidget(self.crf_label)
        slay.addLayout(crf_row)
        self._update_crf_label(self.crf_slider.value())

        self.rb_target = QRadioButton("Docelowy rozmiar pliku (MB) — dwa przebiegi")
        self.size_mode_group.addButton(self.rb_target)
        slay.addWidget(self.rb_target)

        target_row = QHBoxLayout()
        target_row.addSpacing(28)
        target_row.addWidget(QLabel("Rozmiar:"))
        self.target_mb = QSpinBox()
        self.target_mb.setRange(1, 100000)
        self.target_mb.setValue(25)
        self.target_mb.setSuffix(" MB")
        target_row.addWidget(self.target_mb)
        target_row.addStretch()
        slay.addLayout(target_row)

        self.size_box.setVisible(False)
        layout.addWidget(self.size_box)

        layout.addStretch()

    def _update_crf_label(self, value):
        if value <= 20:
            hint = "najlepsza jakość, duży plik"
        elif value <= 25:
            hint = "dobra jakość"
        else:
            hint = "mniejszy plik"
        self.crf_label.setText(f"CRF {value} — {hint}")

    def _toggle_option_boxes(self):
        self.frames_box.setVisible(self.preset_buttons["frames"].isChecked())
        self.size_box.setVisible(self.preset_buttons["h264size"].isChecked())

    def set_files(self, files):
        self.files = files

    def _selected_preset(self):
        for pid, rb in self.preset_buttons.items():
            if rb.isChecked():
                return pid
        return None

    def build_jobs(self):
        return presets.build_video_jobs(
            self._selected_preset(), self.files,
            size_mode=("crf" if self.rb_crf.isChecked() else "size"),
            crf=self.crf_slider.value(), target_mb=self.target_mb.value(),
            frames_format=self.frames_format.currentText().lower(),
            frames_with_wav=self.frames_wav.isChecked(),
        )


class ConvertWorker(QThread):
    log = pyqtSignal(str)
    percent = pyqtSignal(float)
    done = pyqtSignal()

    def __init__(self, jobs):
        super().__init__()
        self.jobs = jobs

    def run(self):
        runner.run_jobs(
            self.jobs,
            on_log=self.log.emit,
            on_percent=lambda frac: self.percent.emit(frac),
        )
        self.done.emit()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FFmpeg Convert")
        # Nie otwieraj okna większego niż dostępny ekran — inaczej dolny pasek
        # z przyciskiem "Konwertuj" wychodzi poza krawędź i nie da się go kliknąć.
        avail = QApplication.primaryScreen().availableGeometry()
        self.setMinimumSize(min(560, avail.width() - 20), min(420, avail.height() - 20))
        self.resize(min(760, avail.width() - 40), min(840, avail.height() - 60))
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

        # Przewijalna część środkowa — przycisk "Konwertuj" zawsze widoczny na dole.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        self.drop_list = DropList()
        self.drop_list.setMaximumHeight(220)
        self.drop_list.filesDropped.connect(self.add_files)
        content_layout.addWidget(self.drop_list)

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
        content_layout.addLayout(btn_row)

        self.stack = QStackedWidget()
        self.empty_page = QLabel("Dodaj pliki, aby zobaczyć opcje konwersji.")
        self.empty_page.setObjectName("Subtitle")
        self.empty_page.setAlignment(Qt.AlignCenter)
        self.image_panel = ImagePanel()
        self.video_panel = VideoPanel()
        self.stack.addWidget(self.empty_page)
        self.stack.addWidget(self.image_panel)
        self.stack.addWidget(self.video_panel)
        content_layout.addWidget(self.stack)
        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

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
            p = Path(p)
            k = presets.kind_of(p)
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
        # Odpór na plik usunięty mid-sesji: odrzuć niedostępne z logiem,
        # zaktualizuj listę panelu, by nie trafiły do build_jobs.
        gone = [f for f in self.files if not f.is_file()]
        for f in gone:
            self.log.appendPlainText(f"Pomijam (plik niedostępny): {f.name}")
        if gone:
            self.files = [f for f in self.files if f.is_file()]
            panel0 = self.image_panel if self.kind == "image" else self.video_panel
            panel0.set_files(self.files)
            # odśwież wizualną listę (usuń usunięte pozycje)
            self.drop_list.clear()
            for f in self.files:
                self.drop_list.addItem(QListWidgetItem(f"{ICON[self.kind]}   {f}"))
            if not self.files:
                self.log.appendPlainText("Brak plików do przetworzenia.")
                self.convert_btn.setEnabled(False)
                return

        panel = self.image_panel if self.kind == "image" else self.video_panel
        try:
            jobs = panel.build_jobs()
        except Exception as exc:
            self.log.appendPlainText(f"Błąd przygotowania zadań: {exc}")
            return

        if not jobs:
            self.log.appendPlainText("Brak plików do przetworzenia (sprawdź ustawienia / filtr formatów).")
            return

        self.convert_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setMaximum(100)
        self.progress.setValue(0)

        self.worker = ConvertWorker(jobs)
        self.worker.log.connect(self.log.appendPlainText)
        self.worker.percent.connect(lambda frac: self.progress.setValue(int(frac * 100)))
        self.worker.done.connect(self._on_done)
        self.worker.start()

    def _on_done(self):
        self.convert_btn.setEnabled(True)
        self.progress.setValue(100)
        self.log.appendPlainText("=== Gotowe ===")


def main(files=None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)
    win = MainWindow()
    if files:
        win.add_files([Path(f) for f in files])
    win.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
