@echo off
cd /d %~dp0
echo ============================================
echo  Voice Dictation - one-time setup
echo ============================================
echo.
if not exist venv_dictation\Scripts\python.exe (
    echo [1/2] Creating Python environment...
    python -m venv venv_dictation
    if errorlevel 1 (
        echo.
        echo ERROR: Python not found. Install Python 3.10+ from https://www.python.org/downloads/
        echo and tick "Add Python to PATH" during installation.
        pause
        exit /b 1
    )
) else (
    echo [1/2] Python environment already exists
)
echo [2/2] Installing faster-whisper and dependencies (first run ~1 min)...
venv_dictation\Scripts\python.exe -m pip install -r requirements.txt
echo.
echo Done! Install the extension (voice-dictation-0.1.4.vsix)
echo and press Ctrl+Alt+Space to start dictating.
echo.
pause