@echo off
set PORT=8000
set PYTHON_EXE=
cd /d "%~dp0"
start "" http://localhost:%PORT%/index.html
"%PYTHON_EXE%" -m http.server %PORT%
