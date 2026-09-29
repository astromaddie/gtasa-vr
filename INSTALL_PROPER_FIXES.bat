@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install-optional-mod.ps1" -Kind properfixes %*
set "result=%errorlevel%"
echo(
pause
exit /b %result%
