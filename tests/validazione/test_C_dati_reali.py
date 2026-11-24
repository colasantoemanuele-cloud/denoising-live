# -*- coding: utf-8 -*-
"""Gruppo C: i 7 file reali del laboratorio passati nella catena in
simulazione (sovracampionamento a 1000 Hz, come in modalita' Digidata).

Riferimento indipendente: notch 50 Hz + Butterworth 4 a 5 Hz a fase zero
(scipy sosfiltfilt) sul grezzo a 1000 Hz ripulito dai picchi con un filtro
mediano (metodo indipendente da quello del programma)."""
from __future__ import division

import hashlib
import io
import json
import os

import numpy as np
import pytest

import comuni as C
from conftest import LAVORO, USCITA

try:
    from scipy import signal
    HA_SCIPY = True
except ImportError:
    HA_SCIPY = False

FILE_REALI = sorted(f for f in os.listdir(C.DATI_REALI) if f.endswith(".wcp")) \
    if os.path.isdir(C.DATI_REALI) else []
FIGURE_DATI = os.path.join(USCITA, "dati_figure")

pytestmark = pytest.mark.skipif(not FILE_REALI, reason=C.SENZA_DATI)


def _md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def togli_picchi(x, fs, conteggi=None, soglia_mv=500.0, finestra_s=0.101):
    """Riferimento ideale (non causale) per l'ingresso:
    1) i campioni sulle rotaie dell'ADC (-32768 / +32767 conteggi) non portano
       informazione: si sostituiscono interpolando tra i campioni validi vicini,
       qualunque sia la durata della saturazione;
    2) i picchi brevi non saturati (scostamento > soglia_mv dalla mediana
       mobile di ~0,1 s) si sostituiscono con la mediana."""
    y = x.astype(np.float64).copy()
    n_sat = 0
    if conteggi is not None:
        sat = (conteggi <= -32768) | (conteggi >= 32767)
        n_sat = int(sat.sum())
        if n_sat and n_sat < len(y):
            idx = np.arange(len(y))
            y[sat] = np.interp(idx[sat], idx[~sat], y[~sat])
    k = int(finestra_s * fs) | 1
    med = signal.medfilt(y, k)
    m = np.abs(y - med) > soglia_mv
    y[m] = med[m]
    return y, int(m.sum()) + n_sat


def regola_readme(x, conteggi, soglia, attesa, saturazione=32700):
    """La regola dei picchi del README (par. 6.1), scritta qui a partire dal testo e non
    dal codice del programma.  x: grezzo in unita' del canale; conteggi: lo stesso in
    conteggi ADC; soglia: unita'; attesa: campioni (50 ms).
      * conteggi oltre +/-saturazione: ultimo valore valido;
      * escursione oltre 'soglia' dall'ultimo valore valido lunga <= attesa campioni:
        sostituita dall'ultimo valore valido;
      * escursione piu' lunga: i primi 'attesa' campioni sostituiti, il resto passa.
    Restituisce (segnale, escursioni) con escursioni = [(inizio, campioni, accettata)]."""
    x = [float(v) for v in x]
    c = conteggi.tolist() if hasattr(conteggi, "tolist") else list(conteggi)
    n = len(x)
    sat = [v >= saturazione or v <= -saturazione - 1 for v in c]
    y = list(x)
    ultimo = None
    for i in range(n):
        if not sat[i]:
            ultimo = x[i]
            break
    ultimo = 0.0 if ultimo is None else ultimo
    escursioni = []
    i = 0
    while i < n:
        if sat[i]:
            y[i] = ultimo
            i += 1
            continue
        if abs(x[i] - ultimo) <= soglia:
            ultimo = x[i]
            i += 1
            continue
        # escursione: campioni non saturati oltre soglia dall'ultimo valore valido
        j = i
        lunghi = 0
        while j < n and (sat[j] or abs(x[j] - ultimo) > soglia):
            if not sat[j]:
                lunghi += 1
            j += 1
        if lunghi <= attesa:
            for k in range(i, j):
                y[k] = ultimo
            escursioni.append((i, lunghi, False))
            i = j
        else:
            tolti = 0
            k = i
            while tolti < attesa:
                if not sat[k]:
                    tolti += 1
                y[k] = ultimo
                k += 1
            while sat[k]:
                y[k] = ultimo
                k += 1
            escursioni.append((i, lunghi, True))
            ultimo = x[k]                     # il resto passa: da qui e' segnale
            i = k + 1
    return np.array(y), escursioni


