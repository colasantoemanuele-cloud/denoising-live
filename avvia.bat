@echo off
rem Avvia denoising_live con il Digidata 1322A (PC del laboratorio, Windows XP).
cd /d "%~dp0"
set PY=C:\Python34\python.exe
if not exist "%PY%" set PY=python
"%PY%" -c "import sys" >nul 2>&1
if errorlevel 1 (
  echo ERRORE: Python 3.4 non trovato ^(C:\Python34\python.exe^).
  echo Rimedio: eseguire prima installa.bat ^(GUIDA_LABORATORIO.txt, parte B^).
  pause
  exit /b 1
)
"%PY%" main.py --digidata %*
if errorlevel 1 (
  echo.
  echo Il programma si e' chiuso con un errore. Mandare la cartella "log".
  pause
)
