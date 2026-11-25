# -*- coding: utf-8 -*-
"""Scrive la versione (una data AAAA-MM-GG) in tutti gli script .bat e in
dlive/versione.py, cosi' che una foto dello schermo dica quale versione gira.

    python strumenti/versione.py                 versione = data di oggi
    python strumenti/versione.py --data 2026-11-25
    python strumenti/versione.py --controlla     codice 1 se non coincide ovunque

Negli script la riga e' "echo denoising_live versione AAAA-MM-GG" (subito dopo
il rilancio dentro cmd /k, quindi la prima a schermo) e, se lo script ha un
log, anche ">> log echo denoising_live versione AAAA-MM-GG".  Dopo averla
cambiata: python strumenti/genera_verifica_pacchetto.py (cambiano le dimensioni).
"""
import datetime
import glob
import io
import os
import re
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
RIGA = re.compile(r"(echo denoising_live versione )(\d{4}-\d{2}-\d{2})")
MODULO = os.path.join("dlive", "versione.py")
TESTO_MODULO = ('# -*- coding: utf-8 -*-\n'
                '"""Versione di denoising_live: la scrive strumenti/versione.py (non modificare a mano)."""\n'
                'VERSIONE = "%s"\n')


def script(radice=RADICE):
    return sorted(glob.glob(os.path.join(radice, "*.bat")))


def versioni(radice=RADICE):
    """{file: [date trovate]} per gli script e per dlive/versione.py."""
    out = {}
    for p in script(radice):
        t = io.open(p, "rb").read().decode("ascii")
        out[os.path.basename(p)] = [m.group(2) for m in RIGA.finditer(t)]
    p = os.path.join(radice, MODULO)
    t = io.open(p, encoding="utf-8").read() if os.path.exists(p) else ""
    out[MODULO.replace(os.sep, "/")] = re.findall(r'VERSIONE = "(\d{4}-\d{2}-\d{2})"', t)
    return out


def scrivi(data, radice=RADICE):
    datetime.datetime.strptime(data, "%Y-%m-%d")
    for p in script(radice):
        b = io.open(p, "rb").read().decode("ascii")
        nuovo = RIGA.sub(lambda m: m.group(1) + data, b)
        if nuovo != b:
            io.open(p, "wb").write(nuovo.encode("ascii"))
    io.open(os.path.join(radice, MODULO), "w", encoding="utf-8", newline="\n").write(TESTO_MODULO % data)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    radice = argv[argv.index("--radice") + 1] if "--radice" in argv else RADICE
    if "--controlla" in argv:
        v = versioni(radice)
        date = set(d for ds in v.values() for d in ds)
        mancanti = [f for f, ds in v.items() if not ds]
        if len(date) != 1 or mancanti:
            print("versioni diverse o mancanti: %s" % v)
            return 1
        print("versione %s in %d file" % (date.pop(), len(v)))
        return 0
    data = argv[argv.index("--data") + 1] if "--data" in argv else datetime.date.today().isoformat()
    scrivi(data, radice)
    print("versione %s scritta in %d script e in %s" % (data, len(script(radice)), MODULO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
