@echo off
REM Setup script for Eco-Loop Building Agents on Windows

echo ============================================================
echo Eco-Loop Building Agents - Setup Script
echo ============================================================
echo.

REM Check Python
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please install Python 3.9 or later.
    echo Visit: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python found
python --version

REM Create virtual environment
echo.
echo Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment
    pause
    exit /b 1
)

echo [OK] Virtual environment created

REM Activate and install dependencies
echo.
echo Installing dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

if errorlevel 1 (
    echo [WARNING] Some packages may have failed to install
    echo Please check the output above
) else (
    echo [OK] Dependencies installed
)

REM Create directories
echo.
echo Creating directories...
if not exist "logs" mkdir logs
if not exist "results" mkdir results

echo [OK] Directories created

REM Check Ollama
echo.
echo Checking Ollama installation...
ollama list > nul 2>&1
if errorlevel 1 (
    echo [WARNING] Ollama not found or not running
    echo Please install Ollama from: https://ollama.ai/download
    echo After installation, run: ollama pull qwen2.5:7b-instruct
) else (
    echo [OK] Ollama is installed
    echo.
    echo Pulling qwen2.5:7b-instruct model...
    ollama pull qwen2.5:7b-instruct
)

REM Check EnergyPlus
echo.
echo Checking for EnergyPlus...
where energyplus > nul 2>&1
if errorlevel 1 (
    echo [WARNING] EnergyPlus not found in PATH
    echo Please install EnergyPlus 23.2 or later from:
    echo https://github.com/NREL/EnergyPlus/releases
    echo.
    echo Common installation locations:
    echo   C:\EnergyPlusV23-2-0\energyplus.exe
    echo   C:\EnergyPlusV24-1-0\energyplus.exe
) else (
    echo [OK] EnergyPlus found
    energyplus --version
)

echo.
echo ============================================================
echo Setup Complete!
echo ============================================================
echo.
echo Next steps:
echo   1. Make sure Ollama is running
echo   2. Activate the virtual environment:
echo      venv\Scripts\activate.bat
echo   3. Run a quick demo:
echo      python src\orchestrator.py --days 1 --verbose
echo.
echo For full instructions, see README.md
echo ============================================================
pause
