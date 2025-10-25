@echo off
REM Quick Start Script for Local Development
REM This script tests MySQL connection and starts the backend

echo ========================================
echo   QADAM Backend - Local Development
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo Please run: python -m venv venv
    echo Then run: venv\Scripts\activate
    echo Then run: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Activate virtual environment
echo [1/4] Activating virtual environment...
call venv\Scripts\activate.bat
echo [OK] Virtual environment activated
echo.

REM Check if .env file exists
if not exist ".env" (
    echo [WARNING] .env file not found!
    echo Creating .env from .env.example...
    copy .env.example .env
    echo.
    echo [ACTION REQUIRED] Please edit .env file and add your API keys
    echo Then run this script again.
    pause
    exit /b 1
)

REM Test MySQL connection
echo [2/4] Testing MySQL connection...
python test_mysql_connection.py
if errorlevel 1 (
    echo.
    echo [ERROR] MySQL connection failed!
    echo Please check the error messages above and fix the issues.
    echo.
    echo Common solutions:
    echo   - Start XAMPP and click "Start" for MySQL
    echo   - Check MySQL credentials in .env file
    echo   - Run: python database.py to create tables
    echo.
    pause
    exit /b 1
)
echo.

REM Initialize database if needed
echo [3/4] Checking database tables...
python -c "from database import init_db; init_db()" 2>nul
if errorlevel 1 (
    echo [INFO] Initializing database tables...
    python database.py
)
echo [OK] Database ready
echo.

REM Start Flask backend
echo [4/4] Starting Flask backend...
echo.
echo ========================================
echo   Backend running on http://localhost:5000
echo   Press Ctrl+C to stop
echo ========================================
echo.

python app.py

pause
