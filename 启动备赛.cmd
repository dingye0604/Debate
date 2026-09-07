@echo off
cd /d "%~dp0engineering\debate-workbench"
if not exist ".runtime\python.exe" (
  echo Project environment is missing. See README.md.
  pause
  exit /b 1
)
".runtime\python.exe" run.py
if errorlevel 1 pause
