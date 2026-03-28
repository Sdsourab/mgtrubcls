@echo off
title UniSync — Local Dev Server

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║     UniSync — Academic Portal                ║
echo  ║     Rabindra University, Bangladesh          ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: Check for .env file
if not exist .env (
    echo  [!] .env file not found.
    echo      Copy .env.example to .env and fill in your keys.
    echo.
    pause
    exit /b 1
)

:: Install dependencies if needed
echo  [1/3] Checking dependencies...
pip install -r requirements.txt --quiet

echo  [2/3] Environment: development
set FLASK_ENV=development

echo  [3/3] Starting server at http://localhost:5000
echo.
echo  Press Ctrl+C to stop.
echo.

python run.py

pause