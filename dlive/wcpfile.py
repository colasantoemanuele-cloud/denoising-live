# -*- coding: utf-8 -*-
"""Lettura e scrittura di file WinWCP (.wcp), formato V9 come scritto da WinWCP 5.1.6.

Struttura del file (vedi WCPFIleUnit.pas, procedure SaveHeader, PutRecord,
PutRecordHeaderOnly):

  * intestazione di NBH=1024 byte: testo "CHIAVE=valore" separato da CR LF,
    riempito con NUL; numeri con la virgola decimale (PC in italiano);
  * NR record, ciascuno con:
      - blocco di analisi di NBA*512 = 1024 byte:
          0   8 byte  stato  "ACCEPTED"
          8   4 byte  tipo   "TEST"
          12  float32 gruppo (numero del record)
          16  float32 istante di inizio del record (s)
          20  float32 intervallo di campionamento (s)
          24  float32 * NC  range di tensione per canale (V)
          ..  16 byte testo identificativo del record
          ..  float32 * max(NC,8) * 28  variabili di analisi
              (Value[0]=numero record, [1]=gruppo, [2]=tempo)
          resto a zero (equazione di fit, cursori)
      - dati di NBD*512 byte: int16 little-endian, canali interlacciati.

Dimensione del file = NBH + NR * (NBA + NBD) * 512 byte.

Questo modulo funziona con e senza numpy (vedi compat.py).
"""
import array
import datetime
import os
import struct
import sys

from . import compat

SETTORE = 512
NBH = 1024
NBA_SETTORI = 2
ADCMAX_WINWCP = 32677          # proprio 32677: e' quello che scrive WinWCP
VERPROG_WINWCP = "V5.1.6"
MAX_VAR_ANALISI = 28
MAX_IDENT = 16
# Limite prudenziale di campioni (tutti i canali) per record.  WinWCP usa
# buffer di MaxADCSamples campioni (componente SESLabIO: 1048576*16 nelle
# versioni recenti, valore ignoto nella 5.1.6); i file di prova arrivano a
# 2 240 000 campioni per record, quindi fin li' e' sicuro.  Restiamo ben sotto.
MAX_CAMPIONI_RECORD = 1000000


# ----------------------------------------------------------------------------
# Formattazione numeri e date come Delphi in locale italiano
# ----------------------------------------------------------------------------
def numero_it(valore, cifre=4):
    """Come format('%.4g') di Delphi, con la virgola decimale."""
    s = ("%." + str(int(cifre)) + "g") % float(valore)
    if "e" in s or "E" in s:
        # Delphi scrive per es. 1E-5; WinWCP rilegge comunque.  Usiamo la
        # notazione decimale per sicurezza (caso che con i valori del
        # programma non capita).
        s = ("%.12f" % float(valore)).rstrip("0").rstrip(".")
    return s.replace(".", ",")


def numero_it_decimali(valore, decimali=3):
    s = ("%." + str(int(decimali)) + "f") % float(valore)
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")


def data_ora_it(dt):
    """'10/12/2007 0:39:53' come nei file di prova (g/mm/aaaa h:mm:ss)."""
    return "%02d/%02d/%04d %d:%02d:%02d" % (dt.day, dt.month, dt.year,
                                             dt.hour, dt.minute, dt.second)


def numero_da_testo(s):
    return float(s.strip().replace(",", "."))


# ----------------------------------------------------------------------------
# Lettura
# ----------------------------------------------------------------------------
def leggi_intestazione_testo(raw1024):
    txt = raw1024.decode("latin-1").split("\x00")[0]
    hdr = {}
    ordine = []
    for riga in txt.replace("\r", "\n").split("\n"):
        if "=" in riga:
            k, v = riga.split("=", 1)
            k = k.strip()
            hdr[k] = v.strip()
            ordine.append(k)
    return hdr, ordine


class RecordWCP(object):
    """Un record letto da file.  adc: campioni grezzi (per canale);
    dati: valori in unita' fisiche (per canale)."""

    def __init__(self):
        self.stato = ""
        self.tipo = ""
        self.gruppo = 0.0
        self.tempo = 0.0
        self.dt = 0.0
        self.vmax = ()
        self.ident = ""
        self.valori = ()
        self.adc = []      # lista di canali; ogni canale: numpy int16 o array('h')
        self.dati = []     # lista di canali; numpy float64 o lista di float
        self.completo = True
        self.n_campioni = 0

    # compatibilita' con il lettore di riferimento (dizionari)
    def __getitem__(self, k):
        mappa = {"status": "stato", "type": "tipo", "group": "gruppo",
                 "time": "tempo", "dt": "dt", "vmax": "vmax", "data": "dati",
                 "adc": "adc"}
        return getattr(self, mappa.get(k, k))


