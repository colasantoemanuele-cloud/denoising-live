# -*- coding: utf-8 -*-
"""Sessione di acquisizione: thread di acquisizione + thread di elaborazione.

  dispositivo --(thread acquisizione)--> coda --(thread elaborazione)-->
      1. grezzo su disco (sempre per primo: non si perde mai)
      2. filtro (gli errori non fermano nulla)
      3. filtrato su disco
      4. buffer del grafico (letto dalla GUI)

La GUI non chiama mai il dispositivo: comunica solo con comandi in coda e
legge lo stato; quindi non puo' bloccare l'acquisizione.
"""
import array
import collections
import threading
import time
import traceback

import queue

from . import compat
from . import filters
from . import registro
from . import sysinfo
from .devices.base import ErroreDispositivo
from .recorder import Registrazione

FINE = object()


class BufferGrafico(object):
    """Storico per il grafico: per ogni "secchio" di ~10 ms il minimo e il
    massimo del grezzo e del filtrato (unita' fisiche).  Thread-safe."""

    def __init__(self, fs, durata_max_s=620.0, secchio_s=0.01):
        self.fs = float(fs)
        self.k = max(1, int(round(secchio_s * self.fs)))
        self.dt_secchio = self.k / self.fs
        self.maxlen = int(durata_max_s / self.dt_secchio) + 10
        self.secchi = collections.deque(maxlen=self.maxlen)
        self.contatore = 0                 # secchi prodotti dall'inizio
        self.lock = threading.Lock()
        self._acc = None
        self._n = 0
        self.ultimo_filtrato = None
        self.ultimo_grezzo = None

    def aggiungi(self, grezzo, filtrato):
        k = self.k
        nuovi = []
        acc = self._acc
        n = self._n
        for r, f in zip(grezzo, filtrato):
            if acc is None:
                acc = [r, r, f, f]
                n = 0
            else:
                if r < acc[0]:
                    acc[0] = r
                elif r > acc[1]:
                    acc[1] = r
                if f < acc[2]:
                    acc[2] = f
                elif f > acc[3]:
                    acc[3] = f
            n += 1
            if n >= k:
                nuovi.append(tuple(acc))
                acc = None
                n = 0
        self._acc = acc
        self._n = n
        with self.lock:
            self.secchi.extend(nuovi)
            self.contatore += len(nuovi)
            if len(filtrato):
                self.ultimo_filtrato = filtrato[-1]
                self.ultimo_grezzo = grezzo[-1]

    def preleva(self, dal_contatore, max_secchi=None):
        """Secchi prodotti dopo 'dal_contatore'.  Restituisce (contatore, lista)."""
        with self.lock:
            c = self.contatore
            disponibili = len(self.secchi)
            mancanti = c - dal_contatore
            if mancanti <= 0:
                return c, []
            if max_secchi is not None:
                mancanti = min(mancanti, max_secchi)
            mancanti = min(mancanti, disponibili)
            if mancanti == disponibili:
                return c, list(self.secchi)
            # deque non supporta lo slicing: si parte dalla fine
            out = []
            it = reversed(self.secchi)
            for _ in range(mancanti):
                out.append(next(it))
            out.reverse()
            return c, out