def riferimento_fase_zero(x, fs):
    sos = np.vstack([np.concatenate(signal.iirnotch(50.0 / (fs / 2.0), 30.0)),
                     signal.butter(4, 5.0 / (fs / 2.0), btype="low", output="sos")])
    return signal.sosfiltfilt(sos, x)


def _casi():
    """Elenco dei casi: (nome, percorso .wcp da riprodurre, canale, record)."""
    casi = []
    for nome in FILE_REALI:
        p = os.path.join(C.DATI_REALI, nome)
        hdr, _, recs = C.leggi_wcp_riferimento(p)
        nc = int(hdr["NC"])
        if nc > 1:
            dati = np.concatenate([r["data"] for r in recs], axis=1)
            canale = int(np.argmax(dati.std(axis=1)))
        else:
            canale = 0
        casi.append((nome, p, canale, 0))
        if nome == "081024_001.wcp":
            # secondo record non dichiarato (NR=1): estratto con il lettore di
            # riferimento e scritto come file a se'
            _, _, tutti = C.leggi_wcp_riferimento(p, nr_forzato=2)
            if len(tutti) > 1:
                q = os.path.join(LAVORO, "081024_001_record2_nascosto.wcp")
                yo = int(hdr["YO%d" % canale])
                C.scrivi_wcp_semplice(q, tutti[1]["adc"][:, yo], tutti[1]["dt"],
                                      nome=hdr["YN%d" % canale], unita=hdr["YU%d" % canale],
                                      yg=hdr["YG%d" % canale], yz=hdr["YZ%d" % canale])
                casi.append(("081024_001.wcp record 2 (non dichiarato)", q, 0, 0))
    return casi


