@echo off
rem Start the RF monitor (Monitor VCh2) without a console window.
rem Python: venv in this folder, else venv one level up, else python from PATH.
rem Extra arguments are passed to the program, e.g.: run_monitor.bat my-config.json
cd /d "%~dp0"

set "PYDIR="
if exist "%~dp0venv\Scripts\python.exe" set "PYDIR=%~dp0venv\Scripts\"
if not defined PYDIR if exist "%~dp0..\venv\Scripts\python.exe" set "PYDIR=%~dp0..\venv\Scripts\"
if defined PYDIR (
    set "PY=%PYDIR%python.exe"
    set "PYW=%PYDIR%pythonw.exe"
) else (
    set "PY=python"
    set "PYW=pythonw"
)

rem quick check that this Python has everything the monitor needs
"%PY%" -c "import tango, PyQt5, pyqtgraph" 2>nul
if errorlevel 1 goto no_python

start "" "%PYW%" -m rfn_app.oapp.mon.rfn_mon_viewer %*
exit /b 0

:no_python
echo.
echo Python with pytango, PyQt5 and pyqtgraph was not found.
echo Python used: %PY%
"%PY%" --version
echo.
echo Create venv in this folder and install packages, see README.md.
echo.
pause
exit /b 1
