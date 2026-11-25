@echo off
rem =====================================================================
rem  Disinstallazione di denoising_live (Windows XP)
rem  Si lancia dalla cartella d'installazione (quella con installa.bat).
rem  Toglie i collegamenti e i file del programma; CONSERVA i dati registrati,
rem  i log, config.ini e i report della diagnostica.  Non tocca WinWCP, le DLL
rem  Axon, WinASPI ne' le DLL di sistema.
rem  Regole di scrittura: vedi installa.bat (niente blocchi con variabili,
rem  percorsi tra virgolette, niente %X:...% su variabili non definite).
rem =====================================================================
rem --- la finestra non si chiude mai da sola: ci si rilancia dentro cmd /k
if defined DLIVE_FINESTRA goto dentro
set DLIVE_FINESTRA=1
cmd /k call "%~f0" %*
exit /b
:dentro
echo denoising_live versione 2026-11-25
setlocal
cd /d "%~dp0"
set "PYDIR=C:\Python34"
set "DEST=C:\denoising_live"
set PY_NOSTRO=0
if exist "%DEST%\python_installato_da_denoising_live.txt" set PY_NOSTRO=1
if exist "%DEST%" goto chiedi
echo denoising_live non risulta installato: la cartella C:\denoising_live non esiste.
echo Tolgo solo gli eventuali collegamenti rimasti sul desktop.
if exist crea_collegamenti.vbs cscript //nologo crea_collegamenti.vbs /rimuovi
goto python
:chiedi
echo Verranno rimossi: i collegamenti sul desktop e i file del programma in C:\denoising_live.
echo Restano: dati_registrati, log, config.ini, report e file della diagnostica.
set RISP=n
set /p RISP=Continuare? [s/n] 
if /i not "%RISP%"=="s" goto fine

echo.
echo ==== 1/3 Collegamenti sul desktop ====
if not exist crea_collegamenti.vbs goto senza_vbs
cscript //nologo crea_collegamenti.vbs /rimuovi
goto file_programma
:senza_vbs
echo Manca crea_collegamenti.vbs in questa cartella: cancellare a mano dal desktop
echo i collegamenti "denoising_live [Digidata]", "Diagnostica Digidata",
echo "Raccogli risultati" e, se c'e', "denoising_live [simulazione]".

:file_programma
echo.
echo ==== 2/3 File del programma in C:\denoising_live ====
for %%d in (dlive dll dati_prova __pycache__) do if exist "%DEST%\%%d" rd /s /q "%DEST%\%%d"
for %%f in (main.py diagnostica_digidata.py avvia.bat avvia_simulazione.bat diagnostica.bat raccogli_risultati.bat README.md GUIDA_RAPIDA.txt GUIDA_COMPLETA.txt GUIDA_LABORATORIO.txt cartella_installazione.txt python_percorso.txt numpy_verificato.txt config.ini.precedente python_installato_da_denoising_live.txt) do if exist "%DEST%\%%f" del /q "%DEST%\%%f"
if exist "%DEST%\dlive" echo ATTENZIONE: non riesco a cancellare C:\denoising_live\dlive: chiudere denoising_live e rilanciare.
rd "%DEST%" 2>nul
if exist "%DEST%" echo In C:\denoising_live restano dati e configurazione: cancellarli a mano solo se non servono.

:python
echo.
echo ==== 3/3 Python 3.4.4 ====
if "%PY_NOSTRO%"=="1" goto chiedi_python
echo Python in C:\Python34 non e' stato installato da installa.bat: lo lascio com'e'.
echo [installa.bat vi aveva aggiunto numpy 1.15.4, che resta.]
goto fine
:chiedi_python
set RISP=n
set /p RISP=Disinstallare anche Python 3.4.4 [installato da installa.bat; altri programmi potrebbero usarlo]? [s/n] 
if /i not "%RISP%"=="s" goto fine
if not exist "%~dp0python-3.4.4.msi" goto senza_msi
msiexec /x "%~dp0python-3.4.4.msi" /qb
goto fine
:senza_msi
echo Manca python-3.4.4.msi in questa cartella: disinstallare Python 3.4.4 da
echo Pannello di controllo, Installazione applicazioni.

:fine
echo.
echo Fine.
pause
exit /b 0
