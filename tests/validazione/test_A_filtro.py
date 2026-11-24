# -*- coding: utf-8 -*-
"""Gruppo A: il filtro misurato su segnali sintetici a verita' nota.

Il programma e' usato come scatola nera (Elaboratore, costruito come lo
costruisce la Sessione); i valori attesi vengono dalla verita' del segnale,
da formule o da scipy."""
from __future__ import division

import array

import numpy as np
import pytest

import comuni as C

try:
    import scipy  # noqa: F401
    HA_SCIPY = True
except ImportError:
    HA_SCIPY = False

richiede_scipy = pytest.mark.skipif(not HA_SCIPY, reason="richiede scipy")


def _fmt(v, cifre=3):
    return ("%." + str(cifre) + "g") % v


def _gradino(l0=20.0, l1=120.0, prima_s=10.0, dopo_s=10.0):
    n0, n1 = int(prima_s * C.FS), int(dopo_s * C.FS)
    mv = np.concatenate((np.full(n0, l0), np.full(n1, l1)))
    c = C.mv_in_conteggi(mv)
    return c, n0, float(c[0]) * C.MV_PER_CONTEGGIO, float(c[-1]) * C.MV_PER_CONTEGGIO


def misura_gradino(par, l0=20.0, l1=120.0):
    """(ritardo al 50 % in s, sovraelongazione %) del programma."""
    c, n0, v0, v1 = _gradino(l0, l1)
    y = C.filtra_programma(c, par)
    rit = C.ritardo_50(y, n0, v0, v1)
    seg = y[n0:]
    sovra = max(0.0, (seg.max() - v1) / (v1 - v0) * 100.0)
    return rit, sovra


def _tono(f, ampiezza=100.0, durata_s=20.0, offset=0.0):
    t = np.arange(int(durata_s * C.FS)) / C.FS
    return C.mv_in_conteggi(offset + ampiezza * np.sin(2 * np.pi * f * t))


def _ampiezza_regime(y, f, da_s=10.0):
    i = int(da_s * C.FS)
    seg = y[i:]
    # numero intero di periodi
    per = C.FS / f
    n = int(int(len(seg) / per) * per)
    return C.ampiezza_sinusoide(seg[:n], f)


# ---------------------------------------------------------------------------
def test_A1_guadagno_banda_passante(registra):
    c = _tono(0.2, 100.0, durata_s=60.0)
    ampiezza_in = C.ampiezza_sinusoide(C.conteggi_in_mv(c)[10000:60000], 0.2)
    y = C.filtra_programma(c, C.parametri())
    a = C.ampiezza_sinusoide(y[10000:60000], 0.2)
    ok = 99.0 <= a <= 101.0
    registra("A1", "%.3f mV (ingresso %.3f mV)" % (a, ampiezza_in), ok,
             {"ampiezza_uscita_mv": a, "ampiezza_ingresso_mv": ampiezza_in})
    assert ok


def test_A2_livello_dei_gradini(registra):
    s = C.sintetico()
    y = C.filtra_programma(s.pulito, C.parametri())
    g = int(2 * C.FS)
    ok_m = np.ones(s.n, dtype=bool)
    ok_m[:g] = False
    for i in s.gradini:
        ok_m[i:i + g] = False
    for a, b in s.deflessioni:
        ok_m[a:b + g] = False
    err = np.abs(y - s.verita)[ok_m]
    peggiore = float(err.max())
    ok = peggiore < 0.5
    registra("A2", "errore massimo %.3f mV (su %d s di segnale, %d gradini)"
             % (peggiore, int(ok_m.sum() / C.FS), len(s.gradini)), ok,
             {"errore_max_mv": peggiore, "errore_medio_mv": float(err.mean())})
    assert ok


def _rif_gradino(fc):
    """Valori attesi da scipy (solo per il rapporto, non per l'esito)."""
    if not HA_SCIPY:
        return None, None
    c, n0, v0, v1 = _gradino()
    y = C.filtra_riferimento(C.sos_riferimento(fc=fc), c) * C.MV_PER_CONTEGGIO
    return C.ritardo_50(y, n0, v0, v1), max(0.0, (y[n0:].max() - v1) / (v1 - v0) * 100.0)


