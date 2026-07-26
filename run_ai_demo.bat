@echo off
echo ============================================================
echo Starting AI-Controlled Building Simulation
echo ============================================================
echo.

REM Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    python src\orchestrator.py --days 2 --verbose
) else (
    echo Virtual environment not found. Using system Python...
    C:\Users\vaira\AppData\Local\Python\bin\python3.exe src\orchestrator.py --days 2 --verbose
)

pause
