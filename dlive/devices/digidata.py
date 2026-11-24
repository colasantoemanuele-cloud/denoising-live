# -*- coding: utf-8 -*-
"""Digidata1322Device: acquisizione continua dal Digidata 1322A tramite
AxDD132x.dll (ctypes).

Il metodo di acquisizione ricalca quello di WinWCP (dd1320.pas,
DD132X_ADCToMemory / DD132X_GetADCSamples), che su questa scheda funziona:
  * buffer circolare nella memoria del PC diviso in sotto-buffer DATABUFFER
    collegati ad anello, di 600 x canali_in x canali_out campioni ciascuno;
  * il buffer e' riempito con EMPTY_FLAG (32767) e con eAIDataBits =
    DD132X_Bit0Tag quel valore non puo' comparire nei dati: i campioni nuovi
    sono quelli diversi da EMPTY_FLAG a partire dal puntatore di lettura;
    dopo la copia si rimettono a EMPTY_FLAG;
  * (opzionale, come WinWCP) le uscite DAC0, DAC1 e digitali sono incluse nel
    protocollo e tenute al valore di riposo (0 V corretto con l'offset di
    calibrazione).
Come WinWCP anche uChunksPerSecond: dd1320.pas non conosce il campo (lo
dichiara "Unused" nel record TDD132X_Protocol) e lo lascia quindi a 0;
l'header Axon suggerisce 20.  Si usa 0, il valore che funziona con WinWCP
sul PC del laboratorio (configurabile: [digidata] chunks_per_second).
In piu' rispetto a WinWCP: DD132X_GetAcquisitionPosition per accorgersi di
un overrun (il programma non ha letto in tempo e la scheda ha riscritto dati
non ancora letti): i campioni persi vengono contati e segnalati.
"""
import array
import ctypes
import glob
import os
import time

from .. import compat
from .. import registro
from .. import sysinfo
from ..rilevamento import RIMEDIO_ASPI, RIMEDIO_DLL  # noqa: F401 (usati anche dalla diagnostica)
from .base import Blocco, Dispositivo, ErroreDispositivo
from . import axdd132x as ax

NOMI_DLL = ("AxDD132x.dll", "axdd132x.dll", "AXDD132X.DLL")


def percorsi_candidati_dll(percorso_config="", cartella_programma=None):
    """Elenco ordinato di percorsi dove cercare AxDD132x.dll."""
    cand = []

    def aggiungi(p):
        if p:
            p = os.path.normpath(p)
            if p.lower() not in [c.lower() for c in cand]:
                cand.append(p)

    if percorso_config:
        if os.path.isdir(percorso_config):
            for n in NOMI_DLL:
                aggiungi(os.path.join(percorso_config, n))
        else:
            aggiungi(percorso_config)
    cartelle = []
    if cartella_programma:
        cartelle.append(cartella_programma)
    # cartelle di WinWCP (e' la DLL che WinWCP usa davvero con questa scheda)
    for pf in sysinfo.cartelle_programmi():
        cartelle.extend(sorted(glob.glob(os.path.join(pf, "WinWCP*")), reverse=True))
        cartelle.extend(sorted(glob.glob(os.path.join(pf, "Strathclyde*", "WinWCP*")), reverse=True))
        cartelle.extend(sorted(glob.glob(os.path.join(pf, "Molecular Devices", "pCLAMP*")), reverse=True))
        cartelle.extend(sorted(glob.glob(os.path.join(pf, "Axon*", "*")), reverse=True))
    # WinWCP carica AxDD132x.dll dalla PROPRIA cartella (dd1320.pas,
    # DD132X_LoadLibrary: ExtractFilePath(ParamStr(0))): C:\WinWCP, C:\WinWCPXE...
    for radice in sorted(glob.glob(r"C:\WinWCP*")) + [r"C:\Axon"]:
        if os.path.isdir(radice):
            cartelle.append(radice)
            cartelle.extend(sorted(glob.glob(os.path.join(radice, "*")), reverse=True))
            cartelle.extend(sorted(glob.glob(os.path.join(radice, "*", "*")), reverse=True))
    windir = os.environ.get("SystemRoot") or os.environ.get("windir") or r"C:\WINDOWS"
    cartelle.append(os.path.join(windir, "system32"))
    cartelle.append(windir)
    for c in cartelle:
        for n in NOMI_DLL[:1]:
            p = os.path.join(c, n)
            if os.path.isfile(p):
                aggiungi(p)
    return [p for p in cand if os.path.isfile(p)] + [p for p in cand if not os.path.isfile(p)]