@pytest.fixture(scope="module")
def risultati_c():
    if not HA_SCIPY:
        pytest.skip("richiede scipy")
    from dlive import wcpfile
    if not os.path.isdir(FIGURE_DATI):
        os.makedirs(FIGURE_DATI)
    out = {"letture": [], "casi": []}
    gia = {}
    for nome in FILE_REALI:
        p = os.path.join(C.DATI_REALI, nome)
        voce = {"file": nome, "md5": _md5(p)}
        try:
            w = wcpfile.leggi_wcp(p, recupera_extra=True)
            hdr, _, recs = C.leggi_wcp_riferimento(p)
            voce.update({"ok": True, "canali": w.nc, "record": w.nr,
                         "record_intestazione": w.nr_intestazione,
                         "fs_hz": 1.0 / w.dt, "durata_s": w.nr * w.campioni_per_record * w.dt,
                         "avvisi": w.avvisi,
                         "uguale_al_riferimento": bool(all(
                             np.array_equal(np.column_stack([np.asarray(c) for c in r.adc]), rr["adc"])
                             for r, rr in zip(w.records, recs)))})
        except Exception as e:
            voce.update({"ok": False, "errore": "%s: %s" % (type(e).__name__, e)})
        out["letture"].append(voce)
    for nome, p, canale, record in _casi():
        md5 = _md5(p)
        if md5 in gia:
            r = dict(gia[md5])
            r["nome"] = nome
            r["nota"] = "identico byte per byte a %s: stessi risultati" % r["nome_originale"]
            out["casi"].append(r)
            continue
        cartella = os.path.join(LAVORO, "reali", str(len(out["casi"])))
        os.makedirs(cartella)
        s, reg, dev = C.esegui_catena(p, cartella, record=record, canale=canale,
                                      sovracampiona=True, velocita=20.0, salta_coda=True)
        _, _, rr = C.leggi_wcp_riferimento(reg.percorso_raw)
        _, _, rf = C.leggi_wcp_riferimento(reg.percorso_filt)
        raw = np.concatenate([r["data"][0] for r in rr])[:reg.campioni_raw]
        raw_c = C.concatena_canale(rr)[:reg.campioni_raw]
        filt = np.concatenate([r["data"][0] for r in rf])[:reg.campioni_filt]
        fs = dev.fs
        pulito, n_picchi = togli_picchi(raw, fs, raw_c)
        # uscita del programma prima dell'arrotondamento a 16 bit del file:
        # stesso ingresso (il grezzo salvato) e stesso Elaboratore della
        # Sessione; B2 verifica che il file filtrato ne sia l'arrotondamento
        cal = dev.calibrazione()
        y_cont = C.filtra_programma(raw_c, C.parametri(), fs=fs, cal=cal, in_conteggi=True)[0::8]
        scala = cal["ad"] / cal["adcmax"] / cal["yg"]
        y_float = (y_cont - cal["yz"]) * scala          # stesse unita' del lettore di riferimento
        filt_c = C.concatena_canale(rf)[:reg.campioni_filt].astype(np.float64)
        coerenza = float(np.max(np.abs(np.round(y_cont) - filt_c))) \
            if len(y_cont) == len(filt_c) else float("inf")
        # D7: lo stesso con l'attesa scritta a mano (50 campioni = 50 ms a 1000 Hz), senza
        # passare dalla configurazione: deve dare lo stesso file campione per campione
        from dlive import filters as _f
        e50 = _f.Elaboratore(C.parametri(), fs, 1, 32700, soglia_picco=500.0 * cal["yg"] * cal["adcmax"] / cal["ad"],
                             max_campioni_picco=50)
        y50 = np.array(e50.elabora(raw_c)[0])[0::8]
        coerenza_50 = int(np.sum(np.round(y50) != filt_c)) if len(y50) == len(filt_c) else -1
        rif = riferimento_fase_zero(pulito, fs)
        # C2: potenza 25-60 Hz
        p_raw = C.potenza_banda(pulito, fs, 25.0, 60.0)
        p_raw_tutto = C.potenza_banda(raw, fs, 25.0, 60.0)
        p_filt = C.potenza_banda(filt, fs / 8.0, 25.0, 60.0)
        p_float = C.potenza_banda(y_float, fs / 8.0, 25.0, 60.0)
        riduzione = 10 * np.log10(p_raw / max(p_filt, 1e-30))
        riduzione_float = 10 * np.log10(p_raw / max(p_float, 1e-30))
        # Fase 3 (decisione D2): C3 e C4 si valutano fuori da +/-1 s attorno ai
        # salti > 500 unita' del grezzo; li' (C3b) il programma si confronta con
        # un filtro causale ideale (scipy, stessi parametri, senza gestione dei
        # picchi) sullo stesso ingresso del riferimento.
        salti = np.flatnonzero(np.abs(np.diff(raw)) > SALTO)
        escluso = np.zeros(len(raw), dtype=bool)
        w = int(FINESTRA_S * fs)
        for j in salti:
            escluso[max(0, j - w):j + w + 1] = True
        frazione = float(escluso.mean()) if len(escluso) else 0.0
        inizio = int(2 * fs / 8)
        m = np.arange(inizio, len(filt))
        tenuti = ~escluso[np.minimum(m * 8, len(raw) - 1)]
        migliore = None
        for lag in range(0, 301, 1):
            idx = m * 8 - lag
            v = (idx >= 0) & tenuti
            v[v] &= ~escluso[idx[v]]
            d = filt[m[v]] - rif[idx[v]]
            rms = float(np.sqrt(np.mean(d ** 2))) if v.any() else float("nan")
            if migliore is None or rms < migliore[1]:
                migliore = (lag, rms, v)
        lag, rms, v = migliore
        idx = m * 8 - lag
        conteggio = cal["ad"] / cal["adcmax"] / cal["yg"]          # 1 conteggio ADC in unita'
        std_rif = float(np.std(rif[idx[v]]))
        corr_applicabile = std_rif >= conteggio
        corr = float(np.corrcoef(filt[m[v]], rif[idx[v]])[0, 1]) if corr_applicabile else None
        # C3 senza esclusione (come in fase 2), per il confronto prima/dopo
        idx0 = m * 8 - lag
        v0 = idx0 >= 0
        rms_tutto = float(np.sqrt(np.mean((filt[m[v0]] - rif[idx0[v0]]) ** 2)))
        # C3b (fase 4, D5): nelle finestre escluse il programma contro il filtro causale
        # ideale (scipy) applicato al grezzo dopo la regola dei picchi del README
        attesa = int(round(ATTESA_MS / 1000.0 * fs))
        dopo_regola, escursioni = regola_readme(raw, raw_c, SALTO, attesa)
        ideale = C.filtra_riferimento(C.sos_riferimento(), dopo_regola)
        campioni_file = fs / dev.fs_sorgente        # campioni a 1000 Hz per campione del file
        mesc = np.arange(len(filt))
        mesc = mesc[escluso[np.minimum(mesc * 8, len(raw) - 1)]]
        finestre = []
        coperti = np.zeros(len(filt), dtype=bool)
        for a_, b_ in C.tratti(escluso):
            mm = np.arange(int(np.ceil(a_ / 8.0)), min(len(filt), int(np.ceil(b_ / 8.0))))
            if not len(mm):
                continue
            coperti[mm] = True
            dentro = [e for e in escursioni if a_ <= e[0] < b_]
            ambigue = [e for e in dentro if abs(e[1] - attesa) <= 2 * campioni_file]
            sat = bool(np.any((raw_c[a_:b_] >= 32700) | (raw_c[a_:b_] <= -32701)))
            dd = filt[mm] - ideale[mm * 8]
            finestre.append({"t_s": round((a_ + b_) / 2.0 / fs, 2), "secondi": (b_ - a_) / fs,
                             "escursioni_ms": [round(e[1] / fs * 1000.0, 1) for e in dentro],
                             "accettate": sum(1 for e in dentro if e[2]), "saturazione": sat,
                             "ambigua": bool(ambigue), "rms": float(np.sqrt(np.mean(dd ** 2))),
                             "max": float(np.max(np.abs(dd)))})
        valutate = [f for f in finestre if not f["ambigua"]]
        rms_c3b = max([f["rms"] for f in valutate]) if valutate else None
        max_c3b = max([f["max"] for f in valutate]) if valutate else None
        copertura = float(coperti[mesc].mean()) if len(mesc) else 1.0
        copertura_esatta = bool(len(mesc) == 0 or np.array_equal(np.flatnonzero(coperti), mesc))
        # C4 fuori dalle finestre
        finiti = bool(np.all(np.isfinite(filt)))
        f_t = filt[m[tenuti]]
        r_t = rif[~escluso]
        sopra = float(f_t.max() - r_t.max())
        sotto = float(r_t.min() - f_t.min())
        r = {"nome": nome, "nome_originale": nome, "canale": canale, "fs_sorgente": dev.fs_sorgente,
             "unita": cal["unita"], "yg": cal["yg"], "yz": cal["yz"],
             "secondi": len(raw) / fs, "picchi_tolti": n_picchi, "persi": s.persi_tot,
             "p_raw_25_60": p_raw, "p_raw_con_picchi_25_60": p_raw_tutto, "p_filt_25_60": p_filt,
             "riduzione_db": float(riduzione), "ritardo_ms": lag / fs * 1000.0, "rms_mv": rms,
             "correlazione": corr, "finiti": finiti, "max_sopra_rif_mv": sopra,
             "min_sotto_rif_mv": sotto, "std_grezzo_mv": float(np.std(pulito)),
             "rms_25_60_grezzo_mv": float(np.sqrt(p_raw)),
             "rms_25_60_filtrato_mv": float(np.sqrt(p_filt)),
             "riduzione_float_db": float(riduzione_float), "rms_25_60_float_mv": float(np.sqrt(p_float)),
             "coerenza_file_float_conteggi": coerenza, "std_rif_mv": std_rif,
             "conteggio_unita": conteggio, "correlazione_applicabile": corr_applicabile,
             "salti": int(len(salti)), "frazione_esclusa": frazione, "rms_senza_esclusione_mv": rms_tutto,
             "c3b_rms_mv": rms_c3b, "c3b_max_mv": max_c3b, "c3b_secondi": len(mesc) * 8 / fs,
             "c3b_copertura": copertura, "c3b_copertura_esatta": copertura_esatta,
             "diversi_con_attesa_50": coerenza_50,
             "campioni_per_campione_file": campioni_file,
             "c3b_finestre": finestre}
        gia[md5] = r
        out["casi"].append(r)
        # dati per le figure C5 (ridotti)
        fname = os.path.join(FIGURE_DATI, "C5_%02d.npz" % len(out["casi"]))
        fw, pw = signal.welch(pulito, fs=fs, nperseg=int(4 * fs))
        ff, pf = signal.welch(filt, fs=fs / 8.0, nperseg=int(4 * fs / 8.0))
        np.savez_compressed(fname, raw=raw[::8].astype(np.float32), raw_min=_mm(raw, 8, np.min),
                            raw_max=_mm(raw, 8, np.max), filt=filt.astype(np.float32),
                            rif=rif[::8].astype(np.float32), lag=lag, fs=fs, fw=fw, pw=pw, ff=ff, pf=pf,
                            nome=nome)
        r["figura_dati"] = fname
    with io.open(os.path.join(USCITA, "risultati_C.json"), "w", encoding="utf-8") as f:
        t = json.dumps(out, indent=1, ensure_ascii=False)
        f.write(t if isinstance(t, type(u"")) else t.decode("utf-8"))
    return out


