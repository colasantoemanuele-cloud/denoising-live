# -*- coding: utf-8 -*-
"""Genera il rapporto di validazione (Markdown + HTML) e le figure.

Uso: python rapporto.py CARTELLA_USCITA [--nome rapporto_validazione] [--lungo]
"""
from __future__ import division, print_function

import argparse
import datetime
import glob
import html
import io
import json
import os
import shutil
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(os.path.dirname(QUI))
sys.path.insert(0, QUI)
sys.path.insert(0, RADICE)

import catalogo as K  # noqa: E402

DOCS = os.path.join(RADICE, "docs", "validazione")      # rapporti ufficiali (e analisi storiche)
DESTINAZIONE = DOCS                                      # dove si scrive (--cartella)
FIGURE = os.path.join(DOCS, "figure")
NOTA_RIPRODUCIBILE = (
    "**Rapporto della sola parte riproducibile.** I dati del laboratorio (`riferimenti/`: file `.wcp` "
    "reali, sorgenti e header Axon) non sono pubblicati: i test che li usano risultano NON VERIFICABILI "
    "e quindi il verdetto qui sotto è al massimo \"PARZIALE\" (0 FAIL, con il numero di test non eseguibili). Il rapporto di validazione ufficiale, "
    "ottenuto con i dati reali, è `docs/validazione/rapporto_validazione.md`.")
SOTTO_FIGURE = {"n": "figure"}

PASS, FAIL, NV = "PASS", "FAIL", "NON VERIFICABILE"


def _leggi(p):
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return None


def _voce(id_, esito, misurato, nota="", ambiente="", dettagli=None):
    liv, cosa, soglia = K.TEST[id_]
    return {"id": id_, "livello": liv, "cosa": cosa, "soglia": soglia, "esito": esito,
            "misurato": misurato, "nota": nota, "ambiente": ambiente, "dettagli": dettagli or {}}


