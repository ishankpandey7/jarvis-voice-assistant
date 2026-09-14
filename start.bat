@echo off
REM Double-click this file to start Jarvis.
title Jarvis
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 goto nopython

python jarvis.py
echo.
echo   Jarvis has stopped.
pause
exit /b 0

:nopython
echo.
echo   Python was not found.
echo   Install it from python.org, and make sure you tick
echo   "Add Python to PATH" during the install.
echo.
pause
exit /b 1
