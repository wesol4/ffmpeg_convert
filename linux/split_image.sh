#!/usr/bin/env bash
set -euo pipefail

LOG="/tmp/split_image_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
trap 'zenity --error --text="Błąd splitowania.\nLog: $LOG"' ERR

# okno z DWOMA polami
GRID=$(zenity --forms \
  --title="Split obrazu na siatkę" \
  --text="Ustaw liczbę podziałów" \
  --add-entry="Ile części w poziomie (X)" \
  --add-entry="Ile części w pionie (Y)" \
  --separator="," ) || exit 1

IFS=',' read -r GRID_X GRID_Y <<< "$GRID"

# walidacja liczb
[[ "$GRID_X" =~ ^[0-9]+$ ]] || { zenity --error --text="X musi być liczbą"; exit 1; }
[[ "$GRID_Y" =~ ^[0-9]+$ ]] || { zenity --error --text="Y musi być liczbą"; exit 1; }

(( GRID_X >= 1 )) || { zenity --error --text="X musi być ≥ 1"; exit 1; }
(( GRID_Y >= 1 )) || { zenity --error --text="Y musi być ≥ 1"; exit 1; }

(( $# > 1 )) && MULTI=1 || MULTI=0

for SRC in "$@"; do
  [[ -f "$SRC" ]] || continue

  DIR=$(dirname "$SRC")
  BASE=$(basename "${SRC%.*}")

  if [[ $MULTI -eq 1 ]]; then
      OUTDIR="$DIR/SplitGrid"; mkdir -p "$OUTDIR"
  else
      OUTDIR="$DIR"
  fi

  # pobranie wymiarów obrazu
  INFO=$(ffprobe -v error -show_entries stream=width,height \
        -of csv=p=0 "$SRC" | head -n1)

  IFS=',' read -r W H <<< "$INFO"

  TILE_W=$(( W / GRID_X ))
  TILE_H=$(( H / GRID_Y ))

  for (( y=0; y<GRID_Y; y++ )); do
    for (( x=0; x<GRID_X; x++ )); do

      CW=$(( x == GRID_X-1 ? W - x*TILE_W : TILE_W ))
      CH=$(( y == GRID_Y-1 ? H - y*TILE_H : TILE_H ))

      OUT="${OUTDIR}/${BASE}_${y}_${x}.png"

      ffmpeg -hide_banner -y -i "$SRC" \
        -vf "crop=${CW}:${CH}:$((x*TILE_W)):$((y*TILE_H))" \
        "$OUT"
    done
  done
done

zenity --info --text="Split zakończony!\nLog: $LOG"


