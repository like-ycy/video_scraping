@echo off
set PYTHON_EXE=
if not defined PYTHON_EXE (
    for /f "delims=" %%p in ('where python') do (
        set "PYTHON_EXE=%%p"
        goto :found_python
    )
)
:found_python
if not defined PYTHON_EXE (
    echo 未找到 python，请编辑本文件顶部 PYTHON_EXE 为 python 绝对路径 & pause & exit
)

set VIDEOS_DIR=%~1
if not defined VIDEOS_DIR (
    echo 用法：运行刮削.bat ^<视频根目录^> & pause & exit
)

"%PYTHON_EXE%" "%~dp0src\generate.py" --dir "%VIDEOS_DIR%"
pause
