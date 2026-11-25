# -*- coding: utf-8 -*-
"""Gli script .bat dopo l'espansione con % (emulata, tests/emula_cmd.py):
virgolette e blocchi bilanciati, IF e FOR validi, nessuna & di un percorso
fuori dalle virgolette, con le variabili dello script definite e non definite
e con la cartella dello script con spazi, "(1)", "&" e apostrofi.

Il cmd vero di Windows XP espande %VAR% quando legge la riga (o il blocco),
prima di valutare IF; il cmd di Wine no: questi errori sotto Wine non si vedono.
"""
import glob
import io
import os
import re

import pytest

from conftest import RADICE
import emula_cmd as E

BAT = sorted(os.path.basename(p) for p in glob.glob(os.path.join(RADICE, "*.bat")))

# Variabili che NON contengono percorsi anche se arrivano da un for: testo del
# registro (Service Pack), riga di dir (spazio libero), data/ora di wmic e nomi
# costruiti da quella.  Le altre impostate da for, set /p o con \ si provano
# come percorsi con caratteri speciali.
NON_PERCORSI = {
    "installa.bat": ["SP", "SPAZIO"],
    "raccogli_risultati.bat": ["LDT", "ORA", "NOME", "DOVE"],
}
# Script le cui subroutine ricevono solo costanti (nomi di file, numeri, indirizzi)
ARGOMENTI_COSTANTI = ["verifica_pacchetto.bat", "prepara.bat"]


def _leggi(nome):
    return io.open(os.path.join(RADICE, nome), "rb").read().decode("ascii")


def errori_di(testo, nome):
    out = []
    for desc, var, args, definite in E.scenari(testo, nome, argomenti_costanti=nome in ARGOMENTI_COSTANTI,
                                               non_percorsi=NON_PERCORSI.get(nome, ())):
        for e in E.controlla(testo, var, args, definite):
            out.append("%s\n    [%s]" % (e, desc))
    return out


@pytest.mark.parametrize("nome", BAT)
def test_bat_sintassi_dopo_l_espansione(nome):
    err = errori_di(_leggi(nome), nome)
    assert not err, "\n".join(err[:8])


def test_scenari_coprono_cartelle_difficili():
    cart = E.CARTELLE
    assert any(" " in c for c in cart) and any("(1)" in c for c in cart)
    assert any("&" in c for c in cart) and any("'" in c for c in cart)


# ---------------------------------------------------------------- i bug di prima
# Righe e blocchi della versione che in laboratorio chiudeva installa.bat dopo
# "Disco C:" (Windows XP SP3, Python non installato): l'emulatore deve vederli.
VECCHIA_INSTALLA_73 = '''@echo off
set PYREG=
for /f "delims=" %%l in ('reg query "HKLM\\SOFTWARE\\Python\\PythonCore\\3.4\\InstallPath" /ve 2^>nul ^| find "REG_SZ"') do set PYREG=%%l
if defined PYREG set PYREG=%PYREG:*REG_SZ=%
if defined PYREG for /f "tokens=*" %%x in ("%PYREG%") do set PYREG=%%x
if defined PYREG if "%PYREG:~-1%"=="\\" set PYREG=%PYREG:~0,-1%
'''
VECCHIA_RACCOGLI_23 = '''@echo off
set PROGETTO=
if defined PROGETTO if "%PROGETTO:~-1%"=="\\" set PROGETTO=%PROGETTO:~0,-1%
'''
VECCHIO_BLOCCO = '''@echo off
> "%~dp0prova.txt" echo prova
if errorlevel 1 (
  echo ERRORE: non riesco a scrivere in questa cartella: %~dp0
  goto errore
)
:errore
'''
VECCHIO_SET = '''@echo off
set LOG=%~dp0installa_log.txt
'''
VECCHIO_IF_SENZA_VIRGOLETTE = '''@echo off
if %RC%==0 goto fine
:fine
'''


def test_emulatore_vede_il_crash_di_installa_riga_73():
    err = errori_di(VECCHIA_INSTALLA_73, "installa.bat")
    assert any(e.startswith("riga 6:") and "virgolette" in e and "non definite" in e for e in err), err


def test_emulatore_vede_raccogli_riga_23():
    err = errori_di(VECCHIA_RACCOGLI_23, "raccogli_risultati.bat")
    assert any(e.startswith("riga 3:") and "virgolette" in e for e in err), err


def test_emulatore_vede_il_blocco_chiuso_dalla_parentesi_del_percorso():
    err = errori_di(VECCHIO_BLOCCO, "installa.bat")
    assert any("senza blocco aperto" in e and "(1)" in e for e in err), err
    assert any("& di un percorso" in e for e in err), err


def test_emulatore_vede_la_e_commerciale_e_l_if_senza_virgolette():
    assert any("& di un percorso" in e for e in errori_di(VECCHIO_SET, "installa.bat"))
    assert any("IF" in e for e in errori_di(VECCHIO_IF_SENZA_VIRGOLETTE, "installa.bat"))


