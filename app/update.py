"""Sprawdzanie aktualizacji przez GitHub API (stdlib urllib, bez zależności).

Bez cichego auto-pull/auto-overwrite: tylko powiadamia o dostępnej wersji.
Wymaga opublikowanego Release/Tagu na GitHub (releases/latest); bez niego
zwraca komunikat „nie udało się”.
"""
from __future__ import annotations

import json
import urllib.request

from app.log import get_logger

REPO = "wesol4/ffmpeg_convert"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
_LOG = get_logger()


def _normalize(version: str) -> tuple:
    """'v1.2.3' → (1, 2, 3); cyfry z каждого segmentu, brakujące = 0."""
    v = version.lstrip("vV")
    parts = []
    for seg in v.split("."):
        digits = "".join(ch for ch in seg if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def fetch_latest_version(url: str = API_URL, timeout: float = 5.0) -> str | None:
    """Tag najnowszego release'u (np. 'v1.2.3') lub None (brak sieci/release)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ffmpeg-convert"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tag = data.get("tag_name")
        return tag if isinstance(tag, str) else None
    except Exception as exc:  # noqa: BLE001 — diagnostyka: każda awaria sieciowa
        _LOG.warning("sprawdzenie aktualizacji nie powiodło się: %s", exc)
        return None


def check_for_updates(current: str, url: str = API_URL) -> tuple:
    """Zwraca (has_update, latest_version, komunikat).

    latest_version may be None, gdy nie udało się pobrać.
    """
    latest = fetch_latest_version(url)
    if not latest:
        return (False, None, "Nie udało się sprawdzić aktualizacji "
                             "(brak sieci, rate-limit GitHub lub brak opublikowanego release'u).")
    if _normalize(latest) > _normalize(current):
        return (True, latest, f"Dostępna nowa wersja: {latest} (masz {current}).")
    return (False, latest, f"Masz najnowszą wersję ({current}).")