def _mm(x, k, f):
    n = len(x) // k * k
    return f(x[:n].reshape(-1, k), axis=1).astype(np.float32)


def test_C1_lettura(registra, risultati_c):
    lett = risultati_c["letture"]
    ok = len(lett) == 7 and all(v["ok"] and v["uguale_al_riferimento"] for v in lett)
    righe = []
    for v in lett:
        if v["ok"]:
            righe.append("%s: %d canali, %d record, %.0f s, %.2f Hz" % (
                v["file"], v["canali"], v["record"], v["durata_s"], v["fs_hz"]))
        else:
            righe.append("%s: ERRORE %s" % (v["file"], v["errore"]))
    registra("C1", "%d file letti su %d" % (sum(1 for v in lett if v["ok"]), len(lett)), ok,
             {"tabella": lett}, nota="; ".join(righe))
    assert ok


# Sotto questo rumore 25-60 Hz nel grezzo (circa 1/3 di conteggio ADC) non c'e'
# rumore da togliere: la riduzione in dB non e' definita (0/0).
RUMORE_MINIMO_MV = 0.1
SALTO = 500.0          # unita' del canale (mV): salti esclusi da C3/C4 (decisione D2 della fase 3)
FINESTRA_S = 1.0       # +/- attorno a ogni salto
ATTESA_MS = 50.0       # README par. 6.1: [filtro] durata_max_picco_ms predefinito
LIMITE_ESCLUSO = 0.02  # fase 4 (D6): era 0,01 in fase 3


