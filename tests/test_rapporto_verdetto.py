# -*- coding: utf-8 -*-
"""Verdetto del rapporto di validazione, in particolare quello della parte
riproducibile (repository senza i dati del laboratorio)."""
import os
import sys

from conftest import RADICE

sys.path.insert(0, os.path.join(RADICE, "tests", "validazione"))
import catalogo as K  # noqa: E402
import rapporto as R  # noqa: E402


def _tutti_pass():
    return {i: {"id": i, "livello": K.TEST[i][0], "esito": R.PASS, "misurato": "", "nota": ""}
            for i in K.TEST}


def _senza_dati(ris):
    for i in ("C1", "C2", "C3", "C3b", "C4", "C5"):
        ris[i].update(esito=R.NV, misurato="test non eseguito")
    ris["B6"].update(esito=R.NV, misurato="confronto con un file WinWCP reale " + R.SENZA_DATI)
    ris["D1"].update(esito=R.NV, misurato="verifica impossibile (%s)" % R.SENZA_DATI)
    ris["B8"].update(esito=R.NV, misurato="non eseguito: richiede ./valida.sh --lungo")
    return ris


def test_ufficiale_pronto():
    assert R.verdetto(_tutti_pass())[0] == "PRONTO PER LA PROVA IN LABORATORIO"


def test_riproducibile_parziale_con_zero_fail():
    v, motivi = R.verdetto(_senza_dati(_tutti_pass()), riproducibile=True)
    assert v == "PARZIALE: 0 FAIL, 8 test non eseguibili senza i dati del laboratorio"
    assert motivi["senza_dati"] == sorted(["B6", "C1", "C2", "C3", "C3b", "C4", "C5", "D1"])


def test_senza_dati_ma_rapporto_ufficiale_resta_non_pronto():
    assert R.verdetto(_senza_dati(_tutti_pass()))[0] == "NON PRONTO"


def test_riproducibile_con_un_fail_non_e_parziale():
    ris = _senza_dati(_tutti_pass())
    ris["A1"]["esito"] = R.FAIL
    assert R.verdetto(ris, riproducibile=True)[0] == "NON PRONTO"
    ris = _senza_dati(_tutti_pass())
    ris["D2"]["esito"] = R.FAIL           # anche un FAIL non critico basta
    assert K.TEST["D2"][0] != K.CRITICO
    assert R.verdetto(ris, riproducibile=True)[0] == "NON PRONTO"


def test_riproducibile_con_critico_mancante_per_altri_motivi():
    ris = _senza_dati(_tutti_pass())
    ris["E1"].update(esito=R.NV, misurato="contenitore Docker con Python 3.4 non disponibile")
    assert R.verdetto(ris, riproducibile=True)[0] == "NON PRONTO"


def test_riproducibile_mutazione_non_rilevata():
    ris = _senza_dati(_tutti_pass())
    ris["M2"]["esito"] = R.FAIL
    assert R.verdetto(ris, riproducibile=True)[0] == "NON PRONTO"
