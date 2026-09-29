#!/usr/bin/env python3
"""Wspólne uruchamianie Jobów (z presets.py) — używane przez CLI i GUI.

Każdy Job to lista komend FFmpeg wykonywanych po kolei. Specjalna komenda
["__copy__", src, dst] kopiuje plik bez przekodowania (tryb „zachowaj oryginał").

Postęp wewnątrz joba: do komend ffmpeg runner dokleja `-progress pipe:2 -nostats`,
więc na stderr pojawiają się linie `out_time_us=…`. Przy znanej długości
(Job.duration) wywoływany jest on_percent(frac 0..1) dla bieżącego joba, a run_jobs
mapuje to na postęp łączny przez wszystkie joby. Separacja audio (worker Pythona)
zgłasza `progress_fraction=…` bezpośrednio.

Przerwanie: CancelToken.cancel() kończy bieżący proces; job zgłasza Cancelled,
jego niedokończone pliki (Job.outputs) są usuwane, a kolejne joby nie startują.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from collections import deque
from pathlib import Path
from typing import Callable

from app.core.ffmpeg import FFMPEG
from app.core.jobs import Job
from app.core.process import subprocess_options
from app.log import get_logger

_LOG = get_logger()

_OUT_US = re.compile(r"out_time_us=(\d+)")
_OUT_MS = re.compile(r"out_time_ms=(\d+)")        # legacy, wartość w mikrosekundach
_OUT_T = re.compile(r"out_time=(\d+):(\d+):(\d+(?:\.\d+)?)")
# Linie bloku -progress (klucz=wartość bez spacji) — nie trafiają do ogona błędu.
_PROGRESS_LINE = re.compile(r"[a-z0-9_]+=\S*")
PROGRESS_ARGS = ["-progress", "pipe:2", "-nostats"]


class Cancelled(Exception):
    """Job przerwany przez użytkownika."""


class CancelToken:
    """Przerwanie z innego wątku (GUI): ustawia flagę i kończy bieżący proces."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        with self._lock:
            self._event.set()
            if self._proc is not None:
                _stop(self._proc)

    def _attach(self, proc: subprocess.Popen | None) -> None:
        with self._lock:
            self._proc = proc
            if proc is not None and self._event.is_set():
                _stop(proc)


def _stop(proc: subprocess.Popen) -> None:
    """Zakończ proces razem z potomkami.

    Na Windows ffmpeg bywa uruchamiany przez nakładkę (np. shim Chocolatey), która
    odpala prawdziwy ffmpeg jako proces potomny — samo terminate() zabiłoby tylko
    nakładkę, a ffmpeg liczyłby dalej. Stąd taskkill /T (całe drzewo).
    """
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       capture_output=True, check=False, **subprocess_options())
    else:
        proc.terminate()


def _out_time_us(line: str) -> int | None:
    """Mikrosekundy osiągniętego czasu wyjściowego z linii postępu ffmpeg, lub None."""
    m = _OUT_US.search(line)
    if m:
        return int(m.group(1))
    m = _OUT_T.search(line)
    if m:
        h, mi, s = m.groups()
        return int((int(h) * 3600 + int(mi) * 60 + float(s)) * 1_000_000)
    m = _OUT_MS.search(line)
    if m:
        return int(m.group(1))  # legacy: mikrosekundy mimo nazwy
    return None


def _with_progress(cmd: list) -> list:
    """Komenda ffmpeg z raportem postępu na stderr (inne programy bez zmian)."""
    if cmd and cmd[0] == FFMPEG and "-progress" not in cmd:
        return [cmd[0], *PROGRESS_ARGS, *cmd[1:]]
    return cmd


