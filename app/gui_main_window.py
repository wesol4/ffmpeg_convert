"""Główne okno aplikacji: drag & drop, panele, przycisk konwersji, log, pasek."""
from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidgetItem,
    QMenuBar, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from app import presets
from app.gui_panels import ImagePanel, SeqPanel, VideoPanel
from app.gui_style import ICON
from app.gui_widgets import DropList
from app.gui_workers import ConvertWorker, UpdateChecker


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FFmpeg Convert")
        # Okno bez systemowego paska tytułowego (brak X/min/max). Zamykanie przez
        # własny przycisk ✕ w nagłówku; przesuwanie przez chwyt nagłówka (drag).
        self.setWindowFlags(Qt.FramelessWindowHint)
        # Nie otwieraj okna większego niż dostępny ekran — inaczej dolny pasek
        # z przyciskiem "Konwertuj" wychodzi poza krawędź i nie da się go kliknąć.
        avail = QApplication.primaryScreen().availableGeometry()
        self.setMinimumSize(min(560, avail.width() - 20), min(420, avail.height() - 20))
        self.resize(min(760, avail.width() - 40), min(840, avail.height() - 60))
        self.files = []
        self.kind = None
        self.worker = None
        self._update_checker = None
        self._drag_pos = None  # pozycja chwytu do przesuwania okna za nagłówek

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Menu Pomoc → Sprawdź aktualizacje… (bez cichego auto-pull).
        menubar = QMenuBar()
        help_menu = menubar.addMenu("Pomoc")
        help_menu.addAction("Sprawdź aktualizacje…", self.check_updates)
        layout.addWidget(menubar)

        # Wiersz nagłówka: tytuł+podtytuł po lewej, przycisk zamykania po prawej.
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)
        header = QVBoxLayout()
        header.setSpacing(2)
        title = QLabel("FFmpeg Convert")
        title.setObjectName("Title")
        subtitle = QLabel("Przeciągnij obrazy lub wideo i przekonwertuj je jednym kliknięciem")
        subtitle.setObjectName("Subtitle")
        header.addWidget(title)
        header.addWidget(subtitle)
        top_row.addLayout(header)
        top_row.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setObjectName("Close")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("Zamknij")
        close_btn.clicked.connect(self.close)
        top_row.addWidget(close_btn)
        layout.addLayout(top_row)

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
        add_folders_btn = QPushButton("Dodaj foldery…")
        add_folders_btn.setObjectName("Secondary")
        add_folders_btn.clicked.connect(self.choose_folders)
        clear_btn = QPushButton("Wyczyść listę")
        clear_btn.setObjectName("Secondary")
        clear_btn.clicked.connect(self.clear_files)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(add_folders_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        content_layout.addLayout(btn_row)

        self.stack = QStackedWidget()
        self.empty_page = QLabel("Dodaj pliki, aby zobaczyć opcje konwersji.")
        self.empty_page.setObjectName("Subtitle")
        self.empty_page.setAlignment(Qt.AlignCenter)
        self.image_panel = ImagePanel()
        self.video_panel = VideoPanel()
        self.seq_panel = SeqPanel()
        self.stack.addWidget(self.empty_page)
        self.stack.addWidget(self.image_panel)
        self.stack.addWidget(self.video_panel)
        self.stack.addWidget(self.seq_panel)
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

    def choose_folders(self):
        # Nie-natywny dialog katalogów z multi-wyborem (natywny pozwala tylko
        # na jeden folder). Włączamy ExtendedSelection na wewnętrznych widokach.
        from PyQt5.QtWidgets import QAbstractItemView, QListView, QTreeView
        dlg = QFileDialog(self, "Wybierz foldery z sekwencjami klatek")
        dlg.setFileMode(QFileDialog.Directory)
        dlg.setOption(QFileDialog.DontUseNativeDialog, True)
        dlg.setOption(QFileDialog.ShowDirsOnly, True)
        for view in (dlg.findChild(QListView, "listView"),
                     dlg.findChild(QTreeView, "treeView")):
            if view is not None:
                view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        if dlg.exec_():
            paths = [Path(u.toLocalFile()) for u in dlg.selectedUrls()]
            if paths:
                self.add_files(paths)

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
            # Folder = tryb sekwencji (jeden mp4 na folder); plik → wg rozszerzenia.
            k = "seq" if p.is_dir() else presets.kind_of(p)
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
        elif self.kind == "video":
            self.video_panel.set_files(self.files)
            self.stack.setCurrentWidget(self.video_panel)
        else:  # "seq"
            self.seq_panel.set_folders(self.files)
            self.stack.setCurrentWidget(self.seq_panel)

        self.convert_btn.setEnabled(True)

    def start_conversion(self):
        self.log.clear()
        # Odpór na plik/folder usunięty mid-sesji: odrzuć niedostępne z logiem,
        # zaktualizuj listę panelu, by nie trafiły do build_jobs. Foldery (seq)
        # sprawdzamy is_dir(); pliki — is_file().
        is_folder_mode = self.kind == "seq"
        exists = (lambda f: f.is_dir()) if is_folder_mode else (lambda f: f.is_file())
        gone = [f for f in self.files if not exists(f)]
        for f in gone:
            self.log.appendPlainText(f"Pomijam (niedostępny): {f.name}")
        if gone:
            self.files = [f for f in self.files if exists(f)]
            if is_folder_mode:
                self.seq_panel.set_folders(self.files)
            else:
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

        panel = (self.seq_panel if self.kind == "seq"
                 else self.image_panel if self.kind == "image"
                 else self.video_panel)
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

    def check_updates(self):
        from app import __version__
        self._update_checker = UpdateChecker(__version__)
        self._update_checker.result.connect(self._on_update_result)
        self._update_checker.start()

    def _on_update_result(self, msg):
        QMessageBox.information(self, "Aktualizacje", msg)

    # --- Przesuwanie okna bez paska tytułowego (chwyt za nagłówek) ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()
