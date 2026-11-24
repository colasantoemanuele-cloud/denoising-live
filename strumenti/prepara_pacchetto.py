# -*- coding: utf-8 -*-
"""Scarica nella cartella del progetto i due file che non sono nel repository
e ne verifica dimensione e SHA-256 (gli stessi controlli di
verifica_pacchetto.bat e di installa.bat):

  * python-3.4.4.msi                  Python 3.4.4 a 32 bit (python.org)
  * numpy-1.15.4-cp34-none-win32.whl  ultima numpy con wheel cp34 win32 (PyPI)

    python strumenti/prepara_pacchetto.py [--cartella C]

Serve a chi prepara la cartella su un PC Linux; su Windows si segue
GUIDA_LABORATORIO.md, parte A.  I due file sono esclusi da git (.gitignore).
"""
import argparse
import os
import shutil
import sys
import urllib.request

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
sys.path.insert(0, RADICE)

from dlive import pacchetto  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cartella", default=RADICE)
    a = ap.parse_args(argv)
    for nome, dim, h, url, pagina in pacchetto.SCARICAMENTI:
        p = os.path.join(a.cartella, nome)
        if not (os.path.isfile(p) and os.path.getsize(p) == dim and pacchetto.sha256(p) == h):
            print("Scarico %s ..." % url)
            tmp = p + ".part"
            with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f)
            os.replace(tmp, p)
    ok, problemi = pacchetto.verifica(a.cartella)
    for r in ok + problemi:
        print("  " + r)
    return 1 if problemi else 0


if __name__ == "__main__":
    sys.exit(main())
