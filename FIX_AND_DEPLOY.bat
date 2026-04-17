@echo off
REM ============================================================
REM UniSync — Complete Fix Script (Windows)
REM Run this from your project root:
REM   C:\Users\soptom\OneDrive\Desktop\univ18
REM ============================================================

echo.
echo ========================================
echo  UniSync Deploy Fix Script
echo ========================================
echo.

REM ── Step 1: Rename files with trailing spaces ──────────────
echo [1/5] Fixing filenames with trailing spaces...

IF EXIST "core\push.py " (
    copy /Y "core\push.py " "core\push.py"
    del "core\push.py "
    echo   Fixed: core\push.py
) ELSE (
    echo   OK: core\push.py already clean
)

IF EXIST "core\schedule_utils.py " (
    copy /Y "core\schedule_utils.py " "core\schedule_utils.py"
    del "core\schedule_utils.py "
    echo   Fixed: core\schedule_utils.py
) ELSE (
    echo   OK: core\schedule_utils.py already clean
)

REM ── Step 2: Create missing __init__.py files ───────────────
echo.
echo [2/5] Creating missing __init__.py files...

IF NOT EXIST "app\classmanagement\__init__.py" (
    type nul > "app\classmanagement\__init__.py"
    echo   Created: app\classmanagement\__init__.py
) ELSE (
    echo   OK: app\classmanagement\__init__.py exists
)

IF NOT EXIST "app\exams\__init__.py" (
    type nul > "app\exams\__init__.py"
    echo   Created: app\exams\__init__.py
) ELSE (
    echo   OK: app\exams\__init__.py exists
)

IF NOT EXIST "app\notices\__init__.py" (
    type nul > "app\notices\__init__.py"
    echo   Created: app\notices\__init__.py
) ELSE (
    echo   OK: app\notices\__init__.py exists
)

IF NOT EXIST "app\push\__init__.py" (
    type nul > "app\push\__init__.py"
    echo   Created: app\push\__init__.py
) ELSE (
    echo   OK: app\push\__init__.py exists
)

IF NOT EXIST "app\teachers\__init__.py" (
    type nul > "app\teachers\__init__.py"
    echo   Created: app\teachers\__init__.py
) ELSE (
    echo   OK: app\teachers\__init__.py exists
)

REM ── Step 3: Replace vercel.json ────────────────────────────
echo.
echo [3/5] Updating vercel.json...
(
echo {
echo   "version": 2,
echo   "builds": [
echo     {
echo       "src": "api/index.py",
echo       "use": "@vercel/python"
echo     }
echo   ],
echo   "routes": [
echo     {
echo       "src": "/sw.js",
echo       "dest": "/api/index.py",
echo       "headers": {
echo         "Service-Worker-Allowed": "/",
echo         "Cache-Control": "no-cache, no-store, must-revalidate"
echo       }
echo     },
echo     {
echo       "src": "/(.*)",
echo       "dest": "/api/index.py"
echo     }
echo   ],
echo   "crons": [
echo     {
echo       "path": "/api/cron/daily",
echo       "schedule": "0 12 * * *"
echo     }
echo   ]
echo }
) > vercel.json
echo   Done: vercel.json updated

REM ── Step 4: Git add + commit + push ────────────────────────
echo.
echo [4/5] Git commit and push...
git add .
git status
git commit -m "fix: vercel config, missing __init__.py, filename spaces - v26"
git push origin main

echo.
echo [5/5] Done!
echo   - vercel.json fixed (wsgi.py -> api/index.py, cron fixed)
echo   - 5 missing __init__.py files created
echo   - Filename spaces removed from core/push.py + schedule_utils.py
echo.
echo Check GitHub and Vercel dashboard now.
pause
