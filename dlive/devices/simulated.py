# -*- coding: utf-8 -*-
"""SimulatedDevice: riproduce un file .wcp in tempo reale, come se i campioni
arrivassero dalla scheda.  Passa per la stessa coda, lo stesso filtro, la
stessa grafica e lo stesso salvataggio del dispositivo vero.
"""
import array
import math
import os
import random
import time

from .. import compat
from .. import filters
from .. import wcpfile
from .base import Blocco, Dispositivo, ErroreDispositivo


def lunghezza_utile(campioni):
    """Lunghezza senza la coda costante lasciata da WinWCP quando lo sweep e'
    fermato prima della fine (ripetizione dell'ultimo valore acquisito).

    Il primo campione della coda costante e' l'ultimo valore acquisito davvero
    e resta: si toglie solo la ripetizione.  Se l'ultimo campione e' diverso
    dal penultimo non c'e' coda e si tiene tutto."""
    n = len(campioni)
    if n == 0:
        return 0
    ultimo = campioni[-1]
    if compat.np is not None and hasattr(campioni, "dtype"):
        diversi = compat.np.nonzero(campioni != ultimo)[0]
        return min(n, int(diversi[-1]) + 2) if len(diversi) else n
    i = n - 1
    while i >= 0 and campioni[i] == ultimo:
        i -= 1
    return min(n, i + 2) if i >= 0 else n


