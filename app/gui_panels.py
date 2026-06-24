"""Panele opcji konwersji: obrazy (ImagePanel) i wideo (VideoPanel).

Warstwa UI — cała logika konwersji w app.presets (te same receptury co CLI).
"""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QRadioButton, QSlider, QSpinBox, QVBoxLayout,
    QWidget,
)

from app import presets


class ImagePanel(QWidget):
    # Wartości, do których „przyciąga" suwak skali (procent oryginału).
    # Suwak kończy na 100% — większe wartości można wpisać ręcznie w polu.
    SNAP = presets.CONFIG.image.scale_snaps

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
        self.scale_pct.setValue(presets.CONFIG.image.scale_default)
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
        self.scale_slider.setValue(self._snap_index(presets.CONFIG.image.scale_default))
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
        self.crf_slider.setRange(presets.CONFIG.h264size.crf_min, presets.CONFIG.h264size.crf_max)
        self.crf_slider.setValue(presets.CONFIG.h264size.crf_default)
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
        self.target_mb.setValue(presets.CONFIG.h264size.target_mb_default)
        self.target_mb.setSuffix(" MB")
        target_row.addWidget(self.target_mb)
        target_row.addStretch()
        slay.addLayout(target_row)

        self.size_box.setVisible(False)
        layout.addWidget(self.size_box)

        # Enkoder wideo (CPU / NVENC / QuickSync / AMF) — dla H.264/H.265
        # (i h264size w trybie CRF). Dostępne opcje filtrowane przez probe_encoders.
        self.encoder_box = QGroupBox("Enkoder wideo")
        elay = QHBoxLayout(self.encoder_box)
        self.encoder_combo = QComboBox()
        enc_labels = {
            presets.Encoder.CPU: "CPU (programowy)",
            presets.Encoder.NVENC: "NVENC (NVIDIA)",
            presets.Encoder.QSV: "QuickSync (Intel)",
            presets.Encoder.AMF: "AMF (AMD)",
        }
        for enc in (presets.Encoder.CPU, presets.Encoder.NVENC,
                    presets.Encoder.QSV, presets.Encoder.AMF):
            if enc in presets.probe_encoders():
                self.encoder_combo.addItem(enc_labels[enc], enc.value)
        elay.addWidget(self.encoder_combo)
        elay.addStretch()
        self.encoder_box.setVisible(False)
        layout.addWidget(self.encoder_box)
        # Tryb rozmiaru (h264size) używa CPU 2-pass — wyłączamy wybór enkodera.
        self.rb_crf.toggled.connect(self._toggle_encoder_enabled)
        self.rb_target.toggled.connect(self._toggle_encoder_enabled)

        # Ustaw widoczność boxów dla domyślnie zaznaczonego presetu (h264):
        # bez tego encoder_box byłby ukryty na starcie, bo sygnał toggled nie
        # emituje się dla radio, które jest już zaznaczone.
        self._toggle_option_boxes()

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
        is_h264 = self.preset_buttons[presets.VideoPreset.H264].isChecked()
        is_h265 = self.preset_buttons[presets.VideoPreset.H265].isChecked()
        is_size = self.preset_buttons[presets.VideoPreset.H264SIZE].isChecked()
        self.frames_box.setVisible(self.preset_buttons[presets.VideoPreset.FRAMES].isChecked())
        self.size_box.setVisible(is_size)
        self.encoder_box.setVisible(is_h264 or is_h265 or is_size)
        self._toggle_encoder_enabled()

    def _toggle_encoder_enabled(self):
        # h264size + tryb docelowego rozmiaru → CPU 2-pass; enkoder nie ma sensu.
        is_size = self.preset_buttons[presets.VideoPreset.H264SIZE].isChecked()
        enabled = not (is_size and self.rb_target.isChecked())
        self.encoder_combo.setEnabled(enabled)
        self.encoder_box.setEnabled(enabled)

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
            encoder=self.encoder_combo.currentData() or "cpu",
        )
