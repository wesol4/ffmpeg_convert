@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
REM Bootstrap only: keep paths as quoted arguments, including spaces and !.
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
call :FIND_PYTHON
if defined PYTHON_EXE goto :RUN
where winget >nul 2>&1
if errorlevel 1 goto :MISSING
choice /c TN /n /m "Brak Python 3.12 64-bit. Zainstalowac przez winget? [T/N]: "
if errorlevel 2 exit /b 1
winget install --id Python.Python.3.12 --exact --source winget --scope user --architecture x64 --accept-source-agreements --accept-package-agreements --disable-interactivity
if errorlevel 1 goto :MISSING
call :FIND_PYTHON
if not defined PYTHON_EXE goto :MISSING
:RUN
"%PYTHON_EXE%" "%~dp0setup.py"
set "SETUP_RESULT=%errorlevel%"
if not "%SETUP_RESULT%"=="0" pause
exit /b %SETUP_RESULT%

:FIND_PYTHON
set "PYTHON_EXE="
py -3.12 -c "import sys,struct; sys.exit(0 if sys.version_info[:2]==(3,12) and struct.calcsize('P')==8 else 1)" >nul 2>&1
if errorlevel 1 goto :LOCAL_PYTHON
for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%P"
if defined PYTHON_EXE exit /b 0
:LOCAL_PYTHON
set "PYTHON_CANDIDATE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PYTHON_CANDIDATE%" goto :PATH_PYTHON
"%PYTHON_CANDIDATE%" -c "import sys,struct; sys.exit(0 if sys.version_info[:2]==(3,12) and struct.calcsize('P')==8 else 1)" >nul 2>&1
if errorlevel 1 goto :PATH_PYTHON
set "PYTHON_EXE=%PYTHON_CANDIDATE%"
exit /b 0
:PATH_PYTHON
python -c "import sys,struct; sys.exit(0 if sys.version_info[:2]==(3,12) and struct.calcsize('P')==8 else 1)" >nul 2>&1
if errorlevel 1 exit /b 1
for /f "delims=" %%P in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%P"
exit /b 0

:MISSING
echo.
echo Wymagany jest Python 3.12 64-bit i App Installer / winget.
echo Zainstaluj Python 3.12 z python.org i uruchom setup.bat ponownie.
echo FFmpeg mozna tez zainstalowac recznie: ffmpeg.exe i ffprobe.exe w PATH.
pause
exit /b 1
