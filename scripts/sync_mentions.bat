@echo off
chcp 65001 >nul
echo [%date% %time%] mentions.json 동기화 시작...
powershell.exe -ExecutionPolicy Bypass -File "%~dp0pull_mentions.ps1"
echo.
pause
