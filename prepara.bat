@echo off
rem =====================================================================
rem  prepara.bat - DA USARE SUL PC CON INTERNET (Windows 10 o 11).
rem  Scarica nella cartella del progetto i due file che servono al PC del
rem  laboratorio (Python 3.4.4 e numpy 1.15.4), con curl.exe oppure, se non
rem  c'e', con PowerShell; poi controlla tutta la cartella (nomi, dimensioni
rem  e SHA-256) con verifica_pacchetto.bat.
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
set MSI=python-3.4.4.msi
set URL_MSI=https://www.python.org/ftp/python/3.4.4/python-3.4.4.msi
set WHL=numpy-1.15.4-cp34-none-win32.whl
set URL_WHL=https://files.pythonhosted.org/packages/e6/10/798bd58c97068aad4cb24e9ba60dcc7ce2e8aac7a871ea493708039a8100/numpy-1.15.4-cp34-none-win32.whl
set SCARICO_KO=0
echo.
echo ==== Preparazione della cartella per il PC del laboratorio ====
ver | find " 5." >nul
if errorlevel 1 goto non_xp
echo.
echo  Questo e' Windows XP: prepara.bat va usato sul PC con internet
echo  (Windows 10 o 11), non sul PC del laboratorio.
echo  Qui, sul PC del laboratorio, fai doppio clic su installa.bat.
echo.
pause
exit /b 1
:non_xp
if exist "main.py" goto scarica_tutto
echo.
echo  NON TROVO I FILE DEL PROGRAMMA in questa cartella.
echo  Prima estrai il file ZIP: clic destro sul file ZIP, "Estrai tutto...",
echo  poi apri la cartella estratta e fai doppio clic su prepara.bat da li'.
echo.
pause
exit /b 1

:scarica_tutto
call :scarica "%MSI%" 24932352 "%URL_MSI%"
call :scarica "%WHL%" 9932905 "%URL_WHL%"
echo.
echo ==== Controllo della cartella ====
call "%~dp0verifica_pacchetto.bat" /prepara
if errorlevel 1 goto problemi
echo.
echo =====================================================================
echo  TUTTO A POSTO: copia questa cartella sulla chiavetta
echo  [la cartella e' "%~dp0"]
echo =====================================================================
echo.
pause
exit /b 0

:problemi
echo.
echo =====================================================================
if "%SCARICO_KO%"=="0" goto problemi_altri
echo  Download non riuscito. Scarica a mano questi due link con il browser,
echo  salva i file in questa cartella e rilancia prepara.bat:
echo    %URL_MSI%
echo    %URL_WHL%
echo =====================================================================
pause
exit /b 1
:problemi_altri
echo  C'e' un problema nella cartella: leggi le righe qui sopra.
echo  Di solito basta scaricare di nuovo il ZIP del progetto, estrarlo e
echo  rilanciare prepara.bat.
echo =====================================================================
pause
exit /b 1

rem ---------------------------------------------------------------------
rem :scarica NOME DIMENSIONE INDIRIZZO
rem (call davanti a curl: cosi' i test possono sostituirlo con un curl.bat)
:scarica
if not exist "%~1" goto scarica_nuovo
if not "%~z1"=="%~2" goto scarica_nuovo
echo   gia' presente: %~1
goto :eof
:scarica_nuovo
if exist "%~1" del "%~1"
if exist "%~1.part" del "%~1.part"
echo   Scarico %~1 ...
call curl --version >nul 2>&1
if errorlevel 1 goto scarica_ps
call curl -L -f -sS --retry 2 -o "%~1.part" "%~3"
if errorlevel 1 goto scarica_ko
goto scarica_fine
:scarica_ps
rem indirizzo e destinazione passano per variabili d'ambiente lette da PowerShell
rem ($env:...): cosi' apostrofi, spazi, parentesi e & nel percorso non danno noia
set "DLIVE_URL=%~3"
set "DLIVE_DEST=%CD%\%~1.part"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = 3072; (New-Object Net.WebClient).DownloadFile($env:DLIVE_URL, $env:DLIVE_DEST)" >nul 2>&1
:scarica_fine
if not exist "%~1.part" goto scarica_ko
for %%p in ("%~1.part") do if not "%%~zp"=="%~2" goto scarica_ko
ren "%~1.part" "%~1"
if not exist "%~1" goto scarica_ko
echo   scaricato: %~1
goto :eof
:scarica_ko
if exist "%~1.part" del "%~1.part"
echo   NON riuscito: %~1
set SCARICO_KO=1
goto :eof
