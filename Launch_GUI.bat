@echo off
title YouXtractor - Audio Extractor & Mastering Suite
cd /d "%~dp0"

echo =======================================================
echo   YouXtractor - Audio Extractor & Mastering Suite
echo =======================================================
echo Launching Graphical User Interface (GUI)...
echo.

python app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred while launching YouXtractor.
    pause
)