class FileWCP(object):
    """Contenuto di un file .wcp letto da disco."""

    def __init__(self):
        self.percorso = ""
        self.hdr = {}
        self.ordine_chiavi = []
        self.nc = 0
        self.nr = 0
        self.nr_intestazione = 0
        self.nbd = 0
        self.dt = 0.0
        self.adcmax = float(ADCMAX_WINWCP)
        self.ad = 10.0
        self.records = []
        self.avvisi = []
        self.extra = 0

    @property
    def campioni_per_record(self):
        return self.nbd * SETTORE // 2 // max(self.nc, 1)

    def canale(self, c):
        return {
            "yo": int(self.hdr.get("YO%d" % c, c)),
            "nome": self.hdr.get("YN%d" % c, "Ch.%d" % c),
            "unita": self.hdr.get("YU%d" % c, ""),
            "yg": numero_da_testo(self.hdr.get("YG%d" % c, "0,001")),
            "yz": numero_da_testo(self.hdr.get("YZ%d" % c, "0")),
        }


def leggi_wcp(percorso, usa_numpy=None, solo_intestazione=False, canali=None,
              recupera_extra=False):
    """Legge un file .wcp.  Gestisce:
       * NR=0 nell'intestazione (WinWCP ricalcola il numero dalla dimensione);
       * file troncato (record finale incompleto: si leggono i campioni presenti);
       * record completi oltre NR (WinWCP interrotto prima di aggiornare
         l'intestazione): segnalati in avvisi e letti solo con recupera_extra=True.
    """
    if usa_numpy is None:
        usa_numpy = compat.ha_numpy()
    np = compat.np if usa_numpy else None
    with open(percorso, "rb") as f:
        raw = f.read()
    w = FileWCP()
    w.percorso = percorso
    if len(raw) < 64:
        raise ValueError("%s: file troppo corto (%d byte)" % (percorso, len(raw)))
    w.hdr, w.ordine_chiavi = leggi_intestazione_testo(raw[:1024])
    hdr = w.hdr
    for chiave in ("NC", "NBD"):
        if chiave not in hdr:
            raise ValueError("%s: manca la chiave %s nell'intestazione" % (percorso, chiave))
    w.nc = int(hdr["NC"])
    nbh = int(hdr.get("NBH", "1024"))
    nba = int(hdr.get("NBA", "2"))
    w.nbd = nbd = int(hdr["NBD"])
    w.nr_intestazione = int(hdr.get("NR", "0"))
    w.adcmax = numero_da_testo(hdr.get("ADCMAX", str(ADCMAX_WINWCP)))
    w.ad = numero_da_testo(hdr.get("AD", "10"))
    w.dt = numero_da_testo(hdr.get("DT", "0"))
    byte_record = (nba + nbd) * SETTORE
    disponibili = max(0, len(raw) - nbh)
    nr_da_dimensione = disponibili // byte_record
    resto = disponibili - nr_da_dimensione * byte_record
    nr = w.nr_intestazione
    if nr <= 0 and nr_da_dimensione > 0:
        w.avvisi.append("NR=%d nell'intestazione, ricalcolato dalla dimensione: %d"
                        % (nr, nr_da_dimensione))
        nr = nr_da_dimensione
    if nr > nr_da_dimensione:
        # file troncato: l'ultimo record (o piu') manca in parte
        if resto >= nba * SETTORE and nr == nr_da_dimensione + 1:
            w.avvisi.append("record %d troncato: presenti %d byte di dati su %d"
                            % (nr, resto - nba * SETTORE, nbd * SETTORE))
        else:
            w.avvisi.append("file troncato: NR=%d ma solo %d record completi"
                            % (nr, nr_da_dimensione))
            nr = nr_da_dimensione + (1 if resto >= nba * SETTORE + 2 * w.nc else 0)
    if 0 < nr < nr_da_dimensione:
        w.extra = nr_da_dimensione - nr
        w.avvisi.append("il file contiene %d record completi oltre NR=%d (non visibili in "
                        "WinWCP)%s" % (w.extra, nr, "; letti" if recupera_extra else ""))
        if recupera_extra:
            nr = nr_da_dimensione
    w.nr = nr
    if solo_intestazione:
        return w
    nc = w.nc
    info = [w.canale(c) for c in range(nc)]
    sel = list(range(nc)) if canali is None else list(canali)
    for r in range(nr):
        off = nbh + r * byte_record
        ab = raw[off:off + nba * SETTORE]
        rec = RecordWCP()
        if len(ab) < 24 + 4 * nc:
            break
        rec.stato = ab[0:8].decode("latin-1")
        rec.tipo = ab[8:12].decode("latin-1")
        rec.gruppo, rec.tempo, rec.dt = struct.unpack("<fff", ab[12:24])
        rec.vmax = struct.unpack("<" + "f" * nc, ab[24:24 + 4 * nc])
        p = 24 + 4 * nc
        rec.ident = ab[p:p + MAX_IDENT].decode("latin-1").split("\x00")[0]
        p += MAX_IDENT
        nval = max(nc, 8) * MAX_VAR_ANALISI
        if len(ab) >= p + 4 * nval:
            rec.valori = struct.unpack("<" + "f" * nval, ab[p:p + 4 * nval])
        dati_b = raw[off + nba * SETTORE: off + byte_record]
        if len(dati_b) < nbd * SETTORE:
            rec.completo = False
        n = len(dati_b) // (2 * nc)
        dati_b = dati_b[:n * nc * 2]
        rec.n_campioni = n
        if np is not None:
            d = np.frombuffer(dati_b, dtype="<i2").reshape(n, nc)
        else:
            d = array.array("h")
            d.frombytes(dati_b)
            if sys.byteorder == "big":
                d.byteswap()
        for c in sel:
            yo = info[c]["yo"]
            yg = info[c]["yg"]
            yz = info[c]["yz"]
            vmax = rec.vmax[c] if rec.vmax[c] != 0 else w.ad
            scala = vmax / w.adcmax / yg
            if np is not None:
                col = d[:, yo]
                rec.adc.append(col)
                rec.dati.append((col.astype(np.float64) - yz) * scala)
            else:
                col = d[yo::nc] if nc > 1 else d
                rec.adc.append(col)
                rec.dati.append([(v - yz) * scala for v in col])
        w.records.append(rec)
    return w