# ---------------------------------------------------------------------------
# Raccolta e unione dei risultati
# ---------------------------------------------------------------------------
def raccogli(uscita, lungo):
    host = _leggi(os.path.join(uscita, "risultati_host.json")) or {"risultati": {}}
    dock = _leggi(os.path.join(uscita, "risultati_docker34.json"))
    gui = {}
    for p in glob.glob(os.path.join(uscita, "risultati_gui_*.json")):
        d = _leggi(p)
        if d:
            hz = d.get("aggiornamento_hz") or 10.0
            gui["%s_hz%g_%s" % (d["modo"], hz, d["python"].rsplit(".", 1)[0])] = d
    mut = _leggi(os.path.join(uscita, "risultati_mutazioni.json"))
    ris = {}
    for id_ in K.TEST:
        if id_ in host["risultati"]:
            v = dict(host["risultati"][id_])
            v["ambiente"] = "Python %s (PC di sviluppo)" % host.get("python", "?")
            ris[id_] = v
    # B8 senza --lungo
    if "B8" not in ris:
        ris["B8"] = _voce("B8", NV, "non eseguito: richiede ./valida.sh --lungo (3 ore di segnale)")
    # B9: parte senza finestra (host) + banda rossa nella finestra (Xvfb)
    g_b9 = [g for k, g in gui.items() if k.startswith("b9_")]
    if "B9" in ris:
        v = ris["B9"]
        if not g_b9:
            v["nota"] = (v.get("nota", "") + " Parte nella finestra non verificata (display "
                         "virtuale non disponibile).").strip()
            if v["esito"] == PASS:
                v["esito"] = NV
        else:
            parti = []
            ok_gui = True
            for g in g_b9:
                b = g.get("b9", {})
                parti.append("finestra (Python %s): banda rossa %s, nel log %s, continua %s, file leggibili %s"
                             % (g["python"], _sn(b.get("banda_rossa")), _sn(b.get("nel_log")),
                                _sn(b.get("continua")), _sn(b.get("leggibili"))))
                ok_gui = ok_gui and g.get("esito")
            v["misurato"] += "; " + "; ".join(parti)
            if v["esito"] == PASS and not ok_gui:
                v["esito"] = FAIL
    # E1: tutti i test A e B in Docker con Python 3.4
    if dock is None:
        ris["E1"] = _voce("E1", NV, "contenitore Docker con Python 3.4 non disponibile")
    else:
        r = dock["risultati"]
        ab = [k for k in K.TEST if k[0] in "AB"]
        falliti = [k for k in ab if r.get(k, {}).get("esito") == FAIL]
        passati = [k for k in ab if r.get(k, {}).get("esito") == PASS]
        esclusi = []
        for k in ab:
            if k not in r:
                esclusi.append("%s (non eseguito: %s)" % (k, "solo con --lungo" if k == "B8" else "?"))
            elif r[k]["esito"] == NV:
                esclusi.append("%s (%s)" % (k, r[k]["misurato"][:100]))
        mancanti = [k for k in ab if k not in r and k != "B8"]
        esito = PASS if not falliti and not mancanti else FAIL
        ris["E1"] = _voce("E1", esito, "Python %s + numpy %s + scipy %s: %d PASS, %d FAIL%s; esclusi: %s"
                          % (dock["python"], dock["numpy"], dock["scipy"], len(passati), len(falliti),
                             (" (" + ", ".join(falliti) + ")") if falliti else "",
                             "; ".join(esclusi) or "nessuno"),
                          ambiente="Docker python:3.4", dettagli={"falliti": falliti, "esclusi": esclusi,
                                                                  "risultati": {k: r[k]["esito"] for k in r}})
        ris["E1"]["risultati_docker"] = r
    # E3 / E5 / E4 con la finestra.  Impostazioni predefinite: 5 Hz (fase 3, D3)
    HZ = 5.0
    g_e3 = sorted([(k, g) for k, g in gui.items() if k.startswith("e3_") and
                   (g.get("aggiornamento_hz") or 10.0) == HZ])
    g_e3_altri = sorted([(k, g) for k, g in gui.items() if k.startswith("e3_") and
                         (g.get("aggiornamento_hz") or 10.0) != HZ])
    if not g_e3:
        ris["E3"] = _voce("E3", NV, "display virtuale (Xvfb in Docker) non disponibile")
        ris["E5"] = _voce("E5", NV, "display virtuale non disponibile: ritardo non misurabile")
    else:
        parti = []
        ok = True
        for k, g in g_e3 + g_e3_altri:
            m = g.get("misure", {})
            parti.append("Python %s, grafico a %g Hz: codice %s, eccezioni nel log %d, nei callback %d, dialoghi "
                         "d'errore %d, finestra %s su schermo %s, controlli fuori %s, registrazione %.1f s, marker e "
                         "cambio filtro nel JSON: %s" % (
                             g["python"], g.get("aggiornamento_hz") or 10, g["codice"], len(g["righe_errore_log"]),
                             len(g["eccezioni_tk"]),
                             len([d for d in g["dialoghi"] if d[0] in ("showerror", "showwarning")]),
                             m.get("geometria"), m.get("schermo"), m.get("fuori_finestra"),
                             (g.get("json") or {}).get("durata_s") or 0, _sn(g.get("esito"))))
            ok = ok and g.get("esito")
        ris["E3"] = _voce("E3", PASS if ok else FAIL, "; ".join(parti), ambiente="Xvfb 1280×1024",
                          dettagli={k: {"righe_errore_log": g["righe_errore_log"],
                                        "eccezioni_tk": g["eccezioni_tk"]} for k, g in g_e3 + g_e3_altri})
        rit = [(g["python"], g.get("ritardo")) for k, g in g_e3 if g.get("ritardo")]
        if rit:
            peggiore = max(r["max_s"] for p, r in rit)
            ris["E5"] = _voce("E5", PASS if peggiore < 0.5 else FAIL, "; ".join(
                "Python %s: mediana %.0f ms, 95° percentile %.0f ms, massimo %.0f ms (%d disegni)"
                % (p, r["mediana_s"] * 1000, r["p95_s"] * 1000, r["max_s"] * 1000, r["n"]) for p, r in rit) +
                " (grafico a %g Hz, predefinito)" % HZ,
                nota="punto di misura esterno: istante del disegno meno istante in cui la sorgente "
                     "simulata ha prodotto l'ultimo campione disegnato", ambiente="Xvfb")
        else:
            ris["E5"] = _voce("E5", NV, "nessun disegno misurato")
    # E4: soglia sul programma intero con la finestra, impostazioni predefinite (5 Hz),
    # Python di sviluppo; Python 3.4 e 10 Hz informativi (fase 3, D3)
    righe = []
    giudizio = None
    for k, g in g_e3:
        if g.get("cpu_%") is not None and not g["python"].startswith("3.4"):
            giudizio = g["cpu_%"]
            righe.append("**con la finestra, grafico a %g Hz (predefinito), Python %s: %.2f %%**"
                         % (HZ, g["python"], g["cpu_%"]))
    for k, g in g_e3 + g_e3_altri:
        if g.get("cpu_%") is None or (not g["python"].startswith("3.4") and (g.get("aggiornamento_hz") or 10) == HZ):
            continue
        righe.append("informativo: con la finestra, grafico a %g Hz, Python %s: %.2f %%"
                     % (g.get("aggiornamento_hz") or 10, g["python"], g["cpu_%"]))
    if "E4" in ris:
        righe.append("informativo: calcolo senza finestra, Python %s: %.2f %%" % (
            host.get("python"), ris["E4"]["dettagli"]["quota_%"]))
    if dock and "E4" in dock["risultati"]:
        righe.append("informativo: calcolo senza finestra, Python %s: %.2f %%" % (
            dock["python"], dock["risultati"]["E4"]["dettagli"]["quota_%"]))
    if giudizio is not None:
        ris["E4"] = _voce("E4", PASS if giudizio < 5.0 else FAIL, "; ".join(righe),
                          nota="fase 3 (D3): grafico a 5 Hz predefinito; esito sul programma intero con la "
                               "finestra, Python di sviluppo; gli altri valori sono informativi",
                          ambiente="PC di sviluppo (Xvfb in Docker)")
    elif "E4" in ris:
        ris["E4"]["esito"] = NV
        ris["E4"]["misurato"] = "solo senza finestra: " + ris["E4"]["misurato"]
    # E6: PC lento
    g_e6 = [g for k, g in gui.items() if k.startswith("e6_")]
    if not g_e6:
        ris["E6"] = _voce("E6", NV, "Docker con --cpus=0.2 non disponibile")
    else:
        g = g_e6[0]
        c = g.get("conformita") or {}
        r = g.get("ritardo") or {}
        b3 = c.get("B3") or {}
        ris["E6"] = _voce("E6", PASS if g.get("esito") else FAIL,
                          "Python %s, CPU limitata a 0,2 (--cpus=0.2), grafico a %g Hz: registrazione %.1f s; persi %s; "
                          "arretrato massimo dell'elaborazione %.2f s, coda massima %.2f s (limite %g s); ritardo del "
                          "grafico massimo %.0f ms (mediana %.0f ms); eccezioni %d; B1 %s campioni diversi; B2 differenza "
                          "massima %s conteggi; B3 persi %s; CPU del processo %.1f %% di un core" % (
                              g["python"], g.get("aggiornamento_hz") or 10, b3.get("durata_s") or 0,
                              g["misure"].get("persi"), g.get("arretrato_max_s") or 0, g.get("coda_max_s") or 0,
                              g.get("limite_coda_s") or 600, 1000 * (r.get("max_s") or 0),
                              1000 * (r.get("mediana_s") or 0),
                              len(g["righe_errore_log"]) + len(g["eccezioni_tk"]), c.get("B1_diversi"),
                              c.get("B2_diff_max_conteggi"), b3.get("persi"), g.get("cpu_%") or 0),
                          nota="la quota di CPU di Docker rallenta a scatti (periodi di 100 ms) e non riproduce "
                               "una CPU vecchia (cache, disco, Windows XP); il limite della coda (600 s) è una "
                               "costante del test: il programma non ne ha uno (D8)", ambiente="Docker --cpus=0.2, Xvfb")
    # E7: modalita' Digidata con la DLL finta
    g_e7 = sorted([(k, g) for k, g in gui.items() if k.startswith("e7_")])
    if not g_e7:
        ris["E7"] = _voce("E7", NV, "display virtuale (Xvfb in Docker) non disponibile")
    else:
        parti = []
        for k, g in g_e7:
            c = g.get("conformita") or {}
            err = "; ".join("%s: %s" % (e["caso"], "OK" if e["ok"] else "NO") for e in g.get("errori_valutati", []))
            parti.append("Python %s: %s; errori → %s; overrun mostrato %s; registrazione B1 %s diversi, B2 %s "
                         "conteggi, B3 persi %s; aggiornamento del grafico cambiato dal vivo %s; schede rimaste "
                         "aperte %s; traceback inattesi %d" % (
                             g["python"], "PASS" if g.get("esito") else "FAIL", err, _sn(g.get("overrun_ok")),
                             c.get("B1_diversi"), c.get("B2_diff_max_conteggi"), (c.get("B3") or {}).get("persi"),
                             ", ".join("%g Hz → %.1f disegni/s" % (a["hz"], a["disegni_al_s"])
                                       for a in g.get("aggiornamento_dal_vivo", [])),
                             g["misure"].get("schede_aperte_alla_fine"), len(g.get("traceback_inattesi", []))))
        ris["E7"] = _voce("E7", PASS if all(g.get("esito") for k, g in g_e7) else FAIL, " | ".join(parti),
                          ambiente="Xvfb, DLL finta rigorosa",
                          dettagli={k: {"errori": g.get("errori_valutati"), "conformita": g.get("conformita")}
                                    for k, g in g_e7})
    # D1 non automatico
    # Mutazioni
    if mut is None:
        for m in ("M1", "M2", "M3", "M4"):
            ris[m] = _voce(m, NV, "prova delle mutazioni non eseguita")
    else:
        for m, v in mut["mutazioni"].items():
            if v.get("errore"):
                ris[m] = _voce(m, FAIL, "errore: %s" % v["errore"])
            else:
                ris[m] = _voce(m, PASS if v["rilevato"] else FAIL,
                               ("rilevato da: " + "; ".join(v["test_critici_falliti"])) if v["rilevato"]
                               else "NON rilevato da nessun test critico (falliti: %s)" % (v["test_falliti"] or "nessuno"))
    for id_ in K.TEST:
        if id_ not in ris:
            ris[id_] = _voce(id_, NV, "test non eseguito")
    return ris, {"host": host, "docker": dock, "gui": gui, "mut": mut}


