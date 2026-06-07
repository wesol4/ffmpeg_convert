#!/usr/bin/env bash
set -e

QUAL=$(zenity --list --radiolist \
  --title="Jakość JPEG" \
  --column="" --column="Jakość" \
  TRUE  "Q2  (~94%, najlepsza)" \
  FALSE "Q5  (~85%, dobra)" \
  FALSE "Q10 (~70%, mała waga)" \
  FALSE "Bez kompresji (maks. jakość JPG)" \
  FALSE "Zachowaj oryginał (bez konwersji, np. PNG/EXR)" \
  --height=290 --width=380) || exit 0

KEEP_ORIGINAL=0
case "$QUAL" in
  Q2*) q=2 ;;
  Q5*) q=5 ;;
  Q10*) q=10 ;;
  "Bez kompresji"*) q=1 ;;
  "Zachowaj oryginał"*) KEEP_ORIGINAL=1 ;;
  *) exit 0 ;;
esac

# zbierz pliki pasujące do wybranych ustawień (raz — kolejność i rozszerzenie wyjściowe są stałe)
declare -a SRC_LIST OUT_EXT_LIST

for SRC in "$@"; do
  [ -f "$SRC" ] || continue

  if [ "$KEEP_ORIGINAL" = "0" ]; then
    [[ "${SRC,,}" == *.png ]] || { echo "Pomijam: $SRC"; continue; }
  fi

  SRC_NAME=$(basename "$SRC")
  SRC_EXT="${SRC_NAME##*.}"

  if [ "$KEEP_ORIGINAL" = "1" ]; then
    OUT_EXT="$SRC_EXT"
  else
    OUT_EXT="jpg"
  fi

  SRC_LIST+=("$SRC")
  OUT_EXT_LIST+=("$OUT_EXT")
done

[ ${#SRC_LIST[@]} -eq 0 ] && { zenity --error --title="Brak plików" --text="Żaden z zaznaczonych plików nie pasuje do wybranych ustawień."; exit 0; }

# zenity nie potrafi pokazać podglądu na żywo podczas pisania — zamiast tego
# wpisana nazwa jest od razu rozwijana na pełną listę i pokazana do akceptacji;
# "Zmień nazwę" wraca do pola z poprzednio wpisaną wartością do poprawy
NEWNAME=""
declare -a BASE_LIST

while true; do
  NEWNAME=$(zenity --entry \
    --title="Zmiana nazwy" \
    --text="Nowa nazwa bazowa plików (puste = zachowaj oryginalne nazwy).\nPliki zostaną ponumerowane, np. nazwa_001.jpg" \
    --entry-text="$NEWNAME") || exit 0

  BASE_LIST=()
  preview=""
  for i in "${!SRC_LIST[@]}"; do
    SRC_NAME=$(basename "${SRC_LIST[$i]}")
    if [ -n "$NEWNAME" ]; then
      BASE=$(printf "%s_%03d" "$NEWNAME" "$((i + 1))")
    else
      BASE="${SRC_NAME%.*}"
    fi
    BASE_LIST+=("$BASE")
    preview+="${SRC_NAME}  →  ${BASE}.${OUT_EXT_LIST[$i]}\n"
  done

  zenity --question \
    --title="Podgląd nazw" \
    --text="Pliki zostaną zapisane jako:\n\n${preview}\nKontynuować z tą nazwą?" \
    --ok-label="Kontynuuj" --cancel-label="Zmień nazwę" \
    --width=420 --height=420 && break
done

zenity --question \
  --title="Gdzie zapisać?" \
  --text="Zapisać pliki w podfolderze 'compressed'?" \
  --ok-label="Podfolder" --cancel-label="Obok oryginału" && USE_SUBDIR=1 || USE_SUBDIR=0

count=0
log=""

for i in "${!SRC_LIST[@]}"; do
  SRC="${SRC_LIST[$i]}"
  BASE="${BASE_LIST[$i]}"
  OUT_EXT="${OUT_EXT_LIST[$i]}"
  DIR=$(dirname "$SRC")

  if [ "$USE_SUBDIR" = "1" ]; then
    mkdir -p "$DIR/compressed"
    OUT="$DIR/compressed/${BASE}.${OUT_EXT}"
  else
    OUT="$DIR/${BASE}.${OUT_EXT}"
  fi

  if [ "$SRC" -ef "$OUT" ]; then
    echo "Pomijam (brak zmian): $SRC"
    continue
  fi

  orig=$(du -k "$SRC" | cut -f1)

  if [ "$KEEP_ORIGINAL" = "1" ]; then
    cp -p "$SRC" "$OUT"
  else
    ffmpeg -y -i "$SRC" -q:v "$q" -vf "format=yuvj420p" "$OUT" -loglevel error
  fi

  comp=$(du -k "$OUT" | cut -f1)

  echo "$BASE: ${orig}KB → ${comp}KB"
  log+="$BASE: ${orig}KB → ${comp}KB\n"
  count=$((count + 1))
done

zenity --info --title="Gotowe" \
  --text="Przetworzono $count plików:\n\n${log}"