def read_wcp(path):
    """Interfaccia compatibile con il lettore di riferimento del documento di
    progetto: restituisce (hdr, records) con records lista di dizionari."""
    w = leggi_wcp(path)
    recs = []
    for r in w.records:
        recs.append(dict(status=r.stato, type=r.tipo, group=r.gruppo, time=r.tempo,
                         dt=r.dt, vmax=r.vmax, data=r.dati, adc=r.adc))
    return w.hdr, recs


# ----------------------------------------------------------------------------
# Scrittura
# ----------------------------------------------------------------------------
def campioni_per_record(durata_s, fs, nc=1, multiplo=None):
    """Numero di campioni per canale in un record di durata ~durata_s.

    WinWCP richiede che i dati di un record occupino un numero intero di
    settori da 512 byte: campioni*nc*2 multiplo di 512.  Si arrotonda al
    multiplo piu' vicino.  'multiplo' permette di imporre un multiplo comune
    (per allineare record grezzi e filtrati)."""
    passo = 256 // _mcd(256, nc)
    if multiplo:
        passo = _mcm(passo, int(multiplo))
    n = int(round(durata_s * fs / float(passo))) * passo
    return max(passo, n)


def _mcd(a, b):
    while b:
        a, b = b, a % b
    return a


def _mcm(a, b):
    return a * b // _mcd(a, b)


class ErroreScrittura(Exception):
    pass


