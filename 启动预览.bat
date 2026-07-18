@echo off
set VIDEOS_DIR=%~dp0videos
set PYTHON_EXE=
set PORT=8000

if not defined PYTHON_EXE (
    echo 未设置 PYTHON_EXE，请先运行 generate.py 或手动编辑本文件顶部 & pause & exit
)
start "" http://localhost:%PORT%/index.html
"%PYTHON_EXE%" -m http.server %PORT% --directory "%VIDEOS_DIR%"
