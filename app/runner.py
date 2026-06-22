#!/usr/bin/env python3
"""Wspólne uruchamianie Jobów (z presets.py) — używane przez CLI i GUI.

Każdy Job to lista komend FFmpeg wykonywanych po kolei. Specjalna komenda
["__copy__", src, dst] kopiuje plik bez przekodowania (tryb „zachowaj oryginał").
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _run_cmd(cmd: list) -> None:
    """Wykonaj jedną komendę; przy błędzie podnieś wyjątek z ogonem stderr."""
    if cmd and cmd[0] == "__copy__":
        shutil.copy2(cmd[1], cmd[2])
        return
    result = subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        tail = (result.stderr or "").strip().splitlines()[-5:]
        raise RuntimeError(f"ffmpeg zwrócił kod {result.returncode}:\n" + "\n".join(tail))


def run_job(job) -> None:
    """Wykonaj pojedynczy Job: mkdir → komendy → cleanup."""
    if job.mkdir is not None:
        job.mkdir.mkdir(parents=True, exist_ok=True)
    try:
        for cmd in job.cmds:
            _run_cmd(cmd)
    finally:
        for leftover in job.cleanup:
            p = Path(leftover)
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink(missing_ok=True)


def run_jobs(jobs, on_log=None, on_progress=None) -> int:
    """Wykonaj listę Jobów. Zwraca liczbę zakończonych sukcesem.

    on_log(str)            — komunikaty (OK/BŁĄD) do logu UI/konsoli.
    on_progress(cur, total)— postęp (numer ukończonego joba, łączna liczba).
    """
    total = len(jobs)
    ok = 0
    for i, job in enumerate(jobs, start=1):
        try:
            run_job(job)
            ok += 1
            if on_log:
                on_log(f"OK:  {job.label}")
        except Exception as exc:
            if on_log:
                on_log(f"BŁĄD: {job.label}\n      {exc}")
        if on_progress:
            on_progress(i, total)
    return ok