class ScrittoreWCP(object):
    """Scrive un file .wcp a record consecutivi di lunghezza fissa, resistente ai crash.

    Strategia (motivata nel README):
      * all'apertura si scrive l'intestazione valida con NR=0;
      * il record in corso viene scritto su disco per intero a ogni flush()
        (tipicamente ogni secondo): i campioni gia' acquisiti, seguiti dalla
        ripetizione dell'ultimo valore fino alla fine del record (lo stesso
        riempimento che WinWCP fa per gli sweep fermati prima);  NR include
        il record in corso, quindi il file e' sempre apribile e completo;
      * dopo ogni scrittura: flush + os.fsync.
    Se il PC si blocca si perde al massimo l'intervallo tra due flush.

    Gli errori di scrittura non sollevano eccezioni durante la registrazione:
    i dati restano in memoria e si riprova al flush successivo; l'errore e'
    disponibile in self.ultimo_errore e self.n_errori.
    """

    def __init__(self, percorso, dt, campioni_record, canali, ad=10.0,
                 adcmax=ADCMAX_WINWCP, ident="", ora_creazione=None,
                 ora_inizio=None, verprog=VERPROG_WINWCP, nz=20,
                 max_record_in_memoria=400, separatore=",", rtimesecs=None):
        self.percorso = percorso
        self.dt = float(dt)
        self.nc = len(canali)
        if self.nc < 1:
            raise ValueError("serve almeno un canale")
        self.n = int(campioni_record)
        if (self.n * self.nc * 2) % SETTORE != 0:
            raise ValueError("campioni per record (%d x %d canali) non multiplo di 256"
                             % (self.n, self.nc))
        if self.n * self.nc > MAX_CAMPIONI_RECORD:
            raise ValueError("record troppo lungo: %d campioni (max %d)"
                             % (self.n * self.nc, MAX_CAMPIONI_RECORD))
        self.canali = canali
        self.ad = float(ad)
        self.adcmax = adcmax
        self.ident = _pulisci_testo(ident, 200)
        self.verprog = verprog
        self.nz = nz
        self.separatore = separatore
        self.ora_creazione = ora_creazione or datetime.datetime.now()
        self.ora_inizio = ora_inizio or self.ora_creazione
        # RTIMESECS: come WinWCP 5.1.6 i secondi dall'avvio di Windows all'inizio
        # della registrazione (guida di WinWCP V5.2.4 p. 163, WCPFIleUnit.pas:254;
        # nei file di prova non coincide con l'ora del giorno).  WinWCP lo usa
        # solo se > 0.  Senza il valore: secondi dalla mezzanotte.
        self.rtimesecs = rtimesecs
        self.nbd = self.n * self.nc * 2 // SETTORE
        self.byte_record = (NBA_SETTORI + self.nbd) * SETTORE
        self.max_record_in_memoria = max_record_in_memoria

        self.nr_su_disco = 0          # record presenti nell'intestazione scritta
        self.record_completi = 0      # record completi (chiusi)
        self.buf = array.array("h", [0]) * (self.n * self.nc)
        self.riempiti = 0             # campioni (tutti i canali) nel record in corso
        self.sporco = False
        self.ident_record = ""
        self.in_attesa = []           # record completi non ancora scritti (errore disco)
        self.ultimo_errore = ""
        self.n_errori = 0
        self.campioni_totali = 0
        self.persi_memoria = 0
        self.chiuso = False
        self._f = None
        try:
            # "x": il file NON deve esistere.  Un file gia' presente (una
            # registrazione precedente, un file di WinWCP) non si apre mai in
            # scrittura, anche se il nome fosse stato calcolato male.
            self._f = open(percorso, "x+b")
        except FileExistsError:
            raise ErroreScrittura("il file %s esiste gia': non viene sovrascritto" % percorso)
        except (IOError, OSError) as e:
            raise ErroreScrittura("impossibile creare %s: %s" % (percorso, e))
        try:
            self._scrivi_intestazione(0)
            self._sincronizza()
        except (IOError, OSError) as e:
            raise ErroreScrittura("impossibile creare %s: %s" % (percorso, e))

    # -- intestazione -------------------------------------------------------
    def testo_intestazione(self, nr):
        righe = []
        a = righe.append
        a("VER=9")
        a("VERPROG=%s" % self.verprog)
        a("CTIME=%s" % data_ora_it(self.ora_creazione))
        if self.rtimesecs is not None:
            sec = float(self.rtimesecs)
        else:
            sec = (self.ora_inizio.hour * 3600 + self.ora_inizio.minute * 60 +
                   self.ora_inizio.second + self.ora_inizio.microsecond * 1e-6)
        sec = max(sec, 0.001)
        a("RTIMESECS=%s" % numero_it_decimali(sec, 3))
        a("RTIME=%s" % data_ora_it(self.ora_inizio))
        a("NBH=%d" % NBH)
        a("ADCMAX=%d" % self.adcmax)
        a("NC=%d" % self.nc)
        a("NBA=%d" % NBA_SETTORI)
        a("NBD=%d" % self.nbd)
        a("AD=%s" % numero_it(self.ad))
        a("NR=%d" % nr)
        a("DT=%s" % numero_it(self.dt, 6))
        a("NZ=%d" % self.nz)
        for c, ch in enumerate(self.canali):
            a("YO%d=%d" % (c, ch.get("yo", c)))
            a("YU%d=%s" % (c, _pulisci_testo(ch.get("unita", "mV"), 8)))
            a("YN%d=%s" % (c, _pulisci_testo(ch.get("nome", "Ch.%d" % c), 16)))
            a("YG%d=%s" % (c, numero_it(ch.get("yg", 0.001))))
            a("YZ%d=%s" % (c, numero_it(ch.get("yz", 0))))
            a("YR%d=%d" % (c, ch.get("yr", -1)))
        a("TXPERC=0")
        a("PKPAVG=1")
        a("NSVCHAN=0")
        a("NSVALIGN=0")
        a("NSVTYPR=0")
        a("NSVS2P=F")
        a("NSVCUR0=0")
        a("NSVCUR1=0")
        a("ID=%s" % self.ident)
        if self.separatore != ",":
            # numeri col punto (PC con impostazioni internazionali inglesi);
            # date, nomi e testi restano come sono
            righe = [r if r.split("=", 1)[0] in ("ID", "CTIME", "RTIME") or r.startswith("YN") or
                     r.startswith("YU") else r.replace(",", self.separatore) for r in righe]
        testo = "\r\n".join(righe) + "\r\n"
        b = testo.encode("latin-1", "replace")
        if len(b) >= NBH:
            raise ValueError("intestazione troppo lunga (%d byte)" % len(b))
        return b + b"\x00" * (NBH - len(b))

    def _scrivi_intestazione(self, nr):
        self._f.seek(0)
        self._f.write(self.testo_intestazione(nr))
        self.nr_su_disco = nr

    # -- blocco di analisi --------------------------------------------------
    def blocco_analisi(self, numero, ident=""):
        """numero: 1-based."""
        t = (numero - 1) * self.n * self.dt
        parti = [b"ACCEPTED", b"TEST", struct.pack("<fff", float(numero), t, self.dt),
                 struct.pack("<" + "f" * self.nc, *([self.ad] * self.nc))]
        idb = _pulisci_testo(ident or " ", MAX_IDENT).encode("latin-1", "replace")[:MAX_IDENT]
        parti.append(idb + b"\x00" * (MAX_IDENT - len(idb)))
        nval = max(self.nc, 8) * MAX_VAR_ANALISI
        valori = [0.0] * nval
        valori[0] = float(numero)
        valori[1] = float(numero)
        valori[2] = t
        parti.append(struct.pack("<" + "f" * nval, *valori))
        b = b"".join(parti)
        return b + b"\x00" * (NBA_SETTORI * SETTORE - len(b))

    # -- API ----------------------------------------------------------------
    def tempo_record(self):
        return self.n * self.dt

    def numero_record_corrente(self):
        """Numero (1-based) del record in corso di riempimento."""
        return self.record_completi + 1

    def imposta_ident_record(self, testo):
        """Testo (max 16 caratteri) mostrato da WinWCP per il record in corso."""
        self.ident_record = _pulisci_testo(testo, MAX_IDENT)
        self.sporco = True

    def aggiungi(self, campioni):
        """Accoda campioni int16 (interlacciati se nc>1).  Accetta lista,
        array('h') o array numpy."""
        if self.chiuso:
            return
        if compat.np is not None and isinstance(campioni, compat.np.ndarray):
            campioni = _np_in_array(campioni)
        elif not isinstance(campioni, array.array):
            campioni = array.array("h", [_satura16(v) for v in campioni])
        i = 0
        tot = len(campioni)
        dimensione = self.n * self.nc
        while i < tot:
            spazio = dimensione - self.riempiti
            k = min(spazio, tot - i)
            self.buf[self.riempiti:self.riempiti + k] = campioni[i:i + k]
            self.riempiti += k
            i += k
            self.sporco = True
            if self.riempiti >= dimensione:
                self._chiudi_record_corrente()
        self.campioni_totali += tot

    def _chiudi_record_corrente(self):
        numero = self.record_completi + 1
        dati = self.buf.tobytes()
        self.in_attesa.append((numero, self.ident_record, dati))
        self.record_completi += 1
        self.riempiti = 0
        self.ident_record = ""
        if len(self.in_attesa) > self.max_record_in_memoria:
            self.in_attesa.pop(0)
            self.persi_memoria += 1
        self._scrivi_in_attesa()

    def _scrivi_in_attesa(self):
        try:
            while self.in_attesa:
                numero, ident, dati = self.in_attesa[0]
                off = NBH + (numero - 1) * self.byte_record
                self._f.seek(off)
                self._f.write(self.blocco_analisi(numero, ident))
                self._f.write(dati)
                self.in_attesa.pop(0)
                if numero > self.nr_su_disco:
                    self._scrivi_intestazione(numero)
            return True
        except (IOError, OSError, ValueError) as e:
            self._registra_errore(e)
            return False

    def _registra_errore(self, e):
        self.n_errori += 1
        self.ultimo_errore = "%s: %s" % (os.path.basename(self.percorso), e)

    def flush(self, includi_parziale=True):
        """Scrive su disco quanto accumulato e chiama os.fsync.
        Restituisce True se tutto e' andato bene."""
        if self.chiuso or self._f is None:
            return False
        ok = self._scrivi_in_attesa()
        if ok and includi_parziale and self.riempiti > 0 and self.sporco:
            ok = self._scrivi_parziale()
        if ok:
            try:
                self._sincronizza()
                self.sporco = False
            except (IOError, OSError) as e:
                self._registra_errore(e)
                ok = False
        return ok

    def _scrivi_parziale(self):
        numero = self.record_completi + 1
        try:
            # dati presenti + ripetizione dell'ultimo campione di ogni canale
            nc = self.nc
            r = self.riempiti - (self.riempiti % nc)
            if r <= 0:
                return True
            ultimi = self.buf[r - nc:r]
            copia = array.array("h", self.buf[:r])
            mancanti = (self.n * nc - r) // nc
            copia.extend(ultimi * mancanti)
            off = NBH + (numero - 1) * self.byte_record
            self._f.seek(off)
            self._f.write(self.blocco_analisi(numero, self.ident_record))
            self._f.write(copia.tobytes())
            if numero > self.nr_su_disco:
                self._scrivi_intestazione(numero)
            return True
        except (IOError, OSError, ValueError) as e:
            self._registra_errore(e)
            return False

    def _sincronizza(self):
        self._f.flush()
        try:
            os.fsync(self._f.fileno())
        except (OSError, AttributeError):
            pass

    def chiudi(self, ident_finale=None):
        """Chiude il file.  Il record finale incompleto viene completato con
        l'ultimo valore (come WinWCP).  Restituisce il numero di record."""
        if self.chiuso:
            return self.nr_su_disco
        if ident_finale is not None:
            self.ident_record = _pulisci_testo(ident_finale, MAX_IDENT)
        self.sporco = True
        self.flush(includi_parziale=True)
        try:
            if self._f is not None:
                self._f.close()
        except (IOError, OSError) as e:
            self._registra_errore(e)
        self.chiuso = True
        return self.nr_su_disco

    def durata_scritta(self):
        return self.campioni_totali // self.nc * self.dt