def _sn(v):
    return "sì" if v else "NO"


SENZA_DATI = "non eseguibile senza i dati del laboratorio"


def senza_dati(v):
    """Voce non verificabile solo perche' mancano i dati del laboratorio (i test C
    usano tutti i file .wcp reali; gli altri lo scrivono nel valore misurato)."""
    return v["esito"] == NV and (v["id"].startswith("C") or
                                 SENZA_DATI in "%s %s" % (v.get("misurato", ""), v.get("nota", "")))


def verdetto(ris, riproducibile=False):
    """Verdetto e motivi.  Con riproducibile=True (repository senza i dati del
    laboratorio) e nessun FAIL, se i test critici non verificati lo sono solo
    per i dati mancanti il verdetto e' "PARZIALE: 0 FAIL, N test non eseguibili
    senza i dati del laboratorio" invece di "NON PRONTO"."""
    crit = [v for v in ris.values() if v["livello"] == K.CRITICO]
    crit_fail = [v["id"] for v in crit if v["esito"] == FAIL]
    crit_nv = [v["id"] for v in crit if v["esito"] == NV]
    imp_fail = [v["id"] for v in ris.values() if v["livello"] == K.IMPORTANTE and v["esito"] == FAIL]
    imp_nv = [v["id"] for v in ris.values() if v["livello"] == K.IMPORTANTE and v["esito"] == NV]
    mut_no = [m for m in ("M1", "M2", "M3", "M4") if ris[m]["esito"] != PASS]
    tutti_fail = [x["id"] for x in ris.values() if x["esito"] == FAIL]
    senza = sorted(x["id"] for x in ris.values() if senza_dati(x))
    if (riproducibile and not tutti_fail and not mut_no and crit_nv
            and all(senza_dati(ris[i]) for i in crit_nv)):
        v = "PARZIALE: 0 FAIL, %d test non eseguibili senza i dati del laboratorio" % len(senza)
    elif crit_fail or crit_nv or mut_no:
        v = "NON PRONTO"
    elif imp_fail:
        v = "PRONTO CON RISERVE"
    else:
        v = "PRONTO PER LA PROVA IN LABORATORIO"
    return v, {"critici_fail": crit_fail, "critici_nv": crit_nv, "importanti_fail": imp_fail,
               "importanti_nv": imp_nv, "mutazioni_non_rilevate": mut_no, "senza_dati": senza}


# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------
def figure(uscita):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import comuni as C
    if not os.path.isdir(FIGURE):
        os.makedirs(FIGURE)
    out = []
    plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.3})
    # 1) segnale sintetico
    s = C.sintetico()
    y = C.filtra_programma(s.rumoroso, C.parametri())
    t = s.t
    rum = C.conteggi_in_mv(s.rumoroso)
    fig, ax = plt.subplots(2, 1, figsize=(10, 6.2))
    ax[0].plot(t[::5], np.clip(rum[::5], -250, 350), color="#bbbbbb", lw=0.4, label="con rumore e picchi (tagliato a −250/+350 mV)")
    ax[0].plot(t, s.verita, color="#1f77b4", lw=1.2, label="verità")
    ax[0].plot(t, y, color="#d62728", lw=0.9, label="filtrato dal programma")
    ax[0].set_xlim(0, t[-1])
    ax[0].set_ylim(-250, 350)
    ax[0].set_ylabel("mV")
    ax[0].set_xlabel("tempo (s)")
    ax[0].set_title("Segnale sintetico a verità nota: 10 minuti")
    ax[0].legend(loc="upper right", fontsize=8)
    g = s.gradini[len(s.gradini) // 2]
    a, b = g - 3000, g + 5000
    ax[1].plot(t[a:b], rum[a:b], color="#bbbbbb", lw=0.5, label="con rumore")
    ax[1].plot(t[a:b], s.verita[a:b], color="#1f77b4", lw=1.5, label="verità")
    ax[1].plot(t[a:b], y[a:b], color="#d62728", lw=1.2, label="filtrato")
    lo, hi = min(s.verita[a:b]), max(s.verita[a:b])
    ax[1].set_ylim(lo - 0.6 * (hi - lo) - 20, hi + 0.6 * (hi - lo) + 20)
    ax[1].set_title("Zoom su un gradino (t = %.1f s): il filtrato segue il gradino con ~65 ms di ritardo" % (g / C.FS))
    ax[1].set_xlabel("tempo (s)")
    ax[1].set_ylabel("mV")
    ax[1].legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    p = os.path.join(FIGURE, "sintetico.png")
    fig.savefig(p, dpi=110)
    plt.close(fig)
    out.append(("sintetico.png", "Verità, segnale con rumore e filtrato (sintetico), con zoom su un gradino."))
    # 2) risposta in frequenza misurata sul programma
    freq = np.unique(np.concatenate((np.logspace(-1, np.log10(450), 70), [5.0, 8.7, 25.0, 37.4, 50.0])))
    misurata = []
    for f in freq:
        dur = max(20.0, 40.0 / f)
        tt = np.arange(int(dur * C.FS)) / C.FS
        # toni da 100 mV non arrotondati a 16 bit: l'arrotondamento limiterebbe
        # la misura a ~-90 dB; con toni da 1 V sopra ~80 Hz il salto tra due
        # campioni supera i 500 mV e interverrebbe il rilevatore dei picchi
        c = 100.0 * np.sin(2 * np.pi * f * tt) / C.MV_PER_CONTEGGIO
        yy = C.filtra_programma(c, C.parametri())
        i = len(tt) // 2
        per = C.FS / f
        n = int(int((len(tt) - i) / per) * per) or (len(tt) - i)
        a_in = C.ampiezza_sinusoide(c[i:i + n] * C.MV_PER_CONTEGGIO, f)
        a_out = C.ampiezza_sinusoide(yy[i:i + n], f)
        misurata.append(20 * np.log10(max(a_out, 1e-9) / a_in))
    misurata = np.maximum(np.array(misurata), -160)
    fig, ax = plt.subplots(figsize=(10, 4.6))
    try:
        from scipy import signal
        ff = np.logspace(-1, np.log10(499), 2000)
        w, h = signal.sosfreqz(C.sos_riferimento(), worN=ff * 2 * np.pi / C.FS)
        ax.semilogx(ff, np.maximum(20 * np.log10(np.abs(h) + 1e-12), -160), color="#1f77b4", lw=1.2,
                    label="atteso (scipy: notch 50 Hz + Bessel 4° ordine 5 Hz)")
    except ImportError:
        pass
    ax.semilogx(freq, misurata, "o", ms=3.5, color="#d62728", label="misurato sul programma (toni da 100 mV)")
    for f, nome in ((8.7, "8,7 Hz"), (25.0, "25 Hz"), (37.4, "37,4 Hz"), (50.0, "50 Hz")):
        ax.axvline(f, color="#ff7f0e", lw=1, alpha=0.7)
        ax.text(f * 1.03, -150, nome, color="#b35900", fontsize=8, rotation=90, va="bottom")
    ax.axvspan(25, 50, color="#ff7f0e", alpha=0.08, label="banda di rumore 25–50 Hz")
    ax.axvline(5.0, color="#2ca02c", lw=1, ls="--", label="taglio 5 Hz")
    ax.set_ylim(-165, 5)
    ax.set_xlim(0.1, 499)
    ax.set_xlabel("frequenza (Hz)")
    ax.set_ylabel("guadagno (dB)")
    ax.set_title("Risposta in frequenza del filtro predefinito (a 1000 Hz)")
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGURE, "risposta_frequenza.png"), dpi=110)
    plt.close(fig)
    out.append(("risposta_frequenza.png", "Risposta in frequenza misurata sul programma e attesa da scipy, "
                                          "con le frequenze di rumore evidenziate (valori sotto −160 dB "
                                          "disegnati a −160)."))
    # 3) dati reali (C5)
    for p in sorted(glob.glob(os.path.join(uscita, "dati_figure", "C5_*.npz"))):
        d = np.load(p)
        nome = str(d["nome"])
        lag = int(d["lag"])
        fs8 = float(d["fs"]) / 8.0
        filt = d["filt"]
        tf = np.arange(len(filt)) / fs8
        tr = np.arange(len(d["raw_min"])) / fs8
        rif = d["rif"]
        trf = np.arange(len(rif)) / fs8 + lag / float(d["fs"])
        fig, ax = plt.subplots(3, 1, figsize=(10, 8.4), gridspec_kw={"height_ratios": [1.2, 1, 1]})
        ax[0].fill_between(tr, d["raw_min"], d["raw_max"], color="#bbbbbb", lw=0, label="grezzo (min–max)")
        ax[0].plot(trf, rif, color="#1f77b4", lw=0.8, label="riferimento a fase zero (spostato del ritardo)")
        ax[0].plot(tf, filt, color="#d62728", lw=0.7, label="filtrato dal programma")
        lo = np.percentile(filt, 0.5)
        hi = np.percentile(filt, 99.5)
        marg = max(20.0, 0.3 * (hi - lo))
        ax[0].set_ylim(lo - marg, hi + marg)
        ax[0].set_title("%s — intero (asse Y sul filtrato; il grezzo può uscire dal grafico)" % nome)
        ax[0].set_ylabel("mV")
        ax[0].legend(loc="upper right", fontsize=7)
        # zoom: 20 s attorno alla massima variazione del filtrato
        dv = np.abs(np.diff(filt))
        c = int(np.argmax(dv)) if len(dv) else 0
        a = max(0, c - int(8 * fs8))
        b = min(len(filt), a + int(20 * fs8))
        m = slice(a, b)
        ax[1].fill_between(tr[m], d["raw_min"][m], d["raw_max"][m], color="#bbbbbb", lw=0)
        ax[1].plot(trf[m], rif[m], color="#1f77b4", lw=1.0)
        ax[1].plot(tf[m], filt[m], color="#d62728", lw=1.0)
        lo, hi = min(filt[m].min(), rif[m].min()), max(filt[m].max(), rif[m].max())
        ax[1].set_ylim(lo - 0.3 * (hi - lo) - 10, hi + 0.3 * (hi - lo) + 10)
        ax[1].set_title("zoom di 20 s attorno alla variazione più rapida")
        ax[1].set_ylabel("mV")
        ax[1].set_xlabel("tempo (s)")
        ax[2].semilogy(d["fw"], d["pw"], color="#888888", lw=0.8, label="grezzo (1000 Hz, senza picchi)")
        ax[2].semilogy(d["ff"], d["pf"], color="#d62728", lw=0.8, label="filtrato salvato (125 Hz)")
        ax[2].axvspan(25, 60, color="#ff7f0e", alpha=0.1, label="banda 25–60 Hz (C2)")
        ax[2].set_xlim(0, 100)
        ax[2].set_xlabel("frequenza (Hz)")
        ax[2].set_ylabel("mV²/Hz")
        ax[2].set_title("spettro prima e dopo")
        ax[2].legend(loc="upper right", fontsize=7)
        fig.tight_layout()
        nf = "reale_%s.png" % os.path.basename(p)[3:5]
        fig.savefig(os.path.join(FIGURE, nf), dpi=100)
        plt.close(fig)
        out.append((nf, "C5 — %s: grezzo, filtrato e riferimento; spettro prima e dopo." % nome))
    return out


# ---------------------------------------------------------------------------
# Testo
# ---------------------------------------------------------------------------
DOMANDE = [
    ("Il filtro toglie il rumore?", ["A7", "C2"], "Sì", "No"),
    ("Deforma il segnale utile?", ["A2", "A3", "A4", "C3", "C3b"], "No", "Sì"),
    ("Perde o altera dati?", ["B1", "B2", "B3"], "No", "Sì"),
    ("I file si aprono in altri programmi?", ["B6"], "Sì", "No"),
    ("Regge registrazioni lunghe e crash?", ["B7", "B8"], "Sì", "No"),
    ("Funziona con la scheda (finta) e su un PC lento?", ["E7", "E6"], "Sì", "No"),
]

