# -*- coding: utf-8 -*-
"""La GUI si avvia, registra, cambia il filtro e si chiude senza errori.
(La prova visiva resta da fare a mano.)"""
import json
import os
import sys

import pytest

from conftest import DATI, RADICE, esegui, richiede_dati, richiede_display_virtuale


@richiede_dati()
@richiede_display_virtuale
@pytest.mark.parametrize("senza_numpy", [False, True])
def test_gui_avvio_registrazione_chiusura(tmp_path, senza_numpy):
    cfg = str(tmp_path / "config.ini")
    dati = str(tmp_path / "dati")
    cmd = [sys.executable, os.path.join(RADICE, "main.py"), "--simulazione", "--config", cfg,
           "--file", os.path.join(DATI, "071210_001.wcp"), "--cartella-dati", dati,
           "--prova-gui", "3"]
    if senza_numpy:
        cmd.append("--senza-numpy")
    codice, out = esegui(cmd, timeout=120)
    print(out)
    assert codice == 0
    assert "Traceback" not in out and "ERROR" not in out
    nomi = os.listdir(dati)
    js = [n for n in nomi if n.endswith(".json")]
    assert len(js) == 1 and any(n.endswith("_raw.wcp") for n in nomi) and any(n.endswith("_filt.wcp") for n in nomi)
    meta = json.load(open(os.path.join(dati, js[0])))
    assert meta["chiusura_regolare"] and meta["marker"][0]["testo"] == "marker di prova"
    assert meta["cambi_parametri"][0]["dopo"]["taglio_hz"] == 2.0
    assert ("Python puro" in meta["percorso_calcolo"]) == senza_numpy
