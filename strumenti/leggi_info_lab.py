# -*- coding: utf-8 -*-
"""Legge la cartella info_pc_lab tornata dal laboratorio e riassume cosa
cambiare in config.ini.

    python strumenti/leggi_info_lab.py [CARTELLA] [--senza-wcp]

CARTELLA predefinita: info_pc_lab/ accanto alla cartella del progetto (con
info_pc_lab.txt e wcp_recenti/, prodotti da docs/comandi_da_incollare.txt).

Riassume:
  1. installabilita': Windows, Service Pack, 32/64 bit, amministratore, disco;
  2. impostazioni di WinWCP (winwcp.ini, lab interface settings.xml): canale
     del segnale, calibrazione, campionamento, modo di registrazione;
  3. stimolazione: RECMODE e righe "Stimulus Protocol" dei log di WinWCP;
  4. file .wcp sul disco: quanti, i piu' recenti, data del PC;
  5. per ogni .wcp di wcp_recenti: canale col segnale, rumore per banda,
     righe spettrali, rumore residuo con i preset 1/2/5/10 Hz e taglio
     suggerito (il piu' alto con rumore residuo sotto 2 mV al 90 percentile,
     il criterio di README § 6.1), notch suggeriti;
e stampa le righe di config.ini da cambiare (non modifica nulla).
Le DLL Axon e WinASPI non le raccoglie il comando: le rileva la diagnostica
sul posto (dlive/rilevamento.py).
"""
import argparse
import datetime
import os
import re
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
sys.path.insert(0, RADICE)

from dlive import config as C                     # noqa: E402
from dlive import filters as F                    # noqa: E402
from dlive import wcpfile                          # noqa: E402
from dlive import winwcp_impostazioni as WI        # noqa: E402

# fuori dal progetto (contiene dati del laboratorio): accanto alla sua cartella
PREDEFINITA = os.path.join(os.path.dirname(RADICE), "info_pc_lab")
PRESET = (1.0, 2.0, 5.0, 10.0)
TAGLIO_PREDEFINITO = 5.0
SOGLIA_RUMORE_MV = 2.0
FS_ACQ = 1000.0


# ---------------------------------------------------------------------------
# info_pc_lab.txt
# ---------------------------------------------------------------------------
def sezioni(testo):
    """{numero: [righe]} dalle intestazioni '===== N TITOLO'."""
    out = {}
    corrente = 0
    out[0] = []
    for riga in testo.splitlines():
        m = re.match(r"^===== (\d+) ", riga)
        if m:
            corrente = int(m.group(1))
            out[corrente] = []
            continue
        if riga.startswith("===== FINE"):
            corrente = -1
            out[-1] = [riga]
            continue
        out.setdefault(corrente, []).append(riga)
    return out


def file_impostazioni(righe):
    """Dalla sezione 3: [(percorso, testo)]."""
    out = []
    percorso = None
    buf = []
    for riga in righe:
        if riga.startswith("----- FILE "):
            if percorso:
                out.append((percorso, "\n".join(buf)))
            percorso = riga[len("----- FILE "):].split(" ; ")[0].strip()
            buf = []
        elif percorso is not None:
            buf.append(riga)
    if percorso:
        out.append((percorso, "\n".join(buf)))
    return out


