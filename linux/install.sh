#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="$HOME/.local/bin"
NEMO_DIR="$HOME/.local/share/nemo/actions"

echo "=== ffmpeg_convert — instalacja ==="

# zależności
echo "► Sprawdzam zależności..."
missing=()
command -v ffmpeg  &>/dev/null || missing+=(ffmpeg)
command -v zenity  &>/dev/null || missing+=(zenity)

if [ ${#missing[@]} -gt 0 ]; then
    echo "  Brakuje: ${missing[*]}"
    echo "  Instaluję: sudo apt install ${missing[*]}"
    sudo apt install -y "${missing[@]}"
else
    echo "  OK (ffmpeg, zenity)"
fi

# symlinki
echo "► Tworzę symlinki w $BIN_DIR..."
mkdir -p "$BIN_DIR"
for script in "$REPO_DIR"/*.sh; do
    name=$(basename "$script")
    ln -sf "$script" "$BIN_DIR/$name"
    chmod +x "$script"
    echo "  $BIN_DIR/$name → $script"
done

# akcje Nemo
echo "► Kopiuję akcje Nemo do $NEMO_DIR..."
mkdir -p "$NEMO_DIR"
for action in "$REPO_DIR"/*.nemo_action; do
    cp "$action" "$NEMO_DIR/"
    echo "  $(basename "$action")"
done

# restart Nemo
echo "► Restartuję Nemo..."
nemo -q 2>/dev/null || true

echo ""
echo "=== Gotowe! ==="
