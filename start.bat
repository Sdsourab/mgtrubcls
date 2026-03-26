@echo off
title UniSync — Starting...
echo.
echo  ╔═══════════════════════════════════════╗
echo  ║   UniSync — Rabindra University       ║
echo  ║   Department of Management            ║
echo  ╚═══════════════════════════════════════╝
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.10+ from python.org
    pause
    exit /b 1
)

:: Check .env
if not exist ".env" (
    echo [WARNING] .env file not found. Copying from .env.example...
    copy ".env.example" ".env"
    echo [ACTION] Please open .env and add your Supabase keys, then re-run this script.
    pause
    exit /b 1
)

:: Install dependencies
echo [INFO] Installing dependencies...
pip install -r requirements.txt --quiet

:: Run
echo [INFO] Starting UniSync on http://localhost:5000
echo [INFO] Press Ctrl+C to stop.
echo.
python run.py
pause
