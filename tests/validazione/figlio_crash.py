# -*- coding: utf-8 -*-
"""Processo figlio per il test B7: registra in tempo reale dalla sorgente
sintetica e scrive ogni 50 ms un "battito" con lo stato; il test lo uccide
con kill -9 (SIGKILL) e controlla i file rimasti su disco.

Uso: python figlio_crash.py SORGENTE.wcp CARTELLA_DATI BATTITO.json
"""
import json
import os
import sys
import time

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)

import comuni as C  # noqa: E402
from dlive import registro  # noqa: E402
from dlive.devices.simulated import SimulatedDevice  # noqa: E402


def main():
    sorgente, cartella, battito = sys.argv[1:4]
    registro.configura(cartella, "figlio.log", a_schermo=False)
    dev = SimulatedDevice(sorgente, record=1, canale=0, velocita=1.0, sovracampiona=False,
                          tempo_reale=True, ciclo=False)
    dev.apri()
    s = C.sessione_come_gui(dev, cartella)
    s.comandi.put(("avvia_reg", None))
    s.avvia_anteprima()
    tmp = battito + ".tmp"
    while s.in_corso:
        stato = {"t": time.time(), "t0_dispositivo": dev._t0, "prodotti": dev._prodotti,
                 "elaborati": s.campioni,
                 "registrazione": s.reg.nome_base if s.reg is not None else None,
                 "cartella": cartella}
        with open(tmp, "w") as f:
            json.dump(stato, f)
        os.replace(tmp, battito)
        time.sleep(0.05)


if __name__ == "__main__":
    main()
