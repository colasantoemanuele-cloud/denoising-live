# -*- coding: utf-8 -*-
"""Gruppo D: il pilota del Digidata senza la scheda vera.

D1: strutture ctypes contro l'header ufficiale AxDD132x.h compilato con
    g++ -m32 (solo compilazione: dimensioni e offset letti dall'assembly).
D2: Digidata1322Device contro la DLL finta (sequenza delle chiamate,
    messaggi d'errore, overrun).
D3: elenco di cio' che non si puo' verificare senza scheda."""
from __future__ import division

import ctypes
import json
import os
import re
import shutil
import subprocess
import tempfile
import time

import pytest

import comuni as C
from conftest import LAVORO, PERCORSO_LOG

HEADER = os.path.join(C.RADICE, "riferimenti", "sdk_axon", "AxDD132x.h")

PRELUDIO = r"""
typedef unsigned int UINT; typedef unsigned char BYTE; typedef unsigned int DWORD;
typedef unsigned short WORD; typedef int BOOL; typedef long long LONGLONG;
typedef long long __int64; typedef short ADC_VALUE; typedef char *LPSTR; typedef const char *LPCSTR;
#define WINAPI __attribute__((stdcall))
#define DECLARE_HANDLE(n) struct n##__ { int unused; }; typedef struct n##__ *n
struct SYSTEMTIME { WORD w[8]; };
extern "C" void *memset(void *, int, unsigned int);
#define offsetof(t, m) __builtin_offsetof(t, m)
/* DATABUFFER non e' nell'header: definizione di dd1320.pas (TDATABUFFER, packed record) */
#pragma pack(push, 1)
struct DATABUFFER { UINT uNumSamples; UINT uFlags; ADC_VALUE *pnData; void *psDataFlags;
                    DATABUFFER *pNextBuffer; DATABUFFER *pPrevBuffer; };
#pragma pack(pop)
"""


def _misure_gcc(bit, strutture, cartella):
    """Compila l'header e restituisce {struttura: (sizeof, {campo: offset})}."""
    if not os.path.exists(HEADER):
        return None, C.SENZA_DATI + " (header Axon AxDD132x.h)"
    gxx = shutil.which("g++")
    if gxx is None:
        return None, "g++ non trovato"
    voci = []
    for nome, campi in strutture:
        voci.append("sizeof(%s)" % nome)
        for c in campi:
            voci.append("offsetof(%s, %s)" % (nome, c))
    src = (PRELUDIO + '#include "%s"\nextern "C" { unsigned int misure[] = {\n%s\n}; }\n'
           % (HEADER, ",\n".join(voci)))
    cpp = os.path.join(cartella, "prova_%d.cpp" % bit)
    asm = os.path.join(cartella, "prova_%d.s" % bit)
    with open(cpp, "w") as f:
        f.write(src)
    pr = subprocess.Popen([gxx, "-m%d" % bit, "-S", "-w", "-fno-asynchronous-unwind-tables",
                           cpp, "-o", asm], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True)
    out, _ = pr.communicate()
    if pr.returncode != 0:
        return None, "compilazione fallita: %s" % out[-800:]
    testo = open(asm).read()
    i = testo.index("misure:")
    valori = [int(v) for v in re.findall(r"\.long\s+(-?\d+)", testo[i:])][:len(voci)]
    risultato = {}
    k = 0
    for nome, campi in strutture:
        dim = valori[k]
        k += 1
        off = {}
        for c in campi:
            off[c] = valori[k]
            k += 1
        risultato[nome] = (dim, off)
    return risultato, ""


def _replica_32bit(cls, cache):
    """Stessi campi della struttura ctypes con i puntatori a 4 byte (come in
    Python a 32 bit su XP)."""
    if cls.__name__ in cache:
        return cache[cls.__name__]
    campi = []
    for nome, tipo in cls._fields_:
        campi.append((nome, _tipo_32(tipo, cache)))
    nuovo = type(cls.__name__ + "_32", (ctypes.Structure,), {"_pack_": getattr(cls, "_pack_", 0),
                                                             "_fields_": campi})
    cache[cls.__name__] = nuovo
    return nuovo


def _tipo_32(tipo, cache):
    if tipo in (ctypes.c_void_p, ctypes.c_char_p) or (
            isinstance(tipo, type) and issubclass(tipo, ctypes._Pointer)):
        return ctypes.c_uint32
    if isinstance(tipo, type) and issubclass(tipo, ctypes.Array):
        return _tipo_32(tipo._type_, cache) * tipo._length_
    return tipo


