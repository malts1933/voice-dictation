@echo off
cd /d %~dp0
echo Starting voice dictation server (model: small)...
venv_dictation\Scripts\python.exe server.py --model small --port 8765
pause