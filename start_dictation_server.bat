@echo off
cd /d %~dp0
echo Starting voice dictation server (model: small)...
if not exist "%USERPROFILE%\.voice-dictation\venv\Scripts\python.exe" (
    echo First run - setting up environment...
    python bootstrap.py --requirements requirements.txt
    if errorlevel 1 (
        echo Setup failed. Install Python 3.11 from https://www.python.org/downloads/
        pause
        exit /b 1
    )
)
"%USERPROFILE%\.voice-dictation\venv\Scripts\python.exe" server.py --model small --port 8765
pause