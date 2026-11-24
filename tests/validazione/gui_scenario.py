# -*- coding: utf-8 -*-
"""Scenari della finestra vera: E3, E4 (con disegno), E5, E6 (PC lento), E7
(modalita' Digidata con la DLL finta) e la parte GUI di B9.

Si esegue SOLO sotto un display virtuale (valida.sh: Docker con xvfb-run a
1280x1024 e DLIVE_DISPLAY_VIRTUALE=1): non apre mai finestre sullo schermo.
Avvia main.main() vero; l'unico intervento e' la sostituzione della prova
automatica (--prova-gui) con lo scenario e alcuni "punti di misura" che non
cambiano la logica:
  * messagebox.* registra le finestre di dialogo (e risponde "si'" alle conferme);
  * Tk.report_callback_exception registra le eccezioni nei callback;
  * gui.Grafico.disegna annota l'istante del disegno e l'ultimo campione
    disegnato (ritardo campione -> grafico, E5/E6);
  * in E7 il caricamento della DLL e' sostituito dalla DLL finta (rigorosa:
    rifiuta una seconda apertura della scheda) e alcuni errori sono provocati.

Uso: python gui_scenario.py e3|b9|e6|e7 CARTELLA_USCITA
Variabili: DLIVE_GUI_AGGIORNAMENTO_HZ (forza l'aggiornamento del grafico),
DLIVE_E6_REGISTRAZIONE_S (durata della registrazione di E6, predefinita 600).
"""
from __future__ import division

import array
import io
import json
import os
import sys
import tempfile
import threading
import time
import traceback

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
import comuni as C  # noqa: E402

# E6: limite della coda (s di segnale in attesa di elaborazione).  Il programma
# non ha un limite configurato: 600 s e' la costante del test (decisione D8).
LIMITE_CODA_S = 600.0

DIALOGHI = []
ECCEZIONI_TK = []
DISEGNI = []        # (istante, ultimo campione disegnato, t0 del dispositivo, fs)


def _prepara(lavoro, modalita="simulazione"):
    s = C.sintetico()
    src = os.path.join(lavoro, "sintetico_1000Hz.wcp")
    C.scrivi_wcp_semplice(src, s.rumoroso, 0.001)
    from dlive import config
    cfg = config.Configurazione(os.path.join(lavoro, "config.ini"), lavoro)
    for k, v in (("generale.modalita", modalita), ("generale.cartella_dati", os.path.join(lavoro, "dati")),
                 ("generale.cartella_log", os.path.join(lavoro, "log")), ("simulazione.file", src),
                 ("simulazione.record", 1), ("simulazione.canale", 0), ("simulazione.velocita", 1.0),
                 ("simulazione.sovracampiona", False), ("simulazione.rumore_sintetico", False)):
        cfg.imposta(k, v)
    if os.environ.get("DLIVE_GUI_AGGIORNAMENTO_HZ"):
        cfg.imposta("grafico.aggiornamento_hz", float(os.environ["DLIVE_GUI_AGGIORNAMENTO_HZ"]))
    cfg.salva()
    return cfg.percorso, src


def _strumenta(gui, tk, messagebox):
    def dialogo(tipo, risposta):
        def f(*a, **k):
            DIALOGHI.append((tipo, " | ".join(str(x) for x in a)))
            return risposta
        return f
    messagebox.askyesno = dialogo("askyesno", True)
    messagebox.showerror = dialogo("showerror", None)
    messagebox.showwarning = dialogo("showwarning", None)
    messagebox.showinfo = dialogo("showinfo", None)

    def eccezione(self, tipo, valore, tb):
        ECCEZIONI_TK.append("".join(traceback.format_exception(tipo, valore, tb)))
    tk.Tk.report_callback_exception = eccezione

    originale = gui.Grafico.disegna

    def disegna(self):
        r = originale(self)
        app = _APP.get("app")
        s = app.sessione if app is not None else None
        if s is not None and s.in_corso and s.grafico is not None and app.contatore:
            dev = s.dev
            t0 = getattr(dev, "_t0", None) or getattr(dev, "_t_avvio", 0.0)
            DISEGNI.append((time.time(), app.contatore * s.grafico.k, t0,
                            s.fs * getattr(dev, "velocita", 1.0)))
        return r
    gui.Grafico.disegna = disegna


