@echo off
REM Complete MySQL Migration to Azure
REM Exports local database and imports to Azure MySQL in one script

echo ========================================
echo   MySQL Migration to Azure
echo ========================================
echo.

REM Set MySQL path
set MYSQL_PATH=D:\MySQL\MySQL Server 8.0\bin

REM Check if MySQL exists
if not exist "%MYSQL_PATH%\mysqldump.exe" (
    echo [ERROR] MySQL not found at: %MYSQL_PATH%
    echo Please verify the MySQL installation path.
    pause
    exit /b 1
)

echo [OK] MySQL found at: %MYSQL_PATH%
echo.

REM ========================================
REM STEP 1: Export Local Database
REM ========================================

echo ========================================
echo   Step 1: Export Local Database
echo ========================================
echo.

set /p LOCAL_USER="Local MySQL username [root]: "
if "%LOCAL_USER%"=="" set LOCAL_USER=root

set /p LOCAL_PASSWORD="Local MySQL password: "

REM Generate filename with timestamp
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set TIMESTAMP=%datetime:~0,8%_%datetime:~8,6%
set BACKUP_FILE=qadam_academic_backup_%TIMESTAMP%.sql

echo.
echo Exporting database...
echo   Database: qadam_academic
echo   Output: %BACKUP_FILE%
echo.

"%MYSQL_PATH%\mysqldump.exe" ^
  -u %LOCAL_USER% ^
  -p%LOCAL_PASSWORD% ^
  --single-transaction ^
  --routines ^
  --triggers ^
  --events ^
  --complete-insert ^
  --default-character-set=utf8mb4 ^
  qadam_academic > %BACKUP_FILE%

if errorlevel 1 (
    echo.
    echo [ERROR] Export failed!
    pause
    exit /b 1
)

REM Check file size
for %%A in (%BACKUP_FILE%) do set FILE_SIZE=%%~zA

if %FILE_SIZE% LEQ 0 (
    echo [ERROR] Export file is empty!
    pause
    exit /b 1
)

echo [OK] Export successful (%FILE_SIZE% bytes)
echo.

REM ========================================
REM STEP 2: Configure Azure MySQL
REM ========================================

echo ========================================
echo   Step 2: Azure MySQL Configuration
echo ========================================
echo.

set /p AZURE_HOST="Azure MySQL hostname [qadam-db.mysql.database.azure.com]: "
if "%AZURE_HOST%"=="" set AZURE_HOST=qadam-db.mysql.database.azure.com

set /p AZURE_USER="Azure MySQL username [qaadmin]: "
if "%AZURE_USER%"=="" set AZURE_USER=qaadmin

set /p AZURE_PASSWORD="Azure MySQL password: "

set /p AZURE_DATABASE="Database name [qadam_academic]: "
if "%AZURE_DATABASE%"=="" set AZURE_DATABASE=qadam_academic

echo.
echo ========================================
echo   Migration Summary
echo ========================================
echo.
echo Source: Local MySQL (qadam_academic)
echo Backup: %BACKUP_FILE% (%FILE_SIZE% bytes)
echo.
echo Target: %AZURE_HOST%
echo User: %AZURE_USER%
echo Database: %AZURE_DATABASE%
echo.

set /p CONFIRM="Continue with migration? (y/n): "
if /i not "%CONFIRM%"=="y" (
    echo Migration cancelled
    pause
    exit /b 0
)

REM ========================================
REM STEP 3: Test Azure Connection
REM ========================================

echo.
echo ========================================
echo   Step 3: Test Azure Connection
echo ========================================
echo.

echo Testing connection...
"%MYSQL_PATH%\mysql.exe" ^
  -h %AZURE_HOST% ^
  -u %AZURE_USER% ^
  -p%AZURE_PASSWORD% ^
  -e "SELECT VERSION();" 2>nul

