@echo off
setlocal EnableDelayedExpansion
REM ===========================================================================
REM  FFmpeg Convert - pelny instalator Windows
REM
REM  Jeden skrypt, odpalany dwukrotnym kliknieciem, dzialajacy na "golym"
REM  Windowsie 11. Sprawdza i instaluje brakujace zaleznosci (Python, PyQt5,
REM  ffmpeg), kopiuje folder app\ oraz dodaje/usuwa menu kontekstowe
REM  Eksploratora.
REM
REM  Dlaczego .bat (a nie .ps1): podwojne klikniecie .bat nie wymaga obejcia
REM  ExecutionPolicy. PowerShell jest wolany tylko INLINE (-Command) do
REM  pobierania/rozpakowywania - to dziala na czystym systemie bez trwalych
REM  zmian polityki.
REM
REM  Instalacja zaleznosci: hybryda. Najpierw winget (preinstalowany na Win11),
REM  a gdy go brak lub zawiedzie - fallback na reczne pobranie (curl) +
REM  instalacja/wypakowanie + dopisanie do user PATH. Wszystko per-user,
REM  BEZ wymogu uprawnien administratora.
REM
REM  Wymaga uruchomienia z kopia repo (skrypt lezy w win\, obok folderu app\).
REM ===========================================================================

:MENU
cls
echo === FFmpeg Convert - instalator ===
echo.
echo  1) Sprawdz zaleznosci        (Python, PyQt5, ffmpeg)
echo  2) Zainstaluj brakujace      (winget, a gdy brak - recznie)
echo  3) Skopiuj app\              do %USERPROFILE%\scripts\app\
echo  4) Dodaj menu kontekstowe    (.mp4 / .mov / .mkv + obrazy)
echo  5) Usun menu kontekstowe
echo  6) Wyjscie
echo.
choice /c 123456 /n /m "Wybierz opcje (1-6): "
set "OPT=%errorlevel%"
if "%OPT%"=="1" call :CHECK
if "%OPT%"=="2" call :INSTALL_DEPS
if "%OPT%"=="3" call :COPY_APP
if "%OPT%"=="4" call :ADD_MENU
if "%OPT%"=="5" call :REMOVE_MENU
if "%OPT%"=="6" goto :END
echo.
pause
goto :MENU

REM ===========================================================================
REM  Detekcja. Ustawia zmienne: PY (komenda lub puste), PYQT (yes/no), FF (yes/no).
REM  Wymaga realnego "Python x.y" na stdout - odfiltrowuje skrot-alias Sklepu
REM  Windows (python.exe w WindowsApps, ktory zamiast wersji otwiera Sklep).
REM ===========================================================================
:DETECT
set "PY="
set "PYQT=no"
set "FF=no"
call :DETECT_PY
if defined PY ( %PY% -c "import PyQt5" >nul 2>&1 && set "PYQT=yes" )
where ffmpeg >nul 2>&1 && set "FF=yes"
goto :eof

:DETECT_PY
set "_V="
for /f "delims=" %%V in ('python --version 2^>nul') do set "_V=%%V"
echo !_V! | findstr /b "Python " >nul && set "PY=python"
if defined PY goto :eof
set "_V="
for /f "delims=" %%V in ('py -3 --version 2^>nul') do set "_V=%%V"
echo !_V! | findstr /b "Python " >nul && set "PY=py -3"
goto :eof

REM ===========================================================================
REM  Odswiezenie PATH biezacej sesji z rejestru (User + Machine) - potrzebne
REM  zaraz po instalacji, zeby pip / ffmpeg byly widoczne bez restartu okna.
REM ===========================================================================
:REFRESH_PATH
set "_U="
set "_M="
for /f "delims=" %%P in ('powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','User')"') do set "_U=%%P"
for /f "delims=" %%P in ('powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','Machine')"') do set "_M=%%P"
set "PATH=%_M%;%_U%"
goto :eof

