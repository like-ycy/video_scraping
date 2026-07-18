@echo off
set VIDEOS_DIR=%~dp0videos
set PYTHON_EXE=
set PORT=8000

REM 将 videos 绝对路径写入 _config.json，供预览页拼本地 PotPlayer 路径
powershell -NoProfile -Command "Set-Content -Path '%VIDEOS_DIR%\_config.json' -Value ('{''root'': ''' + (Resolve-Path '%VIDEOS_DIR%').Path.Replace('\','\\') + '''}') -Encoding UTF8"

where uv >nul 2>&1 && set USE_UV=1
if defined USE_UV (
    start "" http://localhost:%PORT%/index.html
    uv run python -m http.server %PORT% --directory "%VIDEOS_DIR%"
) else if defined PYTHON_EXE (
    start "" http://localhost:%PORT%/index.html
    "%PYTHON_EXE%" -m http.server %PORT% --directory "%VIDEOS_DIR%"
) else (
    echo 未找到 uv 且未设置 PYTHON_EXE，请编辑本文件顶部 & pause & exit
)
