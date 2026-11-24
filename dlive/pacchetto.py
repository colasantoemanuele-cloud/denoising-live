# -*- coding: utf-8 -*-
"""Controllo della cartella d'installazione (gira con Python 3.4 e successivi).

La cartella d'installazione e' quella del progetto scaricata da GitHub
(Code > Download ZIP, estratta) con accanto i due file scaricati a parte:

  * python-3.4.4.msi                  (python.org)
  * numpy-1.15.4-cp34-none-win32.whl  (PyPI)

verifica_pacchetto.bat controlla nomi e dimensioni senza Python (funziona
anche su Windows XP); qui si aggiunge lo SHA-256, che su XP non si puo'
calcolare senza Python: installa.bat lo esegue appena installato Python.

    python -m dlive.pacchetto [--cartella C] [--senza-hash]

L'elenco dei file del programma con le dimensioni e' uno solo: le righe
"call :file" di verifica_pacchetto.bat (rigenerate da
strumenti/genera_verifica_pacchetto.py); questo modulo le rilegge.
"""
import hashlib
import io
import os
import re
import sys

# nome, dimensione (byte), SHA-256, indirizzo di scaricamento, pagina ufficiale
SCARICAMENTI = (
    ("python-3.4.4.msi", 24932352,
     "46c8f9f63cf02987e8bf23934b2f471e1868b24748c5bb551efcf4863b43ca6c",
     "https://www.python.org/ftp/python/3.4.4/python-3.4.4.msi",
     "https://www.python.org/downloads/release/python-344/"),
    ("numpy-1.15.4-cp34-none-win32.whl", 9932905,
     "df04f4bad8a359daa2ff74f8108ea051670cafbca533bb2636c58b16e962989e",
     "https://files.pythonhosted.org/packages/e6/10/798bd58c97068aad4cb24e9ba60dcc7ce2e8aac7a871ea493708039a8100/"
     "numpy-1.15.4-cp34-none-win32.whl",
     "https://pypi.org/project/numpy/1.15.4/#files"),
)
MSI = SCARICAMENTI[0][0]
WHEEL = SCARICAMENTI[1][0]

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
BAT = "verifica_pacchetto.bat"
_RIGA_FILE = re.compile(r'^call :file "([^"]+)" (\d+|"")\s*$')


def elenco_programma(cartella=RADICE):
    """[(percorso relativo con '/', dimensione o None)] dalle righe di verifica_pacchetto.bat."""
    with io.open(os.path.join(cartella, BAT), encoding="ascii") as f:
        righe = f.read().splitlines()
    voci = []
    for r in righe:
        m = _RIGA_FILE.match(r.strip())
        if m:
            dim = None if m.group(2) == '""' else int(m.group(2))
            voci.append((m.group(1).replace("\\", "/"), dim))
    return voci


def sha256(percorso):
    h = hashlib.sha256()
    with open(percorso, "rb") as f:
        for pezzo in iter(lambda: f.read(1 << 20), b""):
            h.update(pezzo)
    return h.hexdigest()


def verifica(cartella=RADICE, con_hash=True):
    """Restituisce (righe_ok, problemi): problemi vuoto = tutto a posto."""
    ok, problemi = [], []
    for nome, dim, h, url, pagina in SCARICAMENTI:
        p = os.path.join(cartella, nome)
        if not os.path.isfile(p):
            problemi.append("MANCA %s: scaricarlo da %s e metterlo in %s" % (nome, url, cartella))
            continue
        d = os.path.getsize(p)
        if d != dim:
            problemi.append("DIMENSIONE ERRATA %s: %d byte invece di %d (scaricamento interrotto?): "
                            "cancellarlo e scaricarlo di nuovo da %s" % (nome, d, dim, url))
            continue
        if con_hash:
            calcolato = sha256(p)
            if calcolato != h:
                problemi.append("SHA-256 ERRATO %s: %s invece di %s (file danneggiato o diverso): "
                                "cancellarlo e scaricarlo di nuovo da %s" % (nome, calcolato, h, url))
                continue
            ok.append("ok %s  %d byte  SHA-256 %s" % (nome, d, h))
        else:
            ok.append("ok %s  %d byte" % (nome, d))
    try:
        voci = elenco_programma(cartella)
    except (IOError, OSError) as e:
        problemi.append("MANCA %s (%s): scaricare di nuovo il ZIP del progetto" % (BAT, e))
        voci = []
    for rel, dim in voci:
        p = os.path.join(cartella, *rel.split("/"))
        if not os.path.isfile(p):
            problemi.append("MANCA %s: scaricare di nuovo il ZIP del progetto ed estrarlo tutto" % rel)
        elif dim is not None and os.path.getsize(p) != dim:
            problemi.append("DIMENSIONE ERRATA %s: %d byte invece di %d: scaricare di nuovo il ZIP "
                            "(Code > Download ZIP) senza modificare i file" % (rel, os.path.getsize(p), dim))
    if voci and not any(p.startswith("MANCA " + r) or p.startswith("DIMENSIONE ERRATA " + r)
                        for p in problemi for r, _ in voci):
        ok.append("ok %d file del programma" % len(voci))
    return ok, problemi


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Controlla la cartella d'installazione di denoising_live")
    ap.add_argument("--cartella", default=RADICE)
    ap.add_argument("--senza-hash", action="store_true")
    a = ap.parse_args(argv)
    ok, problemi = verifica(a.cartella, con_hash=not a.senza_hash)
    for r in ok:
        print("  " + r)
    for r in problemi:
        print("  " + r)
    if problemi:
        print("%d problemi: correggerli e rilanciare." % len(problemi))
        return 1
    print("Pacchetto completo e integro.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
