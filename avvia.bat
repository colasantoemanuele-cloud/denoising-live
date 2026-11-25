@echo off
rem Avvia denoising_live con il Digidata 1322A (PC del laboratorio, Windows XP).
rem Regole di scrittura: vedi installa.bat (niente blocchi con variabili,
rem percorsi tra virgolette, niente %X:...% su variabili non definite).
rem --- la finestra non si chiude mai da sola: ci si rilancia dentro cmd /k
if defined DLIVE_FINESTRA goto dentro
set DLIVE_FINESTRA=1
cmd /k call "%~f0" %*
exit /b
:dentro
echo denoising_live versione 2026-11-25
cd /d "%~dp0"
rem --- quale Python: quello scritto da installa.bat in python_percorso.txt,
rem     altrimenti C:\Python34 (installa.bat non cambia il PATH)
set "PY=C:\Python34\python.exe"
set PYDIR_LETTO=
if exist "%~dp0python_percorso.txt" set /p PYDIR_LETTO=<"%~dp0python_percorso.txt"
if not defined PYDIR_LETTO goto py_scelto
if "%PYDIR_LETTO:~-1%"=="\" set "PYDIR_LETTO=%PYDIR_LETTO:~0,-1%"
if exist "%PYDIR_LETTO%\python.exe" set "PY=%PYDIR_LETTO%\python.exe"
:py_scelto
if exist "%PY%" goto py_ok
echo ERRORE: Python 3.4 non trovato [ne' in python_percorso.txt ne' in C:\Python34].
echo Rimedio: eseguire prima installa.bat dalla cartella d'installazione
echo [GUIDA_COMPLETA.txt, parte B].
pause
exit /b 1
:py_ok
"%PY%" main.py --digidata %*
if not errorlevel 1 goto fine
echo.
echo Il programma si e' chiuso con un errore. Fare doppio clic su Raccogli risultati
echo e mandare la cartella.
pause
:fine
exit /b