_APP = {}
MISURE = {}


def scenario_e3(root, app, durata, esito, log):
    M = MISURE

    def avvio():
        _APP["app"] = app
        M["t_anteprima"] = time.time()
        app.avvia_anteprima()
        M["anteprima_partita"] = bool(app.sessione and app.sessione.in_corso)
        root.after(30000, cambio_e_registrazione)

    def cambio_e_registrazione():
        s = app.sessione
        M["campioni_anteprima"] = s.campioni if s else 0
        app.imposta_taglio(2.0)
        app.var_marker.set("marker E3 anteprima")
        app.aggiungi_marker()
        M["cpu0"] = time.process_time()
        M["t_reg"] = time.time()
        app.avvia_registrazione()
        root.after(10000, marker_in_registrazione)

    def marker_in_registrazione():
        app.var_marker.set("marker E3 registrazione")
        app.aggiungi_marker()
        root.after(10000, secondo_cambio)

    def secondo_cambio():
        app.imposta_taglio(5.0)
        root.after(10000, stop)

    def stop():
        M["cpu1"] = time.process_time()
        M["t_stop"] = time.time()
        s = app.sessione
        M["nome_reg"] = s.reg.nome_base if s and s.reg is not None else None
        M["cartella"] = s.reg.cartella if s and s.reg is not None else None
        M["fuori_finestra"] = len(__import__("dlive.gui", fromlist=["x"]).controlli_fuori(root))
        M["geometria"] = "%dx%d" % (root.winfo_width(), root.winfo_height())
        M["schermo"] = "%dx%d" % (root.winfo_screenwidth(), root.winfo_screenheight())
        app.ferma()
        M["fermata"] = not (app.sessione and app.sessione.in_corso)
        root.after(1000, chiudi)

    def chiudi():
        app.chiudi()

    root.after(500, avvio)


def scenario_b9(root, app, durata, esito, log):
    _FileGuasto = C.FileGuasto
    M = MISURE

    def avvio():
        _APP["app"] = app
        app.avvia_registrazione()
        root.after(5000, guasto)

    def guasto():
        s = app.sessione
        reg = s.reg
        M["percorso_raw"] = reg.percorso_raw
        M["percorso_filt"] = reg.percorso_filt
        M["percorso_json"] = reg.percorso_json
        g = {"attivo": True}
        reg.raw._f = _FileGuasto(reg.raw._f, g)
        reg.filt._f = _FileGuasto(reg.filt._f, g)
        M["campioni_al_guasto"] = s.campioni
        root.after(4000, controlla)

    def controlla():
        s = app.sessione
        M["in_corso"] = bool(s and s.in_corso)
        M["campioni_dopo"] = s.campioni
        M["banda_visibile"] = bool(app.lbl_avviso.winfo_ismapped())
        M["testo_banda"] = app.lbl_avviso.cget("text")
        app.ferma()
        root.after(500, app.chiudi)

    root.after(500, avvio)




# ---------------------------------------------------------------------------
def _passi(root, passi):
    """Esegue in sequenza le funzioni di 'passi'; ognuna restituisce i
    millisecondi di attesa prima della successiva."""
    coda = list(passi)

    def prossimo():
        if not coda:
            return
        f = coda.pop(0)
        try:
            attesa = f()
        except Exception:
            MISURE.setdefault("errori_scenario", []).append(traceback.format_exc())
            attesa = 100
        root.after(int(attesa or 0), prossimo)
    root.after(500, prossimo)


