"""Widżety GUI: lista plików z drag & drop i placeholderem."""
from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QFrame, QListWidget


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
