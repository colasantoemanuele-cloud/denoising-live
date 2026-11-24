# -*- coding: utf-8 -*-
"""Filtri: progettazione (contro scipy), attenuazione, blocchi, ritardo,
cambio dei parametri dal vivo, saturazione e picchi, decimazione."""
import math
import random

import pytest

from dlive import filters as F

try:
    import numpy as np
    from scipy import signal
except ImportError:  # pragma: no cover
    np = None
    signal = None

richiede_scipy = pytest.mark.skipif(signal is None, reason="scipy non disponibile")


@richiede_scipy
@pytest.mark.parametrize("tipo", ["bessel", "butterworth"])
@pytest.mark.parametrize("ordine", list(range(1, 11)))
@pytest.mark.parametrize("fc,fs", [(5.0, 1000.0), (1.0, 1000.0), (5.0, 125.0), (20.0, 113.7)])
def test_risposta_come_scipy(tipo, ordine, fc, fs):
    sos = F.progetta_passabasso(tipo, ordine, fc, fs)
    if tipo == "bessel":
        ref = signal.bessel(ordine, fc, fs=fs, output="sos", norm="mag")
    else:
        ref = signal.butter(ordine, fc, fs=fs, output="sos")
    f = np.linspace(0.01, fs / 2 * 0.999, 400)
    h = np.array(F.risposta_frequenza(sos, f, fs))
    _, hr = signal.sosfreqz(ref, f, fs=fs)
    assert np.max(np.abs(h - hr)) < 1e-9


@richiede_scipy
@pytest.mark.parametrize("f0,q,fs", [(50.0, 30.0, 1000.0), (50.0, 30.0, 125.0), (8.7, 10.0, 113.7)])
def test_notch_come_scipy(f0, q, fs):
    b, a = signal.iirnotch(f0, q, fs)
    mio = F.progetta_notch(f0, q, fs)
    assert np.allclose(mio, list(b) + list(a[1:]), atol=1e-12)


@richiede_scipy
def test_poli_bessel_tabulati():
    for n in range(1, 11):
        z, p, k = signal.besselap(n, norm="mag")
        ps = sorted([q for q in p if q.imag >= -1e-15], key=lambda q: -q.imag)
        tab = F.POLI_BESSEL[n]
        assert len(tab) == len(ps)
        for (re, im), q in zip(tab, ps):
            assert abs(re - q.real) < 1e-12 and abs(im - abs(q.imag)) < 1e-12


@richiede_scipy
def test_catena_come_sosfilt():
    par = F.ParametriFiltro("bessel", 4, 5.0, [50.0])
    x = np.random.RandomState(1).randn(5000)
    y = F.filtra_causale(par, x, 1000.0, regime_iniziale=False)
    sos = np.array([list(s[:3]) + [1.0] + list(s[3:]) for s in par.sezioni(1000.0)])
    assert np.max(np.abs(np.array(y) - signal.sosfilt(sos, x))) < 1e-10


def test_attenuazione_predefinito():
    """Filtro predefinito (Bessel 4 a 5 Hz + notch 50 Hz) a 1000 Hz."""
    par = F.ParametriFiltro("bessel", 4, 5.0, [50.0])
    fs = 1000.0
    sez = par.sezioni(fs)
    a25 = F.attenuazione_db(sez, 25.0, fs)
    a374 = F.attenuazione_db(sez, 37.4, fs)
    a50 = F.attenuazione_db(sez, 50.0, fs)
    a5 = F.attenuazione_db(sez, 5.0, fs)
    print("attenuazione: 5 Hz %.1f dB, 25 Hz %.1f dB, 37,4 Hz %.1f dB, 50 Hz %.1f dB" % (a5, a25, a374, a50))
    assert abs(a5 - 3.0) < 0.2           # -3 dB al taglio
    assert a25 > 40.0
    assert a374 > 55.0
    assert a50 > 100.0                   # notch
    assert abs(F.guadagno_dc(sez) - 1.0) < 1e-12


@pytest.mark.parametrize("n_blocco", [1, 7, 50, 333])
def test_blocchi_uguale_a_un_colpo(n_blocco):
    par = F.ParametriFiltro("butterworth", 6, 3.0, [50.0, 8.7])
    rnd = random.Random(3)
    x = [rnd.gauss(0, 1) + (10 if i > 1500 else 0) for i in range(4000)]
    intero = F.CatenaSOS(par.sezioni(1000.0)).elabora(x)
    c = F.CatenaSOS(par.sezioni(1000.0))
    a_blocchi = []
    i = 0
    while i < len(x):
        k = n_blocco if n_blocco > 1 else rnd.randint(1, 120)
        a_blocchi.extend(c.elabora(x[i:i + k]))
        i += k
    assert max(abs(a - b) for a, b in zip(intero, a_blocchi)) == 0.0


@pytest.mark.parametrize("tipo,ordine,max_sovra", [("bessel", 4, 5.0), ("bessel", 8, 5.0),
                                                   ("butterworth", 2, 5.0)])
