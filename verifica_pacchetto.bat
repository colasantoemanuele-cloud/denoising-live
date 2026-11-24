@echo off
rem =====================================================================
rem  verifica_pacchetto.bat - controlla la cartella d'installazione di
rem  denoising_live prima di copiarla sulla chiavetta (e di nuovo sul PC
rem  del laboratorio): i due file scaricati a parte e i file del
rem  programma, con il nome e la dimensione giusti.  Dice cosa manca e
rem  come rimediare.  Non modifica nulla.
rem  Funziona su Windows XP e su Windows 10/11.  Uso: doppio clic.
rem  (installa.bat lo chiama con l'opzione /installa: niente pausa.)
rem =====================================================================
setlocal
cd /d "%~dp0"
set MODO=%~1
set PROBLEMI=0
set PROG_N=0
set PROG_KO=0
echo.
echo ==== Controllo della cartella %~dp0 ====
if exist "main.py" goto scaricati
echo.
echo   NON TROVO I FILE DEL PROGRAMMA in questa cartella.
echo   Di solito succede quando si apre verifica_pacchetto.bat direttamente
echo   dal file ZIP senza estrarlo.  Rimedio: clic destro sul file ZIP,
echo   "Estrai tutto...", aprire la cartella estratta e rilanciare da li'.
set PROBLEMI=1
goto fine

:scaricati
echo.
echo -- 1. I due file da scaricare a parte, in questa stessa cartella --
call :scaricato "python-3.4.4.msi" 24932352 46c8f9f63cf02987e8bf23934b2f471e1868b24748c5bb551efcf4863b43ca6c "https://www.python.org/ftp/python/3.4.4/python-3.4.4.msi"
call :scaricato "numpy-1.15.4-cp34-none-win32.whl" 9932905 df04f4bad8a359daa2ff74f8108ea051670cafbca533bb2636c58b16e962989e "https://files.pythonhosted.org/packages/e6/10/798bd58c97068aad4cb24e9ba60dcc7ce2e8aac7a871ea493708039a8100/numpy-1.15.4-cp34-none-win32.whl"
echo.
echo -- 2. File del programma --
rem ---- INIZIO ELENCO (generato da strumenti/genera_verifica_pacchetto.py: non modificare a mano)
call :file "installa.bat" 12827
call :file "disinstalla.bat" 2908
call :file "crea_collegamenti.vbs" 1012
call :file "main.py" 7788
call :file "diagnostica_digidata.py" 23513
call :file "avvia.bat" 546
call :file "avvia_simulazione.bat" 237
call :file "diagnostica.bat" 1530
call :file "README.md" 62148
call :file "GUIDA_LABORATORIO.txt" 13585
call :file "config.ini" ""
call :file "dlive\__init__.py" 0
call :file "dlive\acquisizione.py" 22314
call :file "dlive\compat.py" 1871
call :file "dlive\config.py" 16632
call :file "dlive\filters.py" 17791
call :file "dlive\gui.py" 56157
call :file "dlive\lpf8.py" 6192
call :file "dlive\pacchetto.py" 5130
call :file "dlive\recorder.py" 11777
call :file "dlive\registro.py" 1468
call :file "dlive\rilevamento.py" 20691
call :file "dlive\scala.py" 7613
call :file "dlive\sysinfo.py" 6857
call :file "dlive\verifica_numpy.py" 2495
call :file "dlive\wcpfile.py" 24584
call :file "dlive\winwcp_impostazioni.py" 18951
call :file "dlive\devices\__init__.py" 0
call :file "dlive\devices\axdd132x.py" 14262
call :file "dlive\devices\base.py" 1992
call :file "dlive\devices\dd132x_finto.py" 6941
call :file "dlive\devices\digidata.py" 22977
call :file "dlive\devices\simulated.py" 13223
rem ---- FINE ELENCO
if "%PROG_KO%"=="0" echo   ok: %PROG_N% file del programma, tutti con la dimensione giusta
if "%PROG_KO%"=="0" goto fine
echo   Rimedio: scaricare di nuovo il ZIP del progetto ^(pulsante Code, Download ZIP^),
echo   estrarlo tutto, senza aprire ne' modificare i file, e rimettere nella
echo   cartella estratta i due file del punto 1.

:fine
echo.
echo =====================================================================
if not "%PROBLEMI%"=="0" goto fine_problemi
echo  TUTTO A POSTO: la cartella e' completa.
if /i "%MODO%"=="/installa" goto fine_riga
echo  - sul PC con internet: ora copiare l'intera cartella sulla chiavetta USB;
echo  - sul PC del laboratorio: ora fare doppio clic su installa.bat.
:fine_riga
echo =====================================================================
goto uscita
:fine_problemi
echo  ATTENZIONE: %PROBLEMI% problemi, elencati qui sopra con il rimedio.
echo  Correggerli e rilanciare verifica_pacchetto.bat.
echo =====================================================================
:uscita
if /i not "%MODO%"=="/installa" pause
endlocal & exit /b %PROBLEMI%

rem ---------------------------------------------------------------------
rem :scaricato NOME DIMENSIONE SHA256 INDIRIZZO
:scaricato
if exist "%~1" goto scaricato_c
echo   MANCA %~1
echo         Scaricarlo da: %~4
echo         e salvarlo in questa cartella con questo nome esatto.
for %%f in (%~n1*) do echo         Qui c'e' "%%~nxf": se e' lo stesso file, rinominarlo esattamente %~1
set /a PROBLEMI+=1
goto :eof
:scaricato_c
if "%~z1"=="%~2" goto scaricato_hash
echo   DIMENSIONE ERRATA %~1: %~z1 byte invece di %~2
echo         Scaricamento interrotto o file sbagliato: cancellarlo e
echo         scaricarlo di nuovo da: %~4
set /a PROBLEMI+=1
goto :eof
:scaricato_hash
if /i "%MODO%"=="/installa" goto scaricato_ok
call certutil -hashfile "%~1" SHA256 >nul 2>&1
if errorlevel 1 goto scaricato_ok
set H=
set LETTO=
rem l'hash e' la riga di certutil senza ":" (Windows 7 separa i byte con spazi)
for /f "delims=" %%h in ('certutil -hashfile "%~1" SHA256') do (set "L=%%h" & call :riga_hash "%~3")
if defined H (
  echo   ok %~1  %~z1 byte, SHA-256 verificato
  goto :eof
)
rem certutil non ha dato nessuna riga di hash: non si giudica (lo controlla installa.bat)
if not defined LETTO goto scaricato_ok
echo   SHA-256 ERRATO %~1
echo         atteso: %~3
echo         Il file e' danneggiato o non e' quello giusto: cancellarlo e
echo         scaricarlo di nuovo da: %~4
set /a PROBLEMI+=1
goto :eof
:scaricato_ok
echo   ok %~1  %~z1 byte
goto :eof
:riga_hash
set "L=%L: =%"
if "%L%"=="" goto :eof
if not "%L::=%"=="%L%" goto :eof
set LETTO=1
if /i "%L%"=="%~1" set H=1
goto :eof

rem ---------------------------------------------------------------------
rem :file PERCORSO DIMENSIONE   ("" = dimensione non controllata)
:file
set /a PROG_N+=1
if exist "%~1" goto file_c
echo   MANCA %~1
set /a PROBLEMI+=1
set /a PROG_KO+=1
goto :eof
:file_c
if "%~2"=="" goto :eof
if "%~z1"=="%~2" goto :eof
echo   DIMENSIONE ERRATA %~1: %~z1 byte invece di %~2
set /a PROBLEMI+=1
set /a PROG_KO+=1
goto :eof
