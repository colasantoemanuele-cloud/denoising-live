# -*- coding: utf-8 -*-
"""Filtri digitali causali per l'uso in tempo reale.

* Progettazione senza scipy: prototipi analogici (poli di Butterworth calcolati,
  poli di Bessel tabulati), conversione in frequenza con pre-distorsione e
  trasformazione bilineare, una sezione del secondo ordine (SOS) per ogni
  coppia di poli.  Stesso risultato di scipy.signal.butter/bessel(norm='mag')
  con output='sos' (verificato nei test).
* Notch: stessa formula di scipy.signal.iirnotch.
* Applicazione: catena di sezioni in forma diretta II trasposta, float64, con
  stato conservato tra un blocco e l'altro (filtrare a blocchi da' lo stesso
  risultato che filtrare tutto in una volta).

Il nucleo ricorsivo e' in Python puro in entrambi i percorsi (con e senza
numpy): un filtro IIR non si vettorializza con numpy senza scipy, e a 1000
campioni/s con poche sezioni il costo e' piccolo (vedi README, prestazioni).
"""
import math

from . import compat

# Poli del prototipo di Bessel normalizzato in modulo (-3 dB a 1 rad/s),
# semipiano superiore; im == 0 indica un polo reale.  Generati con
# scipy.signal.besselap(n, norm='mag') e verificati nei test.
POLI_BESSEL = {
    1: [(-0.9999999999999993, 0.0)],
    2: [(-1.1016013305921608, 0.636009824757034)],
    3: [(-1.0474091610089349, 0.9992644362806369), (-1.3226757999104441, 0.0)],
    4: [(-0.995208764350272, 1.257105739454664), (-1.3700678305514422, 0.41024971749375155)],
    5: [(-0.9576765485626815, 1.4711243207303943), (-1.3808773258604392, 0.717909587626768),
        (-1.5023162714474785, 0.0)],
    6: [(-0.9306565229468591, 1.6618632689425918), (-1.3818580975965642, 0.9714718907115716),
        (-1.5714904036160318, 0.32089637422262396)],
    7: [(-0.9098677806234705, 1.8364513530363944), (-1.378903216795475, 1.1915667778006531),
        (-1.6120387662261257, 0.589244506931472), (-1.6843681792731817, 0.0)],
    8: [(-0.8928697188471375, 1.9983258436413065), (-1.3738412176373769, 1.388356575877563),
        (-1.6369394181268888, 0.8227956251396998), (-1.757408400401653, 0.2728675751022327)],
    9: [(-0.8783992761609548, 2.1498005243133265), (-1.367588309792908, 1.567733712237272),
        (-1.6523964845788381, 1.0313895669844126), (-1.8071705349621046, 0.5123837305749049),
        (-1.856600501228007, 0.0)],
    10: [(-0.8657569017083749, 2.2926048309824743), (-1.3606922783845439, 1.7335057426614757),
         (-1.6618102413621516, 1.2211002185791606), (-1.842196244524833, 0.7272575977574774),
         (-1.9276196913722756, 0.24162347097153306)],
}

TIPI = ("bessel", "butterworth")
ORDINE_MAX = 10


def poli_butterworth(n):
    """Poli del prototipo di Butterworth (-3 dB a 1 rad/s), semipiano superiore."""
    poli = []
    for k in range(n):
        ang = math.pi * (2 * k + n + 1) / (2.0 * n)
        re, im = math.cos(ang), math.sin(ang)
        if im > 1e-12:
            poli.append((re, im))
        elif abs(im) <= 1e-12:
            poli.append((re, 0.0))
    poli.sort(key=lambda p: -p[1])
    return poli


def prototipo(tipo, ordine):
    tipo = tipo.lower()
    ordine = int(ordine)
    if ordine < 1 or ordine > ORDINE_MAX:
        raise ValueError("ordine del filtro fuori dai limiti (1..%d): %d" % (ORDINE_MAX, ordine))
    if tipo == "bessel":
        return list(POLI_BESSEL[ordine])
    if tipo == "butterworth":
        return poli_butterworth(ordine)
    raise ValueError("tipo di filtro sconosciuto: %r (usa bessel o butterworth)" % tipo)


