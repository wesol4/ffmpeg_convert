#!/usr/bin/env bash
set -euo pipefail

LOG="/tmp/make_flipbook_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
trap 'zenity --error --text="Błąd tworzenia flipbooka.\nLog: $LOG"' ERR

(( $# >= 1 )) || { zenity --error --text="Zaznacz co najmniej jeden plik."; exit 1; }

# sortuj alfabetycznie (numerycznie dla sekwencji)
mapfile -t FILES < <(printf '%s\n' "$@" | sort)
COUNT=${#FILES[@]}

# auto-siatka: szerokość POT, minimalne puste miejsca
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
AUTO_WASTE=$(( AUTO_COLS * AUTO_ROWS - COUNT ))

# wykryj rozdzielczość kafelka z pierwszego pliku
INFO=$(ffprobe -v error -show_entries stream=width,height \
      -of csv=p=0 "${FILES[0]}" | head -n1)
IFS=',' read -r TILE_W TILE_H <<< "$INFO"

PARAMS=$(zenity --forms \
  --title="Utwórz flipbook (spritesheet)" \
  --text="Znaleziono <b>${COUNT} klatek</b> · oryginał ${TILE_W}×${TILE_H} px
Auto-siatka: ${AUTO_COLS}×${AUTO_ROWS} (puste: ${AUTO_WASTE})" \
  --add-entry="Kolumny (auto: ${AUTO_COLS})" \
  --add-entry="Wiersze  (auto: ${AUTO_ROWS})" \
  --add-entry="Rozdzielczość kafelka (auto: ${TILE_W}x${TILE_H})" \
  --separator=",") || exit 1

IFS=',' read -r IN_COLS IN_ROWS IN_TILE <<< "$PARAMS"

COLS=${IN_COLS:-$AUTO_COLS}
ROWS=${IN_ROWS:-$AUTO_ROWS}
IN_TILE=${IN_TILE:-"${TILE_W}x${TILE_H}"}

[[ "$COLS" =~ ^[0-9]+$ ]]  || { zenity --error --text="Kolumny muszą być liczbą"; exit 1; }
[[ "$ROWS" =~ ^[0-9]+$ ]]  || { zenity --error --text="Wiersze muszą być liczbą"; exit 1; }
[[ "$IN_TILE" =~ ^[0-9]+x[0-9]+$ ]] || { zenity --error --text="Rozdzielczość musi być w formacie WxH (np. 128x128)"; exit 1; }

(( COLS >= 1 && ROWS >= 1 )) || { zenity --error --text="Wartości muszą być ≥ 1"; exit 1; }

OUT_TILE_W=${IN_TILE%x*}
OUT_TILE_H=${IN_TILE#*x}

# skalowanie tylko jeśli rozmiar się zmienił
if (( OUT_TILE_W == TILE_W && OUT_TILE_H == TILE_H )); then
    VF="tile=${COLS}x${ROWS}"
else
    VF="scale=${OUT_TILE_W}:${OUT_TILE_H},tile=${COLS}x${ROWS}"
fi

# folder i nazwa wyjściowa — obok pierwszego pliku
DIR=$(dirname "${FILES[0]}")
BASE=$(basename "${FILES[0]}")
STEM=$(echo "${BASE%.*}" | sed 's/\.[0-9]\{3,\}$//' | sed 's/_[0-9]\{3,\}$//')
[[ -z "$STEM" ]] && STEM="flipbook"

OUT="${DIR}/${STEM}_flipbook_${COLS}x${ROWS}.png"

# lista plików dla concat demuxer
TMP_LIST=$(mktemp /tmp/flipbook_list_XXXXXX.txt)
trap 'rm -f "$TMP_LIST"' EXIT

for f in "${FILES[@]}"; do
    echo "file '${f}'" >> "$TMP_LIST"
done

ffmpeg -hide_banner -y \
  -f concat -safe 0 -i "$TMP_LIST" \
  -vf "$VF" \
  -frames:v 1 -update 1 \
  "$OUT"

TOTAL=$(( COLS * ROWS ))
EMPTY=$(( TOTAL - COUNT ))
OUT_W=$(( COLS * OUT_TILE_W ))
OUT_H=$(( ROWS * OUT_TILE_H ))
SIZE_KB=$(du -k "$OUT" | cut -f1)

zenity --info --text="Flipbook gotowy!

Plik:    $(basename "$OUT")
Wymiar:  ${OUT_W}×${OUT_H} px
Kafelek: ${OUT_TILE_W}×${OUT_TILE_H} px
Siatka:  ${COLS}×${ROWS} = ${TOTAL} slotów
Klatki:  ${COUNT} wypełnione · ${EMPTY} puste
Rozmiar: ${SIZE_KB} KB
Log: $LOG"