class Digidata1322Device(Dispositivo):
    modalita = "digidata"

    def __init__(self, canale=2, fs=1000.0, range_v=10.0, percorso_dll="",
                 cartella_programma=None, uscite="come_winwcp", campioni_buffer=1000000,
                 intervallo_lettura=0.05, chunks_per_second=0, calibrazione=None,
                 controlla_processi=True):
        self.canale = int(canale)
        self.fs_richiesta = float(fs)
        self.range_v = float(range_v)
        self.percorso_dll_config = percorso_dll
        self.cartella_programma = cartella_programma
        self.uscite = uscite
        self.campioni_buffer = int(campioni_buffer)
        self.intervallo_lettura = float(intervallo_lettura)
        self.chunks = int(chunks_per_second)
        self._cal = dict(calibrazione or {"yg": 0.001, "yz": 0.0, "unita": "mV",
                                          "nome": "AI%d" % canale})
        self._cal.setdefault("ad", self.range_v)
        self._cal.setdefault("adcmax", 32677)
        self.controlla_processi = controlla_processi
        self.log = registro.get()
        self.lib = None
        self.percorso_dll = None
        self.hdev = None
        self.info_dev = None
        self.cal_dati = None
        self.n_dac = 0
        self.fs = 0.0
        self.intervallo_us = 0.0
        self._ai = None
        self._ai_flags = None
        self._ai_bufs = None
        self._ao = None
        self._ao_bufs = None
        self._proto = None
        self._n = 0
        self._rp = 0
        self._consumati = 0
        self._attivo = False
        self._ultimo = 0.0
        self._t_avvio = 0.0
        self._posizione_affidabile = True
        self._avvisi_posizione = 0
        self.overrun = 0
        self.note = []

    # ------------------------------------------------------------------
    def calibrazione(self):
        return dict(self._cal)

    def descrizione(self):
        nome = ""
        if self.info_dev is not None:
            nome = self.info_dev.szName.decode("latin-1", "replace").strip()
        return "Digidata %s, ingresso AI%d, %g Hz" % (nome or "1322A", self.canale, self.fs or self.fs_richiesta)

    def info(self):
        d = {"modalita": self.modalita, "fs_hz": self.fs, "canale_ingresso": self.canale,
             "range_v": self.range_v, "dll": self.percorso_dll,
             "versione_dll": ax.versione_file(self.percorso_dll) if self.percorso_dll else "",
             "intervallo_campionamento_us": self.intervallo_us, "uscite": self.uscite,
             "campioni_buffer": self._n}
        if self.info_dev is not None:
            i = self.info_dev
            d.update({"nome": i.szName.decode("latin-1", "replace"),
                      "firmware": i.szFirmwareVersion.decode("latin-1", "replace"),
                      "versione_prodotto": i.szProductVersion.decode("latin-1", "replace"),
                      "numero_serie": i.uSerialNumber, "adattatore": i.byAdaptor,
                      "target": i.byTarget})
        if self.cal_dati is not None:
            d.update({"adc_gain_ratio": self.cal_dati.dADCGainRatio,
                      "adc_offset": self.cal_dati.nADCOffset, "n_dac": self.n_dac})
        return d

    # ------------------------------------------------------------------
    def carica_dll(self):
        if not compat.SU_WINDOWS:
            raise ErroreDispositivo("La modalita' Digidata funziona solo su Windows "
                                    "(su Linux usare --simulazione).")
        errori = ax.controlla_strutture()
        if errori:
            raise ErroreDispositivo("Strutture ctypes di dimensione inattesa: %s" % "; ".join(errori))
        cand = percorsi_candidati_dll(self.percorso_dll_config, self.cartella_programma)
        tentativi = []
        for p in cand:
            if not os.path.isfile(p):
                continue
            try:
                lib = ax.LibreriaDD132x(p).carica()
            except OSError as e:
                tentativi.append("%s: %s" % (p, e))
                continue
            self.lib = lib
            self.percorso_dll = p
            self.log.info("DLL Digidata: %s (versione %s)", p, ax.versione_file(p) or "?")
            for n in lib.note:
                self.log.info("  %s", n)
            if lib.mancanti:
                self.log.info("  funzioni facoltative assenti: %s", ", ".join(lib.mancanti))
            return lib
        msg = "AxDD132x.dll non trovata o non caricabile."
        if tentativi:
            msg += " Tentativi: " + " | ".join(tentativi)
        else:
            msg += (" Cercata in: cartella del programma, cartelle di WinWCP, pCLAMP/AxoScope, "
                    "C:\\Axon\\..., system32.  " + RIMEDIO_DLL)
        raise ErroreDispositivo(msg)

    def apri(self):
        if self.controlla_processi:
            conc = sysinfo.programmi_concorrenti_attivi()
            if conc:
                raise ErroreDispositivo(
                    "La scheda Digidata e' gia' in uso da: %s.  Chiudere quel programma "
                    "(la scheda puo' essere usata da un solo programma alla volta) e riprovare."
                    % ", ".join(conc))
        if self.hdev is not None:
            # aperta e mai chiusa (errore precedente): si chiude prima di riaprire,
            # altrimenti il driver rifiuta la seconda apertura
            self.log.warning("Digidata gia' aperto: lo chiudo prima di riaprirlo")
            self.chiudi()
        if self.lib is None:
            self.carica_dll()
        lib = self.lib
        err = ctypes.c_int(0)
        info = ax.DD132X_Info()
        info.uLength = ctypes.sizeof(info)
        info.byAdaptor = 255
        info.byTarget = 255
        n = lib.DD132X_FindDevices(ctypes.byref(info), 1, ctypes.byref(err))
        if n < 1 or err.value != 0:
            aspi = ax.controlla_aspi()
            suggerimenti = ("Controllare che il Digidata sia acceso PRIMA di accendere il PC, "
                            "che il cavo SCSI e il terminatore siano collegati e che il "
                            "controller SCSI compaia in Gestione periferiche.")
            if not aspi["ok"]:
                suggerimenti = ("WinASPI non funziona (%s): %s.  " % (aspi["errore"], RIMEDIO_ASPI)) + suggerimenti
            raise ErroreDispositivo(
                "Nessun Digidata trovato (FindDevices=%d, %s).  %s"
                % (n, lib.testo_errore(None, err.value), suggerimenti))
        self.info_dev = info
        hdev = None
        for tentativo in range(2):   # WinWCP prova due volte (dopo l'accensione la prima fallisce)
            err.value = 0
            hdev = lib.DD132X_OpenDevice(info.byAdaptor, info.byTarget, ctypes.byref(err))
            if hdev and err.value == 0:
                break
            time.sleep(0.5)
        if not hdev or err.value != 0:
            raise ErroreDispositivo(
                "Digidata trovato ma impossibile aprirlo (%s).  Se WinWCP, AxoScope o "
                "Clampex sono aperti chiuderli; altrimenti spegnere e riaccendere il "
                "Digidata e riprovare." % lib.testo_errore(hdev, err.value))
        self.hdev = hdev
        cal = ax.DD132X_CalibrationData()
        cal.uLength = ctypes.sizeof(cal)
        err.value = 0
        if lib.DD132X_GetCalibrationData(hdev, ctypes.byref(cal), ctypes.byref(err)):
            self.cal_dati = cal
            self.n_dac = int(cal.wNumberOfDACs)
            if not (0 < self.n_dac <= 8):
                self.log.warning("Numero di DAC dalla calibrazione non plausibile: %d (uso 2)",
                                 self.n_dac)
                self.n_dac = 2
        else:
            self.log.warning("GetCalibrationData fallita (%s): uso offset DAC nulli",
                             lib.testo_errore(hdev, err.value))
            self.n_dac = 2
        # La frequenza effettiva va nota gia' dopo apri(): la Sessione la legge
        # subito per progettare il filtro (prima di avvia()).  Stesso calcolo
        # di _prepara_buffer: intervallo intero in microsecondi, 1 canale.
        self.intervallo_us = float(int(round(1e6 / self.fs_richiesta)))
        self.fs = 1e6 / self.intervallo_us
        self.log.info("Digidata aperto: %s", self.info())
        return self

    # ------------------------------------------------------------------
    def _prepara_buffer(self):
        n_in = 1
        n_out = (self.n_dac + 1) if self.uscite == "come_winwcp" else 1
        sub = 600 * n_in * n_out                     # DD132X_MaxSamplesPerSubBuf * ...
        n_sub = max(2, self.campioni_buffer // sub)
        n = n_sub * sub
        self._n = n
        self._ai = (ctypes.c_short * n)()
        self._riempi_vuoto(0, n)
        self._ai_flags = (ctypes.c_short * n)()
        self._ai_bufs = (ax.DATABUFFER * n_sub)()
        base_ai = ctypes.addressof(self._ai)
        base_fl = ctypes.addressof(self._ai_flags)
        for i in range(n_sub):
            b = self._ai_bufs[i]
            b.uNumSamples = sub
            b.uFlags = 0
            b.pnData = ctypes.cast(base_ai + i * sub * 2, ctypes.POINTER(ctypes.c_short))
            b.psDataFlags = base_fl + i * sub * 2
            b.pNextBuffer = ctypes.pointer(self._ai_bufs[(i + 1) % n_sub])
            b.pPrevBuffer = ctypes.pointer(self._ai_bufs[(i - 1) % n_sub])
        p = ax.DD132X_Protocol()
        p.uLength = ctypes.sizeof(p)
        self.intervallo_us = float(int(round(1e6 / self.fs_richiesta / n_in)))
        p.dSampleInterval = self.intervallo_us
        p.dwFlags = 0
        p.eTriggering = ax.DD132X_StartImmediately
        p.eAIDataBits = ax.DD132X_Bit0Tag
        p.uAIChannels = n_in
        p.anAIChannels[0] = self.canale
        p.pAIBuffers = ctypes.cast(self._ai_bufs, ctypes.POINTER(ax.DATABUFFER))
        p.uAIBuffers = n_sub
        if self.uscite == "come_winwcp":
            self._ao = (ctypes.c_short * n)()
            default = []
            for ch in range(self.n_dac):
                off = int(self.cal_dati.anDACOffset[ch]) if self.cal_dati is not None else 0
                default.append(-off)
            default.append(0)                               # uscite digitali a 0
            for i in range(n):
                self._ao[i] = default[i % n_out]
            self._ao_bufs = (ax.DATABUFFER * n_sub)()
            base_ao = ctypes.addressof(self._ao)
            for i in range(n_sub):
                b = self._ao_bufs[i]
                b.uNumSamples = sub
                b.uFlags = 0
                b.pnData = ctypes.cast(base_ao + i * sub * 2, ctypes.POINTER(ctypes.c_short))
                b.psDataFlags = None
                b.pNextBuffer = ctypes.pointer(self._ao_bufs[(i + 1) % n_sub])
                b.pPrevBuffer = ctypes.pointer(self._ao_bufs[(i - 1) % n_sub])
            p.uAOChannels = n_out
            for ch in range(self.n_dac):
                p.anAOChannels[ch] = ch
            p.anAOChannels[n_out - 1] = ax.DD132X_PROTOCOL_DIGITALOUTPUT
            p.pAOBuffers = ctypes.cast(self._ao_bufs, ctypes.POINTER(ax.DATABUFFER))
            p.uAOBuffers = n_sub
        else:
            p.uAOChannels = 0
            p.pAOBuffers = None
            p.uAOBuffers = 0
        p.uTerminalCount = 0
        p.eOutputPulseType = ax.DD132X_NoOutputPulse
        p.uChunksPerSecond = self.chunks
        self._proto = p
        self.fs = 1e6 / (self.intervallo_us * n_in)
        if abs(self.fs - self.fs_richiesta) > 1e-6:
            self.log.warning("Frequenza effettiva %.6g Hz (richiesta %.6g Hz)", self.fs, self.fs_richiesta)

    def _riempi_vuoto(self, inizio, k):
        """Rimette EMPTY_FLAG nei campioni [inizio, inizio+k) del buffer (k <= n)."""
        np = compat.np
        n = self._n
        if np is not None:
            vista = np.ctypeslib.as_array(self._ai)
            fine = inizio + k
            if fine <= n:
                vista[inizio:fine] = ax.EMPTY_FLAG
            else:
                vista[inizio:] = ax.EMPTY_FLAG
                vista[:fine - n] = ax.EMPTY_FLAG
        else:
            buf = self._ai
            E = ax.EMPTY_FLAG
            for i in range(inizio, inizio + k):
                buf[i % n] = E

    def avvia(self):
        if self.hdev is None:
            self.apri()
        lib = self.lib
        err = ctypes.c_int(0)
        if lib.DD132X_IsAcquiring(self.hdev):
            lib.DD132X_StopAcquisition(self.hdev, ctypes.byref(err))
        self._prepara_buffer()
        err.value = 0
        if not lib.DD132X_SetProtocol(self.hdev, ctypes.byref(self._proto), ctypes.byref(err)):
            raise ErroreDispositivo("SetProtocol rifiutato dalla scheda (%s)"
                                    % lib.testo_errore(self.hdev, err.value))
        err.value = 0
        if not lib.DD132X_StartAcquisition(self.hdev, ctypes.byref(err)):
            raise ErroreDispositivo("StartAcquisition fallita (%s)"
                                    % lib.testo_errore(self.hdev, err.value))
        self._rp = 0
        self._consumati = 0
        # stato di ogni acquisizione: azzerato anche quando la scheda si riavvia
        self.overrun = 0
        self._posizione_affidabile = True
        self._avvisi_posizione = 0
        self._ultimo = time.time()
        self._t_avvio = self._ultimo
        self._attivo = True
        self.log.info("Acquisizione Digidata avviata: AI%d, intervallo %g us (%.6g Hz), "
                      "buffer %d campioni (%.0f s), uscite=%s, chunks=%d",
                      self.canale, self.intervallo_us, self.fs, self._n, self._n / self.fs,
                      self.uscite, self.chunks)

    def posizione(self):
        """Campioni acquisiti dalla scheda dall'avvio (None se non disponibile)."""
        if not self.lib.ha("DD132X_GetAcquisitionPosition"):
            return None
        pos = ax.LONGLONG(0)
        err = ctypes.c_int(0)
        ok = self.lib.DD132X_GetAcquisitionPosition(self.hdev, ctypes.byref(pos), ctypes.byref(err))
        if not ok or err.value != 0:
            return None
        return int(pos.value)

    def _conta_nuovi(self):
        np = compat.np
        n = self._n
        rp = self._rp
        E = ax.EMPTY_FLAG
        if np is not None:
            vista = np.ctypeslib.as_array(self._ai)
            seg = vista[rp:]
            idx = np.flatnonzero(seg == E)
            if len(idx):
                return int(idx[0])
            k = len(seg)
            idx = np.flatnonzero(vista[:rp] == E)
            return k + (int(idx[0]) if len(idx) else rp)
        buf = self._ai
        k = 0
        i = rp
        while k < n and buf[i] != E:
            k += 1
            i += 1
            if i == n:
                i = 0
        return k

    def _copia(self, k):
        np = compat.np
        n = self._n
        rp = self._rp
        out = array.array("h")
        if np is not None:
            vista = np.ctypeslib.as_array(self._ai)
            fine = rp + k
            if fine <= n:
                parte = vista[rp:fine].copy()
            else:
                parte = np.concatenate((vista[rp:], vista[:fine - n]))
            out.frombytes(parte.astype("<i2").tobytes())
        else:
            buf = self._ai
            for i in range(rp, rp + k):
                out.append(buf[i % n])
        return out

    def leggi(self, timeout=0.2):
        if not self._attivo:
            time.sleep(min(timeout, 0.05))
            return None
        attesa = self.intervallo_lettura - (time.time() - self._ultimo)
        if attesa > 0:
            time.sleep(min(attesa, timeout))
        self._ultimo = time.time()
        persi = 0
        pos = self.posizione() if self._posizione_affidabile else None
        if pos is not None:
            atteso = (time.time() - self._t_avvio) * self.fs
            arretrati = pos - self._consumati
            if arretrati < -600 or pos > 1.1 * atteso + 0.25 * self.fs:
                # il contatore non si comporta come previsto: non lo si usa
                self._avvisi_posizione += 1
                if self._avvisi_posizione >= 3:
                    self._posizione_affidabile = False
                    self.log.warning("GetAcquisitionPosition non coerente (pos=%d, letti=%d, "
                                     "attesi circa %d): rilevamento overrun tramite contatore "
                                     "disattivato", pos, self._consumati, atteso)
            elif arretrati > self._n - 600:
                return self._recupera_overrun(pos)
        k = self._conta_nuovi()
        if k >= self._n:
            # buffer interamente pieno senza valori vuoti: overrun certo
            return self._recupera_overrun(pos if pos is not None else self._consumati + self._n)
        if k <= 0:
            return None
        dati = self._copia(k)
        self._riempi_vuoto(self._rp, k)
        indice = self._consumati
        self._rp = (self._rp + k) % self._n
        self._consumati += k
        return Blocco(dati, indice, persi)

    def _recupera_overrun(self, pos):
        """La scheda ha riscritto campioni non ancora letti: si scartano i dati
        non affidabili, ci si risincronizza e si dichiarano i campioni persi."""
        self._riempi_vuoto(0, self._n)
        pos2 = self.posizione() if self._posizione_affidabile else None
        if pos2 is None:
            pos2 = pos
        persi = max(0, pos2 - self._consumati)
        self.overrun += 1
        self.log.error("OVERRUN del buffer della scheda: %d campioni persi (posizione %d, "
                       "letti %d)", persi, pos2, self._consumati)
        self._rp = pos2 % self._n
        self._consumati = pos2
        return Blocco(array.array("h"), pos2, persi)

    def leggi_valore_singolo(self, canale=None):
        """Lettura di un singolo campione (DD132X_GetAIValue), fuori dal protocollo."""
        if not self.lib.ha("DD132X_GetAIValue"):
            raise ErroreDispositivo("DD132X_GetAIValue non esportata dalla DLL")
        v = ctypes.c_short(0)
        err = ctypes.c_int(0)
        ok = self.lib.DD132X_GetAIValue(self.hdev, self.canale if canale is None else canale,
                                        ctypes.byref(v), ctypes.byref(err))
        if not ok or err.value != 0:
            raise ErroreDispositivo("GetAIValue fallita (%s)" % self.lib.testo_errore(self.hdev, err.value))
        return int(v.value)

    def ferma(self):
        if self.hdev is not None and self.lib is not None:
            err = ctypes.c_int(0)
            try:
                if self.lib.DD132X_IsAcquiring(self.hdev):
                    if not self.lib.DD132X_StopAcquisition(self.hdev, ctypes.byref(err)):
                        self.log.warning("StopAcquisition: %s", self.lib.testo_errore(self.hdev, err.value))
            except Exception as e:
                self.log.warning("Errore fermando l'acquisizione: %s", e)
        self._attivo = False

    def chiudi(self):
        self.ferma()
        if self.hdev is not None and self.lib is not None:
            err = ctypes.c_int(0)
            try:
                self.lib.DD132X_CloseDevice(self.hdev, ctypes.byref(err))
            except Exception as e:
                self.log.warning("CloseDevice: %s", e)
            self.log.info("Digidata chiuso")
        self.hdev = None
