---
name: linux-nemo
description: Integracja z Linuksem — akcje menu kontekstowego Nemo (*.nemo_action), cienkie front-endy bash z Zenity, linux/install.sh i wpis .desktop. Użyj przy każdej zmianie w linux/ albo w poleceniach uruchamiania GUI/CLI na Linuksie.
---

# Linux: Nemo i install.sh

Kontrakt: `docs/rewrite/spec.md`, sekcja 9.1 (CTX-L01…L08).

## Pliki

| plik | rola |
|---|---|
| `linux/install.sh` | zależności przez `apt`, linki `*.sh` do `~/.local/bin`, akcje do `~/.local/share/nemo/actions`, wpis `~/.local/share/applications/ffmpeg-convert-gui.desktop`, `nemo -q` |
| `VideoConvert`, `CompressImages`, `ImagesToVideo` `.nemo_action` | otwierają GUI z zaznaczonymi plikami (`__GUI__ %F`) |
| `ImageSplit`, `MakeFlipbook` `.nemo_action` | terminal → `split_image.sh` / `make_flipbook.sh` → Zenity → CLI `split` / `flipbook` |
| `images_to_video.sh` | niepodpięty pod żadną akcję (audit, sekcja 5) |

Placeholdery w akcjach rozwija `install.sh`: `__HOME__` → `$HOME`, `__GUI__` → polecenie GUI,
`__CLI__` → polecenie CLI.

## Format akcji Nemo

```ini
[Nemo Action]
Name=Konwertuj wideo (FFmpeg)
Comment=Otwórz GUI FFmpeg Convert z zaznaczonymi plikami
Exec=__GUI__ %F
Icon-Name=video-x-generic
Selection=Any
Extensions=mp4;MP4;mov;MOV;
```
`%F` = wszystkie zaznaczone pliki. `Extensions=dir;` dopasowuje foldery (brakuje akcji dla
folderów sekwencji, które Windows ma: A24). Rozszerzenia w obu wielkościach liter.

## Zasady

- **Bash tylko zbiera parametry** (Zenity) i woła CLI. Żadnych receptur ffmpeg w bashu.
- `set -euo pipefail`; każda wartość z Zenity walidowana (liczba ≥ 1, `WxH`); ścieżki zawsze w
  cudzysłowach; pliki przekazywane jako `"$@"`.
- W `Exec=` ścieżki ze spacją muszą być w cudzysłowach (składnia desktop entry), a wartości
  wstawiane przez `sed` escapowane (`&`, `|`, `\`). Dziś tego brakuje (A24).
- `nemo -q` zamyka otwarte okna Nemo: zapytaj albo poinformuj przed wykonaniem.
- Komunikaty po polsku, krótkie; błąd pokazuj w Zenity, a nie tylko w terminalu.

## Sprawdzanie

```bash
bash -n linux/*.sh
shellcheck linux/*.sh                       # jeśli dostępny
# podgląd wygenerowanych akcji bez instalacji (install.sh woła apt i nemo -q):
for a in linux/*.nemo_action; do sed -e "s|__HOME__|$HOME|g" -e "s|__GUI__|python3 $PWD/app/gui.py|g" \
  -e "s|__CLI__|python3 $PWD/app/cli.py|g" "$a"; echo; done
desktop-file-validate ~/.local/share/applications/ffmpeg-convert-gui.desktop   # po instalacji, jeśli dostępny
```
Ręcznie w Nemo: prawy klik na wideo, obrazie, jednej klatce i folderze; ścieżka instalacji ze
spacją; klatki ze spacją i apostrofem w nazwie.

## Zmiany w v2 (D1, D5)

venv `~/.local/share/ffmpeg_convert/venv` z pakietem (PySide6); `apt` instaluje tylko `ffmpeg`,
`zenity`, `python3-venv`, `libegl1`; `Exec=` wskazuje `…/venv/bin/ffmpeg-convert-gui %F` i
`ffmpeg-convert`; nowa akcja dla folderów; skrypt deinstalacji; runtime audio przeniesiony z
`<repo>/.audio-runtime` do katalogu danych przez `mv` na tym samym dysku.
