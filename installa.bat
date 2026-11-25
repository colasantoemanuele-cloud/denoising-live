@echo off
rem =====================================================================
rem  Installazione di denoising_live sul PC del laboratorio (Windows XP
rem  SP3 a 32 bit).  Non serve la rete.  Utente amministratore.
rem  Si lancia con doppio clic dalla cartella del progetto, che deve
rem  contenere anche i due file scaricati a parte:
rem      python-3.4.4.msi
rem      numpy-1.15.4-cp34-none-win32.whl
rem  (li scarica prepara.bat sul PC con internet: GUIDA_RAPIDA.txt).
rem  Controlla la cartella con verifica_pacchetto.bat: non serve lanciarlo a mano.
rem  La DLL Axon (AxDD132x.dll, Axoutils32.dll) NON e' inclusa: si usa
rem  quella di WinWCP gia' installato.  WinASPI e il driver SCSI vengono
rem  dall'installazione di AxoScope.
rem
rem  Regole di scrittura (cmd espande %VAR% quando LEGGE la riga, prima di
rem  valutare gli IF): niente blocchi ( ... ) con variabili dentro; percorsi
rem  sempre tra virgolette (anche negli echo e nei set "X=..."); niente
rem  %X:~...% su una variabile che puo' non essere definita (prima
rem  "if not defined X goto ...").  Controllato da tests/test_bat_espansione.py.
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
set "LOG=%~dp0installa_log.txt"
set AVVISI=0
set PY_NOSTRO=0
set ADMIN=si
echo.
echo ==== 0/8 Rilevamento del PC (scritto anche in installa_log.txt) ====
> "%LOG%" echo denoising_live versione 2026-11-25
if errorlevel 1 goto log_non_scrivibile
>> "%LOG%" echo INSTALLAZIONE denoising_live - %DATE% %TIME% - %COMPUTERNAME%
>> "%LOG%" echo Cartella d'installazione: "%~dp0"
ver >> "%LOG%"
ver
rem Service Pack (dal registro; la riga puo' mancare)
set SP=
for /f "delims=" %%l in ('reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion" /v CSDVersion 2^>nul ^| find "REG_SZ"') do set "SP=%%l"
if not defined SP goto sp_letto
set "SP=%SP:*REG_SZ=%"
for /f "tokens=*" %%x in ("%SP%") do set "SP=%%x"
:sp_letto
if not defined SP set SP=nessun Service Pack
echo Service Pack: %SP%
>> "%LOG%" echo Service Pack: %SP%
set BIT=32 bit
if /i "%PROCESSOR_ARCHITECTURE%"=="AMD64" set BIT=64 bit
if defined PROCESSOR_ARCHITEW6432 set BIT=64 bit
echo Windows a %BIT% [%PROCESSOR_ARCHITECTURE%]
>> "%LOG%" echo Windows a %BIT% [%PROCESSOR_ARCHITECTURE% %PROCESSOR_ARCHITEW6432%]
ver | find " 5.1." >nul
if errorlevel 1 goto sp_ok
echo %SP% | findstr /c:"Service Pack 2" /c:"Service Pack 3" >nul
if not errorlevel 1 goto sp_ok
echo.
echo ATTENZIONE: Windows XP senza Service Pack 2 o 3.  Python 3.4 non funziona
echo   (gli serve msvcr100.dll, che richiede almeno il Service Pack 2).
echo   Rimedio: installare il Service Pack 3 di Windows XP, poi rilanciare.
>> "%LOG%" echo ATTENZIONE: serve XP SP2 o SP3
set /a AVVISI+=1
:sp_ok
fsutil fsinfo drives >nul 2>&1
if errorlevel 1 set ADMIN=no
echo Utente amministratore: %ADMIN%
>> "%LOG%" echo Amministratore: %ADMIN%
set SPAZIO=
for /f "delims=" %%l in ('dir C:\ 2^>nul ^| find /i "byte"') do set "SPAZIO=%%l"
if not defined SPAZIO set SPAZIO=non letto
echo Disco C: %SPAZIO%
>> "%LOG%" echo Disco C: %SPAZIO%
if exist "%SystemRoot%\system32\msvcr100.dll" >> "%LOG%" echo msvcr100.dll presente
if not exist "%SystemRoot%\system32\msvcr100.dll" >> "%LOG%" echo msvcr100.dll assente: la installa Python
>> "%LOG%" echo Python registrati:
reg query "HKLM\SOFTWARE\Python\PythonCore" /s >> "%LOG%" 2>&1
dir /b /ad C:\Python* >> "%LOG%" 2>&1
rem Python 3.4 gia' installato altrove (dal registro; la riga puo' mancare)
set PYREG=
for /f "delims=" %%l in ('reg query "HKLM\SOFTWARE\Python\PythonCore\3.4\InstallPath" /ve 2^>nul ^| find "REG_SZ"') do set "PYREG=%%l"
if not defined PYREG goto pyreg_fatto
set "PYREG=%PYREG:*REG_SZ=%"
for /f "tokens=*" %%x in ("%PYREG%") do set "PYREG=%%x"
if not defined PYREG goto pyreg_fatto
if "%PYREG:~-1%"=="\" set "PYREG=%PYREG:~0,-1%"
if exist "%PYDIR%\python.exe" goto pyreg_fatto
if not exist "%PYREG%\python.exe" goto pyreg_fatto
echo Trovato Python 3.4 gia' installato in "%PYREG%": uso quello.
>> "%LOG%" echo Uso il Python 3.4 gia' installato in "%PYREG%"
set "PYDIR=%PYREG%"
:pyreg_fatto

