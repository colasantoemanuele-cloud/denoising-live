# -*- coding: utf-8 -*-
"""Screenshot della finestra principale in anteprima (per controllare a
occhio la leggibilita' a varie risoluzioni) e controllo automatico che
nessun controllo esca dalla finestra.

Da eseguire sotto un display virtuale della risoluzione voluta, es.:

    xvfb-run -a -s "-screen 0 1024x768x24 -dpi 96" \\
        python strumenti/screenshot_gui.py docs/screenshot/gui_1024x768.png

Opzioni: --dimensione auto|75|100|...  --file FILE.wcp  --secondi N
Serve ImageMagick (comando ``import``) per salvare l'immagine.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, QUI)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("uscita")
    ap.add_argument("--dimensione", default="auto")
    ap.add_argument("--file", default=os.path.join(QUI, "riferimenti", "dati", "071222_002.1.wcp"))
    ap.add_argument("--record", type=int, default=1)
    ap.add_argument("--secondi", type=float, default=12.0)
    args = ap.parse_args()

    import tkinter as tk
    from dlive import config, registro
    from dlive.scala import Scala
    from dlive import gui

    tmp = tempfile.mkdtemp()
    registro.configura(os.path.join(tmp, "log"), "screenshot.log", a_schermo=False)
    cfg = config.carica_o_crea(os.path.join(tmp, "config.ini"), base=QUI)
    cfg.imposta("simulazione.file", os.path.abspath(args.file))
    cfg.imposta("simulazione.record", args.record)
    cfg.imposta("simulazione.velocita", 5)
    cfg.imposta("simulazione.sovracampiona", True)
    cfg.imposta("generale.cartella_dati", os.path.join(tmp, "dati"))
    cfg.imposta("interfaccia.dimensione", args.dimensione)

    root = tk.Tk()
    scala = Scala(root, cfg["interfaccia.dimensione"])
    app = gui.FinestraPrincipale(root, cfg, "simulazione", QUI, None, scala)
    esito = {"codice": 0}

    def scatta():
        root.update_idletasks()
        fuori = gui.controlli_fuori(root)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        print("schermo %dx%d, finestra %dx%d+%d+%d, %s, font base %d pt, valore %d pt" % (
            sw, sh, root.winfo_width(), root.winfo_height(), root.winfo_rootx(), root.winfo_rooty(),
            scala.descrizione(), scala.base_pt, scala.font["DliveValore"].actual("size")))
        if root.winfo_rootx() + root.winfo_width() > sw or root.winfo_rooty() + root.winfo_height() > sh:
            print("ERRORE: la finestra supera lo schermo")
            esito["codice"] = 1
        if fuori:
            print("ERRORE: controlli fuori dalla finestra:\n  " + "\n  ".join(fuori))
            esito["codice"] = 1
        print("barra di scorrimento del pannello: %s" % (
            "si" if gui.barra_scorrimento_visibile(root) else "no"))
        if shutil.which("import"):
            subprocess.check_call(["import", "-window", "root", args.uscita])
            print("salvato %s" % args.uscita)
        else:
            print("ImageMagick 'import' non trovato: nessuna immagine")
        app.chiudi_senza_conferma()

    root.after(300, app.avvia_anteprima)
    root.after(int(args.secondi * 1000), scatta)
    root.mainloop()
    return esito["codice"]


if __name__ == "__main__":
    sys.exit(main())
