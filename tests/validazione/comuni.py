# -*- coding: utf-8 -*-
"""Strumenti comuni della validazione oggettiva.

Regola di indipendenza: i valori ATTESI vengono da
  * il segnale sintetico a verita' nota costruito qui,
  * formule chiuse,
  * scipy.signal (progetto e applicazione dei filtri di riferimento),
mai dalle funzioni di filtro del programma.  Del programma si usano solo le
interfacce che usa la GUI (Elaboratore, Sessione, SimulatedDevice...) come
"scatola nera" da misurare.

Il codice e' compatibile con Python 3.4 + numpy 1.15 + scipy 1.2 (Docker, test E1).
"""
from __future__ import division

import datetime
import os
import struct
import sys
import time

import numpy as np

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(os.path.dirname(QUI))
DATI_REALI = os.path.join(RADICE, "riferimenti", "dati")
# riferimenti/ (dati del laboratorio, sorgenti e header Axon) non e' pubblicato
SENZA_DATI = "non eseguibile senza i dati del laboratorio"
if RADICE not in sys.path:
    sys.path.insert(0, RADICE)

FS = 1000.0
# Digidata 1322A: +/-10 V su 16 bit -> 20 V / 65536 = 0,30518 mV per conteggio
MV_PER_CONTEGGIO = 10000.0 / 32768.0
# Scala dichiarata nei file WinWCP (ADCMAX=32677, AD=10, YG=0,001): la usano neo,
# il lettore di riferimento e il programma per convertire i conteggi in mV.
MV_PER_CONTEGGIO_WCP = 10.0 / 32677 / 0.001
# 10 minuti + 64 ms: multiplo di 256 campioni, cosi' il file .wcp sintetico
# e' un solo record esatto (nessun riempimento).
N_SINTETICO = 600064
SEME = 20261120


def mv_in_conteggi(mv):
    """Conversione come il Digidata: arrotondamento e saturazione a 16 bit."""
    c = np.round(np.asarray(mv, dtype=np.float64) / MV_PER_CONTEGGIO)
    return np.clip(c, -32768, 32767).astype(np.int16)


def conteggi_in_mv(c):
    return np.asarray(c, dtype=np.float64) * MV_PER_CONTEGGIO


