@echo off
setlocal enabledelayedexpansion
title CELMIS Launcher
cd /d "%~dp0"

REM ================= Detect Python =================
set "PY=python"
where python >nul 2>nul
if %errorlevel%==0 goto :py_ok
where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py"
    goto :py_ok
)
echo [ERROR] Python is not installed or not in PATH.
echo Install Python from https://www.python.org/downloads/
echo and tick "Add Python to PATH" during installation.
pause
exit /b 1

:py_ok
echo %PY% version: & %PY% --version

:menu
cls
echo ============================================
echo   CELMIS - Community Extension MIS
echo ============================================
echo.
echo   1. Run CELMIS (keep existing data)
echo   2. Reset demo data, then run
echo   3. Exit
echo.
set "CHOICE="
set /p CHOICE=Select [1-3]: 

if "%CHOICE%"=="1" goto :action_run
if "%CHOICE%"=="2" goto :action_reset
if "%CHOICE%"=="3" exit /b 0
echo Invalid choice. Please pick 1, 2, or 3.
pause
goto :menu

:action_reset
echo.
echo WARNING: This will DELETE all existing data and recreate demo records.
set /p CONFIRM=Type YES to confirm reset: 
if /I not "%CONFIRM%"=="YES" (
    echo Cancelled. Returning to menu...
    pause
    goto :menu
)
echo.
echo [SETUP] Resetting database with demo data...
%PY% seed.py
echo.
goto :install_check

:action_run
echo.
echo [INFO] Use all data. RESET NOT performed.
echo.
goto :install_check

:install_check
REM ---- Install dependencies if missing ----
%PY% -c "import flask, sklearn" >nul 2>nul
if not %errorlevel%==0 (
    echo.
    echo [SETUP] Installing required packages...
    %PY% -m pip install -r requirements.txt
    if not !errorlevel!==0 (
        echo [ERROR] Package installation failed. Check your internet connection.
        pause
        exit /b 1
    )
)

REM ---- First run: create + seed database if missing ----
if not exist celmis.db (
    echo.
    echo [SETUP] First run - creating database and demo data...
    %PY% seed.py
)

:start_server
echo.
echo [RUN] Starting CELMIS server...
echo       URL: http://127.0.0.1:5000
echo       Login: admin / password
echo.
start "CELMIS Server" cmd /k "%PY% run.py"
timeout /t 5 /nobreak >nul
start "" "http://127.0.0.1:5000"
echo Server started. This window can now be closed.
echo (The CELMIS Server window must stay open while using the system.)
echo.
pause
exit /b 0