def test_ritardo_e_sovraelongazione(tipo, ordine, max_sovra):
    par = F.ParametriFiltro(tipo, ordine, 5.0, [])
    for fs in (125.0, 1000.0):
        t50, sovra, salita = F.ritardo_gradino(par, fs)
        print("%s %d fs=%g: ritardo 50%% %.0f ms, sovraelongazione %.2f %%, salita %.0f ms" % (
            tipo, ordine, fs, t50 * 1000, sovra, salita * 1000))
        assert t50 < 0.3
        assert sovra < max_sovra


def test_butterworth4_sovraelonga():
    t50, sovra, _ = F.ritardo_gradino(F.ParametriFiltro("butterworth", 4, 5.0, []), 1000.0)
    assert sovra > 10.0          # motivo per cui il predefinito e' Bessel


def test_ritardo_misurato_su_gradino_reale():
    """Gradino nel segnale -> ritardo misurato all'uscita dell'Elaboratore."""
    fs = 1000.0
    par = F.ParametriFiltro("bessel", 4, 5.0, [50.0])
    e = F.Elaboratore(par, fs, 8)
    x = [0] * 2000 + [327] * 3000           # gradino di ~100 mV
    y, _ = e.elabora(x)
    i50 = next(i for i, v in enumerate(y) if v >= 163.5)
    ritardo = (i50 - 2000) / fs
    assert 0.03 < ritardo < 0.3
    assert max(y) < 327 * 1.05


def test_regime_senza_transitorio():
    c = F.CatenaSOS(F.ParametriFiltro("bessel", 6, 2.0, [50.0]).sezioni(1000.0))
    c.regime(123.4)
    y = c.elabora([123.4] * 500)
    assert max(abs(v - 123.4) for v in y) < 1e-9


def test_cambio_taglio_dal_vivo_senza_buchi():
    fs = 1000.0
    par = F.ParametriFiltro("bessel", 4, 5.0, [50.0])
    e = F.Elaboratore(par, fs, 8)
    rnd = random.Random(5)
    uscita = []
    for blocco in range(200):
        x = [int(300 + 30 * math.sin(2 * math.pi * 40 * (blocco * 50 + i) / fs) + rnd.gauss(0, 5))
             for i in range(50)]
        if blocco == 80:
            e.riconfigura(par.copia(fc=1.0))
        if blocco == 82:          # secondo cambio durante la dissolvenza
            e.riconfigura(par.copia(fc=10.0, tipo="butterworth", ordine=2))
        if blocco == 150:
            e.riconfigura(par.copia(fc=2.0, notch=[]))
        y, dec = e.elabora(x)
        assert len(y) == 50 and len(dec) == len(range((-blocco * 50) % 8, 50, 8))
        uscita.extend(y)
    salti = [abs(uscita[i + 1] - uscita[i]) for i in range(len(uscita) - 1)]
    assert max(salti) < 5.0                # nessuna discontinuita'
    assert all(abs(v - 300) < 40 for v in uscita[100:])


def test_saturazione_mantiene_ultimo_valore():
    e = F.Elaboratore(F.ParametriFiltro("bessel", 4, 5.0, [50.0]), 1000.0, 1)
    x = [100] * 1000 + [-32768] * 3 + [100] * 1000 + [32767] * 2 + [100] * 500
    y, _ = e.elabora(x)
    assert max(abs(v - 100) for v in y) < 1e-6
    ev = e.preleva_eventi()
    assert [t for _, _, t in ev] == ["saturazione", "saturazione"]
    assert e.saturati_tot == 5


def test_picchi_isolati_e_gradini_veri():
    fs = 1000.0
    e = F.Elaboratore(F.ParametriFiltro("bessel", 4, 5.0, []), fs, 1, soglia_picco=1600,
                      max_campioni_picco=50)
    x = [0] * 1000 + [5000, 4000] + [0] * 1000 + [3000] * 2000
    y, _ = e.elabora(x)
    assert max(abs(v) for v in y[:2000]) < 1e-6         # picco di 2 campioni ignorato
    assert abs(y[-1] - 3000) < 1.0                      # gradino vero accettato dopo 50 ms
    tipi = [t for _, _, t in e.preleva_eventi()]
    assert tipi == ["picco", "picco_accettato"]


def test_decimazione_fase_tra_blocchi():
    par = F.ParametriFiltro("bessel", 2, 5.0, [])
    e1 = F.Elaboratore(par, 1000.0, 8)
    e2 = F.Elaboratore(par, 1000.0, 8)
    x = [int(1000 * math.sin(i / 300.0)) for i in range(5000)]
    _, d1 = e1.elabora(x)
    d2 = []
    rnd = random.Random(2)
    i = 0
    while i < len(x):
        k = rnd.randint(1, 37)
        d2.extend(e2.elabora(x[i:i + k])[1])
        i += k
    assert d1 == d2 and len(d1) == 625


def test_controlli_parametri():
    par = F.ParametriFiltro("bessel", 4, 20.0, [50.0])
    err, avv = F.controlla_parametri(par, 1000.0, 125.0, taglio_lpf8=15.0)
    assert not err and any("LPF-8" in a for a in avv)
    err, avv = F.controlla_parametri(par.copia(fc=600.0), 1000.0, 125.0)
    assert err
    err, avv = F.controlla_parametri(par.copia(ordine=12), 1000.0, 125.0)
    assert err
