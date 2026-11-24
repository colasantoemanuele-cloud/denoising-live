# -*- coding: utf-8 -*-
"""Simulazione end-to-end senza GUI: file di prova riprodotto (accelerato) ->
filtro -> salvataggio -> rilettura.  Con numpy e in Python puro."""
import json
import os
import time
import tracemalloc

import pytest

from conftest import DATI, richiede_dati
from dlive import filters, wcpfile
from dlive.acquisizione import Sessione
from dlive.devices.simulated import SimulatedDevice

PAR = filters.ParametriFiltro("bessel", 4, 5.0, [50.0])
SCALA = 10.0 / 32677 / 0.001


def _sessione(dev, cartella, par=PAR, **kw):
    return Sessione(dev, par, {"cartella": cartella, "fs_salvataggio": 125.0,
                               "durata_record_s": kw.pop("durata_record_s", 60.0)},
                    soglia_picchi_unita=kw.pop("soglia_picchi", 500.0), **kw)


def _attendi(s, timeout=300):
    t0 = time.time()
    while s.in_corso and time.time() - t0 < timeout:
        time.sleep(0.05)
    assert not s.in_corso, "la sessione non si e' fermata"


def _concatena(w):
    out = []
    for r in w.records:
        out.extend(list(r.adc[0]))
    return out


@richiede_dati()
@pytest.mark.parametrize("sovra", [False, True])
def test_riproduzione_filtro_salvataggio(cartella, percorso, sovra):
    dev = SimulatedDevice(os.path.join(DATI, "071210_001.wcp"), record=4, sovracampiona=sovra,
                          tempo_reale=False, ciclo=False, blocco_s=0.05)
    dev.apri()
    sorgente = list(dev.sorgente)
    # la registrazione parte subito: comando accodato prima dell'avvio dei thread
    s = _sessione(dev, cartella)
    s.comandi.put(("avvia_reg", None))
    s.avvia_anteprima()
    _attendi(s)
    reg = s.ultima_registrazione
    assert reg is not None and reg.meta["chiusura_regolare"]
    assert s.persi_tot == 0
    raw = wcpfile.leggi_wcp(reg.percorso_raw)
    filt = wcpfile.leggi_wcp(reg.percorso_filt)
    assert not raw.avvisi and not filt.avvisi
    assert raw.nr == filt.nr == reg.meta["record_grezzo"]
    grezzo = _concatena(raw)[:reg.campioni_raw]
    assert reg.campione_inizio == 0
    # nessun campione perso: il grezzo e' esattamente la sorgente (o la sua interpolazione)
    if not sovra:
        assert grezzo == sorgente
    else:
        assert len(grezzo) == s.campioni and abs(len(grezzo) - len(sorgente) * 1000 / dev.fs_sorgente) < 10
    # il filtrato coincide con il filtraggio offline causale del grezzo
    e = filters.Elaboratore(PAR, dev.fs, s.dec, soglia_picco=500.0 / SCALA,
                            max_campioni_picco=int(round(0.05 * dev.fs)))
    _, atteso = e.elabora(grezzo)
    filtrato = _concatena(filt)[:reg.campioni_filt]
    assert len(filtrato) == len(atteso)
    assert max(abs(a - b) for a, b in zip(filtrato, atteso)) == 0
    # stesso numero di record e allineamento temporale
    assert raw.records[-1].tempo == pytest.approx(filt.records[-1].tempo, abs=1e-4)
    meta = json.load(open(reg.percorso_json))
    assert meta["campioni_persi"] == 0 and meta["chiusura_regolare"] is True
    assert meta["filtro_iniziale"]["tipo"] == "bessel"


