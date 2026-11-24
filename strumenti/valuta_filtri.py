# -*- coding: utf-8 -*-
"""Confronto dei filtri candidati sui file di prova (strumento offline, usa scipy).

Per ogni candidato misura:
  * rumore residuo RMS nei tratti quieti (finestre di 4 s in cui il segnale
    "vero", stimato a fase zero, e' piatto), mediana e 90-esimo percentile;
  * sovraelongazione e ritardo al 50 % sulla risposta al gradino;
  * attenuazione a 8,7 / 25 / 37,4 / 50 Hz.
Le prove si fanno sia alla frequenza originale dei file (113,7 o 125 Hz) sia
a 1000 Hz (file sovracampionati per interpolazione lineare, come la catena
della modalita' Digidata).

Uso:  python strumenti/valuta_filtri.py [--grafici CARTELLA]
"""
import argparse
import os
import sys

import numpy as np
from scipy import signal

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(QUI))
from dlive import filters as F          # noqa: E402
from dlive import wcpfile               # noqa: E402

DATI = os.path.join(os.path.dirname(QUI), "riferimenti", "dati")

# (file, record, canale): i tratti con segnale vero
TRACCE = [
    ("071210_001.wcp", 0, 0), ("071210_001.wcp", 1, 0), ("071210_001.wcp", 2, 0),
    ("071210_001.wcp", 3, 0), ("071211_001.1.wcp", 0, 0), ("071210_001.1.wcp", 0, 4),
    ("071222_002.1.wcp", 0, 0),
]

CANDIDATI = [
    ("Bessel 2", F.ParametriFiltro("bessel", 2, 5.0, [50.0])),
    ("Bessel 4", F.ParametriFiltro("bessel", 4, 5.0, [50.0])),
    ("Bessel 6", F.ParametriFiltro("bessel", 6, 5.0, [50.0])),
    ("Bessel 8", F.ParametriFiltro("bessel", 8, 5.0, [50.0])),
    ("Butterworth 2", F.ParametriFiltro("butterworth", 2, 5.0, [50.0])),
    ("Butterworth 4", F.ParametriFiltro("butterworth", 4, 5.0, [50.0])),
    ("Bessel 4 + notch 8,7", F.ParametriFiltro("bessel", 4, 5.0, [50.0, 8.7])),
    ("Bessel 6 + notch 8,7", F.ParametriFiltro("bessel", 6, 5.0, [50.0, 8.7])),
]


def carica_tracce():
    out = []
    for nome, r, c in TRACCE:
        w = wcpfile.leggi_wcp(os.path.join(DATI, nome))
        a = np.asarray(w.records[r].adc[c]).astype(int)
        x = np.asarray(w.records[r].dati[c], dtype=float)
        d = np.nonzero(a != a[-1])[0]
        n = d[-1] + 1
        out.append(("%s r%d c%d" % (nome, r + 1, c), 1.0 / w.dt, a[:n], x[:n]))
    return out


def scala(nome_file):
    return 10.0 / 32677 / 0.001   # mV per conteggio (YG=0,001, AD=10)


def rimuovi_saturazione(a, soglia=32700):
    a = a.astype(float).copy()
    ultimo = a[0]
    for i in range(len(a)):
        if a[i] >= soglia or a[i] <= -soglia - 1:
            a[i] = ultimo
        else:
            ultimo = a[i]
    return a


def finestre_quiete(rif, fs, durata=4.0, ptp_max=2.0, salta=3.0):
    n = int(durata * fs)
    idx = []
    for i0 in range(int(salta * fs), len(rif) - n, n):
        seg = rif[i0:i0 + n]
        if np.ptp(seg) < ptp_max:
            idx.append((i0, i0 + n))
    return idx