NON_VERIFICATO = [
    "**la scheda Digidata 1322A vera** (driver AxDD132x.dll, WinASPI, SCSI, temporizzazione e overrun reali): "
    "si vede solo con `diagnostica.bat` in laboratorio;",
    "**Windows XP** e il PC del laboratorio (Python 3.4 a 32 bit, tkinter, numpy su quella CPU, schermo, disco): "
    "qui si è usato Python 3.4 a 64 bit su Linux in Docker;",
    "**WinWCP 5.1.6**: l'apertura dei file nel programma vero (qui: stesse chiavi di un file scritto da "
    "WinWCP 5.1.6, lettura con neo e con il lettore di riferimento);",
    "**la velocità reale del PC del laboratorio**: E6 la simula limitando la CPU a 0,2 core in Docker, "
    "che non riproduce una CPU di 15 anni fa (cache, disco, Windows XP);",
    "**se gli impulsi oltre 500 mV (~5 V, decine di ms) sono artefatti**: il programma li tratta come "
    "tali e ritarda di 50 ms quelli lunghi (scelta voluta, README § 6.1); se il laboratorio dice che "
    "sono eventi veri si abbassa `durata_max_picco_ms`;",
    "**il giudizio scientifico sul taglio**: quale frequenza di taglio (1, 2, 5, 10 Hz) sia giusta per i "
    "segnali del laboratorio lo decide il laboratorio, non questi test.",
]


class Doc(object):
    def __init__(self):
        self.b = []

    def __getattr__(self, tipo):
        def f(*a):
            self.b.append((tipo,) + a)
        return f


def _md(doc):
    r = []
    for blk in doc.b:
        t = blk[0]
        if t == "h1":
            r.append("# %s\n" % blk[1])
        elif t == "h2":
            r.append("\n## %s\n" % blk[1])
        elif t == "h3":
            r.append("\n### %s\n" % blk[1])
        elif t == "p":
            r.append("%s\n" % blk[1])
        elif t == "verdetto":
            r.append("\n> # VERDETTO: %s\n>\n> %s\n" % (blk[1], blk[2].replace("\n", "\n> ")))
        elif t == "ul":
            r.append("\n".join("* %s" % x for x in blk[1]) + "\n")
        elif t == "tab":
            intest, righe = blk[1], blk[2]
            r.append("| " + " | ".join(intest) + " |")
            r.append("|" + "|".join("---" for _ in intest) + "|")
            for riga in righe:
                r.append("| " + " | ".join(_cella_md(c) for c in riga) + " |")
            r.append("")
        elif t == "img":
            r.append("![%s](%s/%s)\n\n*%s*\n" % (blk[2], SOTTO_FIGURE["n"], blk[1], blk[2]))
        elif t == "pre":
            r.append("```\n%s\n```\n" % blk[1])
        elif t == "salto":
            r.append("\n---\n")
    return "\n".join(r)


def _cella_md(c):
    return ("%s" % c).replace("|", "\\|").replace("\n", " ")


COLORI = {PASS: "#1b7f3b", FAIL: "#c62828", NV: "#8a6d00"}


def _inline(s):
    """Markdown minimo in HTML: **grassetto**, `codice`."""
    import re
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def _html(doc, titolo):
    r = []
    for blk in doc.b:
        t = blk[0]
        if t in ("h1", "h2", "h3"):
            r.append("<%s>%s</%s>" % (t, _inline(blk[1]), t))
        elif t == "p":
            r.append("<p>%s</p>" % _inline(blk[1]))
        elif t == "verdetto":
            col = {"NON PRONTO": "#c62828", "PRONTO CON RISERVE": "#b26a00"}.get(
                blk[1], "#b26a00" if blk[1].startswith("PARZIALE") else "#1b7f3b")
            r.append('<div class="verdetto" style="border-color:%s"><div class="vt" style="color:%s">%s</div>'
                     '<p>%s</p></div>' % (col, col, html.escape(blk[1]), _inline(blk[2]).replace("\n", "<br>")))
        elif t == "ul":
            r.append("<ul>%s</ul>" % "".join("<li>%s</li>" % _inline(x) for x in blk[1]))
        elif t == "tab":
            intest, righe = blk[1], blk[2]
            h = ["<div class='tw'><table><thead><tr>%s</tr></thead><tbody>" %
                 "".join("<th>%s</th>" % html.escape(x) for x in intest)]
            for riga in righe:
                celle = []
                for c in riga:
                    c = "%s" % c
                    stile = ""
                    for k, col in COLORI.items():
                        if c == k or c.startswith(k + " "):
                            stile = " style='color:#fff;background:%s;font-weight:600;white-space:nowrap'" % col
                    if c in ("Sì", "No") and len(riga) <= 3:
                        stile = " style='font-weight:700;font-size:1.15em'"
                    celle.append("<td%s>%s</td>" % (stile, _inline(c)))
                h.append("<tr>%s</tr>" % "".join(celle))
            h.append("</tbody></table></div>")
            r.append("".join(h))
        elif t == "img":
            r.append("<figure><img src='%s/%s' alt='%s'><figcaption>%s</figcaption></figure>"
                     % (SOTTO_FIGURE["n"], blk[1], html.escape(blk[2]), _inline(blk[2])))
        elif t == "pre":
            r.append("<pre>%s</pre>" % html.escape(blk[1]))
        elif t == "salto":
            r.append("<hr class='salto'>")
    css = """
:root{--fg:#1a1a1a;--bg:#ffffff;--mut:#555;--bd:#d0d0d0;--alt:#f5f5f5}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--fg:#e8e8e8;--bg:#16181c;--mut:#aaa;--bd:#3a3d44;--alt:#1f2228}}
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:1100px;margin:0 auto;padding:16px;
color:var(--fg);background:var(--bg);line-height:1.45}
h1{font-size:1.7em}h2{margin-top:1.6em;border-bottom:2px solid var(--bd);padding-bottom:4px}
.verdetto{border:4px solid;border-radius:10px;padding:14px 20px;margin:16px 0}
.verdetto .vt{font-size:2.3em;font-weight:800;letter-spacing:.02em}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;margin:10px 0;font-size:.9em}
th,td{border:1px solid var(--bd);padding:5px 7px;vertical-align:top;text-align:left}
th{background:var(--alt)}tr:nth-child(even) td{background:var(--alt)}
figure{margin:18px 0}img{max-width:100%;height:auto;border:1px solid var(--bd);background:#fff}
figcaption{color:var(--mut);font-size:.9em}code{background:var(--alt);padding:0 3px;border-radius:3px}
pre{background:var(--alt);padding:10px;overflow-x:auto;font-size:.85em}
hr.salto{border:0;border-top:3px double var(--bd);margin:30px 0}
@media print{hr.salto{page-break-after:always;border:0}}
"""
    return ("<!doctype html><html lang='it'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'><title>%s</title>"
            "<style>%s</style></head><body>%s</body></html>" % (html.escape(titolo), css, "\n".join(r)))


