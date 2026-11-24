# -*- coding: utf-8 -*-
"""Dichiarazioni ctypes per AxDD132x.dll (Axon Digidata 1320/1321/1322).

UNICO modulo che contiene le firme del driver.  Fonti, in ordine di fiducia:

  1. header ufficiale Axon AXDD132X.HPP (riferimenti/sdk_axon/AxDD132x.h,
     copia pubblicata nel progetto clampy su GitHub);
  2. dd1320.pas di John Dempster (componente SESLabIO usato da WinWCP:
     riferimenti/winwcp_chiave/dd1320.pas), cioe' il codice che pilota
     davvero questa scheda in laboratorio;
  3. tabella degli export delle DLL estratte (riferimenti/dll/, vedi README).

Le due fonti concordano su tutto quello che usiamo:
  * convenzione di chiamata stdcall (WINAPI / 'stdcall' in Delphi);
  * strutture impacchettate a 1 byte: DD132X_Info 384 byte, DD132X_Protocol
    832 byte, DATABUFFER 24 byte, DD132X_CalibrationData 256 byte;
  * HDD132X e' un handle (puntatore); BOOL a 32 bit.
Punti incerti (verificati passo per passo da diagnostica_digidata.py):
  * DD132X_CalibrationData: l'header ha 16 DAC, dd1320.pas 8.  Gli offset dei
    primi 8 DAC e il guadagno/offset dell'ADC sono nella stessa posizione in
    entrambi; solo i guadagni dei DAC differiscono (non li usiamo).
  * uChunksPerSecond: nell'header (default 20), "Unused" in dd1320.pas
    (WinWCP lo lascia a 0).  Configurabile.
  * GetAcquisitionPosition: contatore a 64 bit dei campioni acquisiti; usato
    solo per rilevare gli overrun (la lettura dei dati usa il metodo di
    WinWCP: buffer riempito con un valore "vuoto" e scansione).
"""
import ctypes
import os

from ..compat import SU_WINDOWS

if SU_WINDOWS:
    from ctypes import wintypes
    UINT = wintypes.UINT
    BYTE = wintypes.BYTE
    DWORD = wintypes.DWORD
    WORD = wintypes.WORD
    BOOL = wintypes.BOOL
else:  # per poter importare il modulo (e testare le strutture) anche su Linux
    UINT = ctypes.c_uint
    BYTE = ctypes.c_ubyte
    DWORD = ctypes.c_uint32
    WORD = ctypes.c_ushort
    BOOL = ctypes.c_int

ADC_VALUE = ctypes.c_short
HDD132X = ctypes.c_void_p
LONGLONG = ctypes.c_longlong

DD132X_MAXAICHANNELS = 16
DD132X_MAXAOCHANNELS = 16
DD132X_SCANLIST_SIZE = 64

DD132X_PROTOCOL_STOPONTC = 0x00000001
DD132X_PROTOCOL_DIGITALOUTPUT = 0x0040
DD132X_PROTOCOL_NULLOUTPUT = 0x0050

# DD132X_Triggering
DD132X_StartImmediately = 0
DD132X_ExternalStart = 1
DD132X_LineTrigger = 2
# DD132X_AIDataBits
DD132X_Bit0Data = 0
DD132X_Bit0ExtStart = 1
DD132X_Bit0Line = 2
DD132X_Bit0Tag = 3
DD132X_Bit0Tag_Bit1ExtStart = 4
DD132X_Bit0Tag_Bit1Line = 5
# DD132X_OutputPulseType
DD132X_NoOutputPulse = 0

# Valore che WinWCP usa per marcare i campioni non ancora acquisiti: con
# eAIDataBits = DD132X_Bit0Tag il bit 0 di ogni campione e' l'ingresso TAG
# (0 se non collegato), quindi 32767 (dispari) non compare nei dati.
EMPTY_FLAG = 32767

ERRORI = {
    1: "ASPINOTFOUND: driver WinASPI (wnaspi32.dll / aspi32.sys) non trovato",
    2: "OUTOFMEMORY: memoria insufficiente",
    3: "NOTDD132X: il dispositivo non e' un Digidata 132x",
    4: "RAMWAREOPEN", 5: "RAMWAREREAD", 6: "RAMWAREWRITE", 7: "RAMWARESTART",
    8: "SETAIPROTOCOL: protocollo di acquisizione rifiutato",
    9: "SETAOPROTOCOL: protocollo di uscita rifiutato",
    10: "STARTACQ: impossibile avviare l'acquisizione",
    11: "STOPACQ", 12: "PAUSEACQ", 13: "READDATA: errore di lettura dati",
    14: "WRITEDATA", 15: "CALIBRATION", 16: "DIAGNOSTICS",
    17: "DTERM_READ", 18: "DTERM_WRITE", 19: "DTERM_BUSY", 20: "DTERM_SETBAUD",
    1000: "ASPIERROR: errore del bus SCSI / WinASPI",
    9999: "CANTCOMPLETE",
}