REM ===========================================================================
REM  Opcja 1 - raport statusu.
REM ===========================================================================
:CHECK
call :DETECT
echo.
echo --- Status zaleznosci ---
if defined PY (echo   Python ....... OK  [%PY%]) else echo   Python ....... BRAK
if "%PYQT%"=="yes" (echo   PyQt5 ........ OK) else echo   PyQt5 ........ BRAK
if "%FF%"=="yes" (echo   ffmpeg ....... OK) else echo   ffmpeg ....... BRAK
echo   Cel kopii .... %USERPROFILE%\scripts\app\
goto :eof

REM ===========================================================================
REM  Opcja 2 - instalacja brakujacych.
REM ===========================================================================
:INSTALL_DEPS
call :DETECT
echo.
echo --- Instalacja brakujacych ---
if not defined PY ( call :INST_PYTHON ) else echo   Python jest.
if defined PY ( call :INST_PYQT )
if "%FF%"=="no" ( call :INST_FFMPEG ) else echo   ffmpeg jest.
echo.
echo Uwaga: po instalacji zalecany restart Eksploratora / wylogowanie, aby nowy
echo PATH i polecenie 'pythonw' byly widoczne w menu kontekstowym.
goto :eof

REM --- Python: winget, a gdy brak/bled - reczne pobranie instalatora --------
:INST_PYTHON
echo [Python] probe winget ...
where winget >nul 2>&1 || goto :PY_MANUAL
winget install --id Python.Python.3.12 -e --scope user --accept-source-agreements --accept-package-agreements
if errorlevel 1 goto :PY_MANUAL
call :REFRESH_PATH
call :DETECT_PY
if defined PY ( echo [Python] zainstalowany przez winget. & goto :eof )
:PY_MANUAL
echo [Python] instalacja reczna ...
REM Wersja przypietana - przy aktualizacji podbij URL i komentarz.
set "PYURL=https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
curl -L -o "%TEMP%\pyinst.exe" "%PYURL%" || ( echo [Python] blad pobierania. & goto :eof )
"%TEMP%\pyinst.exe" /passive InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0
del "%TEMP%\pyinst.exe" >nul 2>&1
call :REFRESH_PATH
call :DETECT_PY
if defined PY ( echo [Python] zainstalowany recznie. ) else echo [Python] NIE UDALO SIE - sprawdz recznie.
goto :eof

REM --- PyQt5: pip --user -----------------------------------------------------
:INST_PYQT
if "%PYQT%"=="yes" ( echo   PyQt5 jest. & goto :eof )
echo [PyQt5] instalacja pip --user ...
%PY% -m pip install --user --disable-pip-version-check PyQt5 || ( echo [PyQt5] blad - sprawdz polaczenie. & goto :eof )
set "PYQT=yes"
echo [PyQt5] zainstalowany.
goto :eof

REM --- ffmpeg: winget, a gdy brak/bled - reczne pobranie zip + PATH ----------
:INST_FFMPEG
echo [ffmpeg] probe winget ...
where winget >nul 2>&1 || goto :FF_MANUAL
winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
if errorlevel 1 goto :FF_MANUAL
call :REFRESH_PATH
where ffmpeg >nul 2>&1 && ( echo [ffmpeg] zainstalowany przez winget. & goto :eof )
:FF_MANUAL
echo [ffmpeg] instalacja reczna ...
set "FFURL=https://www.gyan.dev/builds/ffmpeg-release-essentials.zip"
curl -L -o "%TEMP%\ffmpeg.zip" "%FFURL%" || ( echo [ffmpeg] blad pobierania. & goto :eof )
if exist "%USERPROFILE%\ffmpeg" rmdir /s /q "%USERPROFILE%\ffmpeg"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force -LiteralPath '%TEMP%\ffmpeg.zip' -DestinationPath '%USERPROFILE%\ffmpeg'"
del "%TEMP%\ffmpeg.zip" >nul 2>&1
REM Zip gyan rozpakowuje sie do podfolderu; szukamy bin\ffmpeg.exe.
set "FFROOT=%USERPROFILE%\ffmpeg"
if not exist "%FFROOT%\bin\ffmpeg.exe" (
  for /d %%D in ("%USERPROFILE%\ffmpeg\*") do if exist "%%D\bin\ffmpeg.exe" set "FFROOT=%%D"
)
if not exist "%FFROOT%\bin\ffmpeg.exe" ( echo [ffmpeg] nie znaleziono ffmpeg.exe po rozpakowaniu. & goto :eof )
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=[Environment]::GetEnvironmentVariable('Path','User'); if('%FFROOT%\bin' -notin ($p -split ';')){[Environment]::SetEnvironmentVariable('Path',($p.TrimEnd(';')+';%FFROOT%\bin'),'User')}"
call :REFRESH_PATH
where ffmpeg >nul 2>&1 && ( echo [ffmpeg] zainstalowany recznie. ) else echo [ffmpeg] NIE UDALO SIE - sprawdz PATH.
goto :eof

