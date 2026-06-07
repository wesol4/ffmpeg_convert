#!/usr/bin/env bash
set -e

trap 'echo; echo "=== BŁĄD (linia $LINENO) ==="; read -p "Naciśnij ENTER aby zamknąć..."' ERR

PRESET=$(zenity --list --radiolist \
  --title="Konwersja wideo" \
  --column="" --column="Preset" \
  TRUE  "MP4 (H.264 High Quality)" \
  FALSE "MP4 (H.265 HEVC)" \
  FALSE "DNxHD 1080p" \
  FALSE "ProRes 422 HQ" \
  FALSE "Cineform Q4 (10-bit)" \
  FALSE "Ostatnia klatka PNG" \
  FALSE "Eksport klatek + WAV" \
  --height=430 --width=450) || exit 0

# nazwa podfolderu przy batch (>1 plik)
case "$PRESET" in
  "MP4 (H.264 High Quality)") SUBFOLDER="H264" ;;
  "MP4 (H.265 HEVC)")         SUBFOLDER="HEVC" ;;
  "DNxHD 1080p")              SUBFOLDER="DNxHD" ;;
  "ProRes 422 HQ")            SUBFOLDER="ProRes" ;;
  "Cineform Q4 (10-bit)")     SUBFOLDER="Cineform" ;;
  *)                          SUBFOLDER="" ;;
esac

for SRC in "$@"; do
  [ -f "$SRC" ] || continue

  DIR=$(dirname "$SRC")
  BASE=$(basename "${SRC%.*}")

  # podfolder tylko przy batch i presetach z pojedynczym plikiem wyjściowym
  if [ $# -gt 1 ] && [ -n "$SUBFOLDER" ]; then
    OUTDIR="$DIR/$SUBFOLDER"
    mkdir -p "$OUTDIR"
  else
    OUTDIR="$DIR"
  fi

  if [ "$PRESET" = "MP4 (H.264 High Quality)" ]; then
    ffmpeg -y -i "$SRC" \
      -c:v libx264 -crf 18 -preset slow \
      -pix_fmt yuv420p \
      -c:a aac -b:a 192k \
      "$OUTDIR/${BASE}_H264.mp4"

  elif [ "$PRESET" = "MP4 (H.265 HEVC)" ]; then
    ffmpeg -y -i "$SRC" \
      -c:v libx265 -crf 23 -preset medium \
      -pix_fmt yuv420p \
      -c:a aac -b:a 192k \
      "$OUTDIR/${BASE}_HEVC.mp4"

  elif [ "$PRESET" = "DNxHD 1080p" ]; then
    ffmpeg -y -i "$SRC" \
      -vf scale=1920:1080 \
      -c:v dnxhd -b:v 120M -pix_fmt yuv422p \
      -c:a pcm_s16le \
      "$OUTDIR/${BASE}_DNxHD.mov"

  elif [ "$PRESET" = "ProRes 422 HQ" ]; then
    ffmpeg -y -i "$SRC" \
      -c:v prores_ks -profile:v 3 -pix_fmt yuv422p10le \
      -c:a pcm_s16le \
      "$OUTDIR/${BASE}_PR.mov"

  elif [ "$PRESET" = "Cineform Q4 (10-bit)" ]; then
    ffmpeg -y -i "$SRC" \
      -c:v cfhd -quality 4 -pix_fmt yuv422p10le \
      -c:a pcm_s16le \
      "$OUTDIR/${BASE}_CF.mov"

  elif [ "$PRESET" = "Ostatnia klatka PNG" ]; then
    ffmpeg -y -sseof -1 -i "$SRC" -update 1 \
      "$OUTDIR/${BASE}_last.png"

  elif [ "$PRESET" = "Eksport klatek + WAV" ]; then
    FORMAT=$(zenity --list --radiolist \
      --title="Format klatek" \
      --column="" --column="Format" \
      TRUE  "PNG" \
      FALSE "JPG" \
      FALSE "EXR" \
      --height=250 --width=300) || exit 0

    FRAMESDIR="$DIR/$BASE"
    mkdir -p "$FRAMESDIR"

    if [ "$FORMAT" = "PNG" ]; then
      ffmpeg -y -i "$SRC" "$FRAMESDIR/${BASE}_%04d.png"
    elif [ "$FORMAT" = "JPG" ]; then
      ffmpeg -y -i "$SRC" "$FRAMESDIR/${BASE}_%04d.jpg"
    else
      ffmpeg -y -i "$SRC" "$FRAMESDIR/${BASE}_%04d.exr"
    fi

    ffmpeg -y -i "$SRC" -vn -acodec pcm_s24le \
      "$FRAMESDIR/${BASE}.wav"
  fi

done

zenity --info --text="Gotowe!"