def test_C2_riduzione_rumore(registra, risultati_c):
    """Fase 2: la riduzione si misura sull'uscita del programma prima
    dell'arrotondamento a 16 bit del file (B2 verifica che il file ne sia
    l'arrotondamento esatto).  Nel file salvato il residuo non puo' scendere
    sotto il rumore di arrotondamento (~0,04-0,09 mV RMS nella banda), quindi
    sui file poco rumorosi la riduzione misurabile nel file e' limitata da
    quello e non dal filtro.  Entrambi i valori sono riportati."""
    casi = risultati_c["casi"]
    applicabili = [r for r in casi if r["rms_25_60_grezzo_mv"] >= RUMORE_MINIMO_MV]
    esclusi = [r for r in casi if r["rms_25_60_grezzo_mv"] < RUMORE_MINIMO_MV]
    ok = bool(applicabili) and all(r["riduzione_float_db"] >= 30.0 for r in applicabili) and \
        all(r["coerenza_file_float_conteggi"] == 0 and r["diversi_con_attesa_50"] == 0 for r in casi)
    peggiore = min(applicabili, key=lambda r: r["riduzione_float_db"]) if applicabili else None
    registra("C2", "riduzione minima %.1f dB (%s); per file (uscita del programma / file a 16 bit): %s%s" % (
        peggiore["riduzione_float_db"] if peggiore else float("nan"), peggiore["nome"] if peggiore else "-",
        "; ".join("%s %.1f / %.1f dB (rumore %.2f → %.4f mV RMS)" % (
            r["nome"], r["riduzione_float_db"], r["riduzione_db"], r["rms_25_60_grezzo_mv"],
            r["rms_25_60_float_mv"]) for r in applicabili),
        ("; non applicabile (nessun rumore 25–60 Hz nel grezzo, < %.1f mV RMS): %s" % (
            RUMORE_MINIMO_MV, ", ".join("%s (%.4f mV)" % (r["nome"], r["rms_25_60_grezzo_mv"]) for r in esclusi)))
        if esclusi else ""), ok,
        {"casi": [{k: r[k] for k in ("nome", "riduzione_db", "riduzione_float_db", "rms_25_60_grezzo_mv",
                                      "rms_25_60_filtrato_mv", "rms_25_60_float_mv",
                                      "coerenza_file_float_conteggi")} for r in casi]},
        nota="metodo corretto in fase 2: misura prima dell'arrotondamento a 16 bit del file; casi senza "
             "rumore nella banda esclusi (vedi analisi). Controllo D7 (fase 4): su ogni file il filtrato "
             "salvato coincide campione per campione con l'Elaboratore costruito con l'attesa di 50 "
             "campioni scritta a mano: campioni diversi = %s" % ", ".join(
                 str(r["diversi_con_attesa_50"]) for r in casi))
    assert ok


