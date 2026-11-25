# -*- coding: utf-8 -*-
"""denoising_live: acquisizione con denoising in tempo reale per Digidata 1322A.

Uso:
    python main.py                 modalita' da config.ini (predefinito: chiede)
    python main.py --simulazione   riproduce file .wcp (PC di sviluppo)
    python main.py --digidata      scheda vera (PC del laboratorio, Windows XP)

Altre opzioni: --config FILE, --senza-numpy, --file FILE.wcp (simulazione),
--cartella-dati DIR, --prova-gui SECONDI (avvio automatico per i test).
"""
import argparse
import os
import sys

QUI = os.path.dirname(os.path.abspath(__file__))


def argomenti(argv=None):
    ap = argparse.ArgumentParser(description="Acquisizione con denoising in tempo reale")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--simulazione", action="store_true", help="modalita' simulazione")
    g.add_argument("--digidata", action="store_true", help="modalita' Digidata (Windows XP)")
    ap.add_argument("--config", default=os.path.join(QUI, "config.ini"), help="file di configurazione")
    ap.add_argument("--senza-numpy", action="store_true", help="forza il percorso in Python puro")
    ap.add_argument("--file", default="", help="file .wcp da riprodurre in simulazione")
    ap.add_argument("--cartella-dati", default="", help="cartella dove salvare le registrazioni")
    ap.add_argument("--finto", action="store_true",
                    help="modalita' Digidata con la DLL simulata (solo per le prove automatiche)")
    ap.add_argument("--prova-gui", type=float, default=0.0,
                    help="prova automatica: avvia, registra per N secondi, cambia il filtro, esce")
    return ap.parse_args(argv)


