# -*- coding: utf-8 -*-
"""Rilevamento di numpy e piccole utilita' di compatibilita'.

Il programma deve girare sia su Python 3.4 + numpy 1.15 (Windows XP) sia su
Python moderno + numpy 2.x. Se numpy non si importa (CPU vecchia, runtime
mancanti) si usa un percorso in Python puro.

Per forzare il percorso senza numpy (test, o prova sul PC del laboratorio):
variabile d'ambiente DLIVE_SENZA_NUMPY=1 oppure opzione --senza-numpy.
"""
import os
import sys

np = None
NUMPY_ERRORE = ""


def _prova_numpy():
    global np, NUMPY_ERRORE
    if os.environ.get("DLIVE_SENZA_NUMPY", "").strip() in ("1", "si", "yes", "true"):
        np = None
        NUMPY_ERRORE = "disattivato da DLIVE_SENZA_NUMPY"
        return
    try:
        import numpy as _np
        # piccola prova che le operazioni di base funzionino davvero
        a = _np.arange(8, dtype=_np.int16)
        if int(a.astype(_np.float64).sum()) != 28:
            raise RuntimeError("numpy restituisce risultati errati")
        np = _np
        NUMPY_ERRORE = ""
    except Exception as e:  # ImportError, errori di DLL, CPU non supportata...
        np = None
        NUMPY_ERRORE = "%s: %s" % (type(e).__name__, e)


_prova_numpy()


def disattiva_numpy():
    """Forza il percorso in Python puro (chiamare prima di creare oggetti)."""
    global np, NUMPY_ERRORE
    np = None
    NUMPY_ERRORE = "disattivato su richiesta"


def ha_numpy():
    return np is not None


def descrizione_percorso():
    if np is not None:
        return "numpy %s (percorso veloce)" % np.__version__
    return "Python puro, senza numpy (%s)" % (NUMPY_ERRORE or "numpy assente")


def versione_python():
    return "%s (%d bit) su %s" % (sys.version.split()[0],
                                  64 if sys.maxsize > 2 ** 32 else 32,
                                  sys.platform)


SU_WINDOWS = sys.platform.startswith("win")