def _esito_domanda(ris, ids, si, no):
    crit = [ris[i]["esito"] for i in ids if ris[i]["livello"] == K.CRITICO]
    altri = [i for i in ids if ris[i]["livello"] != K.CRITICO and ris[i]["esito"] != PASS]
    if FAIL in crit:
        return no
    if NV in crit:
        return "Non del tutto verificato"
    if altri:
        return "%s, con una riserva (%s)" % (si, ", ".join(altri))
    return si


def _it(v, cifre=2):
    s = ("%." + str(cifre) + "f") % v
    return s.replace(".", ",")


def numero_breve(id_, v):
    """Il numero chiave di un test, in una riga, per la pagina 1."""
    d = v.get("dettagli") or {}
    try:
        if id_ == "A7":
            return "rumore residuo %s mV RMS (soglia 2), partendo da %s mV" % (
                _it(d["rms_mv"]), _it(d["rms_ingresso_mv"], 1))
        if id_ == "C2":
            casi = [c for c in d["casi"] if c["rms_25_60_grezzo_mv"] >= 0.1]
            return "rumore 25–60 Hz ridotto di almeno %s dB sui file reali (soglia 30)" % _it(
                min(c["riduzione_float_db"] for c in casi), 1)
        if id_ == "A2":
            return "dopo un gradino errore massimo %s mV (soglia 0,5)" % _it(d["errore_max_mv"])
        if id_ == "A3":
            return "sovraelongazione massima %s %% (soglia 5)" % _it(max(
                x for k, x in d.items() if k.startswith("sovra")))
        if id_ == "A4":
            return "ritardo %s ms a 5 Hz (soglia 300)" % _it(d["ritardo_ms_5_Hz"], 0)
        if id_ == "C3":
            casi = d["casi"]
            fuori = [c for c in casi if not (c["frazione_esclusa"] < 0.02 and c["rms_mv"] < 5.0 and
                                             (not c["correlazione_applicabile"] or c["correlazione"] >= 0.99))]
            peggiore = max(casi, key=lambda c: c["frazione_esclusa"])
            if not fuori:
                return ("uguale al riferimento ideale su tutti i %d casi, RMS al massimo %s mV (soglia 5); "
                        "tempo escluso al massimo %s %% (limite 2 %%)" % (
                            len(casi), _it(max(c["rms_mv"] for c in casi)), _it(100 * peggiore["frazione_esclusa"])))
            return "entro le soglie su %d casi su %d; fuori: %s" % (len(casi) - len(fuori), len(casi), "; ".join(
                "%s (esclusi %s %% del tempo, limite 2 %%; RMS %s mV)" % (
                    c["nome"], _it(100 * c["frazione_esclusa"]), _it(c["rms_mv"])) for c in fuori))
        if id_ == "C3b":
            casi = d.get("casi") or []
            fin = [f for c in casi for f in c.get("finestre", []) if not f.get("ambigua")]
            if not fin:
                return v["misurato"]
            m = max(f["rms"] for f in fin)
            return ("attorno ai salti il programma fa esattamente quello che dice il README: al massimo %s mV RMS "
                    "su %d finestre (soglia 2), 100 %% del tempo escluso controllato" % (_it(m), len(fin))) \
                if m < 2 else "attorno ai salti fino a %s mV RMS (soglia 2)" % _it(m, 1)
        if id_ == "E7":
            parti = []
            for k, x in sorted(d.items()):
                c = x.get("conformita") or {}
                err = x.get("errori") or []
                parti.append("%s: registrazione %s, errori mostrati in chiaro %d su %d, riavvio dopo gli errori %s" % (
                    "Python 3.4" if "3.4" in k else "Python di sviluppo",
                    "conforme" if c.get("B1_diversi") == 0 and c.get("B2_diff_max_conteggi") is not None and
                    c["B2_diff_max_conteggi"] <= 1 else "NON conforme",
                    sum(1 for e in err if e["ok"] and e["caso"] != "riprova dopo gli errori"),
                    sum(1 for e in err if e["caso"] != "riprova dopo gli errori"),
                    "sì" if any(e["ok"] and e["caso"] == "riprova dopo gli errori" for e in err) else "NO"))
            return "; ".join(parti)
        if id_ == "E6":
            return v["misurato"].split("; eccezioni")[0]
        if id_ == "B1":
            return "%d campioni diversi su %d" % (d["diversi"], d["campioni"])
        if id_ == "B2":
            return "differenza massima %d conteggi ADC (soglia 1)" % d["diff_max_conteggi"]
        if id_ == "B3":
            return "%d campioni persi" % d["persi"]
        if id_ == "B6":
            return "neo e lettore di riferimento differiscono di %s mV; intestazione come WinWCP 5.1.6" % (
                ("%.4f" % d["neo_diff_max_mv"]).replace(".", ","))
        if id_ == "B7":
            return "dopo un kill -9 persi %s s (soglia 2); file leggibili" % _it(d["persi_s"])
        if id_ == "B8":
            return "3 ore: memoria +%s MB (soglia 50), 0 campioni persi" % _it(d["crescita_mb"], 1)
    except (KeyError, ValueError, TypeError):
        pass
    return _breve(v, 160)


def _numero_domanda(ris, ids):
    return " · ".join("**%s** %s: %s" % (i, ris[i]["esito"], numero_breve(i, ris[i])) for i in ids)


def _breve(v, n=260):
    s = v["misurato"]
    return s if len(s) <= n else s[:n - 1] + "…"


