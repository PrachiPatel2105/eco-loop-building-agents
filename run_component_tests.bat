@echo off
echo ============================================================
echo Running Component Tests
echo ============================================================
echo.

REM Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    python src\test_components.py
) else (
    echo Virtual environment not found. Using system Python...
    C:\Users\vaira\AppData\Local\Python\bin\python3.exe src\test_components.py
)

pause