# ---------------------------------------------------------------------------
# Segnale sintetico a verita' nota
# ---------------------------------------------------------------------------
class Sintetico(object):
    """Verita' S(t) a livelli costanti con gradini ideali + deflessioni a
    semionda di 1 s; rumore come nei dati reali del laboratorio; picchi di
    1-2 campioni a fondo scala (-32768) e a circa +5,6 V, ~3 al minuto."""

    LIVELLI = (20.0, 50.0, 100.0, 120.0, -30.0)

    def __init__(self, n=N_SINTETICO, fs=FS, seme=SEME, picchi_al_minuto=3.0):
        self.n = int(n)
        self.fs = float(fs)
        rng = np.random.RandomState(seme)
        t = np.arange(self.n) / self.fs
        self.t = t
        # --- verita': livelli di 20-120 s ------------------------------------
        verita = np.zeros(self.n)
        self.gradini = []          # indici dei campioni in cui cambia il livello
        self.deflessioni = []      # (inizio, fine) in campioni
        i = 0
        prec = None
        segmenti = []
        while i < self.n:
            dur = int(round(rng.uniform(20.0, 120.0) * self.fs))
            scelte = [v for v in self.LIVELLI if v != prec]
            liv = scelte[rng.randint(len(scelte))]
            fine = min(self.n, i + dur)
            verita[i:fine] = liv
            if i > 0:
                self.gradini.append(i)
            segmenti.append((i, fine, liv))
            prec = liv
            i = fine
        self.segmenti = segmenti
        # deflessioni di 1 s a semionda di 30 mV, in circa meta' dei segmenti
        k = int(self.fs)
        for (a, b, liv) in segmenti:
            if b - a >= 30 * k and rng.rand() < 0.6:
                inizio = a + int(rng.uniform(8, (b - a) / self.fs - 10) * self.fs)
                verita[inizio:inizio + k] += 30.0 * np.sin(np.pi * np.arange(k) / k)
                self.deflessioni.append((inizio, inizio + k))
        self.verita = verita
        # --- rumore ------------------------------------------------------------
        fi = rng.uniform(0, 2 * np.pi, 3)
        self.sinusoidi = (30.0 * np.sin(2 * np.pi * 50.0 * t + fi[0]) +
                          5.0 * np.sin(2 * np.pi * 8.7 * t + fi[1]) +
                          10.0 * np.sin(2 * np.pi * 37.4 * t + fi[2]))
        bianco = rng.randn(self.n)
        spettro = np.fft.rfft(bianco)
        f = np.fft.rfftfreq(self.n, 1.0 / self.fs)
        spettro[(f < 25.0) | (f > 50.0)] = 0.0
        banda = np.fft.irfft(spettro, self.n)
        self.banda = banda * (40.0 / np.sqrt(np.mean(banda ** 2)))     # RMS 40 mV esatti
        self.rumore = self.sinusoidi + self.banda
        # --- picchi ------------------------------------------------------------
        n_picchi = int(round(picchi_al_minuto * self.n / self.fs / 60.0))
        pos = []
        tentativi = 0
        while len(pos) < n_picchi and tentativi < 100000:
            tentativi += 1
            p = int(rng.uniform(5 * self.fs, self.n - 6 * self.fs))
            if all(abs(p - q) > 8 * self.fs for q in pos):
                pos.append(p)
        pos.sort()
        self.picchi = []   # (indice, durata, valore in conteggi)
        for p in pos:
            durata = 1 + rng.randint(2)
            valore = -32768 if rng.rand() < 0.5 else int(round(5600.0 / MV_PER_CONTEGGIO))
            self.picchi.append((p, durata, valore))
        # --- conteggi ----------------------------------------------------------
        self.pulito = mv_in_conteggi(self.verita)                   # senza rumore
        self.rumoroso_senza_picchi = mv_in_conteggi(self.verita + self.rumore)
        self.rumoroso = self.rumoroso_senza_picchi.copy()
        self.maschera_picchi = np.zeros(self.n, dtype=bool)
        for p, d, v in self.picchi:
            self.rumoroso[p:p + d] = v
            self.maschera_picchi[p:p + d] = True

    def senza_picchi_tenuto(self):
        """Il segnale con i picchi sostituiti dall'ultimo campione buono
        (posizioni note dalla costruzione, non rilevate)."""
        x = self.rumoroso.copy()
        for p, d, v in self.picchi:
            x[p:p + d] = x[p - 1]
        return x

    def tratti_quieti(self, dopo_gradino_s=2.0, dopo_picco_s=1.0, minimo_s=10.0):
        """Maschera dei campioni nei tratti quieti: verita' costante da almeno
        2 s (gradini e deflessioni), nessun picco nell'ultimo secondo, tratto
        lungo almeno 10 s."""
        fs = self.fs
        ok = np.ones(self.n, dtype=bool)
        ok[:int(dopo_gradino_s * fs)] = False
        g = int(dopo_gradino_s * fs)
        for i in self.gradini:
            ok[i:i + g] = False
        for a, b in self.deflessioni:
            ok[a:b + g] = False
        q = int(dopo_picco_s * fs)
        for p, d, v in self.picchi:
            ok[p:p + d + q] = False
        # solo tratti contigui lunghi almeno minimo_s
        out = np.zeros(self.n, dtype=bool)
        for a, b in tratti(ok):
            if b - a >= minimo_s * fs:
                out[a:b] = True
        return out


def tratti(maschera):
    """Coppie (inizio, fine) dei tratti True contigui."""
    m = np.concatenate(([False], np.asarray(maschera, dtype=bool), [False]))
    d = np.diff(m.astype(np.int8))
    inizi = np.flatnonzero(d == 1)
    fini = np.flatnonzero(d == -1)
    return list(zip(inizi.tolist(), fini.tolist()))


_CACHE = {}


def sintetico():
    if "s" not in _CACHE:
        _CACHE["s"] = Sintetico()
    return _CACHE["s"]