def componi(ris, extra, verd, motivi, nome, figure_elenco, iniziali, analisi):
    d = Doc()
    host = extra["host"]
    ora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    titolo = "Rapporto di validazione — denoising_live" if nome != "rapporto_iniziale" else \
        "Rapporto di validazione INIZIALE (fase 1, codice non modificato) — denoising_live"
    d.h1(titolo)
    if nome == "rapporto_riproducibile":
        d.p(NOTA_RIPRODUCIBILE)
    d.p("Generato il %s da `./valida.sh` · Python di sviluppo %s, numpy %s, scipy %s · commit del programma: %s"
        % (ora, host.get("python", "?"), host.get("numpy", "?"), host.get("scipy", "?"), _commit()))
    spieg = {
        "NON PRONTO": "Almeno un test critico non è superato%s. Il programma non va usato in laboratorio "
                      "finché non è corretto.",
        "PRONTO CON RISERVE": "Tutti i test critici sono superati, ma almeno un test importante no%s: "
                              "si può fare la prova in laboratorio tenendo presenti le riserve elencate.",
        "PRONTO PER LA PROVA IN LABORATORIO": "Tutti i test critici sono superati e le mutazioni M1–M4 "
                                              "sono state rilevate%s.",
    }.get(verd, "Nessun test è fallito e le mutazioni M1–M4 sono state rilevate; i test che usano i dati "
                "del laboratorio (non pubblicati) non sono stati eseguiti: " + ", ".join(motivi["senza_dati"]) +
                "%s. Il verdetto completo è quello del rapporto ufficiale, ottenuto con i dati reali: "
                "`docs/validazione/rapporto_validazione.md`.")
    if verd.startswith("PARZIALE"):
        motivi = dict(motivi, critici_nv=[])        # gia' spiegati nel testo qui sopra
    dett = []
    if motivi["critici_fail"]:
        dett.append("critici falliti: " + ", ".join(motivi["critici_fail"]))
    if motivi["critici_nv"]:
        dett.append("critici non verificabili: " + ", ".join(motivi["critici_nv"]))
    if motivi["mutazioni_non_rilevate"]:
        dett.append("guasti finti non rilevati: " + ", ".join(motivi["mutazioni_non_rilevate"]))
    if motivi["importanti_fail"]:
        dett.append("importanti falliti: " + ", ".join(motivi["importanti_fail"]))
    testo = spieg % ((" (" + "; ".join(dett) + ")") if dett else "")
    testo += ("\nIl verdetto riguarda **solo il software in simulazione**. Il funzionamento con il Digidata vero "
              "si vede solo con la diagnostica in laboratorio (`diagnostica.bat`), e quale frequenza di taglio "
              "sia scientificamente giusta lo decide il laboratorio, non i test.")
    d.verdetto(verd, testo)
    d.h2("Cinque domande")
    righe = []
    for dom, ids, si, no in DOMANDE:
        righe.append([dom, _esito_domanda(ris, ids, si, no), _numero_domanda(ris, ids)])
    d.tab(["Domanda", "Risposta", "Il numero che la motiva"], righe)
    d.h2("Cosa NON è stato verificato")
    d.ul(NON_VERIFICATO + (["la prova di 3 ore (B8): eseguire `./valida.sh --lungo`"]
                           if ris["B8"]["esito"] == NV else []))
    conteggio = {}
    for v in ris.values():
        conteggio[v["esito"]] = conteggio.get(v["esito"], 0) + 1
    d.p("In tutto %d voci: %d PASS, %d FAIL, %d NON VERIFICABILE." % (
        len(ris), conteggio.get(PASS, 0), conteggio.get(FAIL, 0), conteggio.get(NV, 0)))
    d.salto()
    if analisi:
        for riga in analisi:
            d.b.append(riga)
    d.h2("Tabella completa")
    d.p("**Critico** = decide il verdetto. Valori misurati sul PC di sviluppo salvo dove indicato "
        "(E1: Python 3.4 in Docker; E3/E5: finestra sotto Xvfb).")
    for g, titolo_g in K.GRUPPI.items():
        d.h3("%s. %s" % (g, titolo_g))
        righe = []
        for id_ in K.TEST:
            if id_[0] != g:
                continue
            v = ris[id_]
            righe.append([id_, v["cosa"], _breve(v, 600), v["soglia"], v["esito"],
                          "sì" if v["livello"] == K.CRITICO else ("no (%s)" % v["livello"])])
        d.tab(["ID", "Cosa controlla", "Valore misurato", "Soglia", "Esito", "Critico"], righe)
    note = [(id_, ris[id_]["nota"]) for id_ in K.TEST if ris[id_].get("nota")]
    if note:
        d.h3("Note ai test")
        d.ul(["**%s** — %s" % (i, n) for i, n in note])
    if iniziali is not None:
        d.h2("Prima e dopo: fase 4 → fase 5")
        d.p("Fase 4 = `rapporto_fase4` (archiviato); fase 5 = questo rapporto. Sono riportate le voci con "
            "esito cambiato e, per mostrare che la logica del filtro non è cambiata, A8, B2, C3, C3b, C4. "
            "Le correzioni della fase 5 (protocollo, RTIMESECS, LPF-8, impostazioni di WinWCP, rilevamento) "
            "sono provate dai test di `tests/test_fase5.py`, elencati nella sezione «Cosa è stato ricavato "
            "dai sorgenti».")
        righe = []
        for id_ in K.TEST:
            a = iniziali.get(id_)
            b = ris[id_]
            if a is None:
                a = {"esito": "—", "misurato": "test nuovo"}
            if a["esito"] != b["esito"] or id_ in ("A8", "B2", "C3", "C3b", "C4") or a["esito"] == "—":
                righe.append([id_, a["esito"], _breve(a, 300), b["esito"], _breve(b, 300)])
        d.tab(["ID", "Prima", "Valore prima", "Dopo", "Valore dopo"], righe)
    d.h2("Figure")
    for f, cap in figure_elenco:
        d.img(f, cap)
    d.h2("Dettagli")
    c = _leggi(os.path.join(extra["uscita"], "risultati_C.json"))
    if c:
        d.h3("C1 — I file reali")
        righe = []
        for v in c["letture"]:
            righe.append([v["file"], v.get("canali"), "%d (intestazione: %d)" % (v.get("record", 0), v.get("record_intestazione", 0)),
                          "%.0f s" % v.get("durata_s", 0), "%.2f Hz" % v.get("fs_hz", 0),
                          "; ".join(v.get("avvisi", [])) or "—", v["md5"][:8]])
        d.tab(["File", "Canali", "Record", "Durata", "Campionamento", "Avvisi del lettore", "MD5"], righe)
        righe = []
        for r in c["casi"]:
            corr = ("%.4f" % r["correlazione"]) if r.get("correlazione") is not None else "n. a. (piatto)"
            righe.append([r["nome"], r["canale"], "%.0f s" % r["secondi"], "%.2f" % r["rms_25_60_grezzo_mv"],
                          "%.4f" % r.get("rms_25_60_float_mv", 0), "%.1f / %.1f dB" % (
                              r.get("riduzione_float_db", float("nan")), r["riduzione_db"]),
                          corr, "%.2f" % r["rms_mv"], "%.0f ms" % r["ritardo_ms"],
                          "%d / %.2f %%" % (r.get("salti", 0), 100 * r.get("frazione_esclusa", 0)),
                          ("%.2f" % r["c3b_rms_mv"]) if r.get("c3b_rms_mv") is not None else "—",
                          "+%.1f / −%.1f" % (r["max_sopra_rif_mv"], r["min_sotto_rif_mv"])])
        d.tab(["Caso", "Canale", "Durata utile", "Rumore 25–60 Hz grezzo (RMS)", "… uscita del programma (RMS)",
               "C2 riduzione programma / file", "C3 correlazione", "C3 RMS", "Ritardo",
               "Salti > 500 / tempo escluso", "C3b RMS", "C4 estremi oltre il rif."], righe)
    mut = extra["mut"]
    if mut:
        d.h3("Mutazioni (copia temporanea del codice)")
        d.tab(["ID", "Guasto", "File", "Test falliti", "Rilevato da un test critico"],
              [[k, v["guasto"], v["file"], ", ".join(v["test_falliti"]) or "nessuno",
                "sì" if v["rilevato"] else "NO"] for k, v in sorted(mut["mutazioni"].items())])
    d3 = ris.get("D3", {}).get("dettagli", {}).get("elenco")
    if d3:
        d.h3("D3 — Da verificare solo con la scheda")
        d.ul(d3)
    if "E1" in ris and ris["E1"].get("risultati_docker"):
        d.h3("E1 — Esiti in Python 3.4 (Docker)")
        r = ris["E1"]["risultati_docker"]
        d.tab(["ID", "Esito", "Valore misurato su Python 3.4"],
              [[k, r[k]["esito"], _breve(r[k], 220)] for k in K.TEST if k in r])
    d.h3("Come rifare tutto")
    d.pre("./valida.sh            # tutto tranne la prova di 3 ore (~10 minuti)\n"
          "./valida.sh --lungo    # aggiunge la prova di 3 ore accelerata (B8)")
    return d, titolo