echo.
echo ==== 1/8 Controllo dei file della cartella ====
if exist "verifica_pacchetto.bat" goto verifica_c
echo MANCA verifica_pacchetto.bat in questa cartella.
echo Rimedio: scaricare di nuovo il ZIP del progetto ed estrarlo tutto.
goto errore
:verifica_c
call "%~dp0verifica_pacchetto.bat" /installa
if not errorlevel 1 goto verifica_ok
echo Rimedio: sul PC con internet fare doppio clic su prepara.bat finche' dice
echo TUTTO A POSTO, poi ricopiare la cartella [GUIDA_RAPIDA.txt, passi 1-3].
goto errore
:verifica_ok
>> "%LOG%" echo Cartella completa

echo.
echo ==== 2/8 Python 3.4.4 a 32 bit ====
if exist "%PYDIR%\python.exe" goto python_presente
if "%ADMIN%"=="si" goto python_installa
echo ATTENZIONE: questo utente sembra NON amministratore: l'installazione di Python
echo   probabilmente fallira'.  Se fallisce: uscire da Windows, entrare con un utente
echo   amministratore e rilanciare installa.bat.  Provo comunque.
:python_installa
echo Installo Python 3.4.4 in "%PYDIR%" - attendere 1-2 minuti...
rem Solo interprete, Tcl/Tk (serve a tkinter), libreria C e pip.  Esclusi:
rem PrependPath (modificherebbe il PATH di sistema), Extensions (associazioni
rem dei file .py), Documentation, Tools, Testsuite.
msiexec /i "%~dp0python-3.4.4.msi" /qb ALLUSERS=1 TARGETDIR="%PYDIR%" ADDLOCAL=DefaultFeature,SharedCRT,PrivateCRT,TclTk,pip_feature /l*v "%~dp0python_msi_log.txt"
set RC=%ERRORLEVEL%
>> "%LOG%" echo msiexec: codice %RC%
if "%RC%"=="0" goto python_installato
if "%RC%"=="3010" goto python_installato
echo.
echo ERRORE: l'installazione di Python non e' riuscita [msiexec, codice %RC%].
if "%RC%"=="1602" echo   Installazione annullata: rilanciare installa.bat e lasciarla finire.
if "%RC%"=="1603" echo   Errore durante l'installazione: dettagli in python_msi_log.txt, in questa cartella.
if "%RC%"=="1618" echo   C'e' gia' un'altra installazione in corso: attenderne la fine o riavviare il PC, poi rilanciare.
if "%RC%"=="1619" echo   python-3.4.4.msi non si apre: e' danneggiato. Scaricarlo di nuovo con prepara.bat.
if "%RC%"=="1620" echo   python-3.4.4.msi non si apre: e' danneggiato. Scaricarlo di nuovo con prepara.bat.
if "%RC%"=="1625" echo   Windows non permette l'installazione a questo utente: usare un utente amministratore.
echo   Il dettaglio completo e' in python_msi_log.txt, in questa cartella: mandarlo.
goto errore
:python_installato
set PY_NOSTRO=1
goto python_controllo
:python_presente
echo Python e' gia' presente in "%PYDIR%": non lo reinstallo.
:python_controllo
if exist "%PYDIR%\python.exe" goto python_c2
echo ERRORE: dopo l'installazione non trovo "%PYDIR%\python.exe".
echo Rimedio: vedere python_msi_log.txt in questa cartella; riavviare il PC e rilanciare installa.bat.
goto errore
:python_c2
"%PYDIR%\python.exe" -c "import sys, struct, ctypes, tkinter; assert sys.version_info[:2] == (3, 4), sys.version; assert struct.calcsize('P') == 4, 'serve Python a 32 bit'; print('Python OK: ' + sys.version)"
if not errorlevel 1 goto python_ok
echo.
echo ERRORE: il Python in "%PYDIR%" non e' un Python 3.4 a 32 bit completo di tkinter.
echo Rimedio: se quella cartella contiene un altro Python, disinstallarlo da Pannello di
echo controllo, Installazione applicazioni, e rilanciare installa.bat.
goto errore
:python_ok

