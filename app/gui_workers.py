"""Wątek roboczy konwersji (QThread) — GUI tylko odbiera sygnały.

Konwersja woła app.runner.run_jobs; GUI nigdy nie wywołuje subprocess
bezpośrednio (brak blokowania pętli zdarzeń).
"""
from __future__ import annotations

from PyQt5.QtCore import QThread, pyqtSignal

from app import runner


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
