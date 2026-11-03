---
name: release
description: Wydanie wersji ffmpeg_convert — numer wersji, CHANGELOG, tag vX.Y.Z i GitHub release, z którego korzysta sprawdzanie aktualizacji (app/update.py). Użyj, gdy użytkownik prosi o wydanie, tag albo release.
---

# Wydanie

Tag, push na `master` i release to działania na zewnątrz: wykonuj je tylko na wyraźną prośbę
użytkownika, po pokazaniu mu planu.

## Jak działa sprawdzanie aktualizacji

`app/update.py` pyta `https://api.github.com/repos/wesol4/ffmpeg_convert/releases/latest` i
porównuje `tag_name` z `app.__version__` po cyfrach (`v1.2.3` → `(1, 2, 3)`). `releases/latest`
**pomija drafty i pre-release**: użytkownicy dostaną powiadomienie tylko o opublikowanym, zwykłym
release. Sam tag bez release nie wystarczy.

## Kroki

1. **Wersja (SemVer)** w `app/__init__.py` (`__version__`); w v2 jedno źródło w
   `pyproject.toml` (D5). Zmiana zachowania CLI lub wyniku → minor albo major.
2. **`CHANGELOG.md`** (format Keep a Changelog, po polsku): `## [X.Y.Z] - RRRR-MM-DD` z sekcjami
   „Dodane”, „Zmienione”, „Naprawione”, „Usunięte”. Zmiany zachowania (D14: nadpisywanie, kody
   wyjścia, fps NTSC, nowe flagi) zawsze w „Zmienione” z instrukcją dla skryptów.
3. **Walidacja** na czystym checkout:
   ```bash
   venv/bin/ruff check . && venv/bin/mypy app && QT_QPA_PLATFORM=offscreen venv/bin/python -m pytest -q
   ```
   CI zielone na Linux i Windows.
4. **Merge do `master`** przez PR (tytuł `Release vX.Y.Z`).
5. **Tag na `master`**:
   ```bash
   git tag -a vX.Y.Z -m "ffmpeg_convert X.Y.Z"
   git push origin vX.Y.Z
   ```
6. **GitHub release** z notatkami z CHANGELOG (nie jako pre-release):
   ```bash
   gh release create vX.Y.Z --title "ffmpeg_convert X.Y.Z" --notes-file notes.md
   ```
   albo przez stronę repozytorium. Bez załączników z mediami, modelami i runtime'em.
7. **Sprawdzenie**: `python app/cli.py update` na starszej wersji pokazuje nową; na nowej
   „Masz najnowszą wersję”.

## Po wydaniu

Windows: użytkownik pobiera repo i klika „Zainstaluj / aktualizuj” w `win/setup.vbs` (model audio
zostaje). Linux: `git pull` i `bash linux/install.sh`. Jeśli zmieniła się struktura pakietu albo
polecenia menu, napisz to w notatkach.
