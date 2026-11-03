@echo off
cd /d "%~dp0"
echo [1/2] Compiling title_cleaner.c (C99) with MinGW-W64 GCC...
gcc -shared -O3 -fPIC -o title_cleaner.dll title_cleaner.c
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] title_cleaner.c compilation failed.
    exit /b %ERRORLEVEL%
)
echo [SUCCESS] title_cleaner.dll compiled successfully.

echo [2/2] Compiling audio_probe.cpp (C++20) with MinGW-W64 G++...
g++ -std=c++20 -O3 -s -static -o audio_probe.exe audio_probe.cpp
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] audio_probe.cpp compilation failed.
    exit /b %ERRORLEVEL%
)
echo [SUCCESS] audio_probe.exe compiled successfully.