def _np_in_array(a):
    np = compat.np
    if a.dtype != np.int16:
        a = np.clip(np.round(a), -32768, 32767).astype(np.int16)
    out = array.array("h")
    out.frombytes(a.astype("<i2").tobytes())
    if sys.byteorder == "big":
        out.byteswap()
    return out


def _satura16(v):
    v = int(round(v))
    if v > 32767:
        return 32767
    if v < -32768:
        return -32768
    return v


def _pulisci_testo(s, lunghezza):
    s = "%s" % (s,)
    s = s.replace("\r", " ").replace("\n", " ").replace("\x00", " ").replace("=", "-")
    try:
        s.encode("latin-1")
    except UnicodeEncodeError:
        s = s.encode("latin-1", "replace").decode("latin-1")
    return s[:lunghezza]


def nome_base_libero(cartella, data=None, suffissi=("_raw.wcp", "_filt.wcp", ".json", ".wcp")):
    """Nome base 'AAMMGG_NNN' come WinWCP: indice piu' basso non usato."""
    data = data or datetime.date.today()
    radice = "%02d%02d%02d" % (data.year % 100, data.month, data.day)
    i = 0
    while True:
        i += 1
        base = "%s_%03d" % (radice, i)
        if not any(os.path.exists(os.path.join(cartella, base + s)) for s in suffissi):
            return base