class DD132X_Info(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("uLength", UINT), ("byAdaptor", BYTE), ("byTarget", BYTE),
        ("byImageType", BYTE), ("byResetType", BYTE),
        ("szManufacturer", ctypes.c_char * 16), ("szName", ctypes.c_char * 32),
        ("szProductVersion", ctypes.c_char * 8), ("szFirmwareVersion", ctypes.c_char * 16),
        ("uInputBufferSize", UINT), ("uOutputBufferSize", UINT), ("uSerialNumber", UINT),
        ("uClockResolution", UINT), ("uMinClockTicks", UINT), ("uMaxClockTicks", UINT),
        ("byUnused", BYTE * 280),
    ]


class DATABUFFER(ctypes.Structure):
    pass


DATABUFFER._pack_ = 1
DATABUFFER._fields_ = [
    ("uNumSamples", UINT), ("uFlags", UINT),
    ("pnData", ctypes.POINTER(ADC_VALUE)), ("psDataFlags", ctypes.c_void_p),
    ("pNextBuffer", ctypes.POINTER(DATABUFFER)), ("pPrevBuffer", ctypes.POINTER(DATABUFFER)),
]


class DD132X_Protocol(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("uLength", UINT), ("dSampleInterval", ctypes.c_double), ("dwFlags", DWORD),
        ("eTriggering", ctypes.c_int), ("eAIDataBits", ctypes.c_int),
        ("uAIChannels", UINT), ("anAIChannels", ctypes.c_int * DD132X_SCANLIST_SIZE),
        ("pAIBuffers", ctypes.POINTER(DATABUFFER)), ("uAIBuffers", UINT),
        ("uAOChannels", UINT), ("anAOChannels", ctypes.c_int * DD132X_SCANLIST_SIZE),
        ("pAOBuffers", ctypes.POINTER(DATABUFFER)), ("uAOBuffers", UINT),
        ("uTerminalCount", LONGLONG),
        ("eOutputPulseType", ctypes.c_int), ("bOutputPulsePolarity", ctypes.c_short),
        ("nOutputPulseChannel", ctypes.c_short), ("wOutputPulseThreshold", WORD),
        ("wOutputPulseHystDelta", WORD), ("uChunksPerSecond", UINT),
        ("byUnused", BYTE * 248),
    ]


class DD132X_CalibrationData(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("uLength", UINT), ("uEquipmentStatus", UINT), ("dADCGainRatio", ctypes.c_double),
        ("nADCOffset", ctypes.c_short), ("byUnused1", BYTE * 46),
        ("wNumberOfDACs", WORD), ("byUnused2", BYTE * 6),
        ("anDACOffset", ctypes.c_short * DD132X_MAXAOCHANNELS),
        ("adDACGainRatio", ctypes.c_double * DD132X_MAXAOCHANNELS),
        ("byUnused4", BYTE * 24),
    ]


DIMENSIONI_ATTESE = {"DD132X_Info": 384, "DD132X_Protocol": 832,
                     "DD132X_CalibrationData": 256, "DATABUFFER": 24}
# valori per Python a 32 bit (come su XP): con puntatori a 8 byte (Python a
# 64 bit, solo per i test su Linux) Protocol e DATABUFFER crescono.


def dimensioni_attese():
    p = ctypes.sizeof(ctypes.c_void_p)
    d = dict(DIMENSIONI_ATTESE)
    d["DD132X_Protocol"] = 832 + 2 * (p - 4)
    d["DATABUFFER"] = 8 + 4 * p
    return d


def controlla_strutture():
    """Restituisce una lista di discrepanze (vuota se tutto torna)."""
    err = []
    for nome, attesa in dimensioni_attese().items():
        s = ctypes.sizeof(globals()[nome])
        if s != attesa:
            err.append("%s: %d byte invece di %d" % (nome, s, attesa))
    return err


