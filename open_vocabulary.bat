@echo off
chcp 65001 >nul
if exist "%~dp0output\vocabulary.html" (
    start "" "%~dp0output\vocabulary.html"
) else (
    echo.
    echo  [!] vocabulary.html not found.
    echo  Run analysis first: HSK Menu ^> [5]
    echo.
    pause
)