# ---------------------------------------------------------------------------
# Misure indipendenti
# ---------------------------------------------------------------------------
def ampiezza_sinusoide(x, f, fs=FS):
    """Ampiezza della componente a frequenza f (minimi quadrati con seno,
    coseno e costante)."""
    x = np.asarray(x, dtype=np.float64)
    t = np.arange(len(x)) / fs
    A = np.column_stack((np.sin(2 * np.pi * f * t), np.cos(2 * np.pi * f * t), np.ones(len(x))))
    c = np.linalg.lstsq(A, x, rcond=-1)[0]
    return float(np.hypot(c[0], c[1]))


def ritardo_50(y, inizio, livello0, livello1, fs=FS):
    """Istante (s) dopo 'inizio' in cui y attraversa il 50 % del gradino,
    con interpolazione lineare."""
    meta = livello0 + 0.5 * (livello1 - livello0)
    seg = np.asarray(y[inizio:], dtype=np.float64)
    if livello1 > livello0:
        idx = np.flatnonzero(seg >= meta)
    else:
        idx = np.flatnonzero(seg <= meta)
    if not len(idx):
        return None
    i = int(idx[0])
    if i == 0:
        return 0.0
    v0, v1 = seg[i - 1], seg[i]
    frac = (meta - v0) / (v1 - v0) if v1 != v0 else 0.0
    return (i - 1 + frac) / fs


def potenza_banda(x, fs, f1, f2):
    """Potenza (mV^2) nella banda [f1, f2] dallo spettro di Welch."""
    from scipy import signal
    nper = int(min(len(x), 4 * fs))
    f, p = signal.welch(np.asarray(x, dtype=np.float64), fs=fs, nperseg=nper)
    m = (f >= f1) & (f <= f2)
    return float(np.sum(p[m]) * (f[1] - f[0]))


# ---------------------------------------------------------------------------
# Riferimento indipendente: scipy.signal
# ---------------------------------------------------------------------------
def sos_riferimento(tipo="bessel", ordine=4, fc=5.0, fs=FS, notch=(50.0,), q=30.0,
                    passabasso=True):
    from scipy import signal
    sez = []
    for f0 in notch:
        b, a = signal.iirnotch(f0 / (fs / 2.0), q)
        sez.append(np.concatenate((b, a)))
    if passabasso:
        wn = fc / (fs / 2.0)
        if tipo == "bessel":
            sos = signal.bessel(ordine, wn, btype="low", norm="mag", output="sos")
        else:
            sos = signal.butter(ordine, wn, btype="low", output="sos")
        sez.extend(list(sos))
    return np.array(sez)


def filtra_riferimento(sos, x):
    """Filtro causale scipy, partendo a regime sul primo campione."""
    from scipy import signal
    x = np.asarray(x, dtype=np.float64)
    zi = signal.sosfilt_zi(sos) * x[0]
    y, _ = signal.sosfilt(sos, x, zi=zi)
    return y


# ---------------------------------------------------------------------------
# Il programma come "scatola nera"
# ---------------------------------------------------------------------------
def configurazione_default():
    from dlive import config
    return config.Configurazione(None, RADICE)


def parametri(tipo="bessel", ordine=4, fc=5.0, notch=(50.0,), q=30.0, passabasso=True):
    from dlive import filters
    return filters.ParametriFiltro(tipo, ordine, fc, list(notch), q, passabasso)


def elaboratore(par, fs=FS, decimazione=1, cal=None):
    """Costruito come lo costruisce Sessione.avvia_anteprima con la
    configurazione di default (soglia di saturazione 32700, picchi > 500
    unita' per meno di 50 ms).  cal: calibrazione del canale (yg, ad, adcmax)
    se diversa da quella di default (mV, YG = 0,001)."""
    from dlive import filters
    cfg = configurazione_default()
    if cal is None:
        conv = cfg["digidata.range_v"] / (32677 * cfg["calibrazione.yg"])
    else:
        conv = cal["ad"] / (cal["adcmax"] * cal["yg"])
    return filters.Elaboratore(par, fs, decimazione, cfg["filtro.soglia_saturazione"],
                               soglia_picco=cfg["filtro.soglia_picchi_mv"] / conv,
                               max_campioni_picco=int(round(cfg["filtro.durata_max_picco_ms"] / 1000.0 * fs)))


