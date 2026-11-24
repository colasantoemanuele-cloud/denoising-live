# -*- coding: utf-8 -*-
"""Gruppo B: catena completa in simulazione.

Sorgente: il segnale sintetico (verita' nota + rumore + picchi) scritto come
file .wcp a 1000 Hz da uno scrittore indipendente dal programma, riprodotto da
SimulatedDevice senza sovracampionamento.  La Sessione e' costruita come la
costruisce la GUI con la configurazione di default."""
from __future__ import division

import json
import math
import os
import signal as segnali
import subprocess
import sys
import time

import numpy as np
import pytest

import comuni as C
from conftest import LAVORO, PERCORSO_LOG

try:
    import scipy  # noqa: F401
    HA_SCIPY = True
except ImportError:
    HA_SCIPY = False
try:
    import neo
except ImportError:
    neo = None

FILE_WINWCP_REALE = os.path.join(C.DATI_REALI, "071210_001.wcp")   # VERPROG=V5.1.6, 1 canale


@pytest.fixture(scope="module")
def sorgente():
    s = C.sintetico()
    p = os.path.join(LAVORO, "sintetico_1000Hz.wcp")
    C.scrivi_wcp_semplice(p, s.rumoroso, 0.001, ident="validazione sintetico")
    return p


@pytest.fixture(scope="module")
def catena(sorgente):
    cartella = os.path.join(LAVORO, "catena")
    if not os.path.isdir(cartella):
        os.makedirs(cartella)
    t0 = time.time()
    s, reg, dev = C.esegui_catena(sorgente, cartella)
    return {"sessione": s, "reg": reg, "dev": dev, "durata": time.time() - t0,
            "cartella": cartella}


def _leggi_neo(percorso):
    """Valori in mV letti con neo.io.WinWcpIO (un array per record)."""
    r = neo.io.WinWcpIO(filename=percorso)
    blk = r.read_block()
    out = []
    for seg in blk.segments:
        a = seg.analogsignals[0]
        out.append(np.asarray(a.rescale("mV").magnitude, dtype=np.float64)[:, 0])
    return out


def _prefisso_uguale(a, b):
    """Numero di campioni iniziali uguali."""
    n = min(len(a), len(b))
    d = np.flatnonzero(np.asarray(a[:n]) != np.asarray(b[:n]))
    return int(d[0]) if len(d) else n


# ---------------------------------------------------------------------------
def test_B1_grezzo_identico(registra, catena, sorgente):
    s = C.sintetico()
    reg = catena["reg"]
    hdr, _, recs = C.leggi_wcp_riferimento(reg.percorso_raw)
    raw = C.concatena_canale(recs)
    n = len(s.rumoroso)
    if len(raw) < n:
        registra("B1", "file grezzo troppo corto: %d campioni su %d" % (len(raw), n), False)
        assert False
    diversi = int(np.sum(raw[:n] != s.rumoroso))
    ok = diversi == 0
    registra("B1", "%d campioni diversi su %d" % (diversi, n), ok,
             {"diversi": diversi, "campioni": n, "primo_diverso": _prefisso_uguale(raw, s.rumoroso)})
    assert ok


def test_B2_filtrato_come_riferimento(registra, catena):
    if not HA_SCIPY:
        registra("B2", "scipy assente: riferimento non calcolabile", None)
        pytest.skip("richiede scipy")
    s = C.sintetico()
    reg = catena["reg"]
    _, _, recs = C.leggi_wcp_riferimento(reg.percorso_filt)
    filt = C.concatena_canale(recs).astype(np.int64)
    # riferimento: scipy causale sulla sorgente, con i picchi (posizioni note) tenuti
    # all'ultimo campione buono, ridotto a 125 Hz prendendo un campione ogni 8
    rif = C.filtra_riferimento(C.sos_riferimento(), s.senza_picchi_tenuto())[0::8]
    rif = np.round(rif).astype(np.int64)
    n = len(rif)
    if len(filt) < n:
        registra("B2", "file filtrato troppo corto: %d campioni su %d" % (len(filt), n), False)
        assert False
    d = np.abs(filt[:n] - rif)
    m = int(d.max())
    ok = m <= 1
    registra("B2", "differenza massima %d conteggi (%.2f mV) su %d campioni a 125 Hz; "
             "%d campioni differiscono di 1" % (m, m * C.MV_PER_CONTEGGIO, n, int(np.sum(d == 1))),
             ok, {"diff_max_conteggi": m, "campioni": n})
    assert ok


