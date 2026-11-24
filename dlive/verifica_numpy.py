# -*- coding: utf-8 -*-
"""Verifica di numpy in un processo separato, PRIMA di importarlo.

Su un PC vecchio numpy potrebbe non solo dare ImportError ma far chiudere
Python di colpo (istruzioni della CPU non supportate dalla libreria di
calcolo): un try/except non basterebbe.  Si prova quindi l'import in un
processo figlio; se fallisce si imposta DLIVE_SENZA_NUMPY=1 e il programma
usa il percorso in Python puro.  L'esito viene ricordato in un file per non
ripetere la prova a ogni avvio (si ripete se cambia la versione di Python).

Questo modulo NON importa numpy ne' altri moduli di dlive.
"""
import os
import subprocess
import sys

PROVA = ("import numpy as np; a = np.arange(1000, dtype=np.float64); "
         "b = np.convolve(a, np.ones(5) / 5.0); f = np.fft.rfft(a); "
         "assert abs(float(b.sum()) - float(a.sum())) < 1e-6; "
         "print(np.__version__)")


def verifica(cartella, forza=False, timeout=60):
    """Restituisce (ok, descrizione).  Imposta DLIVE_SENZA_NUMPY=1 se numpy non va."""
    if os.environ.get("DLIVE_SENZA_NUMPY", "") in ("1", "si", "yes", "true"):
        return False, "disattivato da DLIVE_SENZA_NUMPY"
    chiave = "%s|%s" % (sys.executable, sys.version.split()[0])
    memo = os.path.join(cartella, "numpy_verificato.txt")
    if not forza:
        try:
            with open(memo) as f:
                righe = f.read().splitlines()
            if len(righe) >= 3 and righe[0] == chiave:
                ok = righe[1] == "OK"
                if not ok:
                    os.environ["DLIVE_SENZA_NUMPY"] = "1"
                return ok, righe[2] + " (verifica precedente)"
        except (IOError, OSError):
            pass
    try:
        pr = subprocess.Popen([sys.executable, "-c", PROVA], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
        out, err = pr.communicate(timeout=timeout)
        ok = pr.returncode == 0
        descr = ("numpy %s funziona" % out.strip()) if ok else \
            ("numpy non utilizzabile (codice %s): %s" % (pr.returncode, (err or "").strip().splitlines()[-1:]))
    except Exception as e:   # timeout, impossibile avviare il processo...
        ok, descr = False, "verifica di numpy fallita: %s" % e
    if not ok:
        os.environ["DLIVE_SENZA_NUMPY"] = "1"
    try:
        with open(memo, "w") as f:
            f.write("%s\n%s\n%s\n" % (chiave, "OK" if ok else "KO", descr))
    except (IOError, OSError):
        pass
    return ok, descr