def _run_cmd(cmd: list, on_percent: Callable[[float], None] | None = None,
             duration: float | None = None, cancel: CancelToken | None = None) -> None:
    """Wykonaj jedną komendę; przy błędzie podnieś wyjątek z ogonem stderr.

    on_percent(frac) — frac w [0,1] postępu tej komendy (wymaga duration > 0;
    inaczej zgłoszony tylko 1.0 po zakończeniu). cancel — przerwanie z zewnątrz.
    """
    if cancel is not None and cancel.cancelled:
        raise Cancelled()
    if cmd and cmd[0] == "__copy__":
        shutil.copy2(cmd[1], cmd[2])
        if on_percent:
            on_percent(1.0)
        return
    proc = subprocess.Popen(_with_progress(cmd), stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace", bufsize=1,
                            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                            **subprocess_options())
    if cancel is not None:
        cancel._attach(proc)
    last: deque[str] = deque(maxlen=5)
    stream = proc.stderr
    try:
        if stream is not None:
            for line in stream:
                line = line.rstrip()
                if line.startswith("progress_fraction=") and on_percent:
                    try:
                        on_percent(max(0.0, min(1.0, float(line.split("=", 1)[1]))))
                    except ValueError:
                        pass
                    continue
                us = _out_time_us(line)
                if us is not None and duration and duration > 0 and on_percent:
                    on_percent(min(1.0, us / (duration * 1_000_000)))
                if line and not _PROGRESS_LINE.fullmatch(line):
                    last.append(line)
    finally:
        if stream is not None:
            stream.close()
        proc.wait()
        if cancel is not None:
            cancel._attach(None)
    if cancel is not None and cancel.cancelled:
        raise Cancelled()
    if on_percent:
        on_percent(1.0)  # ta komenda ukończona (nawet bez linii postępu)
    if proc.returncode != 0:
        raise RuntimeError(f"{Path(cmd[0]).name} zwrócił kod {proc.returncode}:\n" + "\n".join(last))


def run_job(job: Job, on_percent: Callable[[float], None] | None = None,
            cancel: CancelToken | None = None) -> None:
    """Wykonaj pojedynczy Job: mkdir → komendy (z postępem) → cleanup.

    on_percent(job_frac) — job_frac w [0,1] dla tego joba, mapowane z per-cmd
    udziałów (komendy w jobu ważone równo). Przy błędzie lub przerwaniu pliki
    z job.outputs są usuwane.
    """
    if job.mkdir is not None:
        job.mkdir.mkdir(parents=True, exist_ok=True)
    # Sprzątamy tylko to, co ten job stworzył — nigdy wcześniej istniejący plik.
    created = [Path(o) for o in job.outputs if not Path(o).exists()]
    n = len(job.cmds) or 1
    try:
        for i, cmd in enumerate(job.cmds):
            frac0, span = i / n, 1 / n

            def cmd_cb(frac: float, frac0: float = frac0, span: float = span) -> None:
                if on_percent:
                    on_percent(frac0 + span * frac)

            _run_cmd(cmd, on_percent=cmd_cb, duration=job.duration, cancel=cancel)
        # ffmpeg -n przy istniejącym pliku kończy się kodem 0 („File exists. Exiting.”),
        # więc sukces potwierdzamy po plikach: nowe muszą powstać, stare nie są nadpisywane.
        for output in map(Path, job.outputs):
            if output not in created:
                raise RuntimeError(f"Plik wynikowy już istniał, nie nadpisano: {output}")
            if not output.exists():
                raise RuntimeError(f"ffmpeg nie utworzył pliku: {output}")
    except BaseException:
        for output in created:
            output.unlink(missing_ok=True)
        raise
    finally:
        for leftover in job.cleanup:
            p = Path(leftover)
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink(missing_ok=True)


def run_jobs(jobs: list, on_log: Callable[[str], None] | None = None,
             on_progress: Callable[[int, int], None] | None = None,
             on_percent: Callable[[float], None] | None = None,
             cancel: CancelToken | None = None) -> int:
    """Wykonaj listę Jobów. Zwraca liczbę zakończonych sukcesem.

    on_log(str)               — komunikaty (OK/BŁĄD/PRZERWANO) do logu UI/konsoli.
    on_progress(cur, total)   — ukończony job (numer, łączna liczba).
    on_percent(frac 0..1)     — łączny postęp przez wszystkie joby
                                (realny % wewnątrz joba, gdy znana długość).
    cancel                    — przerwanie: bieżący job jest kończony i sprzątany,
                                kolejne nie startują.
    """
    total = len(jobs) or 1
    ok = 0
    for idx, job in enumerate(jobs, start=1):
        off, span = (idx - 1) / total, 1 / total

        def job_cb(jfrac: float, off: float = off, span: float = span) -> None:
            if on_percent:
                on_percent(off + span * jfrac)

        try:
            run_job(job, on_percent=job_cb, cancel=cancel)
            ok += 1
            if on_log:
                on_log(f"OK:  {job.label}")
            _LOG.info("OK: %s", job.label)
        except Cancelled:
            if on_log:
                on_log(f"PRZERWANO: {job.label} (niedokończony plik usunięty)")
            _LOG.info("PRZERWANO: %s", job.label)
            break
        except Exception as exc:
            if on_log:
                on_log(f"BŁĄD: {job.label}\n      {exc}")
            _LOG.error("BŁĄD: %s — %s", job.label, exc)
        if on_progress:
            on_progress(idx, total)
        if on_percent:
            on_percent(off + span)  # job ukończony w 100%
    return ok