def test_B3_nessun_campione_perso(registra, catena):
    s = catena["sessione"]
    reg = catena["reg"]
    meta = json.load(open(reg.percorso_json))
    n = C.N_SINTETICO
    attesi_filt = n // 8
    h_raw, _, r_raw = C.leggi_wcp_riferimento(reg.percorso_raw)
    h_filt, _, r_filt = C.leggi_wcp_riferimento(reg.percorso_filt)
    n_rec = int(h_raw["NR"])
    per_rec_raw = len(r_raw[0]["adc"]) if r_raw else 0
    per_rec_filt = len(r_filt[0]["adc"]) if r_filt else 0
    rec_attesi = int(math.ceil(n / float(per_rec_raw))) if per_rec_raw else -1
    durata_json = int(round(meta["durata_s"] * C.FS))
    ok = (s.persi_tot == 0 and meta["campioni_persi"] == 0 and
          abs(reg.campioni_raw - n) <= 1 and abs(reg.campioni_filt - attesi_filt) <= 1 and
          abs(durata_json - n) <= 1 and n_rec == rec_attesi == int(h_filt["NR"]) and
          per_rec_raw == 8 * per_rec_filt)
    registra("B3", "Perse = %d; grezzo %d campioni (attesi %d), filtrato %d (attesi %d); "
             "durata nel JSON %.3f s; %d record per file (attesi %d)"
             % (s.persi_tot, reg.campioni_raw, n, reg.campioni_filt, attesi_filt,
                meta["durata_s"], n_rec, rec_attesi), ok,
             {"persi": s.persi_tot, "campioni_grezzo": reg.campioni_raw,
              "campioni_filtrato": reg.campioni_filt, "record": n_rec,
              "durata_elaborazione_s": catena["durata"]})
    assert ok


def test_B4_nessun_aliasing(registra, lavoro):
    t = np.arange(int(60 * C.FS)) / C.FS
    c = C.mv_in_conteggi(50.0 + 100.0 * np.sin(2 * np.pi * 100.0 * t))
    p = os.path.join(lavoro, "tono100.wcp")
    C.scrivi_wcp_semplice(p, c, 0.001)
    s, reg, dev = C.esegui_catena(p, lavoro)
    _, _, recs = C.leggi_wcp_riferimento(reg.percorso_filt)
    f = C.concatena_canale(recs)[:reg.campioni_filt].astype(np.float64) * C.MV_PER_CONTEGGIO
    regime = f[int(2 * 125):]
    alias = C.ampiezza_sinusoide(regime, 25.0, fs=125.0)       # 100 Hz visto a 125 Hz -> 25 Hz
    picco = float(np.max(np.abs(regime - np.median(regime))))
    ok = alias < 0.5
    registra("B4", "ampiezza a 25 Hz (alias di 100 Hz) %.4f mV; scostamento massimo %.3f mV"
             % (alias, picco), ok, {"alias_mv": alias, "scostamento_max_mv": picco})
    assert ok


def test_B5_marker(registra, sorgente, lavoro):
    from dlive.devices.simulated import SimulatedDevice
    dev = SimulatedDevice(sorgente, record=1, canale=0, velocita=1.0, sovracampiona=False,
                          tempo_reale=True, ciclo=False)
    dev.apri()
    s = C.sessione_come_gui(dev, lavoro)
    s.comandi.put(("avvia_reg", None))
    s.avvia_anteprima()
    time.sleep(6.3)
    t_vero = (time.time() - dev._t0) * dev.velocita
    s.marker("prova B5")
    time.sleep(3.0)
    s.ferma()
    reg = s.ultima_registrazione
    meta = json.load(open(reg.percorso_json))
    m = [x for x in meta["marker"] if x["testo"] == "prova B5"]
    if not m:
        registra("B5", "marker assente dal JSON", False)
        assert False
    errore = m[0]["t_s"] - t_vero
    ok = abs(errore) <= 1.0
    registra("B5", "marker a %.3f s nel JSON, istante reale %.3f s (scarto %+.3f s)"
             % (m[0]["t_s"], t_vero, errore), ok,
             {"t_json_s": m[0]["t_s"], "t_reale_s": t_vero, "errore_s": errore})
    assert ok