def test_versione_precedente_degli_script_fallisce():
    """Gli script di prima (copia in tests/bat_prima_della_correzione/, se c'e')
    hanno errori; quelli di oggi no (test sopra)."""
    cart = os.path.join(RADICE, "tests", "bat_prima_della_correzione")
    if not os.path.isdir(cart):
        pytest.skip("copia degli script di prima non presente")
    trovati = {}
    for p in sorted(glob.glob(os.path.join(cart, "*.bat"))):
        nome = os.path.basename(p)
        trovati[nome] = errori_di(io.open(p, "rb").read().decode("ascii"), nome)
    assert any(e.startswith("riga 73:") for e in trovati["installa.bat"])
    assert any(e.startswith("riga 23:") for e in trovati["raccogli_risultati.bat"])
    assert any("senza blocco aperto" in e for e in trovati["diagnostica.bat"])


# ---------------------------------------------------------------- regole dell'emulatore
def test_espansione_regole_batch():
    v = {"A": "uno", "P": "C:\\x (1)\\"}
    assert E.espandi("%A%-%B%-%%", v, ["s.bat"]) == "uno--%"
    assert E.espandi("%P:~-1%", v, ["s.bat"]) == "\\"
    assert E.espandi("%P:~0,-1%", v, ["s.bat"]) == "C:\\x (1)"
    assert E.espandi("x%B:~0,1%y", v, ["s.bat"]) == "x~0,1y"          # "%B:" tolto, si continua
    assert E.espandi("%~dp0a", v, ["C:\\d e\\s.bat"]) == "C:\\d e\\a"
    assert E.espandi("%~nx1 %~z1", v, ["s.bat", "C:\\a\\b.txt"]) == "b.txt 12345"


def test_controllo_blocchi_if_for():
    ok = "@echo off\nif \"%A%\"==\"1\" goto x\nfor %%f in (a b) do echo %%f\n:x\n"
    assert E.controlla(ok, {"A": "1"}, ["s.bat"]) == []
    assert E.controlla("if errorlevel 1 (\necho a\n", {}, ["s.bat"])            # blocco non chiuso
    assert E.controlla("if ==1 goto x\n", {}, ["s.bat"])                         # IF senza sinistra
    assert E.controlla("for %%f in (a b) echo x\n", {}, ["s.bat"])               # FOR senza do


# ---------------------------------------------------------------- regole di scrittura
@pytest.mark.parametrize("nome", BAT)
def test_niente_blocchi_con_variabili(nome):
    """Dentro ( ... ) nessuna %variabile% (le variabili del for, %%x, vanno bene:
    si espandono dopo la lettura)."""
    profondita = 0
    for n, riga in enumerate(_leggi(nome).splitlines(), 1):
        r = riga.strip()
        if r.lower().startswith("rem") or r.startswith(":"):
            continue
        senza = re.sub(r'"[^"]*"', '""', r.replace("^(", "").replace("^)", ""))
        apre = senza.count("(") - senza.count(")")
        if profondita > 0 or (apre > 0 and not r.lower().startswith("for ")):
            assert not re.search(r"(?<!%)%(?!%)[~A-Za-z_*0-9]", riga.replace("%%", "")), (nome, n, riga)
        if not r.lower().startswith("for "):
            profondita += apre


@pytest.mark.parametrize("nome", ["installa.bat", "diagnostica.bat", "raccogli_risultati.bat", "prepara.bat",
                                  "disinstalla.bat", "avvia.bat"])
def test_rilancio_dentro_cmd_k(nome):
    righe = [r.strip() for r in _leggi(nome).splitlines() if r.strip() and not r.strip().lower().startswith("rem")]
    assert righe[:5] == ["@echo off", "if defined DLIVE_FINESTRA goto dentro", "set DLIVE_FINESTRA=1",
                         'cmd /k call "%~f0" %*', "exit /b"], righe[:5]
    assert righe[5] == ":dentro" and re.match(r"^echo denoising_live versione \d{4}-\d{2}-\d{2}$", righe[6])


def test_verifica_pacchetto_non_si_rilancia():
    comandi = [r for r in _leggi("verifica_pacchetto.bat").splitlines() if not r.strip().lower().startswith("rem")]
    assert not [r for r in comandi if "cmd /k" in r or "DLIVE_FINESTRA" in r]


def test_powershell_legge_il_percorso_da_variabili_d_ambiente():
    t = _leggi("prepara.bat")
    riga = [r for r in t.splitlines() if r.lower().startswith("powershell")][0]
    assert "$env:DLIVE_URL" in riga and "$env:DLIVE_DEST" in riga
    assert not re.search(r"%[^%\s]+%", riga), riga          # nessun %percorso% dentro il comando PowerShell