def valuta(tracce, fs_target=None):
    risultati = {}
    for nome_c, par in CANDIDATI:
        rms_tutti = []
        per_traccia = []
        for nome, fs, a, x in tracce:
            xm = rimuovi_saturazione(a) * scala(nome)
            fs_eff = fs
            if fs_target:
                t = np.arange(len(xm)) / fs
                tn = np.arange(int(len(xm) * fs_target / fs)) / fs_target
                xm = np.interp(tn, t, xm)
                fs_eff = fs_target
            y = np.array(F.filtra_causale(par, xm, fs_eff))
            # riferimento a fase zero (segnale "vero"): notch + Butterworth 4 a 1 Hz
            b, aa = signal.iirnotch(50.0, 30.0, fs_eff) if 50.0 < fs_eff / 2 else ([1.0], [1.0])
            rif = signal.sosfiltfilt(signal.butter(4, 1.0, fs=fs_eff, output="sos"),
                                     signal.filtfilt(b, aa, xm))
            fin = finestre_quiete(rif, fs_eff)
            rr = []
            for i0, i1 in fin:
                rr.append(float(np.std(y[i0:i1])))
            rms_tutti.extend(rr)
            per_traccia.append((nome, len(fin), float(np.median(rr)) if rr else float("nan"),
                                float(np.percentile(rr, 90)) if rr else float("nan")))
        fs_step = fs_target or 125.0
        t50, sovra, salita = F.ritardo_gradino(par, fs_step)
        att = [F.attenuazione_db(par.sezioni(1000.0), f, 1000.0) for f in (8.7, 25.0, 37.4, 50.0)]
        risultati[nome_c] = dict(mediana=float(np.median(rms_tutti)),
                                 p90=float(np.percentile(rms_tutti, 90)),
                                 n_finestre=len(rms_tutti), t50=t50, sovra=sovra,
                                 salita=salita, att=att, per_traccia=per_traccia)
    return risultati


def stampa(ris, titolo):
    print("\n=== %s ===" % titolo)
    print("%-22s %8s %8s %6s %10s %8s %8s   %s" % ("filtro (taglio 5 Hz)", "RMS med", "RMS p90",
                                                  "n", "sovra %", "rit.50%", "sal.10-90",
                                                  "attenuazione dB a 8,7/25/37,4/50 Hz"))
    for k, v in ris.items():
        print("%-22s %8.2f %8.2f %6d %10.2f %7.0fms %7.0fms   %s" % (
            k, v["mediana"], v["p90"], v["n_finestre"], v["sovra"], v["t50"] * 1000,
            v["salita"] * 1000, " / ".join("%.0f" % a for a in v["att"])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grafici", default="")
    ap.add_argument("--dettaglio", action="store_true")
    args = ap.parse_args()
    tracce = carica_tracce()
    r1 = valuta(tracce)
    stampa(r1, "frequenza originale dei file (113,7-125 Hz)")
    r2 = valuta(tracce, 1000.0)
    stampa(r2, "sovracampionato a 1000 Hz (catena Digidata)")
    if args.dettaglio:
        for k, v in r1.items():
            print(k)
            for t in v["per_traccia"]:
                print("    %-28s finestre %4d  mediana %.2f  p90 %.2f mV" % t)
    if args.grafici:
        grafici(tracce, args.grafici)


def grafici(tracce, cartella):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(cartella, exist_ok=True)
    scelti = [CANDIDATI[1], CANDIDATI[5]]
    fig, ax = plt.subplots(len(tracce), 1, figsize=(16, 3 * len(tracce)))
    for i, (nome, fs, a, x) in enumerate(tracce):
        xm = rimuovi_saturazione(a) * scala(nome)
        t = np.arange(len(xm)) / fs
        ax[i].plot(t, xm, color="0.8", lw=0.3, label="grezzo")
        for nome_c, par in scelti:
            ax[i].plot(t, F.filtra_causale(par, xm, fs), lw=0.8, label=nome_c)
        lo, hi = np.percentile(xm, [1, 99])
        ax[i].set_ylim(lo - 20, hi + 20)
        ax[i].set_title(nome)
        ax[i].legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(os.path.join(cartella, "confronto_filtri.png"), dpi=70)


if __name__ == "__main__":
    main()
