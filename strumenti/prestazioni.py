# -*- coding: utf-8 -*-
"""Misura del tempo CPU per secondo di segnale (catena completa senza GUI e
disegno del grafico) e stima del carico su un PC con Windows XP.

Uso:  python strumenti/prestazioni.py [--secondi 120] [--fs 1000] [--senza-numpy]
Gira anche con Python 3.4.
"""
import argparse
import array
import math
import os
import sys
import tempfile
import time

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(QUI))

# Rapporto di velocita' prudenziale tra questo PC e un PC da ufficio di circa
# 15 anni fa (es. Pentium 4 / Athlon 64 a 2-3 GHz) con CPython 3.4:
# 10x (CPython 3.4 e' anche ~1,3x piu' lento di 3.12, gia' compreso).
FATTORE_XP = 10.0


def cpu():
    return time.process_time()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secondi", type=float, default=120.0)
    ap.add_argument("--fs", type=float, default=1000.0)
    ap.add_argument("--senza-numpy", action="store_true")
    ap.add_argument("--fattore", type=float, default=FATTORE_XP)
    args = ap.parse_args()
    if args.senza_numpy:
        os.environ["DLIVE_SENZA_NUMPY"] = "1"
    from dlive import compat, filters, registro, wcpfile
    from dlive.acquisizione import BufferGrafico
    from dlive.recorder import Registrazione

    registro.configura(tempfile.mkdtemp(), a_schermo=False)
    fs = args.fs
    n = int(args.secondi * fs)
    blocco = int(0.05 * fs)
    dati = [array.array("h", [int(300 * math.sin(2 * math.pi * 0.2 * (i + j) / fs) +
                                  100 * math.sin(2 * math.pi * 45 * (i + j) / fs))
                              for j in range(blocco)]) for i in range(0, n, blocco)]
    par = filters.ParametriFiltro("bessel", 4, 5.0, [50.0])
    print("Python %s, %s" % (compat.versione_python(), compat.descrizione_percorso()))
    print("Segnale: %g s a %g Hz, blocchi da %d campioni, filtro %s" % (args.secondi, fs, blocco,
                                                                         par.descrizione()))
    risultati = []

    def misura(nome, f):
        t0 = cpu()
        f()
        dt = cpu() - t0
        per_s = dt / args.secondi
        risultati.append((nome, per_s))
        print("  %-38s %7.2f ms CPU per secondo di segnale" % (nome, per_s * 1000))

    def solo_filtro():
        e = filters.Elaboratore(par, fs, 8, soglia_picco=1634, max_campioni_picco=50)
        for b in dati:
            e.elabora(b)

    def grafico():
        g = BufferGrafico(fs)
        conv = 10.0 / 32677 / 0.001
        for b in dati:
            v = [x * conv for x in b]
            g.aggiungi(v, v)

    cartella = tempfile.mkdtemp()

    def scrittura():
        reg = Registrazione(cartella, {"yg": 0.001, "yz": 0, "unita": "mV", "nome": "AI2", "ad": 10.0,
                                       "adcmax": 32677}, fs, 8, par, 60.0, {}, 15.0)
        k = 0
        for b in dati:
            reg.scrivi_grezzo(b)
            reg.scrivi_filtrato(b[::8])
            k += len(b)
            if k >= fs:
                k = 0
                reg.flush()
        reg.chiudi()

    misura("filtro (saturazione+notch+Bessel+decim.)", solo_filtro)
    misura("buffer del grafico", grafico)
    misura("scrittura su disco (flush+fsync 1/s)", scrittura)
    try:
        misura("disegno (10 aggiornamenti/s, 1000 px)", lambda: disegno(args.secondi, fs))
    except Exception as e:
        print("  disegno non misurato: %s" % e)
    tot = sum(r[1] for r in risultati)
    print("  %-38s %7.2f ms CPU per secondo  -> carico %.1f %% su questo PC" % ("TOTALE", tot * 1000, tot * 100))
    print("Stima su un PC con XP di circa 15 anni fa (x%g): carico %.0f %%" % (args.fattore, tot * 100 * args.fattore))


def disegno(secondi, fs):
    """Ridisegna il grafico 10 volte al secondo di segnale con finestra di 30 s."""
    import tkinter as tk
    from dlive.gui import Grafico
    root = tk.Tk()
    c = tk.Canvas(root, width=1000, height=500)
    c.pack()
    g = Grafico(c)
    g.larghezza, g.altezza = 1000, 500
    g.configura(30.0, 0.01)
    secchi_per_agg = 10
    for i in range(int(secondi * 10)):
        nuovi = [(-1.0 - (i % 7), 1.0 + (i % 5), -0.1, 0.1)] * secchi_per_agg
        g.aggiungi_secchi(nuovi)
        g.disegna()
        if i % 10 == 0:
            root.update()
    root.destroy()


if __name__ == "__main__":
    main()
