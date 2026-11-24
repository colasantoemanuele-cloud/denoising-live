# -*- coding: utf-8 -*-
"""Log su file con rotazione (e copia a schermo)."""
import logging
import logging.handlers
import os
import sys

NOME = "dlive"


def configura(cartella, nome_file="denoising_live.log", livello=logging.INFO,
              a_schermo=True, max_byte=2 * 1024 * 1024, copie=10):
    log = logging.getLogger(NOME)
    log.setLevel(logging.DEBUG)
    for h in list(log.handlers):
        log.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s [%(threadName)s] %(message)s")
    percorso = None
    try:
        if not os.path.isdir(cartella):
            os.makedirs(cartella)
        percorso = os.path.join(cartella, nome_file)
        fh = logging.handlers.RotatingFileHandler(percorso, maxBytes=max_byte,
                                                  backupCount=copie, encoding="utf-8")
        fh.setFormatter(fmt)
        fh.setLevel(logging.DEBUG)
        log.addHandler(fh)
    except (IOError, OSError) as e:
        sys.stderr.write("Impossibile aprire il log in %s: %s\n" % (cartella, e))
        percorso = None
    if a_schermo and sys.stdout is not None:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))
        sh.setLevel(livello)
        log.addHandler(sh)
    return log, percorso


def get():
    return logging.getLogger(NOME)