def test_A3_sovraelongazione(registra):
    valori = {}
    for fc in (2.0, 5.0, 10.0):
        rit, sovra = misura_gradino(C.parametri(fc=fc))
        valori[fc] = (sovra, _rif_gradino(fc)[1])
    ok = all(v[0] < 5.0 for v in valori.values())
    testo = "; ".join("%g Hz: %.2f %%" % (fc, valori[fc][0]) for fc in sorted(valori))
    registra("A3", testo, ok, {"sovraelongazione_%%_%g_Hz" % fc: v[0] for fc, v in valori.items()},
             nota="atteso da scipy: " + "; ".join(
                 "%g Hz %.2f %%" % (fc, valori[fc][1]) for fc in sorted(valori)
                 if valori[fc][1] is not None))
    assert ok


def test_A4_ritardo(registra):
    valori = {}
    for fc in (2.0, 5.0, 10.0):
        rit, sovra = misura_gradino(C.parametri(fc=fc))
        valori[fc] = (rit, _rif_gradino(fc)[0])
    ok = all(v[0] is not None and v[0] < 0.3 for v in valori.values())
    testo = "; ".join("%g Hz: %.0f ms" % (fc, valori[fc][0] * 1000) for fc in sorted(valori))
    registra("A4", testo, ok, {"ritardo_ms_%g_Hz" % fc: v[0] * 1000 for fc, v in valori.items()},
             nota="atteso da scipy: " + "; ".join(
                 "%g Hz %.0f ms" % (fc, valori[fc][1] * 1000) for fc in sorted(valori)
                 if valori[fc][1] is not None))
    assert ok


def test_A5_attenuazione_toni(registra):
    soglie = {25.0: 35.0, 37.4: 40.0, 50.0: 40.0}
    misure = {}
    for f in sorted(soglie):
        c = _tono(f, 100.0)
        a_in = _ampiezza_regime(C.conteggi_in_mv(c), f)
        y = C.filtra_programma(c, C.parametri())
        a_out = _ampiezza_regime(y, f)
        misure[f] = 20 * np.log10(a_in / max(a_out, 1e-12))
    ok = all(misure[f] >= soglie[f] for f in soglie)
    attesi = ""
    if HA_SCIPY:
        from scipy import signal
        sos = C.sos_riferimento()
        w, h = signal.sosfreqz(sos, worN=np.array(sorted(soglie)) * 2 * np.pi / C.FS)
        attesi = "atteso da scipy: " + "; ".join(
            "%g Hz %.0f dB" % (f, -20 * np.log10(abs(hh))) for f, hh in zip(sorted(soglie), h))
    registra("A5", "; ".join("%g Hz: %.1f dB" % (f, misure[f]) for f in sorted(misure)), ok,
             {"attenuazione_db_%g_Hz" % f: v for f, v in misure.items()}, nota=attesi)
    assert ok


def test_A6_notch_da_solo(registra):
    par = C.parametri(passabasso=False)
    c50 = _tono(50.0, 100.0)
    a_in = _ampiezza_regime(C.conteggi_in_mv(c50), 50.0)
    a_out = _ampiezza_regime(C.filtra_programma(c50, par), 50.0)
    att50 = 20 * np.log10(a_in / max(a_out, 1e-12))
    c5 = _tono(5.0, 100.0)
    x5 = C.conteggi_in_mv(c5)
    y5 = C.filtra_programma(c5, par)
    a5_in = _ampiezza_regime(x5, 5.0)
    a5_out = _ampiezza_regime(y5, 5.0)
    var_ampiezza = abs(a5_out / a5_in - 1.0) * 100.0
    i = int(10 * C.FS)
    dev_forma = float(np.max(np.abs(y5[i:] - x5[i:]))) / a5_in * 100.0
    ok = att50 >= 30.0 and var_ampiezza < 1.0 and dev_forma < 1.0
    registra("A6", "50 Hz: %.1f dB; 5 Hz: ampiezza %+.3f %%, forma d'onda max %.2f %%"
             % (att50, (a5_out / a5_in - 1) * 100, dev_forma), ok,
             {"attenuazione_50Hz_db": att50, "variazione_ampiezza_5Hz_%": var_ampiezza,
              "scostamento_forma_5Hz_%": dev_forma})
    assert ok


