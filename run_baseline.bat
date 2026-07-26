@echo off
echo ============================================================
echo Starting Baseline Simulation (No AI)
echo ============================================================
echo.

REM Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    python src\baseline_runner.py
) else (
    echo Virtual environment not found. Using system Python...
    C:\Users\vaira\AppData\Local\Python\bin\python3.exe src\baseline_runner.py
)

pause
