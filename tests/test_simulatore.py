# -*- coding: utf-8 -*-
"""SimulatedDevice: coda costante e sovracampionamento (regressioni trovate
dalla validazione, B1 e C4)."""
import array

import pytest

from dlive.devices.simulated import SimulatedDevice, lunghezza_utile

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


@pytest.mark.parametrize("tipo", ["array", "numpy"])
def test_lunghezza_utile_tiene_l_ultimo_campione(tipo):
    if tipo == "numpy" and np is None:
        pytest.skip("numpy assente")
    conv = (lambda v: np.array(v, dtype=np.int16)) if tipo == "numpy" else (lambda v: array.array("h", v))
    assert lunghezza_utile(conv([1, 2, 3])) == 3            # nessuna coda: si tiene tutto
    assert lunghezza_utile(conv([1, 2, 3, 3, 3, 3])) == 3   # coda: resta l'ultimo valore acquisito
    assert lunghezza_utile(conv([5, 5, 5])) == 3            # tutto costante: invariato
    assert lunghezza_utile(conv([])) == 0


def _wcp(tmp_path, campioni, dt=0.008):
    from dlive import wcpfile
    n = wcpfile.campioni_per_record(len(campioni) * dt, 1.0 / dt)
    w = wcpfile.ScrittoreWCP(str(tmp_path / "s.wcp"), dt, n, [{"nome": "Ch.0"}])
    w.aggiungi(list(campioni) + [campioni[-1]] * (n - len(campioni)))
    w.chiudi()
    return str(tmp_path / "s.wcp")


def test_sovracampionamento_non_interpola_i_salti_bruschi(tmp_path):
    # 1 campione a -1115 mV (3644 conteggi) su una base di 0: a 1000 Hz deve
    # restare un salto brusco, non diventare una rampa
    c = [0] * 100 + [-3644] + [0] * 100 + [10, 20, 30]
    dev = SimulatedDevice(_wcp(tmp_path, c), canale=0, sovracampiona=True, tempo_reale=False,
                          ciclo=False, salta_coda=True)
    dev.apri()
    dev.avvia()
    out = []
    while not dev._finito:
        b = dev.leggi(0)
        if b is not None:
            out.extend(b.dati)
    valori = set(out[700:900])
    assert valori <= {0, -3644}, sorted(valori)[:10]
    # i salti piccoli si interpolano ancora
    assert any(10 < v < 20 for v in out[-30:])


def _registra_impulso(tmp_path, attesa_ms):
    """Impulso di 5 V lungo 104 ms a 1000 Hz, registrato da una Sessione costruita
    come in gui._crea_sessione con [filtro] durata_max_picco_ms = attesa_ms."""
    import time
    from dlive import config, filters, wcpfile
    from dlive.acquisizione import Sessione
    p = str(tmp_path / ("impulso_%d.wcp" % attesa_ms))
    conv = 32677 / 10.0 * 0.001                       # conteggi per mV
    c = [0] * 3000 + [int(-4981 * conv)] * 104 + [0] * 2016
    w = wcpfile.ScrittoreWCP(p, 0.001, 5120, [{"nome": "Ch.0"}])
    w.aggiungi(c)
    w.chiudi()
    cfg = config.Configurazione(None, str(tmp_path))
    cfg.imposta("filtro.durata_max_picco_ms", float(attesa_ms))
    assert cfg.controlla()[0] == []
    dev = SimulatedDevice(p, canale=0, tempo_reale=False, ciclo=False, salta_coda=False)
    dev.apri()
    cart = str(tmp_path / ("dati_%d" % attesa_ms))
    s = Sessione(dev, filters.ParametriFiltro(), {"cartella": cart, "fs_salvataggio": 125.0},
                 soglia_picchi_unita=cfg["filtro.soglia_picchi_mv"],
                 durata_max_picco_s=cfg["filtro.durata_max_picco_ms"] / 1000.0)
    s.comandi.put(("avvia_reg", None))
    s.avvia_anteprima()
    t0 = time.time()
    while s.in_corso and time.time() - t0 < 30:
        time.sleep(0.02)
    f = wcpfile.leggi_wcp(s.ultima_registrazione.percorso_filt)
    return [v for r in f.records for v in r.dati[0]]


def test_durata_max_picco_ms_cambia_il_comportamento(tmp_path):
    """[filtro] durata_max_picco_ms arriva al rilevatore: con 50 ms l'impulso
    lungo passa con 50 ms di ritardo, con 20 ms con 20, con 0 non viene
    trattenuto; con 200 ms (piu' lungo dell'impulso) e' tolto del tutto."""
    def inizio(y):          # primo campione a 125 Hz oltre -50 mV dopo 2,9 s
        for i in range(int(2.9 * 125), len(y)):
            if y[i] < -50:
                return i / 125.0
        return None
    t = {a: inizio(_registra_impulso(tmp_path, a)) for a in (0, 20, 50, 200)}
    assert t[200] is None                                   # impulso tolto
    assert t[0] < t[20] < t[50]
    assert abs((t[50] - t[0]) - 0.050) <= 0.016 and abs((t[20] - t[0]) - 0.020) <= 0.016
