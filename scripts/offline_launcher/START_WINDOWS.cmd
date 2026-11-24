@echo off
setlocal DisableDelayedExpansion
title Manufacturing AI Workshop - Offline
chcp 65001 >nul
if not exist "%~dp0runtime\python\python.exe" goto missing
if not exist "%~dp0scripts\launch_offline.py" goto missing
if not exist "%~dp0app\index.html" goto missing
"%~dp0runtime\python\python.exe" -I -X utf8 "%~dp0scripts\launch_offline.py" %*
set "WORKSHOP_EXIT=%ERRORLEVEL%"
if not "%WORKSHOP_EXIT%"=="0" pause
exit /b %WORKSHOP_EXIT%
:missing
echo Please extract the ENTIRE Windows offline ZIP before running this file.
echo Keep START_WINDOWS.cmd, app, scripts and runtime in the same folder.
echo No Python installation is required. See the included readme for help.
pause
exit /b 1
