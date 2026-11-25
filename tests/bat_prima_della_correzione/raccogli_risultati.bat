@echo off
rem =====================================================================
rem  raccogli_risultati.bat - copia in una cartella sul Desktop
rem  (risultati_prova_AAMMGG_HHMM) tutto quello che serve per capire com'e'
rem  andata la prova: report della diagnostica, log, registrazioni e JSON,
rem  file della diagnostica, rilevamento_pc.txt, config.ini, installa_log.txt
rem  e python_msi_log.txt.  Copia quello che c'e', anche se l'installazione
rem  o la prova si sono fermate a meta'.  Non cancella e non cambia nulla.
rem  Si lancia con l'icona "Raccogli risultati" oppure con doppio clic qui
rem  (anche dalla cartella del progetto, prima dell'installazione).
rem =====================================================================
setlocal
cd /d "%~dp0"
set PROG=C:\denoising_live
set QUI=%~dp0
set QUI=%QUI:~0,-1%
set N=0

rem --- cartella del progetto (quella con installa.bat e i suoi log)
set PROGETTO=
if exist "%QUI%\installa.bat" set PROGETTO=%QUI%
if not defined PROGETTO if exist "%PROG%\cartella_installazione.txt" set /p PROGETTO=<"%PROG%\cartella_installazione.txt"
if defined PROGETTO if "%PROGETTO:~-1%"=="\" set PROGETTO=%PROGETTO:~0,-1%

rem --- Desktop dell'utente
set DESK=
for /f "tokens=2,*" %%a in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v Desktop 2^>nul ^| find "REG_SZ"') do set DESK=%%b
if not defined DESK set DESK=%USERPROFILE%\Desktop
if not exist "%DESK%\*" set DESK=%QUI%

rem --- data e ora (AAMMGG_HHMM): wmic, altrimenti la data di Windows
set LDT=
for /f "skip=1 tokens=1" %%a in ('wmic os get localdatetime 2^>nul') do if not defined LDT set LDT=%%a
if defined LDT set ORA=%LDT:~2,6%_%LDT:~8,4%
if not defined LDT set ORA=%DATE:~-2%%DATE:~-7,2%%DATE:~-10,2%_%TIME:~0,2%%TIME:~3,2%
set ORA=%ORA: =0%
set ORA=%ORA:/=%
set ORA=%ORA::=%
set NOME=risultati_prova_%ORA%
set R=%DESK%\%NOME%
if exist "%R%" set NOME=%NOME%_2
if exist "%DESK%\%NOME%" set NOME=%NOME%_3
set R=%DESK%\%NOME%
mkdir "%R%" 2>nul
> "%R%\elenco.txt" echo RISULTATI denoising_live - %DATE% %TIME% - %COMPUTERNAME%
if not exist "%R%\elenco.txt" (
  echo NON riesco a creare la cartella %R%
  echo Fai una foto di questa finestra e mandala.
  pause
  exit /b 1
)

echo.
echo Raccolgo i risultati in:
echo   %R%
echo.
>> "%R%\elenco.txt" echo Programma: %PROG%
>> "%R%\elenco.txt" echo Cartella del progetto: %PROGETTO%

rem --- dal programma installato
if exist "%PROG%\*" (
  call :file "%PROG%\report_diagnostica.txt"
  call :file "%PROG%\rilevamento_pc.txt"
  call :file "%PROG%\config.ini"
  call :file "%PROG%\config.ini.bak"
  call :cartella "%PROG%\log" log
  call :cartella "%PROG%\dati_registrati" dati_registrati
  call :diagnostica "%PROG%" .
) else (
  echo   Il programma non e' installato in %PROG%: copio solo quello che c'e'.
  >> "%R%\elenco.txt" echo %PROG% non esiste
)

rem --- dalla cartella del progetto: log dell'installazione (e una diagnostica
rem     lanciata da li', se c'e')
if defined PROGETTO if exist "%PROGETTO%\*" (
  call :file "%PROGETTO%\installa_log.txt"
  call :file "%PROGETTO%\python_msi_log.txt"
  if exist "%PROGETTO%\report_diagnostica.txt" call :copia_in "%PROGETTO%\report_diagnostica.txt" cartella_progetto
  if exist "%PROGETTO%\log\*" call :cartella "%PROGETTO%\log" cartella_progetto\log
  call :diagnostica "%PROGETTO%" cartella_progetto
)

echo.
echo =====================================================================
if "%N%"=="0" (
  echo  Non ho trovato nessun risultato da copiare.
  echo  Fai una foto dello schermo e mandala insieme alla cartella.
)
echo  FATTO: %N% elementi copiati.
echo  Copia sulla chiavetta la cartella %NOME% dal Desktop.
echo =====================================================================
pause
exit /b 0

rem ---------------------------------------------------------------------
rem :file PERCORSO - copia un file, se c'e', nella cartella dei risultati
:file
if not exist "%~1" goto :eof
copy /y "%~1" "%R%\" >nul
if errorlevel 1 goto file_ko
echo   copiato: %~nx1
>> "%R%\elenco.txt" echo copiato: %~1
set /a N+=1
goto :eof
:file_ko
echo   NON copiato: %~1
>> "%R%\elenco.txt" echo NON copiato: %~1
goto :eof

rem :copia_in PERCORSO SOTTOCARTELLA
:copia_in
if not exist "%R%\%~2\*" mkdir "%R%\%~2"
copy /y "%~1" "%R%\%~2\" >nul
if errorlevel 1 goto :eof
echo   copiato: %~2\%~nx1
>> "%R%\elenco.txt" echo copiato: %~1
set /a N+=1
goto :eof

rem :cartella PERCORSO NOME - copia una cartella intera, se c'e'
:cartella
if not exist "%~1\*" goto :eof
xcopy /e /i /y /q "%~1" "%R%\%~2" >nul
if errorlevel 1 goto cartella_ko
echo   copiata la cartella: %~2
>> "%R%\elenco.txt" echo copiata la cartella: %~1
set /a N+=1
goto :eof
:cartella_ko
echo   NON copiata la cartella: %~1
>> "%R%\elenco.txt" echo NON copiata la cartella: %~1
goto :eof

rem :diagnostica CARTELLA SOTTOCARTELLA - file diagnostica_*.wcp e .csv
rem (caratteri jolly senza virgolette, dopo pushd: la cartella puo' avere spazi)
:diagnostica
pushd "%~1"
for %%f in (diagnostica_*.wcp diagnostica_*.csv) do call :diag_uno "%%~ff" "%~2"
popd
goto :eof
:diag_uno
if "%~2"=="." goto diag_qui
call :copia_in "%~1" "%~2"
goto :eof
:diag_qui
call :file "%~1"
goto :eof