def filtra_programma(conteggi, par, blocchi=None, cambi=None, fs=FS, cal=None, in_conteggi=False):
    """Passa i conteggi al programma (Elaboratore) a blocchi e restituisce
    l'uscita filtrata alla frequenza di acquisizione, in mV.

    blocchi: None (un blocco unico), un intero (lunghezza fissa) o una lista di
             lunghezze;  cambi: {indice_campione: ParametriFiltro} applicati
             prima di quel campione (come un comando della GUI)."""
    e = elaboratore(par, fs, cal=cal)
    x = np.asarray(conteggi)
    n = len(x)
    tagli = set([0, n])
    if blocchi is None:
        pass
    elif isinstance(blocchi, int):
        tagli.update(range(0, n, blocchi))
    else:
        p = 0
        for b in blocchi:
            p += int(b)
            if p >= n:
                break
            tagli.add(p)
    cambi = cambi or {}
    tagli.update(k for k in cambi if 0 < k < n)
    tagli = sorted(tagli)
    out = []
    for a, b in zip(tagli[:-1], tagli[1:]):
        if a in cambi and a > 0:
            e.riconfigura(cambi[a])
        y, _ = e.elabora(x[a:b])
        out.extend(y)
    if in_conteggi:
        return np.array(out, dtype=np.float64)
    return np.array(out, dtype=np.float64) * MV_PER_CONTEGGIO


# ---------------------------------------------------------------------------
# File .wcp: scrittore minimo e lettore di riferimento, indipendenti dal programma
# ---------------------------------------------------------------------------
def scrivi_wcp_semplice(percorso, conteggi, dt, nome="Sint", ident="validazione", unita="mV",
                        yg="0,001", yz="0"):
    """Un solo canale, un solo record (formato V9 come WinWCP 5.1.6).
    yg e yz come testo dell'intestazione (per copiarli da un altro file)."""
    c = np.asarray(conteggi).astype("<i2")
    n = len(c)
    resto = (-n) % 256
    if resto:
        c = np.concatenate((c, np.full(resto, c[-1], dtype="<i2")))
    nbd = len(c) * 2 // 512
    ora = datetime.datetime(2026, 11, 20, 10, 0, 0)
    righe = ["VER=9", "VERPROG=V5.1.6", "CTIME=20/11/2026 10:00:00", "RTIMESECS=36000",
             "RTIME=20/11/2026 10:00:00", "NBH=1024", "ADCMAX=32677", "NC=1", "NBA=2",
             "NBD=%d" % nbd, "AD=10", "NR=1", ("DT=%.6g" % dt).replace(".", ","), "NZ=20",
             "YO0=0", "YU0=%s" % unita, "YN0=%s" % nome, "YG0=%s" % yg, "YZ0=%s" % yz, "YR0=-1",
             "ID=%s" % ident]
    testo = ("\r\n".join(righe) + "\r\n").encode("latin-1")
    testo += b"\x00" * (1024 - len(testo))
    blocco = b"ACCEPTED" + b"TEST" + struct.pack("<fff", 1.0, 0.0, dt) + struct.pack("<f", 10.0)
    blocco += b"\x00" * (1024 - len(blocco))
    with open(percorso, "wb") as f:
        f.write(testo)
        f.write(blocco)
        f.write(c.tobytes())
    del ora
    return percorso


def _num(s):
    return float(s.replace(",", "."))