def _commit():
    try:
        import subprocess
        out = subprocess.check_output(["git", "-C", RADICE, "log", "-1", "--format=%h %s"],
                                      universal_newlines=True).strip()
        sporco = subprocess.check_output(["git", "-C", RADICE, "status", "--porcelain", "dlive", "main.py"],
                                         universal_newlines=True).strip()
        return out + (" (+ modifiche non ancora registrate in dlive/)" if sporco else "")
    except Exception:
        return "?"


def _analisi():
    """Blocchi di testo delle analisi (fase 3, poi fase 2): righe che iniziano
    con '### ' diventano titoli, '* ' elenchi."""
    blocchi = []
    for nome, titolo in (("analisi_fase5.md", "Cosa è stato ricavato dai sorgenti (fase 5)"),
                         ("analisi_fase4.md", "Fase 4 (storico): chiusura di C3, C3b, C4"),
                         ("analisi_fase3.md", "Fase 3 (storico): decisioni, nuovi test E6/E7/C3b, correzioni"),
                         ("analisi_fase2.md", "Fase 2 (storico): FAIL della fase 1 e correzioni")):
        p = os.path.join(DOCS, nome)
        if not os.path.exists(p):
            continue
        blocchi.append(("h2", titolo))
        elenco = []
        for riga in io.open(p, encoding="utf-8").read().splitlines():
            if riga.startswith("* "):
                elenco.append(riga[2:])
                continue
            if elenco:
                blocchi.append(("ul", elenco))
                elenco = []
            if riga.startswith("### "):
                blocchi.append(("h3", riga[4:]))
            elif riga.strip():
                blocchi.append(("p", riga))
        if elenco:
            blocchi.append(("ul", elenco))
    return blocchi or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("uscita")
    ap.add_argument("--nome", default="rapporto_validazione")
    ap.add_argument("--lungo", action="store_true")
    ap.add_argument("--cartella", default=None,
                    help="dove scrivere rapporto, figure e risultati (predefinita: docs/validazione)")
    a = ap.parse_args()
    global DESTINAZIONE
    if a.cartella:
        DESTINAZIONE = os.path.abspath(a.cartella)
        if not os.path.isdir(DESTINAZIONE):
            os.makedirs(DESTINAZIONE)
    ris, extra = raccogli(a.uscita, a.lungo)
    extra["uscita"] = a.uscita
    verd, motivi = verdetto(ris, riproducibile=(a.nome == "rapporto_riproducibile"))
    global FIGURE
    FIGURE = os.path.join(DESTINAZIONE, "figure")
    if a.nome == "rapporto_iniziale":
        SOTTO_FIGURE["n"] = "figure_iniziali"
        FIGURE = os.path.join(DESTINAZIONE, "figure_iniziali")
    figure_elenco = figure(a.uscita)
    cart_ris = os.path.join(DESTINAZIONE, "risultati_iniziali" if a.nome == "rapporto_iniziale" else "risultati")
    if os.path.isdir(cart_ris):
        shutil.rmtree(cart_ris)
    os.makedirs(cart_ris)
    for p in glob.glob(os.path.join(a.uscita, "risultati_*.json")):
        shutil.copy2(p, cart_ris)
    with io.open(os.path.join(cart_ris, "riepilogo.json"), "w", encoding="utf-8") as f:
        t = json.dumps({"verdetto": verd, "motivi": motivi, "risultati": {
            k: {kk: v[kk] for kk in ("id", "livello", "esito", "misurato", "soglia", "nota")}
            for k, v in ris.items()}}, indent=1, ensure_ascii=False)
        f.write(t if isinstance(t, type(u"")) else t.decode("utf-8"))
    iniziali = None
    if a.nome != "rapporto_iniziale":
        r0 = _leggi(os.path.join(DOCS, "risultati_fase4", "riepilogo.json")) or \
            _leggi(os.path.join(DOCS, "risultati_iniziali", "riepilogo.json"))
        iniziali = r0["risultati"] if r0 else None
    doc, titolo = componi(ris, extra, verd, motivi, a.nome, figure_elenco, iniziali,
                          _analisi() if a.nome != "rapporto_iniziale" else None)
    with io.open(os.path.join(DESTINAZIONE, a.nome + ".md"), "w", encoding="utf-8") as f:
        f.write(_md(doc))
    with io.open(os.path.join(DESTINAZIONE, a.nome + ".html"), "w", encoding="utf-8") as f:
        f.write(_html(doc, titolo))
    print("VERDETTO: %s" % verd)
    for k, v in motivi.items():
        if v:
            print("  %s: %s" % (k, ", ".join(v)))
    print("Rapporto: %s.md / .html" % os.path.join(DESTINAZIONE, a.nome))
    return 0


if __name__ == "__main__":
    sys.exit(main())
