@echo off
set PORT=8005
set PYTHON_EXE=
cd /d "%~dp0"
start "" http://localhost:%PORT%/index.html
"%PYTHON_EXE%" preview_server.py --port %PORT%
