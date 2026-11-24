@echo off
rem Avvia denoising_live in simulazione (riproduce i file .wcp di prova), senza scheda.
cd /d "%~dp0"
set PY=C:\Python34\python.exe
if not exist "%PY%" set PY=python
"%PY%" main.py --simulazione %*
if errorlevel 1 pause
