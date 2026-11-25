@echo off
rem Diagnostica del Digidata: DA ESEGUIRE PER PRIMA. Chiudere WinWCP/AxoScope/Clampex.
cd /d "%~dp0"
set PY=C:\Python34\python.exe
if not exist "%PY%" set PY=python
"%PY%" -c "import sys" >nul 2>&1
if errorlevel 1 (
  echo ERRORE: Python 3.4 non trovato ^(C:\Python34\python.exe^).
  echo Rimedio: eseguire prima installa.bat dalla cartella d'installazione
  echo ^(GUIDA_COMPLETA.txt, parte B^).
  pause
  exit /b 1
)
if not exist diagnostica_digidata.py (
  echo ERRORE: manca diagnostica_digidata.py in %~dp0
  echo Rimedio: rilanciare installa.bat dalla cartella d'installazione.
  pause
  exit /b 1
)
tasklist 2>nul | find /i "winwcp.exe" >nul
if not errorlevel 1 (
  echo ATTENZIONE: WinWCP e' aperto. La scheda si usa da un solo programma alla volta.
  echo Rimedio: chiudere WinWCP, poi premere un tasto per continuare.
  pause
)
echo Diagnostica in corso (circa 30 secondi)...
"%PY%" diagnostica_digidata.py %*
set RC=%ERRORLEVEL%
echo.
if "%RC%"=="0" echo ESITO: nessun errore. Si puo' passare all'anteprima ^(avvia.bat^).
if "%RC%"=="1" echo ESITO: ci sono errori: leggere il RIEPILOGO in fondo a report_diagnostica.txt.
if not "%RC%"=="0" if not "%RC%"=="1" echo ESITO: la diagnostica si e' interrotta per un errore imprevisto ^(codice %RC%^): mandare report_diagnostica.txt e la cartella log.
echo Il risultato e' nel file report_diagnostica.txt (si apre ora con il Blocco note).
if exist report_diagnostica.txt start notepad report_diagnostica.txt
pause
exit /b %RC%
