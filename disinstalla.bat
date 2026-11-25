@echo off
rem =====================================================================
rem  Disinstallazione di denoising_live (Windows XP)
rem  Si lancia dalla cartella d'installazione (quella con installa.bat).
rem  Toglie i collegamenti e i file del programma; CONSERVA i dati registrati,
rem  i log, config.ini e i report della diagnostica.  Non tocca WinWCP, le DLL
rem  Axon, WinASPI ne' le DLL di sistema.
rem =====================================================================
setlocal
cd /d "%~dp0"
set PYDIR=C:\Python34
set DEST=C:\denoising_live
set PY_NOSTRO=0
if exist "%DEST%\python_installato_da_denoising_live.txt" set PY_NOSTRO=1
if exist "%DEST%" goto chiedi
echo denoising_live non risulta installato: la cartella %DEST% non esiste.
echo Tolgo solo gli eventuali collegamenti rimasti sul desktop.
if exist crea_collegamenti.vbs cscript //nologo crea_collegamenti.vbs /rimuovi
goto python
:chiedi
echo Verranno rimossi: i collegamenti sul desktop e i file del programma in %DEST%.
echo Restano: %DEST%\dati_registrati, %DEST%\log, config.ini, report e file della diagnostica.
set RISP=n
set /p RISP=Continuare? (s/n)
if /i not "%RISP%"=="s" goto fine

echo.
echo ==== 1/3 Collegamenti sul desktop ====
if exist crea_collegamenti.vbs (
  cscript //nologo crea_collegamenti.vbs /rimuovi
) else (
  echo Manca crea_collegamenti.vbs in questa cartella: cancellare a mano dal desktop
  echo i collegamenti "denoising_live ^(Digidata^)", "Diagnostica Digidata",
  echo "denoising_live ^(simulazione^)" e "Raccogli risultati".
)

echo.
echo ==== 2/3 File del programma in %DEST% ====
for %%d in (dlive dll dati_prova __pycache__) do if exist "%DEST%\%%d" rd /s /q "%DEST%\%%d"
for %%f in (main.py diagnostica_digidata.py avvia.bat avvia_simulazione.bat diagnostica.bat raccogli_risultati.bat README.md GUIDA_RAPIDA.txt GUIDA_COMPLETA.txt GUIDA_LABORATORIO.txt cartella_installazione.txt numpy_verificato.txt config.ini.precedente python_installato_da_denoising_live.txt) do if exist "%DEST%\%%f" del /q "%DEST%\%%f"
if exist "%DEST%\dlive" echo ATTENZIONE: non riesco a cancellare %DEST%\dlive: chiudere denoising_live e rilanciare.
rd "%DEST%" 2>nul
if exist "%DEST%" echo In %DEST% restano dati e configurazione: cancellarli a mano solo se non servono.

:python
echo.
echo ==== 3/3 Python 3.4.4 ====
if "%PY_NOSTRO%"=="1" goto chiedi_python
echo Python in %PYDIR% non e' stato installato da installa.bat: lo lascio com'e'.
echo (installa.bat vi aveva aggiunto numpy 1.15.4, che resta.)
goto fine
:chiedi_python
set RISP=n
set /p RISP=Disinstallare anche Python 3.4.4 (installato da installa.bat; altri programmi potrebbero usarlo)? (s/n)
if /i not "%RISP%"=="s" goto fine
if exist "%~dp0python-3.4.4.msi" (
  msiexec /x "%~dp0python-3.4.4.msi" /qb
) else (
  echo Manca python-3.4.4.msi in questa cartella: disinstallare Python 3.4.4 da
  echo Pannello di controllo, Installazione applicazioni.
)

:fine
echo.
echo Fine.
pause
exit /b 0