# Funzioni usate, con firma (restype, argtypes).
FIRME = {
    "DD132X_FindDevices": (UINT, [ctypes.POINTER(DD132X_Info), UINT, ctypes.POINTER(ctypes.c_int)]),
    "DD132X_OpenDevice": (HDD132X, [BYTE, BYTE, ctypes.POINTER(ctypes.c_int)]),
    "DD132X_CloseDevice": (BOOL, [HDD132X, ctypes.POINTER(ctypes.c_int)]),
    "DD132X_GetDeviceInfo": (BOOL, [HDD132X, ctypes.POINTER(DD132X_Info), ctypes.POINTER(ctypes.c_int)]),
    "DD132X_SetProtocol": (BOOL, [HDD132X, ctypes.POINTER(DD132X_Protocol), ctypes.POINTER(ctypes.c_int)]),
    "DD132X_GetProtocol": (BOOL, [HDD132X, ctypes.POINTER(DD132X_Protocol), ctypes.POINTER(ctypes.c_int)]),
    "DD132X_StartAcquisition": (BOOL, [HDD132X, ctypes.POINTER(ctypes.c_int)]),
    "DD132X_StopAcquisition": (BOOL, [HDD132X, ctypes.POINTER(ctypes.c_int)]),
    "DD132X_IsAcquiring": (BOOL, [HDD132X]),
    "DD132X_GetAcquisitionPosition": (BOOL, [HDD132X, ctypes.POINTER(LONGLONG), ctypes.POINTER(ctypes.c_int)]),
    "DD132X_GetAIValue": (BOOL, [HDD132X, UINT, ctypes.POINTER(ctypes.c_short), ctypes.POINTER(ctypes.c_int)]),
    "DD132X_GetCalibrationData": (BOOL, [HDD132X, ctypes.POINTER(DD132X_CalibrationData), ctypes.POINTER(ctypes.c_int)]),
    "DD132X_GetLastErrorText": (BOOL, [HDD132X, ctypes.c_char_p, UINT, ctypes.POINTER(ctypes.c_int)]),
    "DD132X_Reset": (BOOL, [HDD132X, ctypes.POINTER(ctypes.c_int)]),
}
OBBLIGATORIE = ("DD132X_FindDevices", "DD132X_OpenDevice", "DD132X_CloseDevice",
                "DD132X_SetProtocol", "DD132X_StartAcquisition", "DD132X_StopAcquisition",
                "DD132X_IsAcquiring", "DD132X_GetCalibrationData")


class LibreriaDD132x(object):
    """DLL caricata, con le funzioni risolte."""

    def __init__(self, percorso):
        self.percorso = percorso
        self.dll = None
        self.handle = None
        self.funzioni = {}
        self.mancanti = []
        self.axoutils = None
        self.note = []

    def carica(self):
        if not SU_WINDOWS:
            raise OSError("AxDD132x.dll si puo' caricare solo su Windows")
        k32 = ctypes.windll.kernel32
        cartella = os.path.dirname(os.path.abspath(self.percorso))
        # La versione distribuita con WinWCP (1.0.0.38) dipende da AxoUtils32.dll
        # nella stessa cartella: la si carica prima, come fa WinWCP.
        for nome in ("AxoUtils32.dll", "axoutils32.dll"):
            p = os.path.join(cartella, nome)
            if os.path.isfile(p):
                try:
                    self.axoutils = ctypes.WinDLL(p)
                    self.note.append("caricata %s" % p)
                except OSError as e:
                    self.note.append("impossibile caricare %s: %s" % (p, e))
                break
        # LOAD_WITH_ALTERED_SEARCH_PATH: le dipendenze si cercano nella
        # cartella della DLL e non in quella di python.exe.
        k32.LoadLibraryExW.restype = ctypes.c_void_p
        k32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
        h = k32.LoadLibraryExW(os.path.abspath(self.percorso), None, 0x00000008)
        if not h:
            codice = ctypes.GetLastError()
            raise OSError("LoadLibraryEx fallita (errore Windows %d: %s)"
                          % (codice, ctypes.FormatError(codice).strip()))
        self.handle = h
        self.dll = ctypes.WinDLL(os.path.basename(self.percorso), handle=h)
        for nome, (rt, at) in FIRME.items():
            try:
                f = getattr(self.dll, nome)
            except AttributeError:
                self.mancanti.append(nome)
                continue
            f.restype = rt
            f.argtypes = at
            self.funzioni[nome] = f
        manca = [n for n in OBBLIGATORIE if n in self.mancanti]
        if manca:
            raise OSError("la DLL non esporta: %s" % ", ".join(manca))
        return self

    def __getattr__(self, nome):
        f = self.__dict__.get("funzioni", {}).get(nome)
        if f is None:
            raise AttributeError(nome)
        return f

    def ha(self, nome):
        return nome in self.funzioni

    def testo_errore(self, hdev, codice=None):
        """Testo dell'ultimo errore (dalla DLL se possibile)."""
        parti = []
        if codice is not None:
            parti.append("codice %d%s" % (codice, (" (%s)" % ERRORI[codice]) if codice in ERRORI else ""))
        if hdev and self.ha("DD132X_GetLastErrorText"):
            buf = ctypes.create_string_buffer(512)
            e = ctypes.c_int(0)
            try:
                if self.DD132X_GetLastErrorText(hdev, buf, 512, ctypes.byref(e)):
                    t = buf.value.decode("mbcs" if SU_WINDOWS else "latin-1", "replace").strip()
                    if t:
                        parti.append(t)
            except Exception as ex:  # pragma: no cover
                parti.append("(GetLastErrorText fallita: %s)" % ex)
        return "; ".join(parti) if parti else "errore sconosciuto"