def main(argv=None):
    args = argomenti(argv)
    if args.senza_numpy:
        os.environ["DLIVE_SENZA_NUMPY"] = "1"
    sys.path.insert(0, QUI)
    from dlive import verifica_numpy
    esito_numpy = verifica_numpy.verifica(QUI)       # prima di importare numpy
    from dlive import compat, config, registro

    cfg = config.carica_o_crea(args.config, base=QUI)
    log, percorso_log = registro.configura(cfg.percorso_assoluto("generale.cartella_log"))
    log.info("=" * 70)
    log.info("denoising_live avviato; Python %s", compat.versione_python())
    log.info("Percorso di calcolo: %s", compat.descrizione_percorso())
    log.info("Verifica di numpy: %s", esito_numpy[1])
    log.info("Configurazione: %s", args.config)
    for a in cfg.avvisi:
        log.warning("Configurazione: %s", a)
    if args.cartella_dati:
        cfg.imposta("generale.cartella_dati", args.cartella_dati)
    if args.file:
        cfg.imposta("simulazione.file", os.path.abspath(args.file))

    import tkinter as tk
    from tkinter import messagebox
    from dlive import gui

    errori, avvisi = cfg.controlla()
    for a in avvisi:
        log.warning("Configurazione: %s", a)
    _dpi_windows()
    root = tk.Tk()
    from dlive.scala import Scala
    scala = Scala(root, cfg["interfaccia.dimensione"])
    if errori:
        for e in errori:
            log.error("Configurazione: %s", e)
        root.withdraw()
        messagebox.showerror("Configurazione non valida",
                             "Correggere %s:\n\n%s" % (args.config, "\n".join(errori)))
        root.destroy()
        return 2

    if args.simulazione:
        modalita = "simulazione"
    elif args.digidata:
        modalita = "digidata"
    else:
        modalita = cfg["generale.modalita"]
        if modalita == "chiedi":
            root.withdraw()
            modalita = gui.chiedi_modalita(root, scala)
            if not modalita:
                root.destroy()
                return 0
            root.deiconify()
    log.info("Modalita': %s", modalita)

    dev_digidata = None
    if modalita == "digidata":
        from dlive.devices.digidata import Digidata1322Device
        from dlive.devices.base import ErroreDispositivo
        from dlive import sysinfo, winwcp_impostazioni
        try:
            _, cambi, avv_wcp = winwcp_impostazioni.all_avvio(
                cfg, log, chiedi=lambda t: messagebox.askyesno("Impostazioni di WinWCP", t))
            if cambi or cfg["digidata.impostazioni_winwcp"] != "chiedi":
                cfg.salva()
            if avv_wcp:
                messagebox.showwarning("Impostazioni di WinWCP", "\n\n".join(avv_wcp))
        except Exception:
            log.exception("Lettura delle impostazioni di WinWCP non riuscita (si usa config.ini)")
        dev_digidata = Digidata1322Device(
            canale=cfg["digidata.canale_ingresso"], fs=cfg["digidata.frequenza_acquisizione_hz"],
            range_v=cfg["digidata.range_v"], percorso_dll=cfg["digidata.percorso_dll"],
            cartella_programma=QUI, uscite=cfg["digidata.uscite_analogiche"],
            campioni_buffer=cfg["digidata.campioni_buffer"],
            intervallo_lettura=cfg["digidata.intervallo_lettura_ms"] / 1000.0,
            chunks_per_second=cfg["digidata.chunks_per_second"],
            calibrazione={"yg": cfg["calibrazione.yg"], "yz": cfg["calibrazione.yz"],
                          "unita": cfg["calibrazione.unita"], "nome": cfg["calibrazione.nome_canale"],
                          "ad": cfg["digidata.range_v"], "adcmax": 32677})
        try:
            if args.finto:                       # solo per le prove: nessuna scheda vera
                from dlive.devices.dd132x_finto import LibreriaFinta
                dev_digidata.lib = LibreriaFinta()
                dev_digidata.percorso_dll = "<DLL finta per le prove>"
                log.warning("Modalita' Digidata con la DLL SIMULATA (--finto): nessuna scheda vera")
            else:
                dev_digidata.carica_dll()
        except ErroreDispositivo as e:
            log.error("DLL: %s", e.messaggio)
            messagebox.showwarning("Driver Digidata",
                                   e.messaggio + "\n\nEseguire diagnostica.bat e mandare il file "
                                                 "report_diagnostica.txt.")
        conc = sysinfo.programmi_concorrenti_attivi()
        if conc:
            log.warning("Programmi che usano la scheda aperti: %s", conc)
            messagebox.showwarning("Scheda occupata",
                                   "Sono aperti: %s.\nLa scheda Digidata puo' essere usata da un solo "
                                   "programma alla volta: chiuderli prima di avviare l'anteprima."
                                   % ", ".join(conc))

    app = gui.FinestraPrincipale(root, cfg, modalita, QUI, dev_digidata, scala)
    esito = {"codice": 0}
    if args.prova_gui > 0:
        _prova_automatica(root, app, args.prova_gui, esito, log)
    root.mainloop()
    log.info("Uscita (codice %d)", esito["codice"])
    return esito["codice"]


def _dpi_windows():
    """Su Windows Vista e successivi: la finestra dichiara di gestire da se'
    la scala, cosi' Tk riceve i DPI veri (testi nitidi; la dimensione la
    calcola dlive/scala.py).  Su XP queste funzioni non esistono: nulla."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)      # Windows 8.1+
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()           # Vista+
    except Exception:
        pass


def _prova_automatica(root, app, durata, esito, log):
    """Usata dai test: registra, cambia filtro, aggiunge un marker, chiude."""
    import time

    def passo1():
        app.avvia_registrazione()
        if app.sessione is None or not app.sessione.in_corso:
            esito["codice"] = 3
            log.error("Prova GUI: la sessione non e' partita")
            app.chiudi_senza_conferma()
            return
        root.after(int(durata * 400), passo2)

    def passo2():
        app.var_marker.set("marker di prova")
        app.aggiungi_marker()
        app.imposta_taglio(2.0)
        app.var_finestra.set("10 s")
        app._cambia_finestra()
        root.after(int(durata * 600), passo3)

    def passo3():
        s = app.sessione
        reg = s.reg
        nome = reg.nome_base if reg is not None else None
        app.chiudi_senza_conferma()
        log.info("Prova GUI completata: registrazione %s", nome)
        if nome is None:
            esito["codice"] = 4

    root.after(500, passo1)


if __name__ == "__main__":
    sys.exit(main())
