@echo off
cd /d "%~dp0"
if not exist ".runtime\python.exe" (
  echo Create the project environment first:
  echo conda env create --prefix .runtime --file environment.yml
  pause
  exit /b 1
)
".runtime\python.exe" run.py
if errorlevel 1 pause
