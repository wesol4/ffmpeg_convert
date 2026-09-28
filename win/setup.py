"""Per-user Windows installation, using the same app package as Linux."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import venv

REPO = Path(__file__).resolve().parents[1]
INSTALL = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "FFmpegConvert"
EXTENSIONS = ("mp4", "mov", "mkv", "avi", "webm", "m4v", "png", "jpg", "jpeg", "exr", "tif", "tiff", "webp")
REG_BASE = r"Software\Classes"


def run(args, **kwargs):
    kwargs.setdefault("creationflags", getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
    kwargs.setdefault("stdin", subprocess.DEVNULL)
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def python_path(windowed=False):
    return INSTALL / ".venv" / "Scripts" / ("pythonw.exe" if windowed else "python.exe")


def refresh_path():
    import winreg
    paths = [os.environ.get("PATH", "")]
    for hive, key in ((winreg.HKEY_CURRENT_USER, "Environment"),
                      (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")):
        try:
            with winreg.OpenKey(hive, key) as handle:
                paths.append(os.path.expandvars(winreg.QueryValueEx(handle, "Path")[0]))
        except OSError:
            pass
    paths.append(str(Path(os.environ["LOCALAPPDATA"]) / "Microsoft/WinGet/Links"))
    os.environ["PATH"] = os.pathsep.join(paths)


def find_tools():
    found = {}
    for name in ("ffmpeg", "ffprobe"):
        path = shutil.which(name)
        if path:
            try:
                run([path, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                found[name] = path
            except (OSError, subprocess.SubprocessError):
                pass
    return found


def install_tools():
    refresh_path()
    tools = find_tools()
    if len(tools) != 2:
        winget = shutil.which("winget")
        if not winget:
            raise RuntimeError("Brak ffmpeg/ffprobe i winget. Zainstaluj App Installer ze sklepu Microsoft "
                               "lub dodaj oba narzedzia do PATH i ponow instalacje.")
        run([winget, "install", "--id", "Gyan.FFmpeg", "--exact", "--source", "winget", "--scope", "user",
             "--accept-source-agreements", "--accept-package-agreements", "--disable-interactivity"])
        refresh_path()
        tools = find_tools()
    if len(tools) != 2:
        raise RuntimeError("Brakuje dzialajacego ffmpeg lub ffprobe. Sprawdz PATH i ponow instalacje.")
    return tools


def copy_app(source, destination):
    """Stage and validate the new app, restore the old app if activation fails."""
    required = ("launch.py", "gui.py", "cli.py", "presets/sequence.py", "audio_separation.py")
    if not all((source / name).is_file() for name in required):
        raise RuntimeError("Niepelne repozytorium: pobierz caly projekt, nie sam katalog win.")
    if source.resolve() == destination.resolve():
        raise RuntimeError("Uruchom instalator z pobranej kopii repozytorium.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix="update-", dir=destination.parent))
    staging = temp / "app"
    backup = temp / "previous"
    try:
        shutil.copytree(source, staging, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        # Parse every file without importing Qt, user code, or optional ML packages.
        for path in staging.rglob("*.py"):
            compile(path.read_bytes(), str(path), "exec")
        if destination.exists():
            destination.rename(backup)
        try:
            staging.rename(destination)
        except OSError:
            if backup.exists():
                backup.rename(destination)
            raise
        shutil.rmtree(backup, ignore_errors=True)
    finally:
        if backup.exists():
            print(f"Zachowano kopie poprzedniej aplikacji: {backup}")
        else:
            shutil.rmtree(temp, ignore_errors=True)


def menu_command():
    # Explorer substitutes %1; always quote it, even for selections without spaces.
    return f'"{python_path(True)}" "{INSTALL / "app/launch.py"}" "%1"'


def menu_keys():
    return [rf"{REG_BASE}\SystemFileAssociations\.{ext}\shell\FFmpegConvert" for ext in EXTENSIONS] + [
        rf"{REG_BASE}\Directory\shell\FFmpegConvert"]


def register_menu():
    import winreg
    for key in menu_keys():
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as handle:
            winreg.SetValueEx(handle, "MUIVerb", 0, winreg.REG_SZ, "FFmpeg Convert...")
            winreg.SetValueEx(handle, "Icon", 0, winreg.REG_SZ, f'"{python_path(True)}",0')
            winreg.SetValueEx(handle, "MultiSelectModel", 0, winreg.REG_SZ, "Single")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key + r"\command") as handle:
            winreg.SetValueEx(handle, "", 0, winreg.REG_SZ, menu_command())
    # Remove only legacy entries pointing to this utility's old scripts/app copy.
    legacy = [rf"{REG_BASE}\SystemFileAssociations\.{ext}\shell\KonwertujWideo"
              for ext in ("mp4", "mov", "mkv")]
    legacy += [rf"{REG_BASE}\SystemFileAssociations\video\shell\KonwertujWideo",
               rf"{REG_BASE}\SystemFileAssociations\image\shell\KonwertujObraz"]
    for key in legacy:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key + r"\command") as handle:
                command = winreg.QueryValueEx(handle, "")[0]
            if r"scripts\app\gui.py" in command.lower():
                delete_menu_key(key)
        except FileNotFoundError:
            pass


def delete_menu_key(key):
    import winreg
    for suffix in (r"\command", ""):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key + suffix)
        except FileNotFoundError:
            pass


def create_shortcut():
    shortcut = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/FFmpeg Convert.lnk"
    env = {**os.environ, "FFCONVERT_LINK": str(shortcut), "FFCONVERT_PYTHON": str(python_path(True)),
           "FFCONVERT_LAUNCH": str(INSTALL / "app/launch.py"), "FFCONVERT_ROOT": str(INSTALL)}
    # Paths are environment data, never interpolated as PowerShell source.
    script = ("$ErrorActionPreference='Stop'; "
              "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:FFCONVERT_LINK); "
              "$s.TargetPath=$env:FFCONVERT_PYTHON; "
              "$s.Arguments='\"'+$env:FFCONVERT_LAUNCH+'\"'; "
              "$s.WorkingDirectory=$env:FFCONVERT_ROOT; $s.Save()")
    run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], env=env)


def install():
    print("Sprawdzanie FFmpeg i ffprobe...", flush=True)
    tools = install_tools()
    print("Przygotowanie srodowiska aplikacji...", flush=True)
    INSTALL.mkdir(parents=True, exist_ok=True)
    venv.EnvBuilder(with_pip=True).create(INSTALL / ".venv")
    run([python_path(), "-m", "pip", "install", "--disable-pip-version-check", "PyQt5==5.15.11"])
    run([python_path(), "-c", "from PyQt5 import QtWidgets"])
    print("Aktualizacja plikow aplikacji i skrotow...", flush=True)
    copy_app(REPO / "app", INSTALL / "app")
    (INSTALL / "windows-tools.json").write_text(json.dumps(tools, indent=2), encoding="utf-8")
    register_menu()
    create_shortcut()
    print(f"Gotowe. Aplikacja: {INSTALL}\nUruchom FFmpeg Convert z menu Start.")
    print("Windows 11: wpis menu pliku/folderu moze byc pod 'Pokaz wiecej opcji'.")


def check_installed():
    if not python_path().is_file() or not (INSTALL / "app/launch.py").is_file():
        raise RuntimeError("Najpierw kliknij Zainstaluj / aktualizuj.")


def perform_action(action):
    if action == "install":
        install()
    elif action == "launch":
        check_installed()
        subprocess.Popen([str(python_path(True)), str(INSTALL / "app/launch.py")])
    elif action == "audio":
        check_installed()
        print("Instalowanie lokalnej separacji audio. Pobieranie moze potrwac kilka minut.", flush=True)
        run([python_path(), INSTALL / "app/cli.py", "audio-setup"])
    elif action == "remove-menu":
        for key in menu_keys():
            delete_menu_key(key)
        print("Usunieto menu kontekstowe. Aplikacja i model pozostaja na dysku.")
    elif action == "diagnose":
        refresh_path()
        print(f"Python instalatora: {sys.executable}\nAplikacja: {INSTALL}\nNarzedzia: {find_tools()}")
        if python_path().is_file():
            run([python_path(), "-c", "from PyQt5 import QtWidgets; print('PyQt5: OK')"])
        else:
            print("Aplikacja nie jest jeszcze zainstalowana.")
    else:
        raise ValueError(f"Nieznana operacja: {action}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=["install", "launch", "audio", "remove-menu", "diagnose"])
    args = parser.parse_args(argv)
    if os.name != "nt" or sys.version_info[:2] != (3, 12) or struct.calcsize("P") != 8:
        print("Instalator wymaga Windows i Pythona 3.12 64-bit. Uruchom setup.vbs.")
        return 1
    if args.action is None:
        run(["powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File",
             Path(__file__).with_suffix(".ps1")])
        return 0
    try:
        perform_action(args.action)
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"BLAD: {exc}\nPopraw problem i ponow operacje.", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