def scenario_e6(root, app, durata, esito, log):
    """PC lento: anteprima 30 s e registrazione di 10 minuti, impostazioni predefinite."""
    M = MISURE
    durata_reg = float(os.environ.get("DLIVE_E6_REGISTRAZIONE_S", "600"))
    M["campioni_coda"] = []

    def campiona():
        s = app.sessione
        if s is not None and s.in_corso:
            dev = s.dev
            arretrato = (time.time() - dev._t0) * dev.fs * dev.velocita - s.campioni
            with s.coda.mutex:
                in_coda = sum(len(b.dati) for b in list(s.coda.queue) if hasattr(b, "dati"))
            M["campioni_coda"].append((round(time.time() - M["t_anteprima"], 1), round(arretrato / dev.fs, 3),
                                       round(in_coda / dev.fs, 3)))
            root.after(1000, campiona)

    def avvio():
        _APP["app"] = app
        M["t_anteprima"] = time.time()
        app.avvia_anteprima()
        M["anteprima_partita"] = bool(app.sessione and app.sessione.in_corso)
        campiona()
        return 30000

    def registra():
        M["cpu0"] = time.process_time()
        M["t_reg"] = time.time()
        app.avvia_registrazione()
        return durata_reg * 1000

    def stop():
        M["cpu1"] = time.process_time()
        M["t_stop"] = time.time()
        s = app.sessione
        M["nome_reg"] = s.reg.nome_base if s and s.reg is not None else None
        M["cartella"] = s.reg.cartella if s and s.reg is not None else None
        M["persi"] = s.persi_tot
        app.ferma()
        M["fermata"] = not (app.sessione and app.sessione.in_corso)
        return 1000

    _passi(root, [avvio, registra, stop, lambda: app.chiudi()])


# --- E7: modalita' Digidata con la DLL finta ---------------------------------
E7 = {"dll": "mancante", "aspi_ok": True, "lib": None, "errore_interno": False}


def _prepara_e7():
    from dlive.devices import axdd132x as ax
    from dlive.devices import digidata as dd
    from dlive.devices.dd132x_finto import LibreriaFinta, _obj
    from dlive import compat, filters

    class LibreriaRigorosa(LibreriaFinta):
        """La DLL finta, ma rifiuta di aprire una scheda gia' aperta (come
        farebbe un driver vero) e annota i campioni generati."""

        def __init__(self, **kw):
            self.aperti = 0
            self.doppie_aperture = 0
            self.generati = array.array("h")
            LibreriaFinta.__init__(self, **kw)

        def _DD132X_OpenDevice(self, a, t, perr):
            if self.aperti:
                self.doppie_aperture += 1
                _obj(perr).value = 9999
                return None
            h = LibreriaFinta._DD132X_OpenDevice(self, a, t, perr)
            if h:
                self.aperti += 1
            return h

        def _DD132X_CloseDevice(self, h, perr):
            self.aperti = max(0, self.aperti - 1)
            return LibreriaFinta._DD132X_CloseDevice(self, h, perr)

        def _DD132X_StartAcquisition(self, h, perr):
            self.generati = array.array("h")
            return LibreriaFinta._DD132X_StartAcquisition(self, h, perr)

        def _campione(self, t):
            v = LibreriaFinta._campione(self, t)
            if threading.current_thread().name == "dll_finta":
                self.generati.append(v)
            return v

    E7["lib"] = LibreriaRigorosa(rumore_mv=2.0)
    originale = dd.Digidata1322Device.carica_dll

    def carica_dll(self):
        if E7["dll"] == "mancante":
            vecchio_win, vecchi_perc = compat.SU_WINDOWS, dd.percorsi_candidati_dll
            compat.SU_WINDOWS = True
            dd.percorsi_candidati_dll = lambda *a, **k: []
            try:
                return originale(self)          # messaggio vero del programma
            finally:
                compat.SU_WINDOWS, dd.percorsi_candidati_dll = vecchio_win, vecchi_perc
        self.lib = E7["lib"]
        self.percorso_dll = "<DLL finta rigorosa>"
        return self.lib
    dd.Digidata1322Device.carica_dll = carica_dll
    ax.controlla_aspi = lambda *a: ({"ok": True, "errore": ""} if E7["aspi_ok"] else
                                    {"ok": False, "errore": "wnaspi32.dll non caricabile: [WinError 126] "
                                                            "Impossibile trovare il modulo specificato"})
    elab_originale = filters.Elaboratore

    def elaboratore(*a, **k):
        if E7["errore_interno"]:
            E7["errore_interno"] = False
            raise RuntimeError("ERRORE SIMULATO E7 dopo l'apertura della scheda")
        return elab_originale(*a, **k)
    filters.Elaboratore = elaboratore


