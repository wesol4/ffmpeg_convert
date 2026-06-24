@echo off
REM ===========================================================================
REM  FFmpeg Convert - instalator menu kontekstowego Eksploratora (Windows)
REM
REM  Wymaga: Python 3 + PyQt5 oraz ffmpeg.exe w PATH.
REM  Skopiuj folder app\ do %USERPROFILE%\scripts\app\ (przed uruchomieniem).
REM
REM  Dlaczego .bat, a nie .reg do dwukliku:
REM    Klasyczne wartosci rejestru REG_SZ nie rozwijaja zmiennych srodowiskowych,
REM    wiec wpisanie %USERPROFILE% w pliku .reg powoduje, ze system szuka
REM    doslownie folderu o nazwie "%USERPROFILE%". Tu uzywamy typu
REM    REG_EXPAND_SZ - Windows rozwija %USERPROFILE% dopiero w momencie klikniecia,
REM    wiec menu dziala dla kazdego uzytkownika bez edycji skryptu.
REM
REM    Wideo przypinamy do konkretnych rozszerzen (.mp4/.mov/.mkv) zamiast do
REM    ogolnej kategorii "video" - ta ostatnia bywa wypinana przez zewnetrzne
REM    odtwarzacze i kodeki, przez co menu nie pojawialo sie m.in. dla .mp4.
REM ===========================================================================
setlocal

for %%E in (mp4 mov mkv) do call :ADD_VIDEO %%E
call :ADD_IMAGE

echo.
echo Gotowe. Pozycje "Konwertuj ... (FFmpeg)" dodane do menu kontekstowego.
echo Eksplorator moze wymagać restartu, aby pokazac nowe wpisy.
endlocal
goto :EOF

REM --- Wideo: osobny klucz dla kazdego rozszerzenia --------------------------
:ADD_VIDEO
reg add "HKCU\Software\Classes\SystemFileAssociations\.%~1\shell\KonwertujWideo" /ve /d "Konwertuj wideo (FFmpeg)..." /f >nul
reg add "HKCU\Software\Classes\SystemFileAssociations\.%~1\shell\KonwertujWideo" /v "Icon" /d "ffmpeg.exe" /f >nul
reg add "HKCU\Software\Classes\SystemFileAssociations\.%~1\shell\KonwertujWideo\command" /ve /d "pythonw \"%%USERPROFILE%%\scripts\app\gui.py\" \"%%1\"" /t REG_EXPAND_SZ /f >nul
goto :EOF

REM --- Obrazy: ogolna kategoria image -----------------------------------------
:ADD_IMAGE
reg add "HKCU\Software\Classes\SystemFileAssociations\image\shell\KonwertujObraz" /ve /d "Konwertuj / kompresuj obraz (FFmpeg)..." /f >nul
reg add "HKCU\Software\Classes\SystemFileAssociations\image\shell\KonwertujObraz" /v "Icon" /d "ffmpeg.exe" /f >nul
reg add "HKCU\Software\Classes\SystemFileAssociations\image\shell\KonwertujObraz\command" /ve /d "pythonw \"%%USERPROFILE%%\scripts\app\gui.py\" \"%%1\"" /t REG_EXPAND_SZ /f >nul
goto :EOF