def test_B6_file_apribili(registra, catena):
    reg = catena["reg"]
    note = []
    ok = True
    dett = {}
    # 1) neo contro il lettore di riferimento
    if neo is None:
        esito_neo = None
        note.append("neo non installato: confronto non eseguito")
    else:
        peggiore = 0.0
        for p in (reg.percorso_raw, reg.percorso_filt):
            _, _, recs = C.leggi_wcp_riferimento(p)
            v_neo = _leggi_neo(p)
            if len(v_neo) != len(recs):
                peggiore = float("inf")
                break
            for a, r in zip(v_neo, recs):
                if len(a) != len(r["data"][0]):
                    peggiore = float("inf")
                    break
                peggiore = max(peggiore, float(np.max(np.abs(a - r["data"][0]))))
        esito_neo = peggiore < 0.001
        dett["neo_diff_max_mv"] = peggiore
        note.append("neo vs riferimento: %.2g mV" % peggiore)
    # 2) chiavi dell'intestazione come un file WinWCP 5.1.6 reale
    if os.path.exists(FILE_WINWCP_REALE):
        h_ref, ordine_ref, _ = C.leggi_wcp_riferimento(FILE_WINWCP_REALE, nr_forzato=0)
        esito_chiavi = True
        for p in (reg.percorso_raw, reg.percorso_filt):
            h, ordine, _ = C.leggi_wcp_riferimento(p, nr_forzato=0)
            if ordine != ordine_ref:
                esito_chiavi = False
                note.append("chiavi diverse in %s: in piu' %s, mancanti %s" % (
                    os.path.basename(p), sorted(set(ordine) - set(ordine_ref)),
                    sorted(set(ordine_ref) - set(ordine))))
        note.append("chiavi uguali a %s (VERPROG=%s): %s" % (
            os.path.basename(FILE_WINWCP_REALE), h_ref.get("VERPROG"), "sì" if esito_chiavi else "NO"))
    else:
        esito_chiavi = None
        note.append("confronto delle chiavi con un file WinWCP reale %s" % C.SENZA_DATI)
    # 3) dimensioni dei record
    esito_dim = True
    for p in (reg.percorso_raw, reg.percorso_filt):
        h, _, recs = C.leggi_wcp_riferimento(p)
        nbd, nba, nc, nr = int(h["NBD"]), int(h["NBA"]), int(h["NC"]), int(h["NR"])
        campioni = len(recs[0]["adc"]) * nc
        dim_ok = (os.path.getsize(p) == int(h["NBH"]) + nr * (nba + nbd) * 512 and
                  campioni * 2 == nbd * 512 and campioni < 2200000)
        esito_dim = esito_dim and dim_ok
        note.append("%s: %d record da %d campioni (%d byte di dati = %d settori da 512)"
                    % (os.path.basename(p), nr, campioni, campioni * 2, nbd))
    esiti = [e for e in (esito_neo, esito_chiavi, esito_dim)]
    if False in esiti:
        ok = False
    elif None in esiti:
        ok = None
    registra("B6", "; ".join(note), ok, dett)
    if ok is None:
        pytest.skip((C.SENZA_DATI + ": " if esito_chiavi is None else "parte non verificabile: ") + "; ".join(note))
    assert ok