def leggi_wcp_riferimento(path, nr_forzato=None):
    """Lettore di riferimento del documento di progetto (sezione 8).
    Restituisce (hdr, ordine_chiavi, records); records: dict con 'adc'
    (n x nc, int16) e 'data' (nc x n, mV)."""
    with open(path, "rb") as f:
        raw = f.read()
    txt = raw[:1024].decode("latin-1").split("\x00")[0]
    hdr = {}
    ordine = []
    for line in txt.replace("\r", "\n").split("\n"):
        if "=" in line:
            k, v = line.split("=", 1)
            hdr[k.strip()] = v.strip()
            ordine.append(k.strip())
    nc, nr = int(hdr["NC"]), int(hdr["NR"])
    nbh, nba, nbd = int(hdr["NBH"]), int(hdr["NBA"]), int(hdr["NBD"])
    if nr_forzato is not None:
        nr = nr_forzato
    elif nr == 0:
        nr = (len(raw) - nbh) // ((nba + nbd) * 512)
    adcmax = _num(hdr["ADCMAX"])
    recs = []
    for r in range(nr):
        off = nbh + r * (nba + nbd) * 512
        ab = raw[off:off + nba * 512]
        status = ab[0:8].decode("latin-1")
        rtype = ab[8:12].decode("latin-1")
        group, t, dt = struct.unpack("<fff", ab[12:24])
        vmax = struct.unpack("<" + "f" * nc, ab[24:24 + 4 * nc])
        ident = ab[24 + 4 * nc:24 + 4 * nc + 16].decode("latin-1").split("\x00")[0]
        d = np.frombuffer(raw[off + nba * 512: off + (nba + nbd) * 512], dtype="<i2")
        n = len(d) // nc
        d = d[: n * nc].reshape(n, nc)
        chans = []
        for c in range(nc):
            yo = int(hdr["YO%d" % c])
            yg = _num(hdr["YG%d" % c])
            yz = _num(hdr["YZ%d" % c])
            chans.append((d[:, yo].astype(float) - yz) * vmax[c] / adcmax / yg)
        recs.append(dict(status=status, type=rtype, group=group, time=t, dt=dt, vmax=vmax,
                         ident=ident, data=np.array(chans), adc=d))
    return hdr, ordine, recs


def concatena_canale(recs, canale=0):
    if not recs:
        return np.zeros(0, dtype=np.int16)
    return np.concatenate([r["adc"][:, canale] for r in recs])


# ---------------------------------------------------------------------------
# Catena completa come la costruisce la GUI
# ---------------------------------------------------------------------------
def sessione_come_gui(dev, cartella, par=None):
    """Sessione costruita con gli stessi argomenti di gui._crea_sessione e la
    configurazione di default."""
    from dlive import filters
    from dlive.acquisizione import Sessione
    c = configurazione_default()
    if par is None:
        par = filters.ParametriFiltro(c["filtro.tipo"], c["filtro.ordine"], c["filtro.taglio_hz"],
                                      c.notch(), c["filtro.q_notch"])
    return Sessione(dev, par,
                    {"cartella": cartella,
                     "fs_salvataggio": c["salvataggio.frequenza_salvataggio_hz"],
                     "durata_record_s": c["salvataggio.durata_record_s"],
                     "separatore": c.separatore()},
                    lpf8_taglio=c["lpf8.taglio_hz"], lpf8_guadagno=c["lpf8.guadagno"],
                    soglia_saturazione=c["filtro.soglia_saturazione"],
                    soglia_picchi_unita=c["filtro.soglia_picchi_mv"],
                    durata_max_picco_s=c["filtro.durata_max_picco_ms"] / 1000.0,
                    intervallo_scrittura=c["salvataggio.intervallo_scrittura_s"],
                    spazio_minimo_mb=c["generale.spazio_minimo_mb"])


def attendi_fine(s, timeout=900):
    t0 = time.time()
    while s.in_corso and time.time() - t0 < timeout:
        time.sleep(0.05)
    return not s.in_corso


def esegui_catena(percorso_wcp, cartella, par=None, comandi_iniziali=(), **kw_dev):
    """Sorgente .wcp -> SimulatedDevice (senza sovracampionamento, non in tempo
    reale) -> Sessione -> registrazione dal primo campione.  Restituisce la
    sessione terminata e la registrazione."""
    from dlive.devices.simulated import SimulatedDevice
    opz = dict(record=1, canale=0, velocita=1.0, sovracampiona=False, tempo_reale=False,
               ciclo=False)
    opz.update(kw_dev)
    dev = SimulatedDevice(percorso_wcp, **opz)
    dev.apri()
    s = sessione_come_gui(dev, cartella, par)
    s.comandi.put(("avvia_reg", None))
    for c in comandi_iniziali:
        s.comandi.put(c)
    s.avvia_anteprima()
    if not attendi_fine(s):
        s.ferma()
        raise RuntimeError("la sessione non si e' fermata")
    return s, s.ultima_registrazione, dev


