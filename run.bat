@echo off

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