def progetta_passabasso(tipo, ordine, fc, fs):
    """Restituisce la lista di sezioni (b0, b1, b2, a1, a2), con a0 = 1."""
    fc = float(fc)
    fs = float(fs)
    if not (0 < fc < fs / 2.0):
        raise ValueError("frequenza di taglio %.4g Hz non valida per fs=%.4g Hz" % (fc, fs))
    K = 2.0 * fs
    wc = K * math.tan(math.pi * fc / fs)         # pre-distorsione
    sezioni = []
    for re, im in prototipo(tipo, ordine):
        re *= wc
        im *= wc
        if im > 0:
            A1 = -2.0 * re
            A0 = re * re + im * im
            D = K * K + A1 * K + A0
            b0 = A0 / D
            sezioni.append((b0, 2.0 * b0, b0, (2.0 * A0 - 2.0 * K * K) / D,
                            (K * K - A1 * K + A0) / D))
        else:
            s = -re
            D = K + s
            b0 = s / D
            sezioni.append((b0, b0, 0.0, (s - K) / D, 0.0))
    return sezioni


def progetta_notch(f0, q, fs):
    """Come scipy.signal.iirnotch(f0, Q, fs)."""
    f0 = float(f0)
    fs = float(fs)
    if not (0 < f0 < fs / 2.0):
        raise ValueError("frequenza del notch %.4g Hz non valida per fs=%.4g Hz" % (f0, fs))
    w0 = 2.0 * f0 / fs
    bw = w0 / float(q)
    bw *= math.pi
    w0 *= math.pi
    beta = math.tan(bw / 2.0)                    # gb = 1/sqrt(2)
    gain = 1.0 / (1.0 + beta)
    c = math.cos(w0)
    return (gain, -2.0 * c * gain, gain, -2.0 * gain * c, 2.0 * gain - 1.0)


def risposta_frequenza(sezioni, freq, fs):
    """Modulo e fase della risposta della catena alle frequenze date (Hz)."""
    out = []
    for f in freq:
        w = 2.0 * math.pi * f / fs
        z1 = complex(math.cos(-w), math.sin(-w))
        z2 = z1 * z1
        h = complex(1.0, 0.0)
        for b0, b1, b2, a1, a2 in sezioni:
            h *= (b0 + b1 * z1 + b2 * z2) / (1.0 + a1 * z1 + a2 * z2)
        out.append(h)
    return out


def attenuazione_db(sezioni, f, fs):
    h = risposta_frequenza(sezioni, [f], fs)[0]
    return -20.0 * math.log10(max(abs(h), 1e-300))


def guadagno_dc(sezioni):
    g = 1.0
    for b0, b1, b2, a1, a2 in sezioni:
        g *= (b0 + b1 + b2) / (1.0 + a1 + a2)
    return g