def test_B7_crash_kill9(registra, sorgente, lavoro):
    if not hasattr(segnali, "SIGKILL"):
        registra("B7", "SIGKILL non disponibile su questo sistema", None)
        pytest.skip("niente SIGKILL")
    cartella = os.path.join(lavoro, "crash")
    os.makedirs(cartella)
    battito = os.path.join(lavoro, "battito.json")
    figlio = os.path.join(C.QUI, "figlio_crash.py")
    pr = subprocess.Popen([sys.executable, figlio, sorgente, cartella, battito],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    obiettivo = float(os.environ.get("DLIVE_B7_SECONDI", "64"))   # oltre il primo record da 59,4 s
    t_limite = time.time() + obiettivo + 60
    stato = None
    while time.time() < t_limite:
        time.sleep(0.05)
        if pr.poll() is not None:
            break
        try:
            stato = json.load(open(battito))
        except (IOError, OSError, ValueError):
            continue
        if stato["t0_dispositivo"] and time.time() - stato["t0_dispositivo"] >= obiettivo:
            break
    t_kill = time.time()
    os.kill(pr.pid, segnali.SIGKILL)
    pr.wait()
    if stato is None or not stato.get("registrazione"):
        registra("B7", "il processo figlio non ha iniziato a registrare", False)
        assert False
    acquisiti = (t_kill - stato["t0_dispositivo"]) * C.FS
    base = os.path.join(cartella, stato["registrazione"])
    s = C.sintetico()
    note = []
    leggibili = True
    try:
        _, _, recs = C.leggi_wcp_riferimento(base + "_raw.wcp")
        raw = C.concatena_canale(recs)
        _, _, recs_f = C.leggi_wcp_riferimento(base + "_filt.wcp")
    except Exception as e:
        leggibili = False
        raw = np.zeros(0)
        note.append("lettore di riferimento: %s" % e)
    esito_neo = None
    if neo is not None:
        try:
            for suff in ("_raw.wcp", "_filt.wcp"):
                v = _leggi_neo(base + suff)
                if not v:
                    raise ValueError("nessun record")
            esito_neo = True
        except Exception as e:
            esito_neo = False
            note.append("neo: %s" % e)
    validi = _prefisso_uguale(raw, s.rumoroso)
    persi_s = (acquisiti - validi) / C.FS
    try:
        meta = json.load(open(base + ".json"))
        note.append("JSON leggibile (chiusura_regolare=%s)" % meta.get("chiusura_regolare"))
    except Exception as e:
        note.append("JSON non leggibile: %s" % e)
    ok_dati = leggibili and persi_s <= 2.0 and validi > 0
    if esito_neo is False:
        ok = False
    elif esito_neo is None:
        ok = None if ok_dati else False
        note.append("neo non installato: lettura con neo non verificata")
    else:
        ok = ok_dati
    registra("B7", "ucciso dopo %.1f s di acquisizione; nel file %.1f s validi; persi %.2f s; "
             "leggibile con neo: %s; %s" % (acquisiti / C.FS, validi / C.FS, persi_s,
                                             {True: "sì", False: "NO", None: "non provato"}[esito_neo],
                                             "; ".join(note)), ok,
             {"acquisiti_s": acquisiti / C.FS, "validi_s": validi / C.FS, "persi_s": persi_s,
              "record_grezzo": len(recs) if leggibili else 0})
    if ok is None:
        pytest.skip("neo non installato")
    assert ok


def _rss_mb():
    try:
        with open("/proc/self/status") as f:
            for riga in f:
                if riga.startswith("VmRSS:"):
                    return int(riga.split()[1]) / 1024.0
    except (IOError, OSError):
        pass
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:
        return float("nan")


@pytest.mark.skipif(os.environ.get("DLIVE_LUNGO") != "1", reason="solo con ./valida.sh --lungo")
def test_B8_tre_ore(registra, sorgente, lavoro):
    """3 ore di segnale in tempo reale accelerato 100x (la sorgente sintetica
    di 10 minuti ripetuta 18 volte): la coda tra acquisizione ed elaborazione
    resta limitata come con la scheda vera, quindi la memoria misurata e'
    quella del programma."""
    import gc
    from dlive.devices.simulated import SimulatedDevice
    velocita = float(os.environ.get("DLIVE_B8_VELOCITA", "100"))
    dev = SimulatedDevice(sorgente, record=1, canale=0, velocita=velocita, sovracampiona=False,
                          tempo_reale=True, ciclo=True)
    dev.apri()
    s = C.sessione_come_gui(dev, lavoro)
    obiettivo = 3 * 3600 * int(C.FS)
    gc.collect()
    rss0 = _rss_mb()
    s.comandi.put(("avvia_reg", None))
    t0 = time.time()
    s.avvia_anteprima()
    misure = []
    coda_max = 0
    while s.in_corso and s.campioni < obiettivo and time.time() - t0 < 3 * 3600.0 / velocita * 3 + 60:
        time.sleep(0.25)
        misure.append((s.campioni, _rss_mb()))
        coda_max = max(coda_max, s.coda.qsize())
    s.ferma(attesa=120)
    reg = s.ultima_registrazione
    durata = time.time() - t0
    if reg is None:
        registra("B8", "la registrazione non si e' chiusa (campioni %d, coda %d)" % (s.campioni, s.coda.qsize()),
                 False)
        assert False
    rss_max = max(m for c, m in misure) if misure else float("nan")
    dopo10 = [m for c, m in misure if c >= 600 * C.FS]
    rss10 = dopo10[0] if dopo10 else float("nan")
    crescita = rss_max - rss0
    crescita_dopo10 = rss_max - rss10
    log = open(PERCORSO_LOG).read() if os.path.exists(PERCORSO_LOG) else ""
    inizio_log = log.find("Registrazione iniziata: %s" % reg.nome_base)
    errori_log = [r for r in log[max(0, inizio_log):].splitlines() if " ERROR " in r]
    meta = json.load(open(reg.percorso_json))
    raw = C.leggi_wcp_riferimento(reg.percorso_raw, nr_forzato=0)[0]
    ok = (crescita < 50.0 and s.persi_tot == 0 and meta["campioni_persi"] == 0 and
          reg.n_errori() == 0 and not errori_log and s.campioni >= obiettivo and
          meta["chiusura_regolare"])
    registra("B8", "%.2f ore di segnale in %.0f s (%gx); memoria del processo: %.0f MB all'avvio, %.0f MB "
             "dopo 10 min di segnale, massimo %.0f MB (crescita %.1f MB; %.1f MB dopo i primi 10 min); "
             "persi %d; errori di scrittura %d; errori nel log %d; %s record; coda massima %d blocchi"
             % (s.campioni / C.FS / 3600.0, durata, velocita, rss0, rss10, rss_max, crescita,
                crescita_dopo10, s.persi_tot, reg.n_errori(), len(errori_log), raw.get("NR"), coda_max), ok,
             {"crescita_mb": crescita, "crescita_dopo_10min_mb": crescita_dopo10, "rss_avvio_mb": rss0,
              "rss_10min_mb": rss10, "rss_max_mb": rss_max, "secondi_reali": durata, "coda_max": coda_max,
              "serie_memoria": [(c / C.FS, m) for c, m in misure[::20]]})
    assert ok


_FileGuasto = C.FileGuasto
esegui_b9 = C.esegui_b9


def valuta_b9(s, reg, n, messaggi, log):
    return C.valuta_b9(s, reg, n, messaggi, log, _leggi_neo if neo is not None else None)


def test_B9_errore_di_scrittura(registra, sorgente, lavoro):
    """Parte senza finestra: messaggio inviato alla GUI, log, acquisizione che
    continua, dati gia' scritti leggibili.  La comparsa della banda rossa nella
    finestra e' verificata dallo scenario GUI (E3, sotto Xvfb)."""
    s, reg, n_guasto = esegui_b9(sorgente, lavoro)
    messaggi = []
    # la GUI legge s.messaggi; qui li leggiamo noi mentre l'acquisizione continua
    t_fine = time.time() + 2.0
    while time.time() < t_fine:
        try:
            messaggi.append(s.messaggi.get(timeout=0.1))
        except Exception:
            pass
    s.ferma()
    while True:
        try:
            messaggi.append(s.messaggi.get_nowait())
        except Exception:
            break
    log = open(PERCORSO_LOG).read() if os.path.exists(PERCORSO_LOG) else ""
    m = valuta_b9(s, reg, n_guasto, messaggi, log)
    ok = all(m[k] for k in ("continua", "nel_log", "messaggio_gui", "leggibili"))
    registra("B9", "guasto a %.1f s; acquisizione continuata fino a %.1f s: %s; errore nel log: %s; "
             "messaggio alla finestra: %s; file leggibili con %.1f s di dati corretti: %s"
             % (m["secondi_al_guasto"], m["secondi_totali"], _sn(m["continua"]), _sn(m["nel_log"]),
                _sn(m["messaggio_gui"]), m["secondi_validi"], _sn(m["leggibili"])), ok, m)
    assert ok


def _sn(v):
    return "sì" if v else "NO"