def scenario_e7(root, app, durata, esito, log):
    M = MISURE
    M["errori"] = []
    lib = E7["lib"]
    dev = app.dev_digidata

    def tentativo(nome):
        def f():
            n = len(DIALOGHI)
            app.avvia_anteprima()
            nuovi = DIALOGHI[n:]
            partita = bool(app.sessione and app.sessione.in_corso)
            M["errori"].append({"caso": nome, "dialoghi": nuovi, "partita": partita,
                                "finestra_viva": bool(root.winfo_exists()),
                                "schede_aperte_dopo": lib.aperti})
            return 300
        return f

    def imposta(**k):
        def f():
            E7.update(k)
            if "trovato" in k:
                lib.trovato = k["trovato"]
            return 0
        return f

    def riprova_e_ferma(nome):
        def f():
            tentativo(nome)()
            M["errori"][-1]["campioni_dopo_2s"] = None
            return 2000
        return f

    def ferma_e_annota():
        s = app.sessione
        if M["errori"] and s is not None:
            M["errori"][-1]["campioni_dopo_2s"] = s.campioni
        app.ferma()
        return 500

    # overrun: buffer piccolo e lettura bloccata 8 s una volta
    def prepara_overrun():
        dev.campioni_buffer = 6000
        orig = dev.leggi
        st = {"n": 0}

        def leggi_lenta(timeout=0.2):
            st["n"] += 1
            if st["n"] == 20:
                time.sleep(8.0)
            return orig(timeout)
        dev.leggi = leggi_lenta
        app.avvia_anteprima()
        M["overrun_partita"] = bool(app.sessione and app.sessione.in_corso)
        return 13000

    def controlla_overrun():
        s = app.sessione
        M["overrun"] = {"persi": s.persi_tot if s else None, "overrun_scheda": dev.overrun,
                        "banda_visibile": bool(app.lbl_avviso.winfo_ismapped()),
                        "testo_banda": app.lbl_avviso.cget("text"),
                        "in_corso": bool(s and s.in_corso)}
        app.ferma()
        del dev.leggi
        dev.campioni_buffer = 1000000
        app._nascondi_avviso()
        return 500

    # sessione completa: anteprima 30 s (con cambio dell'aggiornamento del grafico),
    # registrazione 60 s con un marker e un cambio di taglio
    def anteprima():
        _APP["app"] = app
        del DISEGNI[:]
        M["t_anteprima"] = time.time()
        app.avvia_anteprima()
        M["anteprima_partita"] = bool(app.sessione and app.sessione.in_corso)
        return 8000

    def aggiornamento(hz):
        def f():
            M.setdefault("aggiornamento", []).append((hz, time.time(), len(DISEGNI)))
            app.cambia_aggiornamento(hz)
            return 6000
        return f

    def registrazione():
        M.setdefault("aggiornamento", []).append((None, time.time(), len(DISEGNI)))
        M["cfg_aggiornamento_salvato"] = io.open(app.cfg.percorso, encoding="utf-8").read().count(
            "aggiornamento_hz = 5")
        app.avvia_registrazione()
        return 20000

    def marker():
        app.var_marker.set("marker E7")
        app.aggiungi_marker()
        return 10000

    def cambio_taglio():
        app.imposta_taglio(2.0)
        return 30000

    def stop():
        s = app.sessione
        M["nome_reg"] = s.reg.nome_base if s and s.reg is not None else None
        M["cartella"] = s.reg.cartella if s and s.reg is not None else None
        M["persi"] = s.persi_tot
        app.ferma()
        M["fermata"] = not (app.sessione and app.sessione.in_corso)
        M["generati"] = len(lib.generati)
        M["schede_aperte_alla_fine"] = lib.aperti
        return 1000

    _passi(root, [
        tentativo("DLL mancante"),
        imposta(dll="ok", trovato=False, aspi_ok=True), tentativo("scheda assente"),
        imposta(aspi_ok=False), tentativo("WinASPI assente"),
        imposta(aspi_ok=True, trovato=True, errore_interno=True), tentativo("errore interno dopo l'apertura"),
        riprova_e_ferma("riprova dopo gli errori"), ferma_e_annota,
        prepara_overrun, controlla_overrun,
        anteprima, aggiornamento(2.0), aggiornamento(10.0), aggiornamento(5.0), registrazione, marker,
        cambio_taglio, stop, lambda: app.chiudi()])


