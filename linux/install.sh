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

# GUI Convert — aplikacja z drag&drop (PyQt5)
echo "► Konfiguruję GUI Convert..."
chmod +x "$REPO_DIR/gui_convert.py"

if ! python3 -c "from PyQt5 import QtWidgets" &>/dev/null; then
    echo "  Brakuje PyQt5 — instaluję: sudo apt install python3-pyqt5"
    sudo apt install -y python3-pyqt5
fi

APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"
cat > "$APPS_DIR/ffmpeg-convert-gui.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=FFmpeg Convert
Comment=Konwersja i kompresja obrazów oraz wideo (drag & drop)
Exec=$REPO_DIR/gui_convert.py
Icon=applications-multimedia
Terminal=false
Categories=AudioVideo;Utility;
StartupNotify=true
EOF
update-desktop-database "$APPS_DIR" 2>/dev/null || true
echo "  $APPS_DIR/ffmpeg-convert-gui.desktop"

# restart Nemo
echo "► Restartuję Nemo..."
nemo -q 2>/dev/null || true

echo ""
echo "=== Gotowe! ==="
