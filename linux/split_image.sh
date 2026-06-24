#!/usr/bin/env bash
# Cienki front-end: zbiera siatkę X×Y przez zenity, podział wykonuje wspólny
# rdzeń (app/cli.py split) — ta sama receptura, co reszta front-endów.
set -euo pipefail

CLI="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)/../app/cli.py"

(( $# >= 1 )) || { zenity --error --text="Zaznacz co najmniej jeden plik."; exit 1; }

GRID=$(zenity --forms \
  --title="Split obrazu na siatkę" \
  --text="Ustaw liczbę podziałów" \
  --add-entry="Ile części w poziomie (X)" \
  --add-entry="Ile części w pionie (Y)" \
  --separator="," ) || exit 1

IFS=',' read -r GRID_X GRID_Y <<< "$GRID"

[[ "$GRID_X" =~ ^[0-9]+$ ]] || { zenity --error --text="X musi być liczbą"; exit 1; }
[[ "$GRID_Y" =~ ^[0-9]+$ ]] || { zenity --error --text="Y musi być liczbą"; exit 1; }
(( GRID_X >= 1 )) || { zenity --error --text="X musi być ≥ 1"; exit 1; }
(( GRID_Y >= 1 )) || { zenity --error --text="Y musi być ≥ 1"; exit 1; }

python3 "$CLI" split --cols "$GRID_X" --rows "$GRID_Y" "$@"

zenity --info --text="Split zakończony!"