echo.
echo ==== 3/8 Verifica degli SHA-256 dei file scaricati ====
"%PYDIR%\python.exe" -m dlive.pacchetto
if not errorlevel 1 goto hash_ok
echo Rimedio: riscaricare i file indicati sul PC con internet con prepara.bat.
goto errore
:hash_ok

echo.
echo ==== 4/8 numpy 1.15.4 ====
"%PYDIR%\python.exe" -m pip --version
if errorlevel 1 "%PYDIR%\python.exe" -m ensurepip
"%PYDIR%\python.exe" -m pip install --no-index --no-cache-dir --disable-pip-version-check "numpy-1.15.4-cp34-none-win32.whl"
"%PYDIR%\python.exe" -c "import numpy; numpy.fft.rfft(numpy.arange(100.0)); print('numpy ' + numpy.__version__ + ' OK')"
if not errorlevel 1 goto numpy_ok
echo ATTENZIONE: numpy non funziona su questo PC. Lo disinstallo:
echo il programma funzionera' lo stesso, con il percorso senza numpy [piu' lento].
>> "%LOG%" echo numpy non funziona: disinstallato
"%PYDIR%\python.exe" -m pip uninstall -y --disable-pip-version-check numpy
:numpy_ok

echo.
echo ==== 5/8 Copia del programma in "%DEST%" ====
if not exist "%DEST%" mkdir "%DEST%"
if exist "%DEST%" goto dest_ok
echo ERRORE: non riesco a creare "%DEST%".
echo Rimedio: usare un utente amministratore; controllare che il disco C: non sia pieno.
goto errore
:dest_ok
set COPIA_OK=1
for %%f in (main.py diagnostica_digidata.py avvia.bat diagnostica.bat raccogli_risultati.bat README.md GUIDA_RAPIDA.txt GUIDA_COMPLETA.txt) do call :copia "%%f"
xcopy /e /i /y /q dlive "%DEST%\dlive" >nul
if errorlevel 1 set COPIA_OK=0
if "%COPIA_OK%"=="1" goto copia_ok
echo ERRORE: copia non riuscita.  Rimedio: chiudere il programma se e' aperto
echo [denoising_live o la diagnostica] e rilanciare installa.bat.
goto errore
:copia_ok
if exist "%DEST%\config.ini" echo config.ini esistente conservato.
if not exist "%DEST%\config.ini" copy /y config.ini "%DEST%\config.ini" >nul
if exist "%DEST%\numpy_verificato.txt" del "%DEST%\numpy_verificato.txt"
if exist "%DEST%\avvia_simulazione.bat" del "%DEST%\avvia_simulazione.bat"
if "%PY_NOSTRO%"=="1" > "%DEST%\python_installato_da_denoising_live.txt" echo Python 3.4.4 installato da installa.bat il %DATE%
rem per avvia.bat e diagnostica.bat: quale Python usare (set /p "=..." scrive il
rem percorso tra virgolette, cosi' spazi, parentesi, & e apostrofi non danno noia;
rem poi un a capo, che serve a chi la rilegge con set /p)
<nul set /p "=%PYDIR%" > "%DEST%\python_percorso.txt"
>> "%DEST%\python_percorso.txt" echo.
rem per raccogli_risultati.bat: dove sono installa_log.txt e python_msi_log.txt
<nul set /p "=%~dp0" > "%DEST%\cartella_installazione.txt"
>> "%DEST%\cartella_installazione.txt" echo.
echo Programma copiato in "%DEST%"; Python: "%PYDIR%"

echo.
echo ==== 6/8 Collegamenti sul desktop ====
cscript //nologo crea_collegamenti.vbs "%DEST%"
if errorlevel 1 echo Collegamenti non creati: il programma si avvia lo stesso da C:\denoising_live\avvia.bat