class Sessione(object):
    """Gestisce dispositivo, elaborazione, registrazione e stato per la GUI."""

    def __init__(self, dispositivo, par_filtro, cfg_salvataggio, lpf8_taglio=15.0,
                 lpf8_guadagno=1.0, soglia_saturazione=32700, soglia_picchi_unita=500.0,
                 durata_max_picco_s=0.05, intervallo_scrittura=1.0, spazio_minimo_mb=200):
        self.dev = dispositivo
        self.par = par_filtro
        self.cfg = dict(cfg_salvataggio)  # cartella, fs_salvataggio, durata_record_s
        self.lpf8 = float(lpf8_taglio)
        self.lpf8_guadagno = float(lpf8_guadagno)
        self.soglia_sat = soglia_saturazione
        self.soglia_picchi_unita = float(soglia_picchi_unita)
        self.durata_max_picco_s = float(durata_max_picco_s)
        self.intervallo_scrittura = float(intervallo_scrittura)
        self.spazio_minimo_mb = spazio_minimo_mb
        self.log = registro.get()
        self.coda = queue.Queue()
        self.comandi = queue.Queue()
        self.messaggi = queue.Queue()     # (livello, testo) per la GUI
        self.grafico = None
        self.elab = None
        self.reg = None
        self.fs = 0.0
        self.dec = 1
        self.cal = None
        self._stop = threading.Event()
        self._t_acq = None
        self._t_elab = None
        self.in_corso = False
        self.lock = threading.Lock()
        self._stato = {}
        self.campioni = 0
        self.persi_tot = 0
        self.overrun = 0
        self.t_avvio = None
        self.spazio_libero = None
        self.ultimi_errori = []
        self.coda_max_campioni = 0
        self._ultimo_grezzo = 0
        self.errore_fatale = None
        self._reg_pendente = False
        self._marker_pendenti = []
        self.ultima_registrazione = None

    # ------------------------------------------------------------------ API GUI
    def avvia_anteprima(self):
        if self.in_corso:
            return
        self.errore_fatale = None
        self.dev.apri()
        try:
            self.fs = float(self.dev.fs)
            self.cal = self.dev.calibrazione()
            fsv = float(self.cfg.get("fs_salvataggio", 125.0))
            self.dec = max(1, int(round(self.fs / fsv)))
            if abs(self.fs / self.dec - fsv) > 1e-6 * fsv:
                self.log.info("Frequenza del filtrato: %.6g Hz (acquisizione %.6g Hz / %d; "
                              "richiesta %.6g Hz)", self.fs / self.dec, self.fs, self.dec, fsv)
            conv = self.unita_per_conteggio()
            soglia_picco = self.soglia_picchi_unita / conv if self.soglia_picchi_unita > 0 else 0
            self.elab = filters.Elaboratore(self.par, self.fs, self.dec, self.soglia_sat,
                                            soglia_picco=soglia_picco,
                                            max_campioni_picco=int(round(self.durata_max_picco_s * self.fs)))
            self.grafico = BufferGrafico(self.fs)
            self._stop.clear()
            self.coda = queue.Queue()
            self.campioni = 0
            self.persi_tot = 0
            self.t_avvio = time.time()
            self.in_corso = True
            self.log.info("Avvio: %s", self.dev.descrizione())
            self.log.info("Percorso di calcolo: %s", compat.descrizione_percorso())
            self.log.info("Filtro: %s; filtrato a %.6g Hz (decimazione %d)", self.par.descrizione(),
                          self.fs / self.dec, self.dec)
            self._t_elab = threading.Thread(target=self._ciclo_elaborazione, name="elaborazione")
            self._t_elab.daemon = True
            self._t_acq = threading.Thread(target=self._ciclo_acquisizione, name="acquisizione")
            self._t_acq.daemon = True
            self._t_elab.start()
            self._t_acq.start()
        except Exception:
            # qualunque errore dopo l'apertura: si richiude il dispositivo,
            # altrimenti la scheda resta aperta e ogni nuovo tentativo fallisce
            self.in_corso = False
            self._stop.set()
            try:
                self.dev.chiudi()
            except Exception as e:
                self.log.warning("Errore chiudendo il dispositivo dopo un avvio fallito: %s", e)
            raise

    def avvia_registrazione(self):
        if not self.in_corso:
            self.avvia_anteprima()
        self.comandi.put(("avvia_reg", None))

    def ferma(self, attesa=10.0):
        if not self.in_corso:
            return
        self._stop.set()
        if self._t_acq is not None:
            self._t_acq.join(attesa)
        if self._t_elab is not None:
            self._t_elab.join(attesa)
        self.in_corso = False

    def imposta_filtro(self, par):
        self.comandi.put(("filtro", par))

    def imposta_lpf8(self, taglio, guadagno=None):
        self.comandi.put(("lpf8", (taglio, guadagno)))

    def marker(self, testo):
        self.comandi.put(("marker", testo))

    def unita_per_conteggio(self):
        c = self.cal or {"ad": 10.0, "adcmax": 32677, "yg": 0.001}
        return c["ad"] / (c["adcmax"] * c["yg"])

    def stato(self):
        with self.lock:
            s = dict(self._stato)
        s["in_corso"] = self.in_corso
        return s

    # ------------------------------------------------------------- thread acq
    def _ciclo_acquisizione(self):
        try:
            self.dev.avvia()
            while not self._stop.is_set():
                b = self.dev.leggi(0.2)
                if b is None:
                    if getattr(self.dev, "_finito", False):
                        self.log.info("Fine della sorgente")
                        break
                    continue
                self.coda.put(b)
                if b.fine_sorgente and getattr(self.dev, "_finito", False):
                    self.log.info("Fine del file di simulazione")
                    break
        except ErroreDispositivo as e:
            self.errore_fatale = e.messaggio
            self.log.error("Errore del dispositivo: %s", e.messaggio)
            self.messaggi.put(("errore", e.messaggio))
        except Exception as e:
            self.errore_fatale = "%s: %s" % (type(e).__name__, e)
            self.log.error("Errore nel thread di acquisizione:\n%s", traceback.format_exc())
            self.messaggi.put(("errore", "Errore nell'acquisizione: %s" % self.errore_fatale))
        finally:
            try:
                self.dev.ferma()
            except Exception as e:
                self.log.warning("Errore fermando il dispositivo: %s", e)
            try:
                self.dev.chiudi()
            except Exception as e:
                self.log.warning("Errore chiudendo il dispositivo: %s", e)
            self.coda.put(FINE)

    # ------------------------------------------------------------ thread elab
    def _ciclo_elaborazione(self):
        ultimo_flush = time.time()
        ultimo_disco = 0.0
        try:
            while True:
                self._esegui_comandi()
                try:
                    item = self.coda.get(timeout=0.1)
                except queue.Empty:
                    item = None
                if item is FINE:
                    break
                if item is not None:
                    self._elabora_blocco(item)
                ora = time.time()
                if self.reg is not None and ora - ultimo_flush >= self.intervallo_scrittura:
                    ultimo_flush = ora
                    self._flush()
                if ora - ultimo_disco >= 5.0:
                    ultimo_disco = ora
                    self._controlla_disco()
                self._aggiorna_stato()
        except Exception:
            self.log.error("Errore nel thread di elaborazione:\n%s", traceback.format_exc())
            self.messaggi.put(("errore", "Errore interno nell'elaborazione (vedi log)"))
        finally:
            # svuota la coda: il grezzo non si perde
            try:
                while True:
                    item = self.coda.get_nowait()
                    if item is not FINE:
                        self._elabora_blocco(item)
            except queue.Empty:
                pass
            except Exception:
                self.log.error("Errore svuotando la coda:\n%s", traceback.format_exc())
            self._esegui_comandi()
            self._reg_pendente = False
            self._chiudi_registrazione()
            self._aggiorna_stato()
            self.in_corso = False
            self._stop.set()

    def _esegui_comandi(self):
        while True:
            try:
                cmd, arg = self.comandi.get_nowait()
            except queue.Empty:
                return
            try:
                if cmd == "filtro":
                    prima = self.par
                    self.elab.riconfigura(arg)
                    self.par = arg
                    t = self.campioni / self.fs if self.fs else 0
                    self.log.info("Cambio filtro a t=%.3f s: %s -> %s", t, prima.descrizione(),
                                  arg.descrizione())
                    if self.reg is not None:
                        self.reg.evento_parametri("filtro", prima.come_dict(), arg.come_dict())
                elif cmd == "lpf8":
                    taglio, guadagno = arg
                    prima = {"taglio_hz": self.lpf8, "guadagno": self.lpf8_guadagno}
                    self.lpf8 = float(taglio)
                    if guadagno is not None:
                        self.lpf8_guadagno = float(guadagno)
                    dopo = {"taglio_hz": self.lpf8, "guadagno": self.lpf8_guadagno}
                    self.log.info("LPF-8 dichiarato: %s -> %s", prima, dopo)
                    if self.reg is not None:
                        self.reg.evento_parametri("lpf8", prima, dopo)
                        self.reg.meta["lpf8"] = dopo
                elif cmd == "marker":
                    t = self.campioni / self.fs if self.fs else 0
                    if self.reg is not None:
                        tr, rec = self.reg.marker(arg)
                        self.log.info("Marker a %.3f s (record %d): %s", tr, rec, arg)
                    elif self._reg_pendente:
                        self._marker_pendenti.append(arg)
                    else:
                        self.log.info("Marker (non in registrazione) a %.3f s: %s", t, arg)
                    self.messaggi.put(("info", "Marker: %s" % arg))
                elif cmd == "avvia_reg":
                    # la registrazione parte dal prossimo campione multiplo della
                    # decimazione, cosi' grezzo e filtrato sono allineati
                    if self.reg is None:
                        self._reg_pendente = True
            except Exception as e:
                self.log.error("Comando %s fallito:\n%s", cmd, traceback.format_exc())
                self.messaggi.put(("errore", "Comando %s fallito: %s" % (cmd, e)))

    def _avvia_registrazione(self):
        if self.reg is not None:
            return
        cartella = self.cfg["cartella"]
        try:
            self.reg = Registrazione(
                cartella, self.cal, self.fs, self.dec, self.par, self.cfg.get("durata_record_s", 60.0),
                self.dev.info(), self.lpf8, self.lpf8_guadagno, campione_inizio=self.campioni,
                percorso_numpy=compat.descrizione_percorso(),
                separatore=self.cfg.get("separatore", ","))
        except Exception as e:
            self.log.error("Impossibile iniziare la registrazione in %s: %s", cartella, e)
            self.messaggi.put(("errore", "Impossibile iniziare la registrazione in %s:\n%s\n"
                               "La registrazione non e' iniziata; l'acquisizione continua "
                               "(anteprima).  Premere di nuovo Avvia registrazione oppure "
                               "scegliere un'altra cartella." % (cartella, e)))
            self.reg = None
            return
        self.log.info("Registrazione iniziata: %s (record da %.2f s: %d campioni grezzi, "
                      "%d filtrati)", self.reg.nome_base, self.reg.durata_record_effettiva,
                      self.reg.n_raw, self.reg.n_filt)
        for testo in self._marker_pendenti:
            tr, rec = self.reg.marker(testo)
            self.log.info("Marker a %.3f s (record %d): %s", tr, rec, testo)
        self._marker_pendenti = []
        self.messaggi.put(("info", "Registrazione iniziata: %s" % self.reg.nome_base))

    def _chiudi_registrazione(self):
        if self.reg is None:
            return
        try:
            self._flush()
            self.reg.chiudi()
            self.log.info("Registrazione chiusa: %s, %.1f s, %d record, campioni persi %d, "
                          "errori di scrittura %d", self.reg.nome_base, self.reg.t_rel(),
                          self.reg.raw.nr_su_disco, self.reg.meta["campioni_persi"],
                          self.reg.n_errori())
            self.messaggi.put(("info", "Registrazione salvata: %s" % self.reg.nome_base))
        except Exception:
            self.log.error("Errore chiudendo la registrazione:\n%s", traceback.format_exc())
        self.ultima_registrazione = self.reg
        self.reg = None

    def _flush(self):
        reg = self.reg
        if reg is None:
            return
        reg.saturazione(self.elab.saturati_tot, self.elab.eventi_saturazione, [])
        ok = reg.flush()
        if not ok:
            for e in reg.errori():
                if e not in self.ultimi_errori:
                    self.ultimi_errori.append(e)
                    self.log.error("ERRORE DI SCRITTURA: %s", e)
                    self.messaggi.put(("errore_scrittura", e))

    def _controlla_disco(self):
        cartella = self.cfg["cartella"]
        self.spazio_libero = sysinfo.spazio_libero_mb(cartella)
        if self.reg is not None and self.spazio_libero is not None and \
                self.spazio_libero < self.spazio_minimo_mb:
            self.messaggi.put(("avviso_disco", "Spazio su disco quasi esaurito: %.0f MB liberi"
                               % self.spazio_libero))

    def _elabora_blocco(self, b):
        dati = b.dati
        n = len(dati)
        if self._reg_pendente and not b.persi:
            k = (-self.campioni) % self.dec
            if k < n:
                if k:
                    self._elabora_campioni(dati[:k])
                self._reg_pendente = False
                self._avvia_registrazione()
                self._elabora_campioni(dati[k:])
                return
        if b.persi:
            self.persi_tot += b.persi
            self.log.error("Campioni persi: %d (totale %d)", b.persi, self.persi_tot)
            self.messaggi.put(("persi", b.persi))
            riempi = array.array("h", [self._ultimo_grezzo]) * int(b.persi)
            if self.reg is not None:
                self.reg.campioni_persi(b.persi, self.campioni)
            self._elabora_campioni(riempi)
        if n:
            self._elabora_campioni(dati)

    def _elabora_campioni(self, dati):
        n = len(dati)
        # 1. grezzo su disco, prima di tutto il resto
        if self.reg is not None:
            try:
                self.reg.scrivi_grezzo(dati)
            except Exception:
                self.log.error("Errore salvando il grezzo:\n%s", traceback.format_exc())
        # 2. filtro
        try:
            y, dec = self.elab.elabora(dati)
        except Exception:
            self.log.error("Errore nel filtro (riavviato):\n%s", traceback.format_exc())
            self.messaggi.put(("errore", "Errore nel filtro: riavviato (vedi log)"))
            ultimo = self.elab.ultima_uscita or 0.0
            self.elab = filters.Elaboratore(self.par, self.fs, self.dec, self.soglia_sat,
                                            soglia_picco=self.elab.soglia_picco,
                                            max_campioni_picco=self.elab.max_picco)
            self.elab.fase_dec = (self.campioni + n) % self.dec
            self.elab.campioni = self.campioni + n
            self.elab.primo_valore(ultimo)
            y = [ultimo] * n
            fase = (-self.campioni) % self.dec
            dec = [int(round(ultimo))] * len(range(fase, n, self.dec))
        eventi = self.elab.preleva_eventi()
        if eventi:
            for idx, durata, tipo in eventi[:20]:
                self.log.info("%s a t=%.3f s: %d campioni sostituiti con l'ultimo valore valido%s",
                              "Picco isolato" if tipo == "picco" else
                              ("Scostamento lungo accettato come segnale" if tipo == "picco_accettato"
                               else "Saturazione ADC"),
                              idx / self.fs, durata, "" if tipo != "picco_accettato" else "")
            if len(eventi) > 20:
                self.log.info("... altri %d eventi di saturazione/picco", len(eventi) - 20)
            if self.reg is not None:
                self.reg.saturazione(self.elab.saturati_tot, self.elab.eventi_saturazione,
                                     [(i, d, t) for i, d, t in eventi])
        # 3. filtrato su disco
        if self.reg is not None:
            try:
                self.reg.scrivi_filtrato(dec)
            except Exception:
                self.log.error("Errore salvando il filtrato:\n%s", traceback.format_exc())
        # 4. grafico
        try:
            conv = self.unita_per_conteggio()
            yz = self.cal.get("yz", 0.0)
            if hasattr(dati, "tolist"):
                grezzo_l = dati.tolist()
            else:
                grezzo_l = dati
            g = [(v - yz) * conv for v in grezzo_l]
            f = [(v - yz) * conv for v in y]
            self.grafico.aggiungi(g, f)
        except Exception:
            self.log.error("Errore aggiornando il grafico:\n%s", traceback.format_exc())
        self._ultimo_grezzo = int(dati[-1])
        self.campioni += n
        backlog = self.coda.qsize()
        if backlog > self.coda_max_campioni:
            self.coda_max_campioni = backlog

    def _aggiorna_stato(self):
        s = {
            "modalita": self.dev.modalita,
            "descrizione": self.dev.descrizione(),
            "registrazione": self.reg is not None,
            "campioni": self.campioni,
            "tempo_s": self.campioni / self.fs if self.fs else 0.0,
            "persi": self.persi_tot,
            "overrun": getattr(self.dev, "overrun", 0),
            "spazio_libero_mb": self.spazio_libero,
            "saturazioni": self.elab.eventi_saturazione if self.elab else 0,
            "fs": self.fs,
            "fs_filtrato": self.fs / self.dec if self.fs else 0.0,
            "filtro": self.par.descrizione(),
            "lpf8": self.lpf8,
            "coda": self.coda.qsize(),
        }
        if self.reg is not None:
            s.update({"file": self.reg.nome_base, "tempo_reg_s": self.reg.t_rel(),
                      "record": self.reg.numero_record(), "errori_scrittura": self.reg.n_errori(),
                      "cartella": self.reg.cartella})
        with self.lock:
            self._stato = s