class ParametriFiltro(object):
    """Parametri del filtro digitale (passa-basso + notch)."""

    def __init__(self, tipo="bessel", ordine=4, fc=5.0, notch=None, q_notch=30.0,
                 passabasso_attivo=True):
        self.tipo = tipo
        self.ordine = int(ordine)
        self.fc = float(fc)
        self.notch = list(notch) if notch is not None else [50.0]
        self.q_notch = float(q_notch)
        self.passabasso_attivo = bool(passabasso_attivo)

    def copia(self, **modifiche):
        p = ParametriFiltro(self.tipo, self.ordine, self.fc, list(self.notch),
                            self.q_notch, self.passabasso_attivo)
        for k, v in modifiche.items():
            setattr(p, k, v)
        return p

    def come_dict(self):
        return {"tipo": self.tipo, "ordine": self.ordine, "taglio_hz": self.fc,
                "notch_hz": list(self.notch), "q_notch": self.q_notch,
                "passabasso_attivo": self.passabasso_attivo}

    def descrizione(self):
        s = []
        if self.passabasso_attivo:
            s.append("%s ord.%d %s Hz" % (self.tipo.capitalize(), self.ordine,
                                          _fmt(self.fc)))
        else:
            s.append("passa-basso escluso")
        if self.notch:
            s.append("notch " + ",".join(_fmt(f) for f in self.notch) + " Hz")
        return ", ".join(s)

    def sezioni(self, fs):
        sez = []
        for f0 in self.notch:
            if 0 < f0 < fs / 2.0:
                sez.append(progetta_notch(f0, self.q_notch, fs))
        if self.passabasso_attivo:
            sez.extend(progetta_passabasso(self.tipo, self.ordine, self.fc, fs))
        return sez

    def __eq__(self, o):
        return isinstance(o, ParametriFiltro) and self.come_dict() == o.come_dict()

    def __ne__(self, o):
        return not self.__eq__(o)


def _fmt(v):
    return ("%.3g" % v).replace(".", ",")


def controlla_parametri(par, fs_acq, fs_salva, taglio_lpf8=None):
    """Restituisce (errori, avvisi): liste di stringhe in italiano."""
    errori = []
    avvisi = []
    if par.tipo not in TIPI:
        errori.append("Tipo di filtro sconosciuto: %s" % par.tipo)
    if not (1 <= par.ordine <= ORDINE_MAX):
        errori.append("Ordine del filtro fuori dai limiti (1-%d)" % ORDINE_MAX)
    if par.passabasso_attivo:
        if not (0 < par.fc < fs_acq / 2.0):
            errori.append("Taglio %.3g Hz non valido (deve essere tra 0 e %.4g Hz)"
                          % (par.fc, fs_acq / 2.0))
        elif par.fc > 0.4 * fs_salva:
            avvisi.append("Taglio %.3g Hz troppo vicino a meta' della frequenza di salvataggio "
                          "(%.4g Hz): rischio di aliasing nel filtrato" % (par.fc, fs_salva))
        if taglio_lpf8 and par.fc > taglio_lpf8:
            avvisi.append("Il taglio digitale (%.3g Hz) e' superiore a quello dell'LPF-8 "
                          "(%.3g Hz): il filtro digitale non toglie nulla in piu' sopra "
                          "%.3g Hz" % (par.fc, taglio_lpf8, taglio_lpf8))
    else:
        avvisi.append("Passa-basso digitale escluso: il filtrato non e' protetto "
                      "dall'aliasing nella riduzione di frequenza")
    for f0 in par.notch:
        if not (0 < f0 < fs_acq / 2.0):
            errori.append("Notch a %.4g Hz non valido con fs=%.4g Hz" % (f0, fs_acq))
    if par.q_notch <= 0:
        errori.append("Q del notch deve essere positivo")
    return errori, avvisi


class CatenaSOS(object):
    """Catena di sezioni del secondo ordine, forma diretta II trasposta, float64."""

    def __init__(self, sezioni):
        self.sezioni = [tuple(float(c) for c in s) for s in sezioni]
        self.stato = [[0.0, 0.0] for _ in self.sezioni]

    def azzera(self):
        for st in self.stato:
            st[0] = 0.0
            st[1] = 0.0

    def regime(self, x):
        """Imposta lo stato di regime per un ingresso costante x (nessun transitorio)."""
        for (b0, b1, b2, a1, a2), st in zip(self.sezioni, self.stato):
            g = (b0 + b1 + b2) / (1.0 + a1 + a2)
            y = g * x
            z2 = b2 * x - a2 * y
            z1 = b1 * x - a1 * y + z2
            st[0] = z1
            st[1] = z2
            x = y

    def elabora(self, blocco):
        """blocco: sequenza di numeri; restituisce una lista di float."""
        buf = blocco
        for (b0, b1, b2, a1, a2), st in zip(self.sezioni, self.stato):
            z1, z2 = st
            out = []
            app = out.append
            for x in buf:
                y = b0 * x + z1
                z1 = b1 * x - a1 * y + z2
                z2 = b2 * x - a2 * y
                app(y)
            st[0] = z1
            st[1] = z2
            buf = out
        if not self.sezioni:
            buf = [float(v) for v in blocco]
        return buf


