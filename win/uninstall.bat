@echo off
REM ===========================================================================
REM  FFmpeg Convert - usuwanie menu kontekstowego Eksploratora (Windows)
REM  Odwraca wpisy dodane przez install.bat.
REM ===========================================================================
setlocal

for %%E in (mp4 mov mkv) do call :DEL_VIDEO %%E
call :DEL_IMAGE

echo.
echo Usunieto pozycje "Konwertuj ... (FFmpeg)" z menu kontekstowego.
endlocal
goto :EOF

:DEL_VIDEO
reg delete "HKCU\Software\Classes\SystemFileAssociations\.%~1\shell\KonwertujWideo" /f >nul 2>&1
goto :EOF

:DEL_IMAGE
reg delete "HKCU\Software\Classes\SystemFileAssociations\image\shell\KonwertujObraz" /f >nul 2>&1
goto :EOF