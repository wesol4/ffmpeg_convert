#!/usr/bin/env bash
set -e

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

# posortowane pliki → lista dla concat
tmplist=$(mktemp /tmp/ffmpeg_seq.XXXXXX.txt)
printf '%s\n' "$@" | sort | while read -r f; do
  echo "file '$f'"
done > "$tmplist"

DIR=$(dirname "$(printf '%s\n' "$@" | sort | head -1)")
NAME=$(basename "$DIR")
[ "$NAME" = "." ] && NAME="output"

# szukaj audio o tej samej nazwie co folder
AUDIO=""
audio_info=""
for ext in wav mp4; do
  candidate="$DIR/${NAME}.$ext"
  if [ -f "$candidate" ]; then
    AUDIO="$candidate"
    audio_info=" + audio: $(basename "$candidate")"
    break
  fi
done

audio_flags() {
  local codec="$1"
  if [ -n "$AUDIO" ]; then
    echo "-i \"$AUDIO\" -c:a $codec"
  fi
}

case "$FORMAT" in
  "MP4 H.264")
    OUT="$DIR/${NAME}.mp4"
    ffmpeg -y -f concat -safe 0 -i "$tmplist" \
      ${AUDIO:+-i "$AUDIO"} \
      -framerate "$fps" \
      -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p \
      ${AUDIO:+-c:a aac -b:a 192k} \
      "$OUT" -loglevel error
    ;;
  "MP4 H.265")
    OUT="$DIR/${NAME}.mp4"
    ffmpeg -y -f concat -safe 0 -i "$tmplist" \
      ${AUDIO:+-i "$AUDIO"} \
      -framerate "$fps" \
      -c:v libx265 -crf 23 -preset medium -pix_fmt yuv420p \
      ${AUDIO:+-c:a aac -b:a 192k} \
      "$OUT" -loglevel error
    ;;
  "ProRes 422 HQ")
    OUT="$DIR/${NAME}.mov"
    ffmpeg -y -f concat -safe 0 -i "$tmplist" \
      ${AUDIO:+-i "$AUDIO"} \
      -framerate "$fps" \
      -c:v prores_ks -profile:v 3 -pix_fmt yuv422p10le \
      ${AUDIO:+-c:a pcm_s16le} \
      "$OUT" -loglevel error
    ;;
  "DNxHD 1080p")
    OUT="$DIR/${NAME}.mov"
    ffmpeg -y -f concat -safe 0 -i "$tmplist" \
      ${AUDIO:+-i "$AUDIO"} \
      -framerate "$fps" \
      -vf scale=1920:1080 \
      -c:v dnxhd -b:v 120M -pix_fmt yuv422p \
      ${AUDIO:+-c:a pcm_s16le} \
      "$OUT" -loglevel error
    ;;
esac

rm -f "$tmplist"

zenity --info --title="Gotowe" \
  --text="Utworzono wideo z $# klatek${audio_info}:\n$OUT"
