---
name: windows-installer
description: Instalator Windows ffmpeg_convert — setup.vbs/setup.ps1/setup.py, instalacja per użytkownik w %LOCALAPPDATA%, winget (Python 3.12, Gyan.FFmpeg), venv, menu kontekstowe w rejestrze HKCU, skrót Start, aktualizacja z zachowaniem modelu audio i testy na izolowanym kluczu rejestru. Użyj przy każdej zmianie w win/ albo w sposobie uruchamiania aplikacji na Windows.
---

# Instalator Windows

Kontrakt: `docs/rewrite/spec.md`, sekcja 9.2 (CTX-W01…W09). Historia pułapek: `REWRITE.md` §8.1.

## Pliki i przepływ

1. `win/setup.vbs`: uruchamia PowerShell bez konsoli (`-WindowStyle Hidden`, `shell.Run …, 0`).
   `win/setup.bat` tylko wywołuje `setup.vbs` (zgodność wstecz).
2. `win/setup.ps1`: okno WinForms (przyciski, wskaźnik, szczegóły, „Kopiuj szczegóły”). Każda
   akcja to **osobny proces** `setup.ps1 -Action <akcja>` z przekierowanym stdout/stderr do plików
   w `%TEMP%`, odczytywanych timerem; UI nie blokuje się. `-SmokeTest` zamyka okno po 0,5 s.
3. Proces akcji szuka Pythona 3.12 x64 (`py -3.12`, `%LOCALAPPDATA%\Programs\Python\Python312`,
   `python`; alias Sklepu nie przejdzie testu wersji), w razie braku
   `winget install --id Python.Python.3.12 --exact --source winget --scope user --architecture x64
   --silent --accept-source-agreements --accept-package-agreements --disable-interactivity`.
4. `win/setup.py --action install|launch|audio|remove-menu|diagnose`.

## Co robi `install`

| krok | szczegóły |
|---|---|
| narzędzia | `ffmpeg`/`ffprobe` z PATH odświeżonego z rejestru (HKCU i HKLM `Environment`) + `%LOCALAPPDATA%\Microsoft\WinGet\Links`; brak → `winget install --id Gyan.FFmpeg … --scope user`; każde sprawdzane przez `-version` |
| środowisko | venv `%LOCALAPPDATA%\FFmpegConvert\.venv` + `PyQt5==5.15.11` (etap 3: `PySide6-Essentials==6.12.*`, D1) |
| aplikacja | `copy_app`: kopia do `update-*/app`, kompilacja każdego `.py` (bez importu), `rename` starej wersji na backup, nowej na miejsce, przy błędzie przywrócenie |
| ścieżki narzędzi | `windows-tools.json` (pełne ścieżki), czytane przez `app/core/ffmpeg.py::tool_path`, bo Eksplorator może mieć stary PATH |
| menu | `HKCU\Software\Classes\SystemFileAssociations\.<ext>\shell\FFmpegConvert` dla 13 rozszerzeń + `Directory\shell\FFmpegConvert`; `MUIVerb`, `Icon`, `MultiSelectModel=Single`; polecenie `"<venv>\pythonw.exe" "<app>\launch.py" "%1"` |
| skrót | menu Start przez `WScript.Shell`; ścieżki przekazywane **zmiennymi środowiskowymi**, nie wklejane w kod PowerShell |

## Zasady

- Wszystko per użytkownik, bez administratora; `winget --scope user` bywa ignorowane przez
  manifest (możliwe okno UAC).
- Ścieżki w rejestrze absolutne i w cudzysłowach. Zmienne `%VAR%` tylko w `REG_EXPAND_SZ`;
  w `REG_SZ` się nie rozwijają.
- Menu przypinaj do **konkretnych rozszerzeń**, nie do kategorii `video`/`image` (odtwarzacze je
  przejmują).
- PATH zmieniaj przez `[Environment]::SetEnvironmentVariable`, nigdy `setx` (obcina > 1024 znaki);
  po zmianie komunikat o restarcie Eksploratora lub wylogowaniu.
- Polityka wykonywania tylko dla procesu (`-ExecutionPolicy Bypass`), bez trwałych zmian.
- Aktualizacja **zachowuje model audio** (`%LOCALAPPDATA%\FFmpegConvert\.audio-runtime`) i usuwa
  stare moduły (`copy_app` zastępuje cały `app/`). Stare wpisy menu usuwane tylko, gdy wskazują
  `scripts\app\gui.py`.
- Teksty w `setup.py` bez polskich znaków (konsola Windows), w `setup.ps1` z polskimi (UTF-8 z BOM).
  Pliki `.bat`/`.vbs` mają końce linii CRLF (`.gitattributes`).

## Testy

- `tests/test_windows.py`: na każdym systemie dispatch akcji, cudzysłowy polecenia menu
  (ścieżka `Profil O'Neil & !`), zakres kluczy, aktualizacja bez utraty modelu, nieudana
  aktualizacja zostawia starą wersję, kopie zamiast linków w sekwencji.
- Tylko na Windows (CI `windows-latest`): rejestracja i usunięcie menu w **izolowanym kluczu**
  `HKCU\Software\FFmpegConvertTests\<uuid>` (podmiana `setup.REG_BASE`), start okna
  `setup.ps1 -SmokeTest`, start GUI przez `pythonw.exe`.
- Ręcznie przed wydaniem: konto bez Pythona; Python z aliasem Sklepu; profil ze spacją i
  apostrofem w nazwie; skalowanie 100% i 150%; Windows 11 „Pokaż więcej opcji”; aktualizacja
  starej instalacji z modelem; „Usuń menu kontekstowe”.

## Zmiany w v2 (D1, D5)

Instalacja pakietu do venv (`pip install <repo>`), menu i skrót wskazują
`<venv>\Scripts\ffmpeg-convert-gui.exe "%1"`; runtime audio przenoszony przez `rename` do katalogu
danych użytkownika (bez ponownego pobierania); `app\launch.py` zostaje jako przekierowanie przez
jedną wersję; „Usuń menu” usuwa też skrót, dochodzi pełna deinstalacja (A37).