def _c3_ok(r):
    return (r["frazione_esclusa"] < LIMITE_ESCLUSO and r["rms_mv"] < 5.0 and
            (not r["correlazione_applicabile"] or r["correlazione"] >= 0.99))


def test_C3_fedelta(registra, risultati_c):
    casi = risultati_c["casi"]
    ok = all(_c3_ok(r) for r in casi)
    righe = []
    for r in casi:
        corr = ("r = %.4f" % r["correlazione"]) if r["correlazione_applicabile"] else (
            "correlazione non applicabile (il riferimento varia di %.3f, meno di 1 conteggio = %.3f %s)"
            % (r["std_rif_mv"], r["conteggio_unita"], r["unita"]))
        righe.append("%s: %s, RMS %.2f %s, ritardo %.0f ms, esclusi %.2f %% (%d salti)%s" % (
            r["nome"], corr, r["rms_mv"], r["unita"], r["ritardo_ms"], 100 * r["frazione_esclusa"],
            r["salti"], "" if _c3_ok(r) else " ← FUORI SOGLIA"))
    registra("C3", "; ".join(righe), ok,
             {"casi": [{k: r[k] for k in ("nome", "correlazione", "correlazione_applicabile", "rms_mv",
                                          "rms_senza_esclusione_mv", "ritardo_ms", "frazione_esclusa",
                                          "salti", "std_rif_mv")} for r in casi]},
             nota="fase 3 (D2): fuori da ±1 s attorno ai salti > 500 mV del grezzo; il riferimento a fase "
                  "zero applica il filtro due volte e risponde in modo diverso da qualunque filtro in tempo "
                  "reale a impulsi brevi e grandi. Lì vale C3b.")
    assert ok