def test_D1_strutture_come_header(registra):
    from dlive.devices import axdd132x as ax
    classi = [ax.DD132X_Info, ax.DD132X_Protocol, ax.DD132X_CalibrationData, ax.DATABUFFER]
    strutture = [(c.__name__, [n for n, _ in c._fields_]) for c in classi]
    cartella = tempfile.mkdtemp(dir=LAVORO)
    gcc32, err = _misure_gcc(32, strutture, cartella)
    if gcc32 is None:
        registra("D1", "verifica automatica impossibile (%s): vedi revisione riga per riga" % err, None)
        pytest.skip(err)
    gcc64, _ = _misure_gcc(64, strutture, cartella)
    discrepanze = []
    righe = []
    cache = {}
    for cls in classi:
        nome = cls.__name__
        r32 = _replica_32bit(cls, cache)
        dim_c, off_c = gcc32[nome]
        dim_p = ctypes.sizeof(r32)
        if dim_c != dim_p:
            discrepanze.append("%s: sizeof %d (header) vs %d (ctypes, 32 bit)" % (nome, dim_c, dim_p))
        for campo, o in off_c.items():
            op = getattr(r32, campo).offset
            if o != op:
                discrepanze.append("%s.%s: offset %d vs %d" % (nome, campo, o, op))
        # a 64 bit (Python di sviluppo): le classi vere del programma
        if gcc64 is not None and ctypes.sizeof(ctypes.c_void_p) == 8:
            d64, o64 = gcc64[nome]
            if d64 != ctypes.sizeof(cls):
                discrepanze.append("%s: sizeof 64 bit %d vs %d" % (nome, d64, ctypes.sizeof(cls)))
            for campo, o in o64.items():
                if o != getattr(cls, campo).offset:
                    discrepanze.append("%s.%s: offset 64 bit %d vs %d" % (nome, campo, o,
                                                                         getattr(cls, campo).offset))
        righe.append("%s %d byte (%d campi)" % (nome, dim_c, len(off_c)))
    ok = not discrepanze
    registra("D1", "; ".join(righe) + ("; discrepanze: " + "; ".join(discrepanze) if discrepanze
                                       else "; tutti gli offset coincidono (anche a 64 bit)"), ok,
             {"discrepanze": discrepanze},
             nota="DATABUFFER non e' nell'header Axon: confrontata con TDATABUFFER di dd1320.pas")
    assert ok


class _LibreriaRegistrata(object):
    """Avvolge la DLL finta e annota l'ordine delle chiamate."""

    def __init__(self, lib):
        self.__dict__["_lib"] = lib
        self.__dict__["chiamate"] = []

    def __getattr__(self, nome):
        attr = getattr(self._lib, nome)
        if nome.startswith("DD132X_") and callable(attr):
            def f(*a):
                self.chiamate.append(nome)
                return attr(*a)
            return f
        return attr


def _dev(lib, **kw):
    from dlive.devices import digidata as dd
    d = dd.Digidata1322Device(canale=2, fs=kw.pop("fs", 1000.0), controlla_processi=False, **kw)
    d.lib = lib
    return d


def _sottosequenza(attesa, chiamate):
    it = iter(chiamate)
    return all(any(c == a for c in it) for a in attesa)


def test_D2_dll_finta(registra, monkeypatch, lavoro):
    from dlive import compat
    from dlive.devices import axdd132x as ax
    from dlive.devices import digidata as dd
    from dlive.devices.base import ErroreDispositivo
    from dlive.devices.dd132x_finto import LibreriaFinta
    esiti = {}
    note = []
    # 1) sequenza delle chiamate
    lib = _LibreriaRegistrata(LibreriaFinta())
    d = _dev(lib, campioni_buffer=20000, intervallo_lettura=0.03)
    d.apri()
    d.avvia()
    letti = 0
    t0 = time.time()
    while time.time() - t0 < 1.0:
        b = d.leggi(0.2)
        if b is not None:
            letti += len(b.dati)
    d.chiudi()
    attesa = ["DD132X_FindDevices", "DD132X_OpenDevice", "DD132X_GetCalibrationData",
              "DD132X_SetProtocol", "DD132X_StartAcquisition", "DD132X_GetAcquisitionPosition",
              "DD132X_StopAcquisition", "DD132X_CloseDevice"]
    ch = lib.chiamate
    ordine_ok = (_sottosequenza(attesa, ch) and ch[-1] == "DD132X_CloseDevice" and
                 ch.index("DD132X_SetProtocol") < ch.index("DD132X_StartAcquisition"))
    esiti["sequenza"] = ordine_ok and 800 < letti < 1200
    uniche = []
    for c in ch:
        if not uniche or uniche[-1] != c:
            uniche.append(c)
    note.append("sequenza: " + " → ".join(c.replace("DD132X_", "") for c in uniche[:14]) +
                (" …" if len(uniche) > 14 else "") + " (%d campioni in 1 s)" % letti)
    # 2) messaggi: DLL mancante
    monkeypatch.setattr(compat, "SU_WINDOWS", True)
    monkeypatch.setattr(dd, "percorsi_candidati_dll", lambda *a, **k: [])
    try:
        dd.Digidata1322Device(controlla_processi=False).carica_dll()
        msg = ""
    except ErroreDispositivo as e:
        msg = e.messaggio
    monkeypatch.undo()
    esiti["dll_mancante"] = "AxDD132x.dll non trovata" in msg and "config.ini" in msg and "reinstallare" in msg
    note.append("DLL mancante: «%s»" % msg[:160])
    # 3) scheda assente (WinASPI funzionante)
    monkeypatch.setattr(ax, "controlla_aspi", lambda *a: {"ok": True, "errore": ""})
    try:
        _dev(LibreriaFinta(trovato=False)).apri()
        msg = ""
    except ErroreDispositivo as e:
        msg = e.messaggio
    esiti["scheda_assente"] = ("Nessun Digidata trovato" in msg and "acceso PRIMA" in msg and
                               "cavo SCSI" in msg)
    note.append("scheda assente: «%s»" % msg[:160])
    # 4) WinASPI mancante
    monkeypatch.setattr(ax, "controlla_aspi",
                        lambda *a: {"ok": False, "errore": "wnaspi32.dll non caricabile: [WinError 126]"})
    try:
        _dev(LibreriaFinta(trovato=False)).apri()
        msg = ""
    except ErroreDispositivo as e:
        msg = e.messaggio
    monkeypatch.undo()
    # WinASPI non e' distribuito con il programma: il rimedio e' installare AxoScope
    esiti["winaspi"] = "WinASPI non funziona" in msg and "AxoScope" in msg
    note.append("WinASPI mancante: «%s»" % msg[:160])
    # 5) overrun rilevato e contato, fino al JSON della registrazione; la
    #    Sessione e' costruita e avviata come fa la GUI in modalita' Digidata
    #    (dispositivo non ancora aperto: lo apre Sessione.avvia_anteprima)
    try:
        esiti["overrun"], testo = _prova_overrun(lavoro)
    except Exception as e:
        esiti["overrun"] = False
        testo = "ERRORE avviando la sessione con la scheda finta: %s: %s" % (type(e).__name__, e)
    note.append("overrun: " + testo)
    ok = all(esiti.values())
    registra("D2", "; ".join("%s %s" % (k, "OK" if v else "NO") for k, v in esiti.items()), ok,
             {"esiti": esiti, "chiamate": uniche}, nota=" | ".join(note))
    assert ok


