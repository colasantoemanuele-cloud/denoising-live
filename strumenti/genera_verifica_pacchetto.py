# -*- coding: utf-8 -*-
"""Aggiorna l'elenco dei file del programma (con le dimensioni) dentro
verifica_pacchetto.bat e riscrive con a capo CRLF i file per Windows.

    python strumenti/genera_verifica_pacchetto.py           aggiorna
    python strumenti/genera_verifica_pacchetto.py --controlla  solo controlla (codice 1 se da aggiornare)

Va rilanciato dopo ogni modifica a un file dell'elenco (lo ricorda il test
tests/test_pacchetto.py).  Le dimensioni sono quelle dei file nel
repository: il ZIP di GitHub li consegna identici perche' .gitattributes
vieta qualsiasi conversione degli a capo.
"""
import io
import os
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
BAT = os.path.join(RADICE, "verifica_pacchetto.bat")
INIZIO = "rem ---- INIZIO ELENCO"
FINE = "rem ---- FINE ELENCO"

# file nella radice usati da installa.bat (o copiati in C:\denoising_live)
RADICE_FILE = ["installa.bat", "disinstalla.bat", "crea_collegamenti.vbs", "main.py",
               "diagnostica_digidata.py", "avvia.bat", "avvia_simulazione.bat", "diagnostica.bat",
               "README.md", "GUIDA_LABORATORIO.txt"]
# file la cui dimensione non si controlla (si possono modificare)
SENZA_DIMENSIONE = ["config.ini"]
# file per Windows: devono avere a capo CRLF ed essere ASCII
ESTENSIONI_WINDOWS = (".bat", ".vbs", ".txt")


def file_programma(radice=RADICE):
    """[(percorso relativo con '/', dimensione o None)] nell'ordine dell'elenco."""
    voci = [(f, os.path.getsize(os.path.join(radice, f))) for f in RADICE_FILE]
    voci += [(f, None) for f in SENZA_DIMENSIONE]
    pkg = []
    for r, dirs, files in os.walk(os.path.join(radice, "dlive")):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for fn in sorted(files):
            if fn.endswith(".py"):
                p = os.path.join(r, fn)
                pkg.append((os.path.relpath(p, radice).replace(os.sep, "/"), os.path.getsize(p)))
    return voci + pkg


def righe_elenco(radice=RADICE):
    return ['call :file "%s" %s' % (rel.replace("/", "\\"), '""' if dim is None else dim)
            for rel, dim in file_programma(radice)]


def testo_aggiornato(radice=RADICE):
    with io.open(os.path.join(radice, "verifica_pacchetto.bat"), "rb") as f:
        righe = f.read().decode("ascii").replace("\r\n", "\n").split("\n")
    i = next(k for k, r in enumerate(righe) if r.startswith(INIZIO))
    j = next(k for k, r in enumerate(righe) if r.startswith(FINE))
    nuove = righe[:i + 1] + righe_elenco(radice) + righe[j:]
    return "\r\n".join(nuove)


def file_windows(radice=RADICE):
    """File per Windows del progetto (a capo CRLF, ASCII): i .bat, .vbs e .txt
    nella radice, esclusi quelli prodotti dall'uso (log, report...), e i .txt di docs/."""
    prodotti = ("installa_log.txt", "python_msi_log.txt", "numpy_verificato.txt", "rilevamento_pc.txt",
                "comandi_da_incollare.txt")      # quest'ultimo vive in docs/
    voci = []
    for fn in sorted(os.listdir(radice)):
        p = os.path.join(radice, fn)
        if (os.path.isfile(p) and fn.lower().endswith(ESTENSIONI_WINDOWS) and fn not in prodotti
                and not fn.startswith(("report_diagnostica", "diagnostica_"))):
            voci.append(p)
    docs = os.path.join(radice, "docs")
    if os.path.isdir(docs):
        voci.extend(os.path.join(docs, fn) for fn in sorted(os.listdir(docs)) if fn.lower().endswith(".txt"))
    return voci


def a_capo_crlf(radice=RADICE):
    """Riscrive in CRLF i file per Windows che non lo sono; restituisce i nomi."""
    cambiati = []
    for p in file_windows(radice):
        with io.open(p, "rb") as f:
            b = f.read()
        nuovo = b.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        if nuovo != b:
            with io.open(p, "wb") as f:
                f.write(nuovo)
            cambiati.append(os.path.relpath(p, radice))
    return cambiati


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    radice = RADICE
    if "--radice" in argv:
        radice = argv[argv.index("--radice") + 1]
    bat = os.path.join(radice, "verifica_pacchetto.bat")
    if "--controlla" in argv:
        with io.open(bat, "rb") as f:
            attuale = f.read().decode("ascii")
        if attuale != testo_aggiornato(radice):
            print("verifica_pacchetto.bat NON aggiornato: lanciare python strumenti/genera_verifica_pacchetto.py")
            return 1
        print("verifica_pacchetto.bat aggiornato")
        return 0
    for c in a_capo_crlf(radice):
        print("a capo CRLF: %s" % c)
    testo = testo_aggiornato(radice)          # prima si legge, poi si riscrive
    with io.open(bat, "wb") as f:
        f.write(testo.encode("ascii"))
    print("verifica_pacchetto.bat: %d file nell'elenco" % len(righe_elenco(radice)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
