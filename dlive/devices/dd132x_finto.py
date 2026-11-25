# -*- coding: utf-8 -*-
"""DLL AxDD132x "finta", in Python, SOLO PER I TEST.

Imita il comportamento documentato del driver (header Axon + dd1320.pas):
legge il protocollo, controlla che i sotto-buffer siano collegati ad anello
e, in un thread, scrive i campioni nei buffer alla frequenza richiesta,
come fa la DLL vera.  Serve a collaudare Digidata1322Device e la
diagnostica su un PC senza scheda (Linux compreso).
"""
import ctypes
import math
import random
import threading
import time

from . import axdd132x as ax


class _Funzione(object):
    def __init__(self, f):
        self.f = f

    def __call__(self, *a):
        return self.f(*a)


def _obj(arg):
    """Oggetto puntato da un ctypes.byref(...) o da un puntatore."""
    if hasattr(arg, "_obj"):
        return arg._obj
    if hasattr(arg, "contents"):
        return arg.contents
    return arg


class LibreriaFinta(object):
    def __init__(self, segnale_mv=None, rumore_mv=2.0, trovato=True, apribile=True,
                 blocco_dopo_s=None, posizione_scala=1.0, ingresso_segnale=None):
        self.percorso = "<DLL finta per i test>"
        self.note = ["DLL finta (test)"]
        self.mancanti = []
        self.segnale_mv = segnale_mv or (lambda t: 20.0 * math.sin(2 * math.pi * 0.5 * t) + 30.0)
        self.rumore_mv = rumore_mv
        self.trovato = trovato
        self.apribile = apribile
        self.blocco_dopo_s = blocco_dopo_s       # simula un PC che smette di leggere
        self.posizione_scala = posizione_scala   # per simulare un contatore "strano"
        # None = segnale su tutti gli ingressi; N = segnale solo sull'ingresso N
        # nelle letture singole (GetAIValue), gli altri restano a +-2 conteggi
        self.ingresso_segnale = ingresso_segnale
        self.protocollo = None
        self.acquisisce = False
        self.scritti = 0
        self._thread = None
        self._stop = threading.Event()
        self.errori_protocollo = []
        self.chunks_ricevuti = None       # uChunksPerSecond dell'ultimo protocollo
        self.funzioni = {}
        for nome in ax.FIRME:
            if hasattr(self, "_" + nome):
                self.funzioni[nome] = _Funzione(getattr(self, "_" + nome))

    def ha(self, nome):
        return nome in self.funzioni

    def __getattr__(self, nome):
        f = self.__dict__.get("funzioni", {}).get(nome)
        if f is None:
            raise AttributeError(nome)
        return f

    def testo_errore(self, hdev, codice=None):
        return "errore finto %s" % codice

    # ------------------------------------------------------------ funzioni
    def _DD132X_FindDevices(self, pinfo, nmax, perr):
        info = _obj(pinfo)
        if not self.trovato:
            _obj(perr).value = 1000
            return 0
        info.byAdaptor = 1
        info.byTarget = 0
        info.szName = b"Digidata 1322A"
        info.szManufacturer = b"Axon (finto)"
        info.szFirmwareVersion = b"1.2"
        info.szProductVersion = b"A"
        info.uSerialNumber = 12345
        _obj(perr).value = 0
        return 1

    def _DD132X_OpenDevice(self, a, t, perr):
        if not self.apribile:
            _obj(perr).value = 9999
            return None
        _obj(perr).value = 0
        return 0x1234

    def _DD132X_CloseDevice(self, h, perr):
        self._ferma()
        return 1

    def _DD132X_GetCalibrationData(self, h, pcal, perr):
        cal = _obj(pcal)
        cal.wNumberOfDACs = 2
        cal.anDACOffset[0] = 3
        cal.anDACOffset[1] = -2
        cal.dADCGainRatio = 1.0
        cal.nADCOffset = 0
        return 1

    def _DD132X_SetProtocol(self, h, pp, perr):
        p = _obj(pp)
        e = []
        if p.uLength != ctypes.sizeof(ax.DD132X_Protocol):
            e.append("uLength %d" % p.uLength)
        if p.uAIChannels < 1 or p.dSampleInterval <= 0:
            e.append("canali/intervallo non validi")
        # il primo buffer e i successivi devono formare un anello di uAIBuffers elementi
        primo = ctypes.addressof(p.pAIBuffers.contents)
        b = p.pAIBuffers.contents
        for _ in range(p.uAIBuffers):
            b = b.pNextBuffer.contents
        if ctypes.addressof(b) != primo:
            e.append("anello dei buffer AI non chiuso")
        if p.uAOChannels:
            primo = ctypes.addressof(p.pAOBuffers.contents)
            b = p.pAOBuffers.contents
            for _ in range(p.uAOBuffers):
                b = b.pNextBuffer.contents
            if ctypes.addressof(b) != primo:
                e.append("anello dei buffer AO non chiuso")
        self.errori_protocollo = e
        # il driver vero accetta 0 (WinWCP lo manda sempre a 0: "Unused" in
        # dd1320.pas) e usa il proprio valore predefinito
        self.chunks_ricevuti = int(p.uChunksPerSecond)
        if e:
            _obj(perr).value = 8
            return 0
        self.protocollo = p
        return 1

    def _DD132X_StartAcquisition(self, h, perr):
        if self.protocollo is None:
            _obj(perr).value = 10
            return 0
        self._stop.clear()
        self.scritti = 0
        self.acquisisce = True
        self._thread = threading.Thread(target=self._scrivi, name="dll_finta")
        self._thread.daemon = True
        self._thread.start()
        return 1

    def _DD132X_StopAcquisition(self, h, perr):
        self._ferma()
        return 1

    def _DD132X_IsAcquiring(self, h):
        return 1 if self.acquisisce else 0

    def _DD132X_GetAcquisitionPosition(self, h, ppos, perr):
        _obj(ppos).value = int(self.scritti * self.posizione_scala)
        return 1

    def _DD132X_GetAIValue(self, h, canale, pv, perr):
        if self.ingresso_segnale is not None and canale != self.ingresso_segnale:
            _obj(pv).value = random.choice((-2, 0, 0, 2))        # ingresso scollegato
        else:
            _obj(pv).value = self._campione(time.time())
        return 1

    def _DD132X_GetLastErrorText(self, h, buf, n, perr):
        return 0

    # ------------------------------------------------------------ interno
    def _ferma(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(2.0)
        self.acquisisce = False

    def _campione(self, t):
        mv = self.segnale_mv(t) + random.gauss(0, self.rumore_mv)
        v = int(round(mv * 0.001 * 32677 / 10.0)) & ~1        # bit 0 = TAG = 0
        return max(-32768, min(32766, v))

    def _scrivi(self):
        p = self.protocollo
        fs = 1e6 / p.dSampleInterval
        bufs = []
        b = p.pAIBuffers.contents
        for _ in range(p.uAIBuffers):
            bufs.append((b.pnData, b.uNumSamples))
            b = b.pNextBuffer.contents
        t0 = time.time()
        ib = 0
        pos = 0
        while not self._stop.is_set():
            if self.blocco_dopo_s is not None and time.time() - t0 > self.blocco_dopo_s:
                pass   # la scheda continua: e' il PC che (nel test) non legge
            dovuti = int((time.time() - t0) * fs) - self.scritti
            for _ in range(max(0, dovuti)):
                dati, n = bufs[ib]
                dati[pos] = self._campione(t0 + self.scritti / fs)
                pos += 1
                self.scritti += 1
                if pos >= n:
                    pos = 0
                    ib = (ib + 1) % len(bufs)
            time.sleep(0.01)
