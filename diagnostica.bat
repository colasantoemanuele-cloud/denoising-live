@echo off
rem Diagnostica del Digidata: DA ESEGUIRE PER PRIMA. Chiudere WinWCP/AxoScope/Clampex.
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
if exist diagnostica_digidata.py goto script_ok
echo ERRORE: manca diagnostica_digidata.py nella cartella del programma:
echo   "%~dp0"
echo Rimedio: rilanciare installa.bat dalla cartella d'installazione.
pause
exit /b 1
:script_ok
tasklist 2>nul | find /i "winwcp.exe" >nul
if errorlevel 1 goto winwcp_chiuso
echo ATTENZIONE: WinWCP e' aperto. La scheda si usa da un solo programma alla volta.
echo Rimedio: chiudere WinWCP, poi premere un tasto per continuare.
pause
:winwcp_chiuso
echo Diagnostica in corso [circa 30 secondi]...
"%PY%" diagnostica_digidata.py %*
set RC=%ERRORLEVEL%
echo.
if "%RC%"=="0" echo ESITO: nessun errore. Si puo' passare all'anteprima ^(avvia.bat^).
if "%RC%"=="1" echo ESITO: ci sono errori: leggere il RIEPILOGO in fondo a report_diagnostica.txt.
if "%RC%"=="0" goto esito_scritto
if "%RC%"=="1" goto esito_scritto
echo ESITO: la diagnostica si e' interrotta per un errore imprevisto [codice %RC%]: fare doppio clic su Raccogli risultati e mandare la cartella.
:esito_scritto
echo Il risultato e' nel file report_diagnostica.txt [si apre ora con il Blocco note].
if exist report_diagnostica.txt start notepad report_diagnostica.txt
pause
exit /b %RC%