def _data(s):
    s = s.strip()
    for f in ("%d/%m/%Y %H.%M", "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(s, f)
        except ValueError:
            pass
    return None


def elenco_wcp(righe):
    out = []
    for riga in righe:
        parti = riga.split(";", 2)
        if len(parti) == 3 and parti[2].lower().endswith(".wcp"):
            try:
                dim = int(parti[1].strip())
            except ValueError:
                dim = None
            out.append((_data(parti[0]), dim, parti[2].strip()))
    return out


def sistema(righe):
    r = {"testo": [x for x in righe if x.strip()]}
    t = "\n".join(righe)
    m = re.search(r"Versione\s+([\d.]+)|Version\s+([\d.]+)", t)
    r["versione"] = (m.group(1) or m.group(2)) if m else None
    m = re.search(r"CSDVersion\s+REG_SZ\s+(.+)", t)
    r["service_pack"] = m.group(1).strip() if m else None
    r["amministratore"] = "AMMINISTRATORE=SI" in t if "AMMINISTRATORE=" in t else None
    r["64bit"] = ("AMD64" in t) or ("IA64" in t)
    m = re.search(r"([\d.]+)\s+byte disponibili|([\d,]+)\s+bytes free", t)
    if m:
        n = (m.group(1) or m.group(2)).replace(".", "").replace(",", "")
        r["libero_mb"] = int(n) / 1048576.0
    else:
        r["libero_mb"] = None
    return r


# ---------------------------------------------------------------------------
# analisi del rumore di un .wcp
# ---------------------------------------------------------------------------
def analizza_wcp(percorso):
    import numpy as np
    from dlive.devices.simulated import lunghezza_utile, scegli_canale
    w = wcpfile.leggi_wcp(percorso, recupera_extra=True)
    r = {"file": os.path.basename(percorso), "verprog": w.hdr.get("VERPROG", "?"),
         "ctime": w.hdr.get("CTIME", "?"), "nc": w.nc, "dt": w.dt, "nr": w.nr,
         "canali": [w.canale(c) for c in range(w.nc)], "avvisi": list(w.avvisi)}
    if not w.records:
        r["errore"] = "nessun record"
        return r
    c = scegli_canale(w)
    r["canale"] = c
    pezzi = []
    for rec in w.records:
        a = np.asarray(rec.adc[c])
        n = lunghezza_utile(a)
        x = np.asarray(rec.dati[c], dtype=float)[:n]
        sat = (a[:n] >= 32700) | (a[:n] <= -32701)
        if sat.any():
            x = x.copy()
            ultimo = x[0]
            for i in range(len(x)):          # come il programma: ultimo valore valido
                if sat[i]:
                    x[i] = ultimo
                else:
                    ultimo = x[i]
        if len(x) > 10:
            pezzi.append(x)
    fs = 1.0 / w.dt
    r["fs"] = fs
    r["secondi"] = sum(len(p) for p in pezzi) / fs
    if not pezzi or r["secondi"] < 20:
        r["errore"] = "meno di 20 s di segnale"
        return r
    # rumore per banda (Welch semplice)
    seg = int(min(4096, max(256, 2 ** int(np.log2(fs * 8)))))
    spettri = []
    for x in pezzi:
        x = x - np.mean(x)
        fin = np.hanning(seg)
        for i in range(0, len(x) - seg + 1, seg // 2):
            spettri.append(np.abs(np.fft.rfft(x[i:i + seg] * fin)) ** 2 / (fs * (fin ** 2).sum()) * 2)
    P = np.mean(spettri, axis=0)
    f = np.fft.rfftfreq(seg, 1.0 / fs)
    df = f[1] - f[0]

    def banda(lo, hi):
        sel = (f >= lo) & (f < min(hi, fs / 2))
        return float(np.sqrt(P[sel].sum() * df)) if sel.any() else float("nan")
    r["bande"] = [("0-2", banda(0, 2)), ("2-20", banda(2, 20)), ("25-50", banda(25, 50)),
                  ("49-51", banda(49, 51))]
    # righe: picchi oltre 10 volte la mediana locale, tra 2 e fs/2
    righe = []
    for i in range(3, len(P) - 3):
        if f[i] < 2:
            continue
        loc = np.median(P[max(0, i - 12):i + 13])
        if P[i] > 10 * loc and P[i] == P[i - 2:i + 3].max():
            righe.append((float(f[i]), float(10 * np.log10(P[i] / loc))))
    righe.sort(key=lambda t: -t[1])
    r["righe"] = righe[:6]
    notch = [round(fr, 1) for fr, _ in righe if 2 <= fr <= 20 and abs(fr - 50) > 1][:2]
    r["notch_suggeriti"] = notch
    # rumore residuo con i preset (come strumenti/valuta_filtri.py, a fase
    # zero il riferimento; finestre quiete di 4 s)
    from scipy import signal
    ris = {}
    for fc in PRESET:
        if fc >= fs / 2:
            continue
        par = F.ParametriFiltro("bessel", 4, fc, [50.0] + notch)
        rr = []
        for x in pezzi:
            y = np.array(F.filtra_causale(par, x, fs))
            b, aa = signal.iirnotch(50.0, 30.0, fs) if 50.0 < fs / 2 else ([1.0], [1.0])
            if len(x) <= 30:
                continue
            rif = signal.sosfiltfilt(signal.butter(4, min(1.0, fc), fs=fs, output="sos"),
                                     signal.filtfilt(b, aa, x))
            n = int(4 * fs)
            for i0 in range(int(3 * fs), len(x) - n, n):
                if np.ptp(rif[i0:i0 + n]) < 2.0:
                    rr.append(float(np.std(y[i0:i0 + n])))
        ris[fc] = (float(np.percentile(rr, 90)) if rr else float("nan"), len(rr))
    r["preset"] = ris
    ok = [fc for fc, (p90, n) in ris.items() if n and p90 < SOGLIA_RUMORE_MV]
    r["taglio_massimo"] = max(ok) if ok else None
    # si tiene il predefinito (5 Hz) se basta; altrimenti il piu' alto che basta
    # (o il piu' basso disponibile se nessuno basta)
    if TAGLIO_PREDEFINITO in ok:
        r["taglio_suggerito"] = TAGLIO_PREDEFINITO
    elif ok:
        r["taglio_suggerito"] = max(f for f in ok if f < TAGLIO_PREDEFINITO) \
            if any(f < TAGLIO_PREDEFINITO for f in ok) else min(ok)
    else:
        r["taglio_suggerito"] = min(ris) if ris else None
    return r


# ---------------------------------------------------------------------------
def riassumi(cartella, analizza=True):
    out = []
    a = out.append
    cfg = C.Configurazione()
    proposte = {}
    p_txt = os.path.join(cartella, "info_pc_lab.txt")
    if not os.path.isfile(p_txt):
        a("MANCA %s" % p_txt)
        return out, proposte
    with open(p_txt, "rb") as f:
        testo = f.read().decode("cp1252", "replace")
    sz = sezioni(testo)
    a("Cartella: %s" % cartella)
    a((sz.get(0) or ["?"])[0] if sz.get(0) else "")
    a("")
    a("== 1. Installazione")
    s = sistema(sz.get(1, []))
    a("Windows %s, Service Pack: %s, %s, amministratore: %s, C: libero %s MB" % (
        s["versione"] or "?", s["service_pack"] or "nessuno?", "64 bit" if s["64bit"] else "32 bit",
        {True: "si", False: "NO", None: "?"}[s["amministratore"]],
        "%.0f" % s["libero_mb"] if s["libero_mb"] is not None else "?"))
    if s["service_pack"] and not re.search(r"Service Pack [23]", s["service_pack"]):
        a("  ATTENZIONE: Python 3.4 richiede XP SP2 o SP3 (msvcr100.dll): portare SP3")
    if s["amministratore"] is False:
        a("  ATTENZIONE: utente non amministratore: per installa.bat serve la password di un amministratore")
    if s["libero_mb"] is not None and s["libero_mb"] < 150:
        a("  ATTENZIONE: meno di 150 MB liberi su C:: l'installazione non entra")
    a("")
    a("== 2. Impostazioni di WinWCP")
    imp = WI.Impostazioni()
    for percorso, contenuto in file_impostazioni(sz.get(3, [])):
        nome = os.path.basename(percorso.replace("\\", "/")).lower()
        imp.percorsi[nome] = percorso
        try:
            if nome == "winwcp.ini":
                imp.ini = WI.leggi_ini_testo(contenuto)
            elif nome == "lab interface settings.xml":
                imp.interfaccia = WI.leggi_xml_interfaccia_testo(contenuto, percorso)
        except Exception as e:
            imp.errori.append("%s: %s" % (percorso, e))
    for riga in imp.righe():
        a("  " + riga)
    valori, note, avvisi = WI.proposta(imp, cfg["digidata.canale_ingresso"], FS_ACQ)
    for n in note:
        a("  nota: " + n)
    for v in avvisi:
        a("  ATTENZIONE: " + v)
    proposte.update(valori)
    a("")
    a("== 3. Stimolazione")
    log = [x for x in sz.get(4, []) if x.strip()]
    stim = [x for x in log if "stimulus protocol" in x.lower()]
    m = imp.modo_registrazione()
    a("  modo di registrazione in winwcp.ini: %s" % (WI.MODI_REGISTRAZIONE.get(m, "?") if m is not None else "?"))
    a("  righe dei log di WinWCP: %d, di cui 'Stimulus Protocol': %d" % (len(log), len(stim)))
    for x in stim[:10]:
        a("    " + x)
    if stim or m == 0:
        a("  >>> IL LABORATORIO USA LA STIMOLAZIONE DI WINWCP: denoising_live non la genera. "
          "Cambia il progetto: parlarne prima della visita.")
    elif log:
        a("  nessuna traccia di protocolli di stimolazione nei log")
    a("")
    a("== 4. File .wcp sul disco C:")
    el = elenco_wcp(sz.get(2, []))
    a("  %d file" % len(el))
    datati = sorted([e for e in el if e[0]], key=lambda e: e[0], reverse=True)
    for d, dim, p in datati[:8]:
        a("  %s  %s byte  %s" % (d.strftime("%d/%m/%Y %H:%M"), dim, p))
    if datati and datati[0][0].year < WI_ANNO():
        a("  NOTA: il file piu' recente ha data %d: l'orologio del PC e' indietro (WinWCP 5.1.6 e' "
          "del 2016), come nei file di prova; i nomi AAMMGG non dicono l'anno vero" % datati[0][0].year)
    a("")
    a("== 5. Rumore dei .wcp recenti (wcp_recenti/)")
    cart = os.path.join(cartella, "wcp_recenti")
    tagli = []
    notch_tutti = []
    elenco = sorted(f for f in os.listdir(cart) if f.lower().endswith(".wcp")) if os.path.isdir(cart) else []
    if not elenco:
        a("  nessun file")
    for nome in elenco:
        if not analizza:
            a("  %s (non analizzato)" % nome)
            continue
        try:
            r = analizza_wcp(os.path.join(cart, nome))
        except Exception as e:
            a("  %s: non leggibile (%s)" % (nome, e))
            continue
        a("  %s: %s, CTIME %s, %d canali, %g Hz, %d record" % (
            r["file"], r["verprog"], r["ctime"], r["nc"], 1.0 / r["dt"] if r["dt"] else 0, r["nr"]))
        a("    canali: " + ", ".join("Ch.%d '%s' %s YG=%g" % (i, c["nome"], c["unita"], c["yg"])
                                    for i, c in enumerate(r["canali"])))
        if "errore" in r:
            a("    " + r["errore"])
            continue
        a("    segnale su Ch.%d, %.0f s utili" % (r["canale"], r["secondi"]))
        a("    rumore RMS per banda (unita' del canale): " +
          ", ".join("%s Hz %.2f" % (b, v) for b, v in r["bande"]))
        if r["righe"]:
            a("    righe spettrali: " + ", ".join("%.1f Hz (+%.0f dB)" % t for t in r["righe"]))
        a("    rumore residuo (90 perc.) con Bessel 4 + notch 50%s: %s" % (
            "".join(" + %g" % n for n in r["notch_suggeriti"]),
            ", ".join("%g Hz %.2f (%d finestre)" % (fc, p, n) for fc, (p, n) in sorted(r["preset"].items()))))
        a("    taglio suggerito: %s Hz (si tiene %g Hz se il rumore residuo resta sotto %g mV; "
          "massimo con rumore sotto %g mV: %s Hz)" % (r["taglio_suggerito"], TAGLIO_PREDEFINITO,
                                                     SOGLIA_RUMORE_MV, SOGLIA_RUMORE_MV, r["taglio_massimo"]))
        if r["taglio_suggerito"]:
            tagli.append(r["taglio_suggerito"])
        notch_tutti.extend(r["notch_suggeriti"])
    if tagli:
        proposte["filtro.taglio_hz"] = min(tagli)
    if notch_tutti:
        proposte["filtro.notch_hz"] = " ; ".join(["50"] + sorted(set(("%g" % n).replace(".", ",")
                                                                     for n in notch_tutti)))
    a("")
    a("== Da cambiare in config.ini (rispetto ai valori predefiniti)")
    diff = WI.differenze(cfg, {k: v for k, v in proposte.items() if k != "filtro.notch_hz"})
    if "filtro.notch_hz" in proposte and proposte["filtro.notch_hz"] != cfg["filtro.notch_hz"]:
        diff.append(("filtro.notch_hz", cfg["filtro.notch_hz"], proposte["filtro.notch_hz"]))
    if not diff:
        a("  niente: i valori predefiniti vanno bene")
    for k, prima, dopo in diff:
        sez, chiave = k.split(".", 1)
        a("  [%s] %s = %s      (ora: %s)" % (sez, chiave, dopo, prima))
    a("  DLL Axon, WinASPI, schermo, separatore decimale, Python: li rileva da sola la diagnostica "
      "sul PC (passo 1b), non servono modifiche preventive.")
    return out, proposte


def WI_ANNO():
    from dlive.rilevamento import ANNO_WINWCP_516
    return ANNO_WINWCP_516


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cartella", nargs="?", default=PREDEFINITA)
    ap.add_argument("--senza-wcp", action="store_true", help="non analizzare i .wcp (piu' veloce)")
    a = ap.parse_args(argv)
    righe, _ = riassumi(a.cartella, analizza=not a.senza_wcp)
    print("\n".join(righe))
    return 0


if __name__ == "__main__":
    sys.exit(main())
