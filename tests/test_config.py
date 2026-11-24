# -*- coding: utf-8 -*-
import io
import os

from dlive import config


def test_crea_e_rilegge(tmp_path):
    p = str(tmp_path / "config.ini")
    c = config.carica_o_crea(p)
    assert os.path.exists(p)
    testo = io.open(p, encoding="utf-8").read()
    assert "; Ingresso analogico del Digidata" in testo
    assert c["digidata.canale_ingresso"] == 2
    assert c["calibrazione.yg"] == 0.001
    assert c.notch() == [50.0]
    c.imposta("filtro.taglio_hz", 2.5)
    c.imposta("filtro.notch_hz", "50 ; 8,7")
    c.salva()
    c2 = config.carica_o_crea(p)
    assert c2["filtro.taglio_hz"] == 2.5
    assert c2.notch() == [50.0, 8.7]
    assert "; Frequenza di taglio" in io.open(p, encoding="utf-8").read()


def test_virgola_e_errori(tmp_path):
    p = str(tmp_path / "c.ini")
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(u"[salvataggio]\nfrequenza_salvataggio_hz = 300\n[filtro]\ntaglio_hz = 2,5\n[boh]\nx=1\n")
    c = config.carica_o_crea(p)
    assert c["filtro.taglio_hz"] == 2.5
    errori, avvisi = c.controlla()
    assert any("dividere" in e for e in errori)
    assert any("sconosciuta" in a for a in avvisi)


def test_predefiniti_validi():
    c = config.Configurazione()
    errori, avvisi = c.controlla()
    assert errori == []


def test_durata_max_picco_fuori_intervallo_e_errore_chiaro():
    from dlive import config
    c = config.Configurazione(None, ".")
    for v, errato in ((50, False), (0, False), (500, False), (501, True), (-1, True)):
        c.imposta("filtro.durata_max_picco_ms", float(v))
        errori = c.controlla()[0]
        assert any("durata_max_picco_ms" in e and "0-500" in e for e in errori) == errato, (v, errori)
