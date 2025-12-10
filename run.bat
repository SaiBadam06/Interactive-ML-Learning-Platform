@echo off
REM ML Learning Assistant Startup Script for Windows
REM This script sets up and runs the application

echo ======================================
echo    ML Learning Assistant
echo ======================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed!
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)

echo Python found
python --version
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    echo Virtual environment created
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo Virtual environment activated
echo.

REM Install/update dependencies
echo Installing dependencies...
pip install -r requirements.txt --quiet
echo Dependencies installed
echo.

REM Check if .env file exists
if not exist ".env" (
    if exist ".env.example" (
        echo No .env file found
        echo Creating .env from .env.example...
        copy .env.example .env
        echo .env file created
        echo Please edit .env file and add your API keys
        echo.
    )
)

REM Start the application
echo ======================================
echo    Starting ML Learning Assistant...
echo ======================================
echo.
echo Server will be available at:
echo    http://localhost:5000
echo    http://127.0.0.1:5000
echo.
echo Press Ctrl+C to stop the server
echo.

python app.py
pause
