@echo off
setlocal DisableDelayedExpansion
REM Compatibility launcher. Double-click setup.vbs to avoid a console entirely.
start "" "%SystemRoot%\System32\wscript.exe" "%~dp0setup.vbs"
exit /b
