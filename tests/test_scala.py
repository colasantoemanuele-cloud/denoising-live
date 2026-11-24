# -*- coding: utf-8 -*-
"""Dimensione dell'interfaccia: fattore automatico, chiave di configurazione,
layout senza controlli tagliati a 1024x768 e 1280x1024, cambio dal vivo."""
import io
import os
import sys

import pytest

from conftest import richiede_display_virtuale
from dlive import config
from dlive.scala import fattore_automatico, leggi_impostazione, percento_da_fattore


def test_fattore_automatico():
    def p(w, h, dpi=96):
        return percento_da_fattore(fattore_automatico(w, h, dpi))
    assert p(1920, 1080) == 100
    assert p(3840, 2160) == 200
    assert p(2560, 1440) == 135
    assert p(1024, 768) == 80          # minimo: font di base 10 pt
    assert p(1280, 1024) == 80
    assert p(1920, 1080, 144) == 150   # Windows con scala al 150 %
    assert p(1024, 768, 120) == 125    # XP con "caratteri grandi"
    assert p(1920, 1080, 100) == 100   # 96-110 DPI: valore generico, ignorato
    assert p(3840 + 1920, 2160) == 200  # due schermi affiancati
    assert p(10000, 10000) == 400


def test_leggi_impostazione():
    assert leggi_impostazione("auto") is None
    assert leggi_impostazione("") is None
    assert leggi_impostazione("150") == 150
    assert leggi_impostazione("150 %") == 150
    assert leggi_impostazione("1,25") == 125
    for cattivo in ("enorme", "20", "1000"):
        with pytest.raises(ValueError):
            leggi_impostazione(cattivo)


def test_chiave_config(tmp_path):
    p = str(tmp_path / "config.ini")
    c = config.carica_o_crea(p)
    assert c["interfaccia.dimensione"] == "auto"
    assert "[interfaccia]" in io.open(p, encoding="utf-8").read()
    c.imposta("interfaccia.dimensione", "125%")
    c.salva()
    assert config.carica_o_crea(p)["interfaccia.dimensione"] == "125"
    # valore non valido: avviso e scala automatica, non un errore
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(u"[interfaccia]\ndimensione = gigante\n")
    c = config.carica_o_crea(p)
    assert c["interfaccia.dimensione"] == "auto"
    assert any("dimensione" in a for a in c.avvisi)
    # vecchio config.ini senza la sezione: predefinito
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(u"[filtro]\ntaglio_hz = 5\n")
    assert config.carica_o_crea(p)["interfaccia.dimensione"] == "auto"


@richiede_display_virtuale
@pytest.mark.parametrize("schermo", [(1024, 768), (1280, 1024)])
def test_layout_schermi_piccoli_e_cambio_dal_vivo(tmp_path, schermo):
    import tkinter as tk
    from dlive import gui
    from dlive.scala import Scala

    cfg = config.carica_o_crea(str(tmp_path / "config.ini"), base=str(tmp_path))
    cfg.imposta("generale.cartella_dati", str(tmp_path / "dati"))
    root = tk.Tk()
    app = None
    try:
        if root.winfo_screenwidth() < schermo[0] or root.winfo_screenheight() < schermo[1]:
            pytest.skip("display piu' piccolo di %dx%d" % schermo)
        scala = Scala(root, "auto", schermo=schermo)
        app = gui.FinestraPrincipale(root, cfg, "simulazione", str(tmp_path), None, scala)
        root.update()
        assert scala.percento == 80 and scala.base_pt * scala.dpi / 72.0 >= 12   # >= 12 px
        assert scala.font["DliveValore"].actual("size") >= 3 * scala.base_pt
        w, h, x, y = scala.geometria_iniziale()
        assert x + w <= schermo[0] and y + h <= schermo[1]
        if root.winfo_width() == w and root.winfo_height() == h:   # senza window manager (Xvfb)
            assert root.winfo_width() <= schermo[0] and root.winfo_height() <= schermo[1]
        assert gui.controlli_fuori(root) == []
        assert not gui.barra_scorrimento_visibile(root)

        # 200 %: si ricostruisce subito, nulla tagliato (il pannello scorre)
        app.var_dimensione.set("200 %")
        app.cambia_dimensione()
        root.update()
        assert scala.percento == 200 and cfg["interfaccia.dimensione"] == "200"
        assert scala.font["DliveValore"].actual("size") == 3 * scala.base_pt
        assert gui.controlli_fuori(root) == []
        assert "interfaccia" in io.open(str(tmp_path / "config.ini"), encoding="utf-8").read()

        app.var_dimensione.set(app._nomi_dimensione()[0])
        app.cambia_dimensione()
        root.update()
        assert scala.percento == 80 and cfg["interfaccia.dimensione"] == "auto"
        assert gui.controlli_fuori(root) == []
    finally:
        # distruzione esplicita nel thread principale: le variabili Tk
        # raccolte dal garbage collector in un altro thread fanno chiudere Python
        if app is not None:
            app.chiudi_senza_conferma()
        else:
            root.destroy()
        app = scala = root = None
        import gc
        gc.collect()