@richiede_dati()
def test_cambi_filtro_marker_e_campioni_persi(cartella, percorso):
    dev = SimulatedDevice(os.path.join(DATI, "071222_002.1.wcp"), sovracampiona=True,
                          tempo_reale=False, ciclo=False, persi_test={40: 250, 300: 1000},
                          rumore=True)
    s = _sessione(dev, cartella, durata_record_s=30.0)
    s.comandi.put(("avvia_reg", None))
    s.comandi.put(("marker", "inizio prova"))
    s.avvia_anteprima()
    time.sleep(0.05)
    s.imposta_filtro(PAR.copia(fc=2.0))
    s.marker("dopo il cambio")
    s.imposta_lpf8(10.0)
    _attendi(s)
    reg = s.ultima_registrazione
    meta = json.load(open(reg.percorso_json))
    assert meta["campioni_persi"] == 1250
    assert len(meta["eventi_campioni_persi"]) == 2
    assert [m["testo"] for m in meta["marker"]] == ["inizio prova", "dopo il cambio"]
    assert any(c["descrizione"] == "filtro" and c["dopo"]["taglio_hz"] == 2.0
               for c in meta["cambi_parametri"])
    assert any(c["descrizione"] == "lpf8" for c in meta["cambi_parametri"])
    assert meta["lpf8"]["taglio_hz"] == 10.0
    assert meta["saturazioni"]["eventi"] > 0      # rumore sintetico con picchi
    raw = wcpfile.leggi_wcp(reg.percorso_raw)
    assert raw.records[0].ident.startswith("M")   # marker visibile in WinWCP
    # i campioni persi sono riempiti: la base dei tempi resta corretta
    assert reg.campioni_raw == s.campioni


@pytest.mark.skipif(os.environ.get("DLIVE_TEST_VELOCI") == "1", reason="test lungo (circa 3 minuti)")
def test_memoria_stabile_e_tre_ore(cartella):
    """3 ore di segnale a 1000 Hz (10,8 milioni di campioni) con record da 60 s:
    nessun degrado, memoria stabile."""
    from dlive import compat
    if compat.np is None:
        pytest.skip("percorso veloce richiesto per la durata del test")
    from dlive.devices.base import Blocco, Dispositivo
    import array
    import math

    class Generatore(Dispositivo):
        modalita = "simulazione"
        fs = 1000.0

        def __init__(self, secondi):
            self.tot = int(secondi * self.fs)
            self.pos = 0
            self._finito = False

        def apri(self):
            return self

        def calibrazione(self):
            return {"yg": 0.001, "yz": 0.0, "unita": "mV", "nome": "AI2", "ad": 10.0, "adcmax": 32677}

        def avvia(self):
            pass

        def ferma(self):
            pass

        def leggi(self, timeout=0.2):
            if self.pos >= self.tot:
                self._finito = True
                return None
            k = min(5000, self.tot - self.pos)
            d = array.array("h", [int(300 * math.sin((self.pos + i) / 5000.0)) for i in range(k)])
            b = Blocco(d, self.pos, 0, self.pos + k >= self.tot)
            self.pos += k
            self._finito = self.pos >= self.tot
            return b

        def info(self):
            return {"modalita": "simulazione"}

    dev = Generatore(3 * 3600)
    s = _sessione(dev, cartella, intervallo_scrittura=1e9)
    s.comandi.put(("avvia_reg", None))
    tracemalloc.start()
    s.avvia_anteprima()
    misure = []
    while s.in_corso:
        time.sleep(0.5)
        misure.append((s.campioni, tracemalloc.get_traced_memory()[0]))
    tracemalloc.stop()
    reg = s.ultima_registrazione
    assert reg.campioni_raw == 3 * 3600 * 1000
    raw = wcpfile.leggi_wcp(reg.percorso_raw, solo_intestazione=True)
    assert raw.nr == reg.meta["record_grezzo"] >= 180
    assert raw.campioni_per_record * raw.nc < 1000000
    # memoria: tra il primo terzo e la fine non cresce piu' di 30 MB
    terzo = [m for c, m in misure if c > 3600 * 1000]
    if len(terzo) > 2:
        assert max(terzo) - terzo[0] < 30 * 1024 * 1024