# ---------------------------------------------------------------------------
def _confronta_b123(raw_p, filt_p, json_p, sorgente_tenuta, sorgente, cambi=None, fs=C.FS):
    """B1/B2/B3 sui file di una registrazione.  sorgente: i conteggi prodotti
    dalla sorgente dall'avvio della sessione; sorgente_tenuta: la stessa con i
    picchi tenuti (ingresso del filtro di riferimento); cambi: [(campione, sos)]."""
    import numpy as np
    meta = json.load(io.open(json_p, encoding="utf-8"))
    inizio = int(meta["acquisizione"]["campione_inizio"])
    n = int(round(meta["durata_s"] * fs))
    _, _, rr = C.leggi_wcp_riferimento(raw_p)
    _, _, rf = C.leggi_wcp_riferimento(filt_p)
    raw = C.concatena_canale(rr)[:n]
    nf = (n + 7) // 8
    filt = C.concatena_canale(rf)[:nf].astype(np.int64)
    atteso = np.asarray(sorgente[inizio:inizio + n])
    b1 = int(np.sum(raw[:len(atteso)] != atteso)) + abs(len(atteso) - n)
    # B2: filtro di riferimento (scipy) dal primo campione della sessione
    fine = inizio + 8 * nf
    x = np.asarray(sorgente_tenuta[:fine], dtype=np.float64)
    segmenti = [(0, C.sos_riferimento())] + list(cambi or [])
    rif = np.zeros(len(x))
    confrontabile = np.ones(len(x), dtype=bool)
    for k, (da, sos) in enumerate(segmenti):
        a_ = segmenti[k + 1][0] if k + 1 < len(segmenti) else len(x)
        y = C.filtra_riferimento(sos, x)
        rif[da:a_] = y[da:a_]
        if k > 0:
            confrontabile[da:min(len(x), da + int(3 * fs))] = False    # 3 s dopo il cambio
    idx = inizio + 8 * np.arange(nf)
    idx = idx[idx < len(x)]
    ok_i = confrontabile[idx]
    d = np.abs(filt[:len(idx)][ok_i] - np.round(rif[idx][ok_i]))
    b2 = int(d.max()) if len(d) else None
    b3 = {"persi": meta["campioni_persi"], "campioni": n, "filtrati": nf,
          "record_grezzo": meta["record_grezzo"], "record_filtrato": meta["record_filtrato"],
          "durata_s": meta["durata_s"]}
    return {"B1_diversi": b1, "B2_diff_max_conteggi": b2, "B2_campioni_confrontati": int(ok_i.sum()),
            "B3": b3, "campione_inizio": inizio, "json": {k: meta.get(k) for k in (
                "chiusura_regolare", "marker", "cambi_parametri", "campioni_persi")}}