def _prova_overrun(lavoro):
    from dlive.devices.dd132x_finto import LibreriaFinta
    d = _dev(LibreriaFinta(), fs=5000.0, campioni_buffer=6000)
    originale = d.leggi
    stato = {"n": 0}

    def leggi_lenta(timeout=0.2):
        stato["n"] += 1
        if stato["n"] == 15:
            time.sleep(2.0)       # il PC "si blocca" per 2 s: la scheda riscrive il buffer
        return originale(timeout)

    d.leggi = leggi_lenta
    s = C.sessione_come_gui(d, lavoro)
    s.comandi.put(("avvia_reg", None))
    try:
        s.avvia_anteprima()
        time.sleep(4.0)
    finally:
        s.ferma()
        d.chiudi()
    reg = s.ultima_registrazione
    if reg is None:
        return False, "nessuna registrazione (errore: %s)" % s.errore_fatale
    meta = json.load(open(reg.percorso_json))
    log = open(PERCORSO_LOG).read()
    ok = (d.overrun >= 1 and s.persi_tot > 0 and meta["campioni_persi"] == s.persi_tot
          and "OVERRUN" in log and reg.campioni_raw == s.campioni)
    return ok, ("%d evento, %d campioni persi contati (JSON: %d), base dei tempi conservata: %s"
                % (d.overrun, s.persi_tot, meta["campioni_persi"],
                   "sì" if reg.campioni_raw == s.campioni else "NO"))


NON_VERIFICABILE = [
    "la DLL vera AxDD132x.dll (quale versione funziona, firme reali, convenzione di chiamata a runtime)",
    "WinASPI (wnaspi32.dll / aspi32.sys) e il controller SCSI su Windows XP",
    "che la scheda accetti il protocollo (uChunksPerSecond = 20, uscite DAC nel protocollo)",
    "la temporizzazione reale: 1000 campioni al secondo esatti, deriva del clock della scheda",
    "il significato reale di DD132X_GetAcquisitionPosition e gli overrun veri",
    "il valore 32767 come 'vuoto' con il bit TAG: comportamento del firmware reale",
    "la calibrazione (offset/guadagno ADC, offset DAC: 8 o 16 DAC nella struttura)",
    "la forma reale dei picchi a 1000 Hz (nei file di prova sono campionati a 114-125 Hz)",
    "il guadagno reale della catena (LPF-8, scala mV) rispetto a quanto mostra WinWCP",
    "l'apertura dei file in WinWCP 5.1.6 su Windows XP",
    "tkinter, numpy 1.15 e le prestazioni sul PC del laboratorio (CPU, schermo, disco)",
]


def test_D3_non_verificabile(registra):
    registra("D3", "%d punti verificabili solo in laboratorio (passi della diagnostica)" %
             len(NON_VERIFICABILE), True, {"elenco": NON_VERIFICABILE})