def prefisso_uguale(a, b):
    """Numero di campioni iniziali uguali."""
    n = min(len(a), len(b))
    d = np.flatnonzero(np.asarray(a[:n]) != np.asarray(b[:n]))
    return int(d[0]) if len(d) else n


def campioni_validi(percorso_raw, percorso_json, sorgente):
    """Campioni del grezzo salvato uguali alla sorgente, tenendo conto del
    campione d'inizio della registrazione (dal JSON)."""
    import io as _io
    import json as _json
    inizio = 0
    try:
        with _io.open(percorso_json, encoding="utf-8") as f:
            inizio = int(_json.load(f)["acquisizione"]["campione_inizio"])
    except (IOError, OSError, ValueError, KeyError):
        pass
    _, _, recs = leggi_wcp_riferimento(percorso_raw)
    return prefisso_uguale(concatena_canale(recs), sorgente[inizio:])


# ---------------------------------------------------------------------------
# Errore di scrittura simulato (B9)
# ---------------------------------------------------------------------------
class FileGuasto(object):
    """Avvolge il file del programma: dopo l'attivazione ogni scrittura fallisce
    come su un disco pieno (ENOSPC)."""

    def __init__(self, f, guasto):
        self._f = f
        self._guasto = guasto

    def write(self, b):
        if self._guasto["attivo"]:
            raise IOError(28, "No space left on device (simulato)")
        return self._f.write(b)

    def flush(self):
        if self._guasto["attivo"]:
            raise IOError(28, "No space left on device (simulato)")
        return self._f.flush()

    def __getattr__(self, k):
        return getattr(self._f, k)


def esegui_b9(sorgente, cartella, attesa_prima=6.0, attesa_dopo=6.0):
    """Registrazione in tempo reale con disco 'pieno' dopo attesa_prima secondi.
    Restituisce un dizionario con le misure (usato anche dallo scenario GUI)."""
    from dlive.devices.simulated import SimulatedDevice
    dev = SimulatedDevice(sorgente, record=1, canale=0, velocita=1.0, sovracampiona=False,
                          tempo_reale=True, ciclo=False)
    dev.apri()
    s = sessione_come_gui(dev, cartella)
    s.comandi.put(("avvia_reg", None))
    s.avvia_anteprima()
    t0 = time.time()
    while s.reg is None and time.time() - t0 < 5:
        time.sleep(0.02)
    time.sleep(attesa_prima)
    guasto = {"attivo": False}
    reg = s.reg
    reg.raw._f = FileGuasto(reg.raw._f, guasto)
    reg.filt._f = FileGuasto(reg.filt._f, guasto)
    guasto["attivo"] = True
    campioni_al_guasto = s.campioni
    time.sleep(attesa_dopo)
    return s, reg, campioni_al_guasto


def valuta_b9(s, reg, campioni_al_guasto, messaggi, log, leggi_neo=None):
    sorg = sintetico().rumoroso
    continua = s.campioni > campioni_al_guasto + 3 * FS
    nel_log = "ERRORE DI SCRITTURA" in log
    in_gui = any(t == "errore_scrittura" for t, _ in messaggi)
    try:
        validi = campioni_validi(reg.percorso_raw, reg.percorso_json, sorg)
        leggi_wcp_riferimento(reg.percorso_filt)
        leggibili = validi > 0
        if leggi_neo is not None:
            leggi_neo(reg.percorso_raw)
            leggi_neo(reg.percorso_filt)
    except Exception:
        validi = 0
        leggibili = False
    return {"continua": continua, "nel_log": nel_log, "messaggio_gui": in_gui,
            "leggibili": leggibili, "secondi_validi": validi / FS,
            "secondi_al_guasto": campioni_al_guasto / FS,
            "secondi_totali": s.campioni / FS}
