# -*- coding: utf-8 -*-
"""Passo 9 della diagnostica: su quale ingresso c'e' il segnale e se coincide
con config.ini; config.ini modificato con il Blocco note di Windows XP."""
import io
import os
import re
import sys

import pytest

from conftest import RADICE, esegui

sys.path.insert(0, RADICE)
import diagnostica_digidata as D  # noqa: E402
from dlive import config  # noqa: E402

SCOLLEGATO = [1, -2, 0, 2, 1]                 # come gli ingressi scollegati dei file di prova
SEGNALE = [-200, -198, -201, -199, -200]       # circa -61 mV a 1 mV/unita'


def _letture(**con_segnale):
    l = dict((c, list(SCOLLEGATO)) for c in range(16))
    for nome, v in con_segnale.items():
        l[int(nome[2:])] = v
    return l


def test_ingressi_scollegati_non_hanno_segnale():
    assert D.ingressi_con_segnale(_letture()) == []


def test_segnale_continuo_o_rumoroso():
    assert D.ingressi_con_segnale(_letture(ai4=SEGNALE)) == [4]
    rumore = [0, 40, -35, 10, 25]                    # media ~0 ma ampiezza 75 conteggi
    assert D.ingressi_con_segnale(_letture(ai7=rumore, ai4=SEGNALE)) == [4, 7]


def test_riga_ingresso_coincide():
    esito, t = D.riga_ingresso(D.ingressi_con_segnale(_letture(ai2=SEGNALE)), 2)
    assert esito is True and t == "segnale trovato sull'ingresso AI2; config.ini usa AI2"


def test_riga_ingresso_diverso_dice_cosa_fare():
    esito, t = D.riga_ingresso(D.ingressi_con_segnale(_letture(ai4=SEGNALE)), 2)
    assert esito is None
    assert t.startswith("segnale trovato sull'ingresso AI4; config.ini usa AI2: ")
    assert "C:\\denoising_live\\config.ini" in t and "Blocco note" in t and "canale_ingresso = 4" in t
    assert "rifare la diagnostica" in t


def test_riga_ingresso_nessun_segnale():
    esito, t = D.riga_ingresso([], 2)
    assert esito is None and t.startswith("nessun ingresso con segnale") and "config.ini usa AI2" in t


def test_riga_ingresso_piu_ingressi():
    esito, t = D.riga_ingresso(D.ingressi_con_segnale(_letture(ai2=SEGNALE, ai5=[-500] * 5)), 2)
    assert esito is True and "AI5" in t and "config.ini usa AI2" in t
    esito, t = D.riga_ingresso(D.ingressi_con_segnale(_letture(ai2=SEGNALE, ai5=[30] * 5)), 2)
    assert esito is True and t.startswith("segnale trovato sull'ingresso AI2; config.ini usa AI2 (segnale anche su AI5)")


def test_diagnostica_con_dll_finta_scrive_la_riga(tmp_path):
    codice, out = esegui([sys.executable, os.path.join(RADICE, "diagnostica_digidata.py"), "--finto",
                          "--secondi", "3", "--uscita", str(tmp_path)], timeout=180, cwd=RADICE)
    rep = io.open(str(tmp_path / "report_diagnostica.txt"), encoding="utf-8", errors="replace").read()
    assert codice == 0, out[-2000:]
    blocco = rep.split("PASSO 9")[1].split("PASSO 10")[0]
    assert len(re.findall(r"^  AI\d+ +=", blocco, re.M)) == 16
    assert re.search(r"^>>> (OK|AVVISO): (segnale trovato sull'ingresso AI\d+|segnale su piu' ingressi).*"
                     r"config\.ini usa AI\d+", blocco, re.M), blocco
    assert re.search(r"^\[(OK    |AVVISO)\] passo 9: .*config\.ini usa AI\d+", rep, re.M)


# ---------------------------------------------------------------- config.ini e Blocco note di XP
def _config_repo():
    return io.open(os.path.join(RADICE, "config.ini"), "rb").read()


def test_config_ini_del_repository_e_ascii():
    _config_repo().decode("ascii")


@pytest.mark.parametrize("codifica", ["ansi", "utf8_bom"])
def test_config_ini_modificato_col_blocco_note(tmp_path, codifica):
    """Il Blocco note di XP salva in ANSI (cp1252) con a capo CRLF; con "Salva con
    nome" si puo' scegliere UTF-8, che aggiunge il BOM.  In entrambi i casi il
    programma rilegge il valore cambiato e, quando risalva, tiene CRLF e ASCII."""
    testo = _config_repo().decode("ascii").replace("\r\n", "\n")
    assert re.search(r"^canale_ingresso = \d+$", testo, re.M)
    testo = re.sub(r"^canale_ingresso = \d+$", "canale_ingresso = 4", testo, flags=re.M)
    testo = testo.replace("\n", "\r\n")
    b = testo.encode("cp1252") if codifica == "ansi" else b"\xef\xbb\xbf" + testo.encode("utf-8")
    p = tmp_path / "config.ini"
    p.write_bytes(b)
    c = config.Configurazione(str(p), base=str(tmp_path))
    assert c.carica() and c["digidata.canale_ingresso"] == 4
    assert not c.avvisi, c.avvisi
    c.salva()
    nuovo = p.read_bytes()
    nuovo.decode("ascii")
    assert nuovo.count(b"\n") == nuovo.count(b"\r\n") > 0
    assert b"canale_ingresso = 4\r\n" in nuovo and b"; Ingresso analogico del Digidata" in nuovo