def versione_file(percorso):
    """Versione (FileVersion) di una DLL Windows, letta dalle risorse."""
    if not SU_WINDOWS:
        return ""
    try:
        ver = ctypes.windll.version
        n = ver.GetFileVersionInfoSizeW(percorso, None)
        if not n:
            return ""
        buf = ctypes.create_string_buffer(n)
        if not ver.GetFileVersionInfoW(percorso, 0, n, buf):
            return ""
        p = ctypes.c_void_p()
        lung = ctypes.c_uint()
        if not ver.VerQueryValueW(buf, "\\", ctypes.byref(p), ctypes.byref(lung)):
            return ""

        class VS_FIXEDFILEINFO(ctypes.Structure):
            _fields_ = [(k, ctypes.c_uint32) for k in (
                "dwSignature", "dwStrucVersion", "dwFileVersionMS", "dwFileVersionLS",
                "dwProductVersionMS", "dwProductVersionLS", "dwFileFlagsMask", "dwFileFlags",
                "dwFileOS", "dwFileType", "dwFileSubtype", "dwFileDateMS", "dwFileDateLS")]
        fi = ctypes.cast(p, ctypes.POINTER(VS_FIXEDFILEINFO)).contents
        return "%d.%d.%d.%d" % (fi.dwFileVersionMS >> 16, fi.dwFileVersionMS & 0xFFFF,
                                fi.dwFileVersionLS >> 16, fi.dwFileVersionLS & 0xFFFF)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# WinASPI: il driver Axon parla con la scheda SCSI attraverso wnaspi32.dll.
# ---------------------------------------------------------------------------
SS_COMP = 0x01
SS_NO_ADAPTERS = 0xE8
STATI_ASPI = {0x01: "OK", 0xE8: "nessun adattatore SCSI", 0xE4: "inizializzazione fallita",
              0xE5: "ASPI non disponibile", 0xE2: "WinASPI non valido",
              0xE7: "versione errata", 0xE3: "buffer troppo grande"}


def controlla_aspi(percorso=None):
    """Carica wnaspi32.dll e chiama GetASPI32SupportInfo (cdecl, nessun argomento).
    Restituisce dict(ok, stato, adattatori, percorso, errore)."""
    r = {"ok": False, "stato": None, "adattatori": 0, "percorso": percorso or "wnaspi32.dll",
         "errore": ""}
    if not SU_WINDOWS:
        r["errore"] = "non Windows"
        return r
    try:
        dll = ctypes.CDLL(percorso or "wnaspi32.dll")
    except OSError as e:
        r["errore"] = "wnaspi32.dll non caricabile: %s" % e
        return r
    try:
        f = dll.GetASPI32SupportInfo
        f.restype = ctypes.c_uint32
        f.argtypes = []
        v = f()
        stato = (v >> 8) & 0xFF
        r["stato"] = stato
        r["adattatori"] = v & 0xFF
        r["ok"] = stato == SS_COMP
        if not r["ok"]:
            r["errore"] = "GetASPI32SupportInfo: stato 0x%02X (%s)" % (
                stato, STATI_ASPI.get(stato, "sconosciuto"))
    except Exception as e:
        r["errore"] = "GetASPI32SupportInfo fallita: %s" % e
    return r
