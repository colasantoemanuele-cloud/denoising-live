@echo off
rem Avvia denoising_live in simulazione (riproduce i file .wcp di prova), senza scheda.
rem Non ha un'icona: nella repository non ci sono i file di prova (servono i propri .wcp).
echo denoising_live versione 2026-11-25
cd /d "%~dp0"
set "PY=C:\Python34\python.exe"
if not exist "%PY%" set PY=python
"%PY%" main.py --simulazione %*
if errorlevel 1 pause
