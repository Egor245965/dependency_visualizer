@echo off

set "GRAPHVIZ_BIN=C:\Program Files\Graphviz\bin"

where dot >nul 2>nul
if errorlevel 1 (
    if exist "%GRAPHVIZ_BIN%\dot.exe" (
        set "PATH=%PATH%;%GRAPHVIZ_BIN%"
    )
)

if "%~1"=="" (
    python src\main.py ^
        --package express ^
        --repository https://registry.npmjs.org ^
        --output graph.png ^
        --max-depth 2
) else (
    python src\main.py %*
)

pause