def _ritardi(da_s=1.0):
    rit = []
    for t, ultimo, t0d, fs in DISEGNI:
        if t0d and t - t0d > da_s:
            rit.append(t - (t0d + ultimo / fs))
    rit.sort()
    if not rit:
        return None
    return {"n": len(rit), "mediana_s": rit[len(rit) // 2], "p95_s": rit[int(0.95 * (len(rit) - 1))],
            "max_s": rit[-1], "min_s": rit[0]}


def _leggi_json(cart, nome):
    try:
        return json.load(io.open(os.path.join(cart, nome + ".json"), encoding="utf-8"))
    except Exception:
        return {}


def main():
    modo, uscita = sys.argv[1], sys.argv[2]
    if os.environ.get("DLIVE_DISPLAY_VIRTUALE") != "1" and not sys.platform.startswith("win"):
        sys.stderr.write("gui_scenario.py apre la finestra: si esegue solo sotto xvfb-run con "
                         "DLIVE_DISPLAY_VIRTUALE=1\n")
        return 2
    lavoro = tempfile.mkdtemp(prefix="dlive_gui_")
    percorso_cfg, src = _prepara(lavoro, "digidata" if modo == "e7" else "simulazione")
    sys.path.insert(0, C.RADICE)
    import main as M
    import tkinter as tk
    from tkinter import messagebox
    from dlive import config, gui
    _strumenta(gui, tk, messagebox)
    hz = config.carica_o_crea(percorso_cfg)["grafico.aggiornamento_hz"]
    M._prova_automatica = {"e3": scenario_e3, "b9": scenario_b9, "e6": scenario_e6, "e7": scenario_e7}[modo]
    if modo == "e7":
        _prepara_e7()
        argomenti = ["--digidata"]
    else:
        argomenti = ["--simulazione", "--file", src]
    t0 = time.time()
    codice = M.main(argomenti + ["--config", percorso_cfg, "--cartella-dati", os.path.join(lavoro, "dati"),
                                 "--prova-gui", "1"])
    durata = time.time() - t0
    log_p = os.path.join(lavoro, "log", "denoising_live.log")
    log = io.open(log_p, encoding="utf-8").read() if os.path.exists(log_p) else ""
    righe_err = [r for r in log.splitlines() if " ERROR " in r or "Traceback" in r or "CRITICAL" in r]
    errori_dialogo = [d for d in DIALOGHI if d[0] in ("showerror", "showwarning")]
    ris = {"modo": modo, "codice": codice, "durata_s": durata, "python": sys.version.split()[0],
           "aggiornamento_hz": hz, "misure": MISURE, "dialoghi": DIALOGHI, "eccezioni_tk": ECCEZIONI_TK,
           "righe_errore_log": righe_err[:50], "n_righe_log": len(log.splitlines())}
    MISURE.pop("generati_lista", None)
    if modo == "e3":
        meta = _leggi_json(MISURE.get("cartella", ""), MISURE.get("nome_reg") or "")
        ris["json"] = {k: meta.get(k) for k in ("chiusura_regolare", "durata_s", "marker", "cambi_parametri",
                                                 "campioni_persi")}
        ris["ritardo"] = _ritardi()
        if "cpu1" in MISURE:
            ris["cpu_%"] = (MISURE["cpu1"] - MISURE["cpu0"]) / (MISURE["t_stop"] - MISURE["t_reg"]) * 100.0
        ok = (codice == 0 and not righe_err and not ECCEZIONI_TK and not errori_dialogo and
              MISURE.get("anteprima_partita") and MISURE.get("fermata") and meta.get("chiusura_regolare")
              and any(m.get("testo") == "marker E3 registrazione" for m in meta.get("marker") or [])
              and any(c.get("descrizione") == "filtro" for c in meta.get("cambi_parametri") or []))
        ris["esito"] = bool(ok)
    elif modo == "b9":
        validi = 0
        leggibili = False
        try:
            validi = C.campioni_validi(MISURE["percorso_raw"], MISURE["percorso_json"],
                                       C.sintetico().rumoroso)
            C.leggi_wcp_riferimento(MISURE["percorso_filt"])
            leggibili = validi > 0
        except Exception as e:
            ris["errore_lettura"] = str(e)
        ris["b9"] = {"banda_rossa": MISURE.get("banda_visibile") and
                     "ERRORE DI SCRITTURA" in (MISURE.get("testo_banda") or ""),
                     "nel_log": "ERRORE DI SCRITTURA" in log,
                     "continua": MISURE.get("in_corso") and
                     MISURE.get("campioni_dopo", 0) > MISURE.get("campioni_al_guasto", 0) + 3 * C.FS,
                     "leggibili": leggibili, "secondi_validi": validi / C.FS,
                     "secondi_al_guasto": MISURE.get("campioni_al_guasto", 0) / C.FS,
                     "testo_banda": MISURE.get("testo_banda")}
        ris["esito"] = bool(codice == 0 and not ECCEZIONI_TK and all(
            ris["b9"][k] for k in ("banda_rossa", "nel_log", "continua", "leggibili")))
    elif modo == "e6":
        import numpy as np
        sint = C.sintetico()
        conf = {}
        try:
            base = os.path.join(MISURE["cartella"], MISURE["nome_reg"])
            meta = _leggi_json(MISURE["cartella"], MISURE["nome_reg"])
            n_tot = int(meta["acquisizione"]["campione_inizio"]) + int(round(meta["durata_s"] * C.FS)) + 16
            giri = n_tot // sint.n + 2
            conf = _confronta_b123(base + "_raw.wcp", base + "_filt.wcp", base + ".json",
                                   np.tile(sint.senza_picchi_tenuto(), giri), np.tile(sint.rumoroso, giri))
        except Exception:
            conf = {"errore": traceback.format_exc()}
        ris["conformita"] = conf
        ris["ritardo"] = _ritardi()
        coda = MISURE.get("campioni_coda") or []
        ris["arretrato_max_s"] = max([c[1] for c in coda] or [float("nan")])
        ris["coda_max_s"] = max([c[2] for c in coda] or [float("nan")])
        ris["limite_coda_s"] = LIMITE_CODA_S
        ris["arretrato_finale_s"] = coda[-1][1] if coda else None
        if "cpu1" in MISURE:
            ris["cpu_%"] = (MISURE["cpu1"] - MISURE["cpu0"]) / (MISURE["t_stop"] - MISURE["t_reg"]) * 100.0
        limite = LIMITE_CODA_S
        ok = (codice == 0 and not righe_err and not ECCEZIONI_TK and not errori_dialogo and
              MISURE.get("persi") == 0 and conf.get("B1_diversi") == 0 and
              conf.get("B2_diff_max_conteggi") is not None and conf["B2_diff_max_conteggi"] <= 1 and
              conf["B3"]["persi"] == 0 and ris["arretrato_max_s"] < limite and ris["coda_max_s"] < limite and
              ris["ritardo"] is not None and ris["ritardo"]["max_s"] < 1.0)
        ris["esito"] = bool(ok)
    else:   # e7
        import numpy as np
        lib = E7["lib"]
        conf = {}
        try:
            base = os.path.join(MISURE["cartella"], MISURE["nome_reg"])
            meta = _leggi_json(MISURE["cartella"], MISURE["nome_reg"])
            gen = np.frombuffer(lib.generati.tobytes(), dtype=np.int16) if hasattr(lib.generati, "tobytes") \
                else np.array(lib.generati, dtype=np.int16)
            cambi = []
            for c in meta.get("cambi_parametri", []):
                if c["descrizione"] == "filtro":
                    k = int(meta["acquisizione"]["campione_inizio"]) + int(round(c["t_s"] * C.FS))
                    d = c["dopo"]
                    cambi.append((k, C.sos_riferimento(d["tipo"], d["ordine"], d["taglio_hz"],
                                                       notch=tuple(d["notch_hz"]), q=d["q_notch"])))
            conf = _confronta_b123(base + "_raw.wcp", base + "_filt.wcp", base + ".json", gen, gen, cambi)
        except Exception:
            conf = {"errore": traceback.format_exc()}
        ris["conformita"] = conf
        ris["ritardo"] = _ritardi()
        # tracebacks nel log: solo quelli dell'errore provocato apposta sono attesi
        blocchi_tb = log.split("Traceback")[1:]
        ris["traceback_inattesi"] = [b[:300] for b in blocchi_tb if "ERRORE SIMULATO E7" not in b[:3000]]
        errori = MISURE.get("errori", [])
        attese = {"DLL mancante": ["AxDD132x.dll", "config.ini"], "scheda assente": ["Nessun Digidata",
                  "acceso PRIMA"], "WinASPI assente": ["WinASPI non funziona", "AxoScope"],
                  "errore interno dopo l'apertura": [], "riprova dopo gli errori": []}
        valut = []
        for e in errori:
            testi = " ".join(d[1] for d in e["dialoghi"])
            chiavi = attese.get(e["caso"], [])
            if e["caso"] == "riprova dopo gli errori":
                ok_e = e["partita"] and not e["dialoghi"] and (e.get("campioni_dopo_2s") or 0) > 1000
            else:
                ok_e = (not e["partita"] and e["finestra_viva"] and len(e["dialoghi"]) == 1 and
                        "Traceback" not in testi and 'File "' not in testi and
                        all(k in testi for k in chiavi) and e["schede_aperte_dopo"] == 0)
            valut.append({"caso": e["caso"], "ok": bool(ok_e), "messaggio": testi[:400],
                          "schede_aperte_dopo": e["schede_aperte_dopo"],
                          "campioni_dopo_2s": e.get("campioni_dopo_2s")})
        ris["errori_valutati"] = valut
        ov = MISURE.get("overrun", {})
        ris["overrun_ok"] = bool(ov.get("persi") and ov.get("banda_visibile") and
                                 "Campioni persi" in (ov.get("testo_banda") or "") and ov.get("in_corso"))
        # aggiornamento del grafico cambiato dal vivo: disegni al secondo per ogni valore
        agg = MISURE.get("aggiornamento", [])
        ritmi = []
        for (hz_, t_a, n_a), (_, t_b, n_b) in zip(agg, agg[1:]):
            if hz_ is not None and t_b - t_a > 1:
                ritmi.append({"hz": hz_, "disegni_al_s": (n_b - n_a) / (t_b - t_a)})
        ris["aggiornamento_dal_vivo"] = ritmi
        ritmi_ok = all(0.6 * r["hz"] <= r["disegni_al_s"] <= 1.2 * r["hz"] for r in ritmi) and len(ritmi) == 3
        ris["doppie_aperture"] = lib.doppie_aperture
        ok = (codice == 0 and not ECCEZIONI_TK and not ris["traceback_inattesi"] and
              len(valut) == 5 and all(v["ok"] for v in valut) and ris["overrun_ok"] and
              conf.get("B1_diversi") == 0 and conf.get("B2_diff_max_conteggi") is not None and
              conf["B2_diff_max_conteggi"] <= 1 and conf["B3"]["persi"] == 0 and
              MISURE.get("persi") == 0 and conf["json"]["chiusura_regolare"] and
              any(m["testo"] == "marker E7" for m in conf["json"]["marker"]) and
              any(c["descrizione"] == "filtro" for c in conf["json"]["cambi_parametri"]) and
              MISURE.get("schede_aperte_alla_fine") == 0 and ritmi_ok and
              MISURE.get("cfg_aggiornamento_salvato", 0) >= 1)
        ris["esito"] = bool(ok)
    nome = "risultati_gui_%s%s_py%d%d.json" % (modo, ("_hz%g" % hz) if modo == "e3" else "",
                                               sys.version_info[0], sys.version_info[1])
    with io.open(os.path.join(uscita, nome), "w", encoding="utf-8") as f:
        t = json.dumps(ris, indent=1, ensure_ascii=False, default=str)
        f.write(t if isinstance(t, type(u"")) else t.decode("utf-8"))
    print(json.dumps({"modo": modo, "hz": hz, "python": ris["python"], "esito": ris["esito"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