def scegli_canale(fw):
    """Canale con la maggiore deviazione standard nel primo record."""
    if not fw.records:
        return 0
    migliore, best = 0, -1.0
    for c in range(fw.nc):
        d = fw.records[0].adc[c]
        n = lunghezza_utile(d)
        if n < 2:
            continue
        if compat.np is not None and hasattr(d, "dtype"):
            s = float(d[:n].astype(compat.np.float64).std())
        else:
            passo = max(1, n // 20000)
            v = [d[i] for i in range(0, n, passo)]
            m = sum(v) / float(len(v))
            s = math.sqrt(sum((x - m) ** 2 for x in v) / len(v))
        if s > best:
            best, migliore = s, c
    return migliore


class GeneratoreRumore(object):
    """Rumore sintetico simile a quello dei file di prova (in unita' fisiche)."""

    def __init__(self, fs, seme=12345, amp50=20.0, amp8_7=5.0, amp37_4=10.0,
                 rms_banda=30.0, picchi_ogni_s=30.0):
        self.fs = float(fs)
        self.rnd = random.Random(seme)
        self.amp50 = amp50
        self.amp87 = amp8_7
        self.amp374 = amp37_4
        self.rms_banda = rms_banda
        self.picchi_ogni_s = picchi_ogni_s
        self.n = 0
        nyq = self.fs / 2.0
        alto = min(50.0, 0.95 * nyq)
        self.lp_alto = filters.CatenaSOS(filters.progetta_passabasso("butterworth", 4, alto, fs))
        self.lp_basso = filters.CatenaSOS(filters.progetta_passabasso("butterworth", 4, 25.0, fs)) \
            if 25.0 < nyq else None
        # normalizzazione approssimata della banda: varianza ~ (alto-25)/nyq
        quota = max(0.05, (alto - 25.0) / nyq)
        self.scala_banda = rms_banda / math.sqrt(quota)
        self.picco_restante = 0

    def genera(self, k):
        """Restituisce (rumore: lista di float, saturati: lista di bool)."""
        g = self.rnd.gauss
        w = [g(0.0, 1.0) for _ in range(k)]
        a = self.lp_alto.elabora(w)
        if self.lp_basso is not None:
            b = self.lp_basso.elabora(w)
            banda = [(x - y) * self.scala_banda for x, y in zip(a, b)]
        else:
            banda = [0.0] * k
        out = []
        sat = []
        dpi = 2.0 * math.pi / self.fs
        p_picco = 1.0 / (self.picchi_ogni_s * self.fs) if self.picchi_ogni_s > 0 else 0.0
        for i in range(k):
            t = (self.n + i) * dpi
            v = (self.amp50 * math.sin(50.0 * t) + self.amp87 * math.sin(8.7 * t + 0.3) +
                 self.amp374 * math.sin(37.4 * t + 1.1) + banda[i])
            out.append(v)
            if self.picco_restante > 0:
                self.picco_restante -= 1
                sat.append(True)
            elif p_picco and self.rnd.random() < p_picco:
                self.picco_restante = self.rnd.randint(0, max(0, int(0.003 * self.fs)))
                sat.append(True)
            else:
                sat.append(False)
        self.n += k
        return out, sat


class SimulatedDevice(Dispositivo):
    modalita = "simulazione"

    def __init__(self, percorso, record=1, canale=-1, velocita=1.0, salta_coda=True,
                 sovracampiona=False, fs_sovracampionamento=1000.0, rumore=False,
                 blocco_s=0.05, tempo_reale=True, ciclo=True, seme=12345,
                 persi_test=None, salto_brusco_mv=500.0):
        self.percorso = percorso
        self.record = int(record)
        self.canale = int(canale)
        self.velocita = float(velocita)
        self.salta_coda = bool(salta_coda)
        self.sovracampiona = bool(sovracampiona)
        self.fs_sovra = float(fs_sovracampionamento)
        self.rumore = bool(rumore)
        self.blocco_s = float(blocco_s)
        self.tempo_reale = bool(tempo_reale)
        self.ciclo = bool(ciclo)
        self.seme = seme
        self.persi_test = dict(persi_test or {})   # {numero_blocco: campioni_da_saltare}
        # Nel sovracampionamento i salti piu' grandi di questo valore (tra due
        # campioni consecutivi del file) non si interpolano: un picco di 1
        # campione a 114-125 Hz e' un evento brusco, e l'interpolazione
        # lineare lo trasformerebbe in una rampa di ~17 ms che nessuna
        # acquisizione a 1000 Hz produrrebbe.  Stesso trattamento delle
        # saturazioni.  0 = interpola sempre.
        self.salto_brusco_mv = float(salto_brusco_mv)
        self._salto_brusco = 0
        self.sorgente = None
        self.fs_sorgente = 0.0
        self.fs = 0.0
        self._cal = None
        self._attivo = False
        self._pos = 0.0          # posizione (frazionaria) nella sorgente
        self._prodotti = 0       # campioni in uscita prodotti
        self._t0 = 0.0
        self._blocchi = 0
        self._finito = False
        self.giri = 0
        self.nome_file = os.path.basename(percorso)
        self.rumore_gen = None
        self.descr_sorgente = ""

    # ------------------------------------------------------------------
    def apri(self):
        if not os.path.isfile(self.percorso):
            raise ErroreDispositivo("File di simulazione non trovato: %s" % self.percorso)
        try:
            fw = wcpfile.leggi_wcp(self.percorso)
        except Exception as e:
            raise ErroreDispositivo("Impossibile leggere %s: %s" % (self.percorso, e))
        if not fw.records:
            raise ErroreDispositivo("Il file %s non contiene record" % self.percorso)
        if self.canale < 0 or self.canale >= fw.nc:
            self.canale = scegli_canale(fw)
        sel = range(len(fw.records)) if self.record <= 0 else [self.record - 1]
        if self.record > len(fw.records):
            raise ErroreDispositivo("Il file ha solo %d record (richiesto %d)"
                                    % (len(fw.records), self.record))
        dati = array.array("h")
        for r in sel:
            d = fw.records[r].adc[self.canale]
            n = lunghezza_utile(d) if self.salta_coda else len(d)
            if compat.np is not None and hasattr(d, "dtype"):
                dati.frombytes(d[:n].astype("<i2").tobytes())
            else:
                dati.extend(d[:n])
        if len(dati) < 2:
            raise ErroreDispositivo("Il canale %d del file e' vuoto o costante" % self.canale)
        self.sorgente = dati
        self.fs_sorgente = 1.0 / fw.dt
        self.fs = self.fs_sovra if self.sovracampiona else self.fs_sorgente
        info = fw.canale(self.canale)
        self._cal = {"yg": info["yg"], "yz": info["yz"], "unita": info["unita"],
                     "nome": info["nome"], "ad": fw.ad, "adcmax": int(fw.adcmax)}
        conv = self._cal["yg"] * self._cal["adcmax"] / self._cal["ad"]     # unita' -> conteggi
        self._salto_brusco = int(round(self.salto_brusco_mv * conv)) if self.salto_brusco_mv > 0 else 0
        if self.rumore:
            self.rumore_gen = GeneratoreRumore(self.fs, seme=self.seme)
        self.descr_sorgente = "%s, record %s, canale %d (%s), %.4g Hz%s" % (
            self.nome_file, "tutti" if self.record <= 0 else self.record, self.canale,
            info["nome"], self.fs_sorgente,
            (", sovracampionato a %g Hz" % self.fs) if self.sovracampiona else "")
        return self

    def calibrazione(self):
        return dict(self._cal)

    def durata_sorgente(self):
        return len(self.sorgente) / self.fs_sorgente if self.sorgente else 0.0

    def avvia(self):
        if self.sorgente is None:
            self.apri()
        self._t0 = time.time()
        self._pos = 0.0
        self._prodotti = 0
        self._blocchi = 0
        self._finito = False
        self._attivo = True

    def ferma(self):
        self._attivo = False

    def chiudi(self):
        self._attivo = False

    def descrizione(self):
        return "Simulazione: %s, velocita' %gx%s" % (
            self.descr_sorgente, self.velocita, ", rumore sintetico" if self.rumore else "")

    def info(self):
        return {"modalita": self.modalita, "fs_hz": self.fs, "file": self.percorso,
                "record": self.record, "canale": self.canale, "velocita": self.velocita,
                "salta_coda": self.salta_coda, "sovracampiona": self.sovracampiona,
                "rumore_sintetico": self.rumore, "fs_sorgente_hz": self.fs_sorgente}

    # ------------------------------------------------------------------
    def leggi(self, timeout=0.2):
        if not self._attivo or self._finito:
            if timeout:
                time.sleep(min(timeout, 0.05))
            return None
        min_blocco = max(1, int(round(self.blocco_s * self.fs)))
        min_eff = int(min_blocco * max(1.0, self.velocita))
        if self.tempo_reale:
            fine_attesa = time.time() + timeout
            while True:
                ora = time.time()
                dovuti = int((ora - self._t0) * self.velocita * self.fs) - self._prodotti
                if dovuti >= min_eff:
                    break
                if ora >= fine_attesa:
                    if dovuti <= 0:
                        return None
                    break
                attesa = (min_eff - dovuti) / (self.velocita * self.fs)
                time.sleep(max(0.002, min(attesa, fine_attesa - ora, 0.05)))
            # dopo una pausa lunga (PC lento) non si recupera piu' di 2 s per volta
            k = min(dovuti, int(self.fs * max(1.0, self.velocita) * 2))
        else:
            k = min_eff
        persi = 0
        self._blocchi += 1
        if self._blocchi in self.persi_test:
            persi = int(self.persi_test[self._blocchi])
            self._avanza(persi)
            self._prodotti += persi
        dati, fine = self._genera(k)
        indice = self._prodotti
        self._prodotti += len(dati)
        if fine and not self.ciclo:
            self._finito = True
        return Blocco(dati, indice, persi, fine)

    def _avanza(self, k):
        passo = self.fs_sorgente / self.fs
        self._pos += k * passo
        n = len(self.sorgente)
        if self.ciclo:
            while self._pos >= n:
                self._pos -= n

    def _genera(self, k):
        src = self.sorgente
        n = len(src)
        out = array.array("h")
        fine = False
        if not self.sovracampiona:
            i = int(self._pos)
            while len(out) < k:
                if i >= n:
                    fine = True
                    self.giri += 1
                    if not self.ciclo:
                        break
                    i = 0
                prendi = min(k - len(out), n - i)
                out.extend(src[i:i + prendi])
                i += prendi
            self._pos = float(i)
            if i >= n and not self.ciclo:
                fine = True
        else:
            passo = self.fs_sorgente / self.fs
            pos = self._pos
            app = out.append
            for _ in range(k):
                if pos >= n - 1:
                    fine = True
                    self.giri += 1
                    if not self.ciclo:
                        break
                    pos -= (n - 1)
                i = int(pos)
                fr = pos - i
                a = src[i]
                b = src[i + 1]
                if a <= -32768 or a >= 32767 or b <= -32768 or b >= 32767 or \
                        (self._salto_brusco and abs(b - a) > self._salto_brusco):
                    app(a if fr < 0.5 else b)       # non interpolare saturazioni e salti bruschi
                else:
                    app(int(round(a + (b - a) * fr)))
                pos += passo
            self._pos = pos
        if self.rumore_gen is not None and len(out):
            cal = self._cal
            conv = cal["yg"] * cal["adcmax"] / cal["ad"]       # unita' -> conteggi
            rum, sat = self.rumore_gen.genera(len(out))
            for j in range(len(out)):
                if sat[j]:
                    out[j] = -32768
                elif -32768 < out[j] < 32767:
                    v = out[j] + int(round(rum[j] * conv))
                    out[j] = 32767 if v > 32767 else (-32768 if v < -32768 else v)
        return out, fine