def test_A7_rumore_residuo(registra):
    s = C.sintetico()
    rit, _ = misura_gradino(C.parametri())
    d = int(round(rit * C.FS))
    y = C.filtra_programma(s.rumoroso, C.parametri())
    v = np.concatenate((np.full(d, s.verita[0]), s.verita[:s.n - d]))
    q = s.tratti_quieti()
    rms = float(np.sqrt(np.mean((y - v)[q] ** 2)))
    rms_ingresso = float(np.sqrt(np.mean((C.conteggi_in_mv(s.rumoroso_senza_picchi) - s.verita)[q] ** 2)))
    ok = rms < 2.0
    registra("A7", "%.2f mV RMS (rumore in ingresso %.1f mV RMS; %d s di tratti quieti)"
             % (rms, rms_ingresso, int(q.sum() / C.FS)), ok,
             {"rms_mv": rms, "rms_ingresso_mv": rms_ingresso, "ritardo_campioni": d,
              "secondi_quieti": q.sum() / C.FS})
    assert ok


def test_A8_picchi_di_saturazione(registra):
    s = C.sintetico()
    par = C.parametri()
    y1 = C.filtra_programma(s.rumoroso, par)
    y0 = C.filtra_programma(s.rumoroso_senza_picchi, par)
    w = int(5 * C.FS)
    peggiori = []
    for p, dur, v in s.picchi:
        peggiori.append(float(np.max(np.abs(y1[p:p + w] - y0[p:p + w]))))
    m = max(peggiori)
    ok = m <= 2.0
    n_fs = sum(1 for p in s.picchi if p[2] == -32768)
    registra("A8", "differenza massima %.3f mV (%d picchi: %d a fondo scala, %d a +5,6 V)"
             % (m, len(s.picchi), n_fs, len(s.picchi) - n_fs), ok,
             {"differenza_max_mv": m, "per_picco_mv": peggiori})
    assert ok


def test_A9_equivalenza_a_blocchi(registra):
    s = C.sintetico()
    par = C.parametri()
    ref = C.filtra_programma(s.rumoroso, par)
    rng = np.random.RandomState(7)
    casuali = rng.randint(1, 2001, size=5000).tolist()
    diffs = {}
    for nome, b in (("1", 1), ("7", 7), ("100", 100), ("1000", 1000), ("casuali 1-2000", casuali)):
        y = C.filtra_programma(s.rumoroso, par, blocchi=b)
        diffs[nome] = float(np.max(np.abs(y - ref))) if len(y) == len(ref) else float("inf")
    m = max(diffs.values())
    ok = m < 1e-6
    registra("A9", "differenza massima %.2g mV" % m, ok, {"per_blocco_mv": diffs})
    assert ok


@richiede_scipy
def test_A10_coincidenza_con_scipy(registra):
    s = C.sintetico()
    x = s.rumoroso_senza_picchi
    diffs = {}
    for tipo in ("bessel", "butterworth"):
        for ordine in (2, 4, 8):
            for fc in (1.0, 2.0, 5.0, 10.0):
                y = C.filtra_programma(x, C.parametri(tipo, ordine, fc, notch=()))
                r = C.filtra_riferimento(C.sos_riferimento(tipo, ordine, fc, notch=()), x) * C.MV_PER_CONTEGGIO
                diffs["%s %d %g Hz" % (tipo, ordine, fc)] = float(np.max(np.abs(y - r)))
    peggiore = max(diffs, key=lambda k: diffs[k])
    m = diffs[peggiore]
    ok = m < 1e-4
    registra("A10", "differenza massima %.2g mV (%s), 24 combinazioni" % (m, peggiore), ok,
             {"per_combinazione_mv": diffs})
    assert ok


def test_A11_stabilita_bessel8_1Hz(registra):
    c, n0, v0, v1 = _gradino(0.0, 100.0, prima_s=2.0, dopo_s=10.0)
    y = C.filtra_programma(c, C.parametri("bessel", 8, 1.0))
    finiti = bool(np.all(np.isfinite(y)))
    k = n0 + int(5 * C.FS)
    err = float(np.max(np.abs(y[k:] - v1)) / (v1 - v0) * 100.0) if finiti else float("inf")
    # tempo dopo il quale l'errore resta sotto lo 0,1 %
    fuori = np.flatnonzero(np.abs(y[n0:] - v1) / (v1 - v0) >= 0.001)
    t_conv = (fuori[-1] + 1) / C.FS if len(fuori) else 0.0
    ok = finiti and err < 0.1
    registra("A11", "uscite finite: %s; errore dopo 5 s %.4f %% (sotto lo 0,1 %% da %.2f s)"
             % ("sì" if finiti else "NO", err, t_conv), ok,
             {"errore_dopo_5s_%": err, "tempo_convergenza_s": t_conv})
    assert ok


