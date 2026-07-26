@echo off
REM Quick analysis script - finds most recent AI and baseline logs

echo Looking for most recent simulation logs...

REM Find most recent files
for /f "delims=" %%i in ('dir /b /o-d logs\ai_controlled_run_*.json 2^>nul') do set AI_LOG=%%i & goto :found_ai
echo Error: No AI simulation logs found!
pause
exit /b 1

:found_ai
for /f "delims=" %%i in ('dir /b /o-d logs\baseline_run_*.json 2^>nul') do set BASELINE_LOG=%%i & goto :found_baseline
echo Error: No baseline simulation logs found!
pause
exit /b 1

:found_baseline
echo AI Log: %AI_LOG%
echo Baseline Log: %BASELINE_LOG%
echo.

python src\analyze_results.py --ai logs\%AI_LOG% --baseline logs\%BASELINE_LOG% --output results

if errorlevel 1 (
    echo.
    echo Error during analysis!
) else (
    echo.
    echo Analysis complete! Check the results\ folder.
)

pause
