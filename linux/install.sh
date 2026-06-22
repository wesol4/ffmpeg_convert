#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"           # .../linux
APP_DIR="$(cd "$REPO_DIR/../app" && pwd)"           # .../app  (wspólny rdzeń)
BIN_DIR="$HOME/.local/bin"
NEMO_DIR="$HOME/.local/share/nemo/actions"

echo "=== ffmpeg_convert — instalacja ==="

# zależności
echo "► Sprawdzam zależności..."
missing=()
command -v ffmpeg &>/dev/null || missing+=(ffmpeg)
command -v zenity &>/dev/null || missing+=(zenity)
python3 -c "from PyQt5 import QtWidgets" &>/dev/null || missing+=(python3-pyqt5)

if [ ${#missing[@]} -gt 0 ]; then
    echo "  Brakuje: ${missing[*]}"
    echo "  Instaluję: sudo apt install ${missing[*]}"
    sudo apt install -y "${missing[@]}"
else
    echo "  OK (ffmpeg, zenity, PyQt5)"
fi

# symlinki do narzędzi bash (zenity front-endy: sekwencja, split, flipbook)
echo "► Tworzę symlinki w $BIN_DIR..."
mkdir -p "$BIN_DIR"
for script in "$REPO_DIR"/*.sh; do
    name=$(basename "$script")
    [ "$name" = "install.sh" ] && continue
    chmod +x "$script"
    ln -sf "$script" "$BIN_DIR/$name"
    echo "  $BIN_DIR/$name → $script"
done
chmod +x "$APP_DIR/cli.py" "$APP_DIR/gui.py"

# akcje Nemo — rozwijamy placeholdery do realnych ścieżek tego użytkownika:
#   __HOME__ → $HOME (narzędzia bash w ~/.local/bin)
#   __GUI__  → uruchomienie wspólnego GUI
#   __CLI__  → uruchomienie wspólnego CLI
echo "► Kopiuję akcje Nemo do $NEMO_DIR..."
mkdir -p "$NEMO_DIR"
for action in "$REPO_DIR"/*.nemo_action; do
    sed -e "s|__HOME__|$HOME|g" \
        -e "s|__GUI__|python3 $APP_DIR/gui.py|g" \
        -e "s|__CLI__|python3 $APP_DIR/cli.py|g" \
        "$action" > "$NEMO_DIR/$(basename "$action")"
    echo "  $(basename "$action")"
done

# Skrót aplikacji w menu
echo "► Konfiguruję skrót GUI Convert..."
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"
cat > "$APPS_DIR/ffmpeg-convert-gui.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=FFmpeg Convert
Comment=Konwersja i kompresja obrazów oraz wideo (drag & drop)
Exec=python3 $APP_DIR/gui.py %F
Icon=applications-multimedia
Terminal=false
Categories=AudioVideo;Utility;
StartupNotify=true
EOF
update-desktop-database "$APPS_DIR" 2>/dev/null || true
echo "  $APPS_DIR/ffmpeg-convert-gui.desktop"

echo "► Restartuję Nemo..."
nemo -q 2>/dev/null || true

echo ""
echo "=== Gotowe! ==="
