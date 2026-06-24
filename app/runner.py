#!/usr/bin/env python3
"""Wspólne uruchamianie Jobów (z presets.py) — używane przez CLI i GUI.

Każdy Job to lista komend FFmpeg wykonywanych po kolei. Specjalna komenda
["__copy__", src, dst] kopiuje plik bez przekodowania (tryb „zachowaj oryginał").

Postęp wewnątrz joba: stderr ffmpeg jest strumieniowane i parsowane
(out_time_us / out_time= / out_time_ms) — przy znanej długości (Job.duration)
wywoływany jest on_percent(frac 0..1) dla bieżącego joba, a run_jobs mapuje
to na postęp łączny przez wszystkie joby. Dzięki temu pasek GUI pokazuje
realny procent, a nie tylko liczbę ukończonych jobów (ważne przy 2-pass
i dużych plikach).
"""
from __future__ import annotations

import re
import shutil
import subprocess
from collections import deque
from pathlib import Path
from typing import Callable

from app.core.jobs import Job

_OUT_US = re.compile(r"out_time_us=(\d+)")
_OUT_MS = re.compile(r"out_time_ms=(\d+)")        # legacy, wartość w mikrosekundach
_OUT_T = re.compile(r"out_time=(\d+):(\d+):(\d+(?:\.\d+)?)")


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


def _run_cmd(cmd: list, on_percent: Callable[[float], None] | None = None,
             duration: float | None = None) -> None:
    """Wykonaj jedną komendę; przy błędzie podnieś wyjątek z ogonem stderr.

    on_percent(frac) — frac w [0,1] postępu tej komendy (wymaga duration > 0
    i linii out_time na stderr; inaczej zgłoszony tylko 1.0 po zakończeniu).
    """
    if cmd and cmd[0] == "__copy__":
        shutil.copy2(cmd[1], cmd[2])
        if on_percent:
            on_percent(1.0)
        return
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            text=True, bufsize=1)
    last: deque[str] = deque(maxlen=5)
    stream = proc.stderr
    try:
        if stream is not None:
            for line in stream:
                line = line.rstrip()
                if line:
                    last.append(line)
                us = _out_time_us(line)
                if us is not None and duration and duration > 0 and on_percent:
                    on_percent(min(1.0, us / (duration * 1_000_000)))
    finally:
        if stream is not None:
            stream.close()
    proc.wait()
    if on_percent:
        on_percent(1.0)  # ta komenda ukończona (nawet bez linii postępu)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg zwrócił kod {proc.returncode}:\n" + "\n".join(last))


def run_job(job: Job, on_percent: Callable[[float], None] | None = None) -> None:
    """Wykonaj pojedynczy Job: mkdir → komendy (z postępem) → cleanup.

    on_percent(job_frac) — job_frac w [0,1] dla tego joba, mapowane z per-cmd
    udziałów (komendy w jobu ważone równo).
    """
    if job.mkdir is not None:
        job.mkdir.mkdir(parents=True, exist_ok=True)
    n = len(job.cmds) or 1
    try:
        for i, cmd in enumerate(job.cmds):
            frac0, span = i / n, 1 / n

            def cmd_cb(frac: float, frac0: float = frac0, span: float = span) -> None:
                if on_percent:
                    on_percent(frac0 + span * frac)

            _run_cmd(cmd, on_percent=cmd_cb, duration=job.duration)
    finally:
        for leftover in job.cleanup:
            p = Path(leftover)
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink(missing_ok=True)


def run_jobs(jobs: list, on_log: Callable[[str], None] | None = None,
             on_progress: Callable[[int, int], None] | None = None,
             on_percent: Callable[[float], None] | None = None) -> int:
    """Wykonaj listę Jobów. Zwraca liczbę zakończonych sukcesem.

    on_log(str)               — komunikaty (OK/BŁĄD) do logu UI/konsoli.
    on_progress(cur, total)   — ukończony job (numer, łączna liczba).
    on_percent(frac 0..1)     — łączny postęp przez wszystkie joby
                                (realny % wewnątrz joba, gdy znana długość).
    """
    total = len(jobs) or 1
    ok = 0
    for idx, job in enumerate(jobs, start=1):
        off, span = (idx - 1) / total, 1 / total

        def job_cb(jfrac: float, off: float = off, span: float = span) -> None:
            if on_percent:
                on_percent(off + span * jfrac)

        try:
            run_job(job, on_percent=job_cb)
            ok += 1
            if on_log:
                on_log(f"OK:  {job.label}")
        except Exception as exc:
            if on_log:
                on_log(f"BŁĄD: {job.label}\n      {exc}")
        if on_progress:
            on_progress(idx, total)
        if on_percent:
            on_percent(off + span)  # job ukończony w 100%
    return ok