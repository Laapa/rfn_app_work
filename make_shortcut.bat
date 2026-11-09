@echo off
rem Creates the desktop shortcut for the monitor (runs make_shortcut.ps1).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0make_shortcut.ps1"
pause