echo.
echo ==== 7/8 WinWCP, DLL Axon e WinASPI ====
set WCPDIR=
call :cerca_wcp "C:"
call :cerca_wcp "%ProgramFiles%"
if defined WCPDIR goto winwcp_trovato
echo ATTENZIONE: WinWCP non trovato in C:\WinWCP* ne' in "%ProgramFiles%".
echo   denoising_live usa la DLL Axon di WinWCP [AxDD132x.dll e Axoutils32.dll].
echo   Rimedio: controllare dove e' installato WinWCP [clic destro sull'icona, Proprieta']
echo   e mandare il percorso; la diagnostica cerca la DLL anche altrove.
>> "%LOG%" echo WinWCP non trovato
set /a AVVISI+=1
goto aspi
:winwcp_trovato
echo WinWCP: "%WCPDIR%"
>> "%LOG%" echo WinWCP: "%WCPDIR%"
if not exist "%WCPDIR%\AxDD132x.dll" goto manca_axdd
echo   AxDD132x.dll: presente
goto axoutils
:manca_axdd
echo ATTENZIONE: manca AxDD132x.dll nella cartella di WinWCP.
echo   Rimedio: reinstallare WinWCP [il suo installatore la copia accanto a WinWCP.exe].
>> "%LOG%" echo AxDD132x.dll assente nella cartella di WinWCP
set /a AVVISI+=1
:axoutils
if not exist "%WCPDIR%\Axoutils32.dll" goto manca_axoutils
echo   Axoutils32.dll: presente
goto aspi
:manca_axoutils
echo ATTENZIONE: manca Axoutils32.dll nella cartella di WinWCP.
echo   La AxDD132x.dll di WinWCP ne ha bisogno: se la diagnostica [passo 5]
echo   non riesce a caricare la DLL, reinstallare WinWCP.
>> "%LOG%" echo Axoutils32.dll assente nella cartella di WinWCP
set /a AVVISI+=1
:aspi
set ASPI_OK=1
if not exist "%SystemRoot%\system32\wnaspi32.dll" set ASPI_OK=0
if not exist "%SystemRoot%\system32\drivers\aspi32.sys" set ASPI_OK=0
if "%ASPI_OK%"=="0" goto manca_aspi
echo WinASPI: presente
>> "%LOG%" echo WinASPI presente
goto rilevamento
:manca_aspi
echo ATTENZIONE: WinASPI non installato [manca wnaspi32.dll o aspi32.sys].
echo   Il Digidata 1322A comunica via SCSI attraverso WinASPI.
echo   Rimedio: installare AxoScope dall'installatore di Axon del laboratorio:
echo   installa WinASPI e il driver SCSI [guida di WinWCP, p. 21]. Poi riavviare il PC.
>> "%LOG%" echo WinASPI assente
set /a AVVISI+=1

:rilevamento
echo.
echo ==== 8/8 Rilevamento completo (C:\denoising_live\rilevamento_pc.txt) ====
pushd "%DEST%"
if exist rilevamento_pc.txt del rilevamento_pc.txt
"%PYDIR%\python.exe" -m dlive.rilevamento --installazione --cartella-programma "%DEST%" --uscita "%DEST%\rilevamento_pc.txt"
popd
if exist "%DEST%\rilevamento_pc.txt" type "%DEST%\rilevamento_pc.txt" >> "%LOG%"

echo.
echo =====================================================================
if not "%AVVISI%"=="0" goto fine_avvisi
echo  INSTALLAZIONE COMPLETATA.
goto fine_testo
:fine_avvisi
echo  INSTALLAZIONE COMPLETATA, MA CI SONO %AVVISI% ATTENZIONI [qui sopra, con il rimedio].
echo  Sistemarle prima della diagnostica, poi rilanciare installa.bat.
:fine_testo
echo  Ora: chiudere WinWCP e avviare "Diagnostica Digidata" dal desktop
echo  oppure C:\denoising_live\diagnostica.bat
echo  Il resoconto di questa installazione e' in installa_log.txt, in questa cartella.
echo =====================================================================
>> "%LOG%" echo INSTALLAZIONE COMPLETATA [attenzioni: %AVVISI%]
pause
exit /b 0

:log_non_scrivibile
echo ERRORE: non riesco a scrivere in questa cartella:
echo   "%~dp0"
echo Rimedio: copiare la cartella sul disco C: del PC, per esempio in C:\denoising-live-main,
echo e lanciare installa.bat da li'.
:errore
>> "%LOG%" echo INSTALLAZIONE INTERROTTA
echo.
echo *** INSTALLAZIONE INTERROTTA: vedere il messaggio qui sopra. ***
echo *** Se non si risolve: doppio clic su raccogli_risultati.bat e mandare la cartella. ***
pause
exit /b 1

rem ---------------------------------------------------------------------
rem :copia NOME - copia un file del programma in DEST (fallimento -> COPIA_OK=0)
:copia
copy /y "%~1" "%DEST%\" >nul
if errorlevel 1 echo   copia non riuscita: %~nx1
if errorlevel 1 set COPIA_OK=0
goto :eof

rem ---------------------------------------------------------------------
rem :cerca_wcp CARTELLA - cerca WinWCP*\WinWCP.exe nella cartella (e in Strathclyde*\).
rem I caratteri jolly si usano senza virgolette, dopo pushd (la cartella puo' avere spazi).
:cerca_wcp
if not exist "%~1\*" goto :eof
pushd "%~1\"
for /d %%d in (WinWCP*) do if exist "%%~fd\WinWCP.exe" set "WCPDIR=%%~fd"
for /d %%a in (Strathclyde*) do call :cerca_wcp "%%~fa"
popd
goto :eof
