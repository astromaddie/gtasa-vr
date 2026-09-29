@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\disable-optional-mods.ps1" %*
set "result=%errorlevel%"
echo(
pause
exit /b %result%
