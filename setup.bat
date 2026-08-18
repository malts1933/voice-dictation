@echo off
cd /d %~dp0
echo ============================================
echo  Voice Dictation - one-time setup
echo ============================================
echo.
echo Running auto-setup (Python, environment, dependencies)...
python bootstrap.py --requirements requirements.txt
if errorlevel 1 (
    echo.
    echo Setup failed. Install Python 3.11 from https://www.python.org/downloads/
    echo (tick "Add Python to PATH"), then run this file again.
    pause
    exit /b 1
)
echo.
echo Done! Environment is ready at %USERPROFILE%\.voice-dictation\venv
echo Install the extension and press Ctrl+Alt+G to start dictating.
echo.
pause