def test_C3b_attorno_ai_salti(registra, risultati_c):
    """Fase 4 (D5): finestra per finestra, programma contro filtro causale ideale
    dopo la regola dei picchi del README; soglia 2 mV RMS per finestra; finestre con
    escursioni di 50 ms +/- 2 campioni del file: ambigue, elencate ma fuori soglia.
    C3b deve coprire il 100 % del tempo escluso da C3 e C4."""
    casi = risultati_c["casi"]
    con = [r for r in casi if r["c3b_finestre"]]
    fuori = [(r, f) for r in con for f in r["c3b_finestre"] if not f["ambigua"] and f["rms"] >= 2.0]
    copertura_ok = all(r["c3b_copertura_esatta"] for r in casi)
    ok = not fuori and copertura_ok
    parti = []
    for r in con:
        val = [f for f in r["c3b_finestre"] if not f["ambigua"]]
        amb = [f for f in r["c3b_finestre"] if f["ambigua"]]
        parti.append("%s: %d finestre, RMS massimo %s %s%s; copertura del tempo escluso %.0f %%" % (
            r["nome"], len(r["c3b_finestre"]),
            ("%.2f" % max(f["rms"] for f in val)) if val else "—", r["unita"],
            ("; ambigue (fuori soglia): " + ", ".join("%.1f s escursioni %s ms RMS %.2f" % (
                f["t_s"], "/".join("%g" % e for e in f["escursioni_ms"]), f["rms"]) for f in amb)) if amb else "",
            100 * r["c3b_copertura"]))
    if fuori:
        parti.append("FUORI SOGLIA: " + "; ".join("%s %.1f s: RMS %.2f (massimo %.1f), escursioni %s ms" % (
            r["nome"], f["t_s"], f["rms"], f["max"], f["escursioni_ms"]) for r, f in fuori))
    testo = "; ".join(parti) if parti else "nessun salto > 500 mV nei file: niente da confrontare"
    registra("C3b", testo, ok, {"casi": [{"nome": r["nome"], "finestre": r["c3b_finestre"],
                                          "copertura": r["c3b_copertura"]} for r in con]},
             nota="fase 4 (D5): filtro causale ideale (scipy, notch 50 Hz + Bessel 4° ordine 5 Hz, partenza a "
                  "regime) applicato al grezzo a 1000 Hz dopo la regola dei picchi del README § 6.1, scritta "
                  "nel test senza usare il codice del programma: saturazioni e escursioni > 500 mV fino a "
                  "50 ms sostituite dall'ultimo valore valido, delle escursioni più lunghe solo i primi 50 ms")
    assert ok


def test_C4_nessun_artefatto(registra, risultati_c):
    casi = risultati_c["casi"]
    ok = all(r["finiti"] and r["max_sopra_rif_mv"] <= 10.0 and r["min_sotto_rif_mv"] <= 10.0 and
             r["frazione_esclusa"] < LIMITE_ESCLUSO for r in casi)
    registra("C4", "; ".join("%s: finiti %s, massimo %+.2f, minimo %+.2f %s rispetto al riferimento" % (
        r["nome"], "sì" if r["finiti"] else "NO", r["max_sopra_rif_mv"], -r["min_sotto_rif_mv"], r["unita"])
        for r in casi), ok, nota="fuori da ±1 s attorno ai salti > 500 mV (come C3); valori positivi del "
                                 "massimo o negativi del minimo = il filtrato va oltre il riferimento")
    assert ok


def test_C5_figure(registra, risultati_c):
    n = len([r for r in risultati_c["casi"] if r.get("figura_dati")])
    registra("C5", "dati per %d figure salvati (le figure sono disegnate dal rapporto)" % n, True)