def filtra_causale(par, x, fs, regime_iniziale=True):
    """Filtra un intero segnale in un colpo solo (riferimento offline causale)."""
    c = CatenaSOS(par.sezioni(fs))
    if hasattr(x, "tolist"):
        x = x.tolist()
    if regime_iniziale and len(x):
        c.regime(x[0])
    return c.elabora(x)


class Elaboratore(object):
    """Catena di elaborazione in tempo reale per un canale:

      conteggi ADC grezzi -> blocco dei picchi di saturazione -> filtro SOS
      -> (filtrato alla frequenza di acquisizione, per il grafico)
      -> decimazione -> conteggi int16 da salvare.

    Il cambio dei parametri e' immediato e senza buchi: il nuovo filtro parte
    dallo stato di regime al livello attuale del filtrato e la sua uscita viene
    miscelata linearmente con quella del vecchio per un breve tempo.
    """

    def __init__(self, par, fs, decimazione=1, soglia_saturazione=32700,
                 durata_dissolvenza=None, soglia_picco=0, max_campioni_picco=0):
        self.fs = float(fs)
        self.decimazione = max(1, int(decimazione))
        self.soglia = int(soglia_saturazione)
        self.soglia_picco = float(soglia_picco)       # conteggi; 0 = disattivato
        self.max_picco = int(max_campioni_picco)
        self.par = par
        self.catena = CatenaSOS(par.sezioni(self.fs))
        self.vecchia = None
        self.dissolvenza_tot = 0
        self.dissolvenza_pos = 0
        self.durata_dissolvenza = durata_dissolvenza
        self.ultimo_valido = None
        self.ultima_uscita = None
        self.fase_dec = 0
        self.campioni = 0
        self.saturati_tot = 0           # campioni sostituiti (saturazione + picchi)
        self.eventi_saturazione = 0     # eventi (sequenze consecutive)
        self.picchi_tot = 0
        self._stato_art = None          # None, "saturazione" o "picco"
        self._inizio_art = 0
        self._durata_picco = 0
        self.nuovi_eventi = []          # (indice_campione, durata_campioni, tipo)

    def riconfigura(self, par):
        nuova = CatenaSOS(par.sezioni(self.fs))
        if self.ultima_uscita is not None:
            nuova.regime(self.ultima_uscita)
            # se una dissolvenza e' gia' in corso la si chiude: la "vecchia"
            # diventa il filtro che era in arrivo
            self.vecchia = self.catena
            d = self.durata_dissolvenza
            if d is None:
                fc = par.fc if par.passabasso_attivo else 5.0
                fc_old = self.par.fc if self.par.passabasso_attivo else 5.0
                d = min(2.0, max(0.25, 1.5 / min(fc, fc_old)))
            self.dissolvenza_tot = max(1, int(round(d * self.fs)))
            self.dissolvenza_pos = 0
        self.catena = nuova
        self.par = par

    def _chiudi_artefatto(self, idx):
        if self._stato_art is not None:
            self.nuovi_eventi.append((self._inizio_art, idx - self._inizio_art, self._stato_art))
            self._stato_art = None

    def _apri_artefatto(self, idx, tipo):
        if self._stato_art != tipo:
            self._chiudi_artefatto(idx)
            self._stato_art = tipo
            self._inizio_art = idx
            self.eventi_saturazione += 1

    def _togli_saturazione(self, blocco):
        """Sostituisce con l'ultimo valore valido i campioni saturati e i
        picchi isolati (scostamento > soglia_picco per meno di max_picco campioni)."""
        soglia = self.soglia
        sp = self.soglia_picco
        mp = self.max_picco
        out = []
        app = out.append
        ultimo = self.ultimo_valido if self.ultimo_valido is not None else 0.0
        idx = self.campioni
        for v in blocco:
            if v >= soglia or v <= -soglia - 1:
                self.saturati_tot += 1
                self._apri_artefatto(idx, "saturazione")
                app(ultimo)
            elif sp > 0 and abs(v - ultimo) > sp and self._durata_picco < mp:
                self._durata_picco += 1
                self.saturati_tot += 1
                self.picchi_tot += 1
                self._apri_artefatto(idx, "picco")
                app(ultimo)
            else:
                if self._durata_picco >= mp and self._stato_art == "picco":
                    # lo scostamento dura troppo: e' segnale vero, lo si accetta
                    self._stato_art = "picco_accettato"
                self._durata_picco = 0
                self._chiudi_artefatto(idx)
                ultimo = float(v)
                app(ultimo)
            idx += 1
        self.ultimo_valido = ultimo
        return out

    def primo_valore(self, v):
        """Inizializza il filtro a regime sul primo valore (evita il gradino iniziale)."""
        self.catena.regime(float(v))
        self.ultima_uscita = float(v)
        self.ultimo_valido = float(v)

    def elabora(self, blocco):
        """blocco: conteggi ADC (lista, array o numpy) del canale.
        Restituisce (filtrato_acq: lista di float, filtrato_salva: lista di int)."""
        if hasattr(blocco, "tolist"):
            blocco = blocco.tolist()
        n = len(blocco)
        if n == 0:
            return [], []
        if self.ultima_uscita is None:
            primo = None
            for v in blocco:
                if -self.soglia - 1 < v < self.soglia:
                    primo = v
                    break
            self.primo_valore(primo if primo is not None else 0.0)
        x = self._togli_saturazione(blocco)
        y = self.catena.elabora(x)
        if self.vecchia is not None:
            yv = self.vecchia.elabora(x)
            tot = float(self.dissolvenza_tot)
            pos = self.dissolvenza_pos
            for i in range(n):
                if pos >= tot:
                    break
                w = (pos + 1) / tot
                y[i] = w * y[i] + (1.0 - w) * yv[i]
                pos += 1
            self.dissolvenza_pos = pos
            if pos >= tot:
                self.vecchia = None
        self.ultima_uscita = y[-1]
        self.campioni += n
        # decimazione
        D = self.decimazione
        inizio = (-self.fase_dec) % D
        dec = []
        for v in y[inizio::D]:
            r = int(round(v))
            if r > 32767:
                r = 32767
            elif r < -32768:
                r = -32768
            dec.append(r)
        self.fase_dec = (self.fase_dec + n) % D
        return y, dec

    def preleva_eventi(self):
        e = self.nuovi_eventi
        self.nuovi_eventi = []
        return e


def ritardo_gradino(par, fs, durata=None):
    """Ritardo al 50 % e sovraelongazione (%) della risposta al gradino."""
    durata = durata or max(2.0, 20.0 / max(par.fc, 0.1))
    n = int(durata * fs)
    c = CatenaSOS(par.sezioni(fs))
    y = c.elabora([1.0] * n)
    t50 = None
    for i, v in enumerate(y):
        if v >= 0.5:
            # interpolazione lineare
            v0 = y[i - 1] if i > 0 else 0.0
            frac = (0.5 - v0) / (v - v0) if v != v0 else 0.0
            t50 = (i - 1 + frac) / fs if i > 0 else 0.0
            break
    sovra = (max(y) - 1.0) * 100.0
    # tempo di salita 10-90 %
    t10 = t90 = None
    for i, v in enumerate(y):
        if t10 is None and v >= 0.1:
            t10 = i / fs
        if t90 is None and v >= 0.9:
            t90 = i / fs
            break
    salita = (t90 - t10) if (t10 is not None and t90 is not None) else None
    return t50, max(0.0, sovra), salita
