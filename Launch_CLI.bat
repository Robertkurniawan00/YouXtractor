@echo off
title YouXtractor - Command Line Interface (CLI)
cd /d "%~dp0"

python cli.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    pause
)
