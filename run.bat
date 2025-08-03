@echo off
echo Starting TikTok Downloader Bot...
echo.

REM Check if .env file exists
if not exist .env (
    echo ERROR: .env file not found!
    echo Copy .env.example to .env and add your BOT_TOKEN
    pause
    exit /b 1
)

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not found in PATH
    pause
    exit /b 1
)

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Start bot
echo Starting bot...
python bot.py

pause
