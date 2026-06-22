#!/usr/bin/env bash
# Cienki front-end: zbiera FPS i format przez zenity, a samą konwersję wykonuje
# wspólny rdzeń (app/cli.py seq) — ta sama receptura, co GUI. Dzięki temu nie ma
# już zdublowanej logiki ffmpeg ani dawnego błędu z gubieniem klatek.
set -e

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
CLI="$SCRIPT_DIR/../app/cli.py"

if [ $# -eq 0 ]; then
  zenity --error --text="Nie zaznaczono plików."
  exit 1
fi

FPS=$(zenity --list --radiolist \
  --title="Klatki na sekundę" \
  --column="" --column="FPS" \
  TRUE  "24 fps (film)" \
  FALSE "25 fps (PAL)" \
  FALSE "30 fps (video)" \
  FALSE "60 fps (płynne)" \
  --height=260 --width=320) || exit 0

case "$FPS" in
  24*) fps=24 ;;
  25*) fps=25 ;;
  30*) fps=30 ;;
  60*) fps=60 ;;
  *) exit 0 ;;
esac

FORMAT=$(zenity --list --radiolist \
  --title="Format wyjściowy" \
  --column="" --column="Format" \
  TRUE  "MP4 H.264" \
  FALSE "MP4 H.265" \
  FALSE "ProRes 422 HQ" \
  FALSE "DNxHD 1080p" \
  --height=260 --width=320) || exit 0

case "$FORMAT" in
  "MP4 H.264")      fmt=h264 ;;
  "MP4 H.265")      fmt=h265 ;;
  "ProRes 422 HQ")  fmt=prores ;;
  "DNxHD 1080p")    fmt=dnxhd ;;
  *) exit 0 ;;
esac

python3 "$CLI" seq --fps "$fps" --format "$fmt" "$@"

zenity --info --title="Gotowe" --text="Utworzono wideo z $# klatek (${fps} fps, ${FORMAT})."
