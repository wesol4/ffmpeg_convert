#!/usr/bin/env bash
# Cienki front-end: auto-siatka i rozdzielczość kafelka służą tylko do
# prefille'owania okna zenity; spritesheet tworzy wspólny rdzeń
# (app/cli.py flipbook) — ta sama receptura, co reszta front-endów.
set -euo pipefail

CLI="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)/../app/cli.py"

(( $# >= 1 )) || { zenity --error --text="Zaznacz co najmniej jeden plik."; exit 1; }

# sortuj alfabetycznie (numerycznie dla sekwencji)
mapfile -t FILES < <(printf '%s\n' "$@" | sort)
COUNT=${#FILES[@]}

# auto-siatka: szerokość z kandydatów, minimalne puste miejsca
auto_grid() {
    local n=$1 best_cols=32 best_rows best_waste=9999
    best_rows=$(( (n + 31) / 32 ))
    best_waste=$(( 32 * best_rows - n ))
    for cols in 8 16 32 64; do
        local rows=$(( (n + cols - 1) / cols ))
        local waste=$(( cols * rows - n ))
        if (( waste < best_waste )); then
            best_waste=$waste; best_cols=$cols; best_rows=$rows
        fi
    done
    echo "${best_cols}x${best_rows}"
}

AUTO_GRID=$(auto_grid "$COUNT")
AUTO_COLS=${AUTO_GRID%x*}
AUTO_ROWS=${AUTO_GRID#*x}

# wykryj rozdzielczość kafelka z pierwszego pliku (tylko do podpowiedzi)
INFO=$(ffprobe -v error -show_entries stream=width,height \
      -of csv=p=0:s=x "${FILES[0]}" 2>/dev/null || true)
TILE_W=${INFO%x*}; TILE_H=${INFO#*x}
[[ -z "${TILE_W:-}" || -z "${TILE_H:-}" ]] && { TILE_W="?"; TILE_H="?"; }

PARAMS=$(zenity --forms \
  --title="Utwórz flipbook (spritesheet)" \
  --text="Znaleziono <b>${COUNT} klatek</b> · oryginał ${TILE_W}×${TILE_H} px
Auto-siatka: ${AUTO_COLS}×${AUTO_ROWS}" \
  --add-entry="Kolumny (auto: ${AUTO_COLS})" \
  --add-entry="Wiersze  (auto: ${AUTO_ROWS})" \
  --add-entry="Rozdzielczość kafelka (auto: ${TILE_W}x${TILE_H})" \
  --separator=",") || exit 1

IFS=',' read -r IN_COLS IN_ROWS IN_TILE <<< "$PARAMS"

COLS=${IN_COLS:-$AUTO_COLS}
ROWS=${IN_ROWS:-$AUTO_ROWS}

[[ "$COLS" =~ ^[0-9]+$ ]]  || { zenity --error --text="Kolumny muszą być liczbą"; exit 1; }
[[ "$ROWS" =~ ^[0-9]+$ ]]  || { zenity --error --text="Wiersze muszą być liczbą"; exit 1; }
(( COLS >= 1 && ROWS >= 1 )) || { zenity --error --text="Wartości muszą być ≥ 1"; exit 1; }

TILE_ARG=()
if [[ -n "${IN_TILE:-}" ]]; then
    [[ "$IN_TILE" =~ ^[0-9]+x[0-9]+$ ]] || { zenity --error --text="Rozdzielczość musi być WxH (np. 128x128)"; exit 1; }
    TILE_ARG=(--tile "$IN_TILE")
fi

python3 "$CLI" flipbook --cols "$COLS" --rows "$ROWS" "${TILE_ARG[@]}" "$@"

zenity --info --text="Flipbook gotowy!"