if errorlevel 1 (
    echo [ERROR] Cannot connect to Azure MySQL!
    echo.
    echo Check:
    echo   1. Credentials are correct
    echo   2. Firewall allows your IP
    echo   3. Network connection
    echo.
    pause
    exit /b 1
)

echo [OK] Connection successful
echo.

REM ========================================
REM STEP 4: Prepare Database
REM ========================================

echo ========================================
echo   Step 4: Prepare Database
echo ========================================
echo.

echo Dropping existing database (if exists)...
"%MYSQL_PATH%\mysql.exe" ^
  -h %AZURE_HOST% ^
  -u %AZURE_USER% ^
  -p%AZURE_PASSWORD% ^
  -e "DROP DATABASE IF EXISTS %AZURE_DATABASE%;" 2>nul

echo Creating fresh database...
"%MYSQL_PATH%\mysql.exe" ^
  -h %AZURE_HOST% ^
  -u %AZURE_USER% ^
  -p%AZURE_PASSWORD% ^
  -e "CREATE DATABASE %AZURE_DATABASE% CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

if errorlevel 1 (
    echo [ERROR] Failed to create database
    pause
    exit /b 1
)

echo [OK] Database ready
echo.

REM ========================================
REM STEP 5: Import Data
REM ========================================

echo ========================================
echo   Step 5: Import Data to Azure
echo ========================================
echo.

echo Importing %BACKUP_FILE%...
echo This may take several minutes...
echo.

"%MYSQL_PATH%\mysql.exe" ^
  -h %AZURE_HOST% ^
  -u %AZURE_USER% ^
  -p%AZURE_PASSWORD% ^
  %AZURE_DATABASE% < %BACKUP_FILE%

if errorlevel 1 (
    echo.
    echo [ERROR] Import failed!
    pause
    exit /b 1
)

echo [OK] Import successful
echo.

REM ========================================
REM STEP 6: Verify Migration
REM ========================================

echo ========================================
echo   Step 6: Verify Migration
echo ========================================
echo.

echo Checking tables...
"%MYSQL_PATH%\mysql.exe" ^
  -h %AZURE_HOST% ^
  -u %AZURE_USER% ^
  -p%AZURE_PASSWORD% ^
  %AZURE_DATABASE% ^
  -e "SHOW TABLES;"

if errorlevel 1 (
    echo [ERROR] Failed to verify tables
    pause
    exit /b 1
)

echo.
echo Checking row counts...
"%MYSQL_PATH%\mysql.exe" ^
  -h %AZURE_HOST% ^
  -u %AZURE_USER% ^
  -p%AZURE_PASSWORD% ^
  %AZURE_DATABASE% ^
  -e "SELECT 'users' as tbl, COUNT(*) as cnt FROM users UNION ALL SELECT 'uploaded_papers', COUNT(*) FROM uploaded_papers UNION ALL SELECT 'textbooks', COUNT(*) FROM textbooks UNION ALL SELECT 'parsed_questions', COUNT(*) FROM parsed_questions UNION ALL SELECT 'sample_questions', COUNT(*) FROM sample_questions UNION ALL SELECT 'question_bank', COUNT(*) FROM question_bank UNION ALL SELECT 'ai_search_results', COUNT(*) FROM ai_search_results UNION ALL SELECT 'usage_logs', COUNT(*) FROM usage_logs;" 2>nul

echo.
echo ========================================
echo   Migration Complete!
echo ========================================
echo.
echo Backup file: %BACKUP_FILE%
echo Azure Host: %AZURE_HOST%
echo Database: %AZURE_DATABASE%
echo.
echo Next steps:
echo.
echo 1. Update .env file:
echo    MYSQL_HOST=%AZURE_HOST%
echo    MYSQL_USER=%AZURE_USER%
echo    MYSQL_DATABASE=%AZURE_DATABASE%
echo    MYSQL_PASSWORD=your_password
echo.
echo 2. Test backend:
echo    python app.py
echo.
echo 3. Configure Azure Function App:
echo    configure_azure_function.bat
echo.

pause