REM ===========================================================================
REM  Opcja 3 - kopia folderu app\ (skrypt lezy w win\, zrodlem jest ..\app).
REM ===========================================================================
:COPY_APP
if not exist "%~dp0..\app" ( echo [app] brak folderu app\ obok setup.bat - uruchom z kopia repo. & goto :eof )
robocopy "%~dp0..\app" "%USERPROFILE%\scripts\app" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 ( echo [app] blad kopiowania. ) else echo [app] skopiowano do %USERPROFILE%\scripts\app\
goto :eof

REM ===========================================================================
REM  Opcja 4 - rejestracja menu (REG_EXPAND_SZ - %USERPROFILE% rozwija sie
REM  w locie; wideo przypiete do konkretnych rozszerzen, nie do kategorii video).
REM ===========================================================================
:ADD_MENU
for %%E in (mp4 mov mkv) do call :ADD_VIDEO %%E
call :ADD_IMAGE
echo [menu] dodano pozycje "Konwertuj ... (FFmpeg)" (.mp4/.mov/.mkv + obrazy).
echo (Eksplorator moze wymagac restartu, aby pokazac nowe wpisy.)
goto :eof

:ADD_VIDEO
reg add "HKCU\Software\Classes\SystemFileAssociations\.%~1\shell\KonwertujWideo" /ve /d "Konwertuj wideo (FFmpeg)..." /f >nul
reg add "HKCU\Software\Classes\SystemFileAssociations\.%~1\shell\KonwertujWideo" /v "Icon" /d "ffmpeg.exe" /f >nul
reg add "HKCU\Software\Classes\SystemFileAssociations\.%~1\shell\KonwertujWideo\command" /ve /d "pythonw \"%%USERPROFILE%%\scripts\app\gui.py\" \"%%1\"" /t REG_EXPAND_SZ /f >nul
goto :eof

:ADD_IMAGE
reg add "HKCU\Software\Classes\SystemFileAssociations\image\shell\KonwertujObraz" /ve /d "Konwertuj / kompresuj obraz (FFmpeg)..." /f >nul
reg add "HKCU\Software\Classes\SystemFileAssociations\image\shell\KonwertujObraz" /v "Icon" /d "ffmpeg.exe" /f >nul
reg add "HKCU\Software\Classes\SystemFileAssociations\image\shell\KonwertujObraz\command" /ve /d "pythonw \"%%USERPROFILE%%\scripts\app\gui.py\" \"%%1\"" /t REG_EXPAND_SZ /f >nul
goto :eof

REM ===========================================================================
REM  Opcja 5 - usuniecie menu.
REM ===========================================================================
:REMOVE_MENU
for %%E in (mp4 mov mkv) do reg delete "HKCU\Software\Classes\SystemFileAssociations\.%%E\shell\KonwertujWideo" /f >nul 2>&1
reg delete "HKCU\Software\Classes\SystemFileAssociations\image\shell\KonwertujObraz" /f >nul 2>&1
echo [menu] usunieto pozycje "Konwertuj ... (FFmpeg)".
goto :eof

:END
echo.
echo Do widzenia.
endlocal
pause