def test_A12_cambio_dal_vivo(registra):
    P = C.parametri
    # 1) segnale costante di 100 mV
    n = int(70 * C.FS)
    c = C.mv_in_conteggi(np.full(n, 100.0))
    vero = float(c[0]) * C.MV_PER_CONTEGGIO
    k = int(C.FS)
    cambi = {10 * k: P(fc=2.0), 20 * k: P(fc=10.0), 30 * k: P(fc=5.0),
             40 * k: P(notch=()), 50 * k: P(notch=(50.0,)), 60 * k: P(fc=2.0, notch=(50.0, 8.7))}
    y = C.filtra_programma(c, P(), blocchi=50, cambi=cambi)
    nan = int(np.sum(~np.isfinite(y)))
    salto = float(np.max(np.abs(y - vero))) if nan == 0 else float("inf")
    # 2) segnale a gradini senza rumore: cambi a meta' livello e subito dopo un gradino
    livelli = [20.0, 120.0, -30.0, 50.0, 100.0, 20.0, 120.0]
    seg = int(15 * C.FS)
    verita = np.concatenate([np.full(seg, v) for v in livelli])
    cg = C.mv_in_conteggi(verita)
    sequenza = [P(fc=2.0), P(fc=10.0), P(fc=5.0), P(notch=()), P(notch=(50.0,)), P(fc=1.0),
                P(fc=10.0), P(fc=5.0), P(tipo="butterworth"), P()]
    istanti = []
    for i in range(1, len(livelli)):
        istanti.append(i * seg + int(0.2 * C.FS))      # 0,2 s dopo il gradino
        istanti.append(i * seg + int(7 * C.FS))        # a meta' livello
    istanti = istanti[:len(sequenza)]
    cambi2 = dict(zip(istanti, sequenza))
    y2 = C.filtra_programma(cg, P(), blocchi=50, cambi=cambi2)
    nan += int(np.sum(~np.isfinite(y2)))
    peggiore_ritorno = 0.0
    for t in istanti:
        prossimo = (t // seg + 1) * seg
        a = t + int(3 * C.FS)
        if a < prossimo:
            e = float(np.max(np.abs(y2[a:prossimo] - verita[a:prossimo])))
            peggiore_ritorno = max(peggiore_ritorno, e)
    ok = nan == 0 and salto < 0.5 and peggiore_ritorno < 0.5
    registra("A12", "salto massimo su 100 mV costanti %.3f mV; NaN: %d; scarto dal livello vero "
             "3 s dopo un cambio %.3f mV (%d cambi)" % (salto, nan, peggiore_ritorno,
                                                        len(cambi) + len(cambi2)), ok,
             {"salto_mv": salto, "nan": nan, "scarto_dopo_3s_mv": peggiore_ritorno})
    assert ok


def test_A13_senza_numpy(registra, monkeypatch):
    from dlive import compat
    if compat.np is None:
        registra("A13", "numpy non disponibile: confronto impossibile", None)
        pytest.skip("numpy assente")
    s = C.sintetico()
    par = C.parametri()
    y_np = C.filtra_programma(s.rumoroso, par, blocchi=50)
    # percorso in Python puro: numpy disattivato nel programma, blocchi array('h')
    monkeypatch.setattr(compat, "np", None)
    e = C.elaboratore(par)
    puro = []
    x = s.rumoroso.tolist()
    for i in range(0, len(x), 50):
        yb, _ = e.elabora(array.array("h", x[i:i + 50]))
        puro.extend(yb)
    monkeypatch.undo()
    y_puro = np.array(puro) * C.MV_PER_CONTEGGIO
    m = float(np.max(np.abs(y_puro - y_np)))
    ok = m < 1e-6
    registra("A13", "differenza massima %.2g mV" % m, ok, {"differenza_max_mv": m})
    assert ok
