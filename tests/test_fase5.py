# -*- coding: utf-8 -*-
"""Fase 5: correzioni ricavate dai sorgenti di WinWCP e rilevamento sul posto.

  * protocollo come WinWCP: uChunksPerSecond = 0 (dd1320.pas: "Unused");
  * RTIMESECS = secondi dall'avvio di Windows (guida V5.2.4 p. 163);
  * LPF-8: valori ammessi, Bypass, aliasing (manuale LPF-8);
  * impostazioni di WinWCP lette (mai scritte), proposte come valori iniziali;
  * rilevamento sul posto con un ambiente finto;
  * comando minimo da incollare (controlli statici: non c'e' Wine);
  * strumenti/leggi_info_lab.py su una cartella info_pc_lab costruita qui.
"""
import datetime
import hashlib
import io
import os
import re
import shutil
import sys

import pytest

from dlive import config, lpf8, rilevamento, sysinfo, wcpfile
from dlive import winwcp_impostazioni as WI
from dlive.devices import digidata as dd
from dlive.devices.dd132x_finto import LibreriaFinta

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATI = os.path.join(RADICE, "riferimenti", "dati")
from conftest import SENZA_DATI  # noqa: E402


class _Log(object):
    def __init__(self):
        self.righe = []

    def info(self, *a):
        self.righe.append(a[0] % a[1:] if len(a) > 1 else a[0])

    warning = info
    error = info


# ---------------------------------------------------------------- protocollo
def test_chunks_per_second_come_winwcp():
    """WinWCP non imposta uChunksPerSecond (in dd1320.pas il campo e' parte di
    'Unused', quindi 0): prima il programma mandava 20."""
    lib = LibreriaFinta()
    d = dd.Digidata1322Device(canale=2, controlla_processi=False, campioni_buffer=20000)
    d.lib = lib
    d.apri()
    d.avvia()
    try:
        assert d._proto.uChunksPerSecond == 0
        assert lib.chunks_ricevuti == 0
        # gli altri campi che WinWCP lascia a zero
        assert d._proto.dwFlags == 0 and d._proto.uTerminalCount == 0
        assert d._proto.eOutputPulseType == 0
    finally:
        d.chiudi()


def test_chunks_per_second_configurabile():
    c = config.Configurazione()
    assert c["digidata.chunks_per_second"] == 0
    lib = LibreriaFinta()
    d = dd.Digidata1322Device(canale=2, controlla_processi=False, campioni_buffer=20000,
                              chunks_per_second=20)
    d.lib = lib
    d.apri()
    d.avvia()
    d.chiudi()
    assert lib.chunks_ricevuti == 20


def test_cartelle_winwcp_cercate(monkeypatch, tmp_path):
    """WinWCP carica la DLL dalla propria cartella (C:\\WinWCP, C:\\WinWCPXE...)."""
    import glob as _g
    vero = _g.glob

    def finto(p):
        if p == r"C:\WinWCP*":
            return [str(tmp_path / "WinWCPXE")]
        return vero(p)
    (tmp_path / "WinWCPXE").mkdir()
    (tmp_path / "WinWCPXE" / "AxDD132x.dll").write_bytes(b"MZ")
    monkeypatch.setattr(dd.glob, "glob", finto)
    monkeypatch.setattr(dd.os.path, "isdir", lambda p: p in (str(tmp_path / "WinWCPXE"), r"C:\Axon") and
                        p != r"C:\Axon")
    cand = dd.percorsi_candidati_dll("", None)
    assert str(tmp_path / "WinWCPXE" / "AxDD132x.dll") in cand


# ---------------------------------------------------------------- RTIMESECS
def test_rtimesecs_secondi_dall_avvio(tmp_path):
    w = wcpfile.ScrittoreWCP(str(tmp_path / "a.wcp"), 0.001, 256, [{"nome": "AI2"}], rtimesecs=4242.5)
    w.aggiungi([1, 2, 3])
    w.chiudi()
    f = wcpfile.leggi_wcp(str(tmp_path / "a.wcp"))
    assert f.hdr["RTIMESECS"] == "4242,5"


def test_rtimesecs_registrazione(monkeypatch, tmp_path):
    from dlive import recorder
    monkeypatch.setattr(sysinfo, "secondi_dall_avvio", lambda: 777.25)
    par = __import__("dlive.filters", fromlist=["x"]).ParametriFiltro("bessel", 4, 5.0, [50.0])
    r = recorder.Registrazione(str(tmp_path), {"yg": 0.001, "yz": 0, "unita": "mV", "nome": "AI2"},
                               1000.0, 8, par, 60.0, {}, 15.0)
    r.chiudi()
    for p in (r.percorso_raw, r.percorso_filt):
        assert wcpfile.leggi_wcp(p, solo_intestazione=True).hdr["RTIMESECS"] == "777,25"


def test_rtimesecs_mai_zero(tmp_path):
    w = wcpfile.ScrittoreWCP(str(tmp_path / "b.wcp"), 0.001, 256, [{"nome": "AI2"}], rtimesecs=0.0)
    w.chiudi()
    assert wcpfile.numero_da_testo(wcpfile.leggi_wcp(str(tmp_path / "b.wcp")).hdr["RTIMESECS"]) > 0


def test_secondi_dall_avvio():
    v = sysinfo.secondi_dall_avvio()
    assert v is None or v > 0


# ---------------------------------------------------------------- LPF-8
@pytest.mark.parametrize("fc", [0.1, 1.0, 15.0, 15.5, 199.9, 10.0, 200.0, 210.0, 1000.0, 19990.0])
def test_lpf8_valori_ammessi(fc):
    assert lpf8.valore_ammesso(fc) is None


@pytest.mark.parametrize("fc", [0.05, 15.05, 205.0, 1234.0, 20000.0, -1.0])
def test_lpf8_valori_impossibili(fc):
    assert lpf8.valore_ammesso(fc)
    err, _ = lpf8.controlla(fc, 1000.0)
    assert err


def test_lpf8_testo_e_bypass():
    assert lpf8.leggi_taglio("15,5") == 15.5
    assert lpf8.leggi_taglio("Bypass") == lpf8.BYPASS
    assert lpf8.testo_campo(0.0) == "Bypass"
    assert lpf8.testo_campo(15.0) == "15,0"
    with pytest.raises(ValueError):
        lpf8.leggi_taglio("abc")


def test_lpf8_attenuazione_come_manuale():
    # manuale: -3 dB al taglio, -14 dB a 2f, -114 dB a 10f ma massimo 60 dB
    assert abs(lpf8.attenuazione_db(15.0, 15.0) - 3.0) < 0.1
    assert abs(lpf8.attenuazione_db(30.0, 15.0) - 14.0) < 0.5
    assert lpf8.attenuazione_db(150.0, 15.0) == 60.0
    assert lpf8.attenuazione_db(500.0, 0.0) == 0.0


def test_lpf8_aliasing():
    # 15 Hz (valore del laboratorio): nessun avviso a 1000 Hz
    assert lpf8.controlla(15.0, 1000.0) == ([], [])
    # fino a ~150 Hz l'attenuazione a 500 Hz e' >= 40 dB
    assert 145 < lpf8.taglio_massimo_senza_aliasing(1000.0) < 155
    _, a = lpf8.controlla(170.0, 1000.0)
    assert a and "aliasing" in a[0].lower()
    _, a = lpf8.controlla(1000.0, 1000.0)
    assert a and "Rischio di aliasing" in a[0]
    _, a = lpf8.controlla(lpf8.BYPASS, 1000.0)
    assert a and "Bypass" in a[0]


def test_lpf8_guadagno():
    _, a = lpf8.controlla(15.0, 1000.0, guadagno=3)
    assert a and "Guadagno" in a[0]
    _, a = lpf8.controlla(15.0, 1000.0, guadagno=10, yg=0.001, unita="mV")
    assert a and "0,001 x 10" in a[0]
    assert lpf8.controlla(15.0, 1000.0, guadagno=10, yg=0.01, unita="mV") == ([], [])


def test_config_avvisa_lpf8():
    c = config.Configurazione()
    c.imposta("lpf8.taglio_hz", 199.9)
    errori, avvisi = c.controlla()
    assert not errori and any("[lpf8]" in a for a in avvisi)


def test_config_separatore_auto():
    c = config.Configurazione()
    assert c["salvataggio.separatore_decimale"] == "auto"
    assert c.separatore() in (",", ".")
    c.imposta("salvataggio.separatore_decimale", "punto")
    assert c.separatore() == "."


# ---------------------------------------------------------------- impostazioni WinWCP
INI = (u"FILE=C:\\Documents and Settings\\lab\\Documenti\\WinWCP Data\\160402_003.wcp\r\n"
       u"FILEAVG=C:\\x\\160402_003.avg\r\nNC=1\r\nNSAMP=448000\r\nRECDUR=3584\r\n"
       u"RECMODE=1\r\nFILEVPR=\r\nNC=1\r\nNBA=2\r\nNBD=1750\r\nAD=10\r\nDT=0,008\r\n"
       u"DDIR=C:\\Documents and Settings\\lab\\Documenti\\WinWCP Data\\\r\n"
       u"VPDIR=C:\\Documents and Settings\\All Users\\Documenti\\WinWCP\\Vprot\\\r\n"
       u"RF0=C:\\Documents and Settings\\lab\\Documenti\\WinWCP Data\\160402_003.wcp\r\n"
       u"RF1=C:\\Documents and Settings\\lab\\Documenti\\WinWCP Data\\160401_001.wcp\r\n"
       u"LABINT=6\r\n")


def _xml(canali, tipo=6, n=None):
    """Come TSESLabIO.SaveToXMLFile1 (SESLabIO.pas): un'unica riga, virgola
    o punto decimale."""
    parti = ['<?xml version="1.0"?>\r\n<LABINTERFACESETTINGS><INTERFACETYPE>%d</INTERFACETYPE>'
             '<DEVICENUMBER>1</DEVICENUMBER><ADCINPUTMODE>0</ADCINPUTMODE>'
             '<ADCNUMCHANNELS>%d</ADCNUMCHANNELS><ADCNUMSamples>448000</ADCNUMSamples>'
             '<ADCVOLTAGERANGEINDEX>0</ADCVOLTAGERANGEINDEX>'
             '<ADCVOLTAGERANGE><NUMBER>0</NUMBER><RANGE>10</RANGE></ADCVOLTAGERANGE>'
             % (tipo, n if n is not None else len(canali))]
    for i, (nome, unita, vpu, g, ingresso) in enumerate(canali):
        parti.append('<ADCCHANNEL><NUMBER>%d</NUMBER><NAME>%s</NAME><UNITS>%s</UNITS>'
                     '<VOLTSPERUNIT>%s</VOLTSPERUNIT><GAIN>%s</GAIN><UNITSPERBIT>0,3051757813</UNITSPERBIT>'
                     '<ZEROLEVEL>0</ZEROLEVEL><CHANNELOFFSET>%d</CHANNELOFFSET><VISIBLE>T</VISIBLE>'
                     '<DISPLAYMIN>-32678</DISPLAYMIN><DISPLAYMAX>32677</DISPLAYMAX>'
                     '<INPUTNUMBER>%d</INPUTNUMBER><ADCVOLTAGERANGE>10</ADCVOLTAGERANGE>'
                     '<INVERT>F</INVERT></ADCCHANNEL>' % (i, nome, unita, vpu, g, i, ingresso))
    parti.append('<DIGHOLDINGLEVEL>0</DIGHOLDINGLEVEL></LABINTERFACESETTINGS>\r\n')
    return "".join(parti)


def _doc_condivisi(tmp_path, ini=INI, xml=None):
    doc = tmp_path / "All Users" / "Documenti"
    (doc / "WinWCP").mkdir(parents=True)
    (doc / "SESLABIO").mkdir(parents=True)
    (doc / "WinWCP" / "winwcp.ini").write_bytes(ini.encode("cp1252"))
    (doc / "SESLABIO" / "lab interface settings.xml").write_bytes(
        (xml or _xml([("Vm", "mV", "0,001", "1", 2)])).encode("utf-8"))
    return str(doc)


def _impronta(cartella):
    h = {}
    for r, _, files in os.walk(cartella):
        for f in files:
            p = os.path.join(r, f)
            h[p] = (hashlib.md5(open(p, "rb").read()).hexdigest(), os.path.getmtime(p))
    return h


def test_winwcp_cerca_e_legge(tmp_path):
    doc = _doc_condivisi(tmp_path)
    trovati = WI.cerca(documenti=[doc], programmi=[])
    assert set(trovati) == {"winwcp.ini", "lab interface settings.xml"}
    imp = WI.leggi(trovati)
    assert not imp.errori
    assert imp.ini["DT"] == "0,008" and imp.ini["NC"] == "1"
    assert imp.modo_registrazione() == 1
    i = imp.interfaccia
    assert i["tipo"] == WI.DIGIDATA132X and i["n_canali"] == 1 and i["range_v"] == 10.0
    assert i["canali"][0]["ingresso"] == 2 and i["canali"][0]["volt_per_unita"] == 0.001
    testo = "\n".join(imp.righe())
    assert "AI2" in testo and "Free run" in testo


def test_winwcp_vecchia_cartella_programma(tmp_path):
    prog = tmp_path / "WinWCP"
    prog.mkdir()
    (prog / "winwcp.ini").write_bytes(INI.encode("cp1252"))
    trovati = WI.cerca(documenti=[str(tmp_path / "niente")], programmi=[str(prog)])
    assert trovati == {"winwcp.ini": str(prog / "winwcp.ini")}


def test_winwcp_proposta_un_canale(tmp_path):
    imp = WI.leggi(WI.cerca(documenti=[_doc_condivisi(tmp_path)], programmi=[]))
    valori, note, avvisi = WI.proposta(imp, canale_attuale=0)
    assert valori["digidata.canale_ingresso"] == 2
    assert valori["calibrazione.yg"] == 0.001
    assert valori["calibrazione.unita"] == "mV" and valori["calibrazione.nome_canale"] == "Vm"
    assert valori["salvataggio.frequenza_salvataggio_hz"] == 125.0
    assert not avvisi


def test_winwcp_guadagno_nella_calibrazione(tmp_path):
    xml = _xml([("Vm", "mV", "0.001", "10", 2)])
    imp = WI.leggi(WI.cerca(documenti=[_doc_condivisi(tmp_path, xml=xml)], programmi=[]))
    valori, note, _ = WI.proposta(imp)
    assert abs(valori["calibrazione.yg"] - 0.01) < 1e-12
    assert any("guadagno" in n for n in note)


def test_winwcp_piu_canali(tmp_path):
    xml = _xml([("Ch.0", "mV", "0,001", "1", 0), ("Ch.1", "mV", "0,001", "1", 1),
                ("Vm", "mV", "0,001", "1", 2)])
    imp = WI.leggi(WI.cerca(documenti=[_doc_condivisi(tmp_path, xml=xml)], programmi=[]))
    v, _, avv = WI.proposta(imp, canale_attuale=2)
    assert v["digidata.canale_ingresso"] == 2 and v["calibrazione.nome_canale"] == "Vm"
    v, _, avv = WI.proposta(imp, canale_attuale=7)
    assert "digidata.canale_ingresso" not in v and avv and "AI7" in avv[0]


def test_winwcp_stimolazione_e_altra_interfaccia(tmp_path):
    ini = INI.replace("RECMODE=1", "RECMODE=0").replace("FILEVPR=", "FILEVPR=C:\\vprot\\passi.xml")
    xml = _xml([("Im", "pA", "0,0005", "1", 0)], tipo=11)
    imp = WI.leggi(WI.cerca(documenti=[_doc_condivisi(tmp_path, ini=ini, xml=xml)], programmi=[]))
    v, _, avv = WI.proposta(imp)
    testo = " ".join(avv)
    assert "Stimulus protocol" in testo and "passi.xml" in testo
    assert "Digidata 132X" in testo
    assert "digidata.canale_ingresso" not in v


def test_winwcp_xml_vero_del_sorgente():
    p = os.path.join(RADICE, "riferimenti", "winwcp_sorgenti", "XE-5.8.1", "lab interface settings.xml")
    if not os.path.exists(p):
        pytest.skip(SENZA_DATI)
    i = WI.leggi_xml_interfaccia(p)
    assert i["tipo"] == 11 and i["canali"][0]["nome"] == "Im" and i["canali"][1]["volt_per_unita"] > 0
    ini = WI.leggi_ini(os.path.join(os.path.dirname(p), "WinWCP.ini"))
    assert ini["NC"] == "1" and "FILE" in ini


@pytest.mark.parametrize("modo,risposta,cambia,modo_finale", [
    ("chiedi", True, True, "usa"), ("chiedi", False, False, "ignora"),
    ("usa", None, True, "usa"), ("ignora", None, False, "ignora")])
def test_winwcp_all_avvio(tmp_path, modo, risposta, cambia, modo_finale):
    doc = _doc_condivisi(tmp_path)
    prima = _impronta(doc)
    c = config.Configurazione()
    c.imposta("digidata.impostazioni_winwcp", modo)
    c.imposta("digidata.canale_ingresso", 5)
    domande = []
    imp = WI.leggi(WI.cerca(documenti=[doc], programmi=[]))
    _, diff, _ = WI.all_avvio(c, _Log(), chiedi=lambda t: domande.append(t) or risposta, imp=imp)
    assert (c["digidata.canale_ingresso"] == 2) == cambia
    assert c["digidata.impostazioni_winwcp"] == modo_finale
    assert bool(domande) == (modo == "chiedi")
    if domande:
        assert "AI2" in domande[0]
    # i file di WinWCP non sono stati toccati
    assert _impronta(doc) == prima


def test_winwcp_non_trovate():
    imp = WI.leggi({})
    assert not imp.trovate
    c = config.Configurazione()
    _, diff, avv = WI.all_avvio(c, _Log(), imp=imp)
    assert diff == [] and avv == []


# ---------------------------------------------------------------- rilevamento
class AmbienteFinto(object):
    def __init__(self, **kw):
        self.win = kw.get("win", True)
        self.ver = kw.get("ver", (5, 1, 2600, "Service Pack 3", "Microsoft Windows XP"))
        self.bit64 = kw.get("bit64", False)
        self.admin = kw.get("admin", True)
        self.reg = kw.get("reg", {})
        self.file = kw.get("file", {})       # percorso -> (dimensione, md5, versione)
        self.libero = kw.get("libero", 5000.0)
        self.scr = kw.get("schermo", (1024, 768, 96))
        self.sep = kw.get("sep", ",")
        self.proc = kw.get("processi", ["explorer.exe"])
        self.ora = kw.get("ora", datetime.datetime(2026, 11, 22, 10, 0))
        self.py = kw.get("python", ("3.4.4", 32, r"C:\Python34\python.exe"))
        self.imp = kw.get("imp", WI.Impostazioni())
        self.cand = kw.get("candidati", [])

    def su_windows(self):
        return self.win

    def env(self, n, d=None):
        return {"SystemRoot": r"C:\WINDOWS"}.get(n, d)

    def versione_windows(self):
        return self.ver

    def windows_64bit(self):
        return self.bit64

    def amministratore(self):
        return self.admin

    def reg_valore(self, r, k, v):
        return self.reg.get((r, k, v))

    def reg_sottochiavi(self, r, k):
        return sorted(set(kk.split("\\")[-2] for (rr, kk, _) in self.reg
                          if rr == r and kk.startswith(k + "\\")))

    def esiste(self, p):
        return p in self.file

    def elenca(self, c):
        return ["Python34", "WINDOWS"] if c == "C:\\" else []

    def dimensione(self, p):
        return self.file[p][0]

    def md5(self, p):
        return self.file[p][1]

    def versione_file(self, p):
        return self.file.get(p, (0, 0, ""))[2]

    def spazio_libero_mb(self, p):
        return self.libero

    def schermo(self):
        return self.scr

    def separatore_decimale(self):
        return self.sep

    def processi(self):
        return self.proc

    def adesso(self):
        return self.ora

    def python(self):
        return self.py

    def candidati_dll(self, c):
        return self.cand

    def impostazioni_winwcp(self):
        return self.imp

    def cartelle_winwcp(self):
        return [r"C:\WinWCP"]


ASPI = {os.path.join(r"C:\WINDOWS", "system32", "wnaspi32.dll"): (45056, "128ec62ff59a59beb5772e52ed8d3148", "4.60"),
        os.path.join(r"C:\WINDOWS", "system32", "drivers", "aspi32.sys"): (25244, "b979979ab8027f7f53fb16ec4229b7db", "4.60")}


def _livelli(esiti):
    return dict((e.nome, e.livello) for e in esiti)


def test_rilevamento_pc_buono():
    f = dict(ASPI)
    f[r"C:\WinWCP\AxDD132x.dll"] = (359936, "00a2606072035dffb8b8924c7c18bab9", "1.0.0.38")
    f[os.path.join(r"C:\WINDOWS", "system32", "msvcr100.dll")] = (773968, "x", "10.0.40219.325")
    amb = AmbienteFinto(file=f, candidati=[r"C:\WinWCP\AxDD132x.dll"],
                        reg={("HKLM", r"SOFTWARE\Python\PythonCore\3.4\InstallPath", ""): "C:\\Python34\\"})
    es = rilevamento.tutti(amb, cfg=config.Configurazione(), cartella_programma=r"C:\denoising_live",
                           cartella_dati=r"C:\dati", installazione=True)
    lv = _livelli(es)
    assert lv["Windows"] == lv["Diritti"] == lv["Python"] == lv["DLL Axon e WinASPI"] == "OK"
    assert lv["Disco"] == lv["Disco (installazione)"] == lv["Orologio"] == "OK"
    t = rilevamento.testo(es)
    assert "Service Pack 3" in t and "32 bit" in t and "di WinWCP" in t and "80 %" in t
    assert "PythonCore" not in t and "HKLM 3.4: C:\\Python34\\" in t
    assert "msvcr100.dll presente" in t


@pytest.mark.parametrize("kw,nome,livello,parola", [
    (dict(ver=(5, 1, 2600, "Service Pack 1", "XP")), "Windows", "ERRORE", "Service Pack 2"),
    (dict(ver=(5, 1, 2600, "", "XP")), "Windows", "ERRORE", "senza Service Pack"),
    (dict(bit64=True), "Windows", "OK", "64 bit"),
    (dict(admin=False), "Diritti", "AVVISO", "NON amministratore"),
    (dict(python=("3.12.1", 64, "x")), "Python", "AVVISO", "3.4 a 32 bit"),
    (dict(schermo=(800, 600, 96)), "Schermo", "AVVISO", "dimensione = 75"),
    (dict(schermo=(1280, 1024, 120)), "Schermo", "OK", "caratteri grandi"),
    (dict(sep="."), "Separatore decimale", "OK", "punto"),
    (dict(sep=None), "Separatore decimale", "AVVISO", "non determinabile"),
    (dict(libero=210.0), "Disco", "AVVISO", "NON bastano per 3 ore"),
    (dict(libero=100.0), "Disco (installazione)", "ERRORE", "150"),
    (dict(file={}), "DLL Axon e WinASPI", "ERRORE", "AxDD132x.dll non trovata"),
    (dict(file={r"C:\WinWCP\AxDD132x.dll": (359936, "00a2606072035dffb8b8924c7c18bab9", "1.0.0.38")},
          candidati=[r"C:\WinWCP\AxDD132x.dll"]), "DLL Axon e WinASPI", "ERRORE", "installare AxoScope"),
    (dict(processi=["winwcp.exe"]), "WinWCP in esecuzione", "AVVISO", "winwcp.exe"),
    (dict(ora=datetime.datetime(2008, 10, 24, 21, 56)), "Orologio", "AVVISO", "2016"),
    (dict(win=False), "Windows", "AVVISO", "non e' Windows"),
])
def test_rilevamento_casi(kw, nome, livello, parola):
    kw.setdefault("file", dict(ASPI))
    amb = AmbienteFinto(**kw)
    es = [e for e in rilevamento.tutti(amb, cfg=config.Configurazione(), cartella_programma=r"C:\d",
                                       cartella_dati=r"C:\dati", installazione=True) if e.nome == nome]
    assert es and es[0].livello == livello, es
    assert parola in "\n".join(es[0].righe())


def test_rilevamento_dll_sconosciuta_senza_axoutils():
    f = dict(ASPI)
    f[r"C:\Axon\AxDD132x.dll"] = (1, "ffff", "9.9")
    amb = AmbienteFinto(file=f, candidati=[r"C:\Axon\AxDD132x.dll"])
    e = rilevamento.controlla_dll(amb, r"C:\d")
    t = "\n".join(e.righe())
    assert e.livello == "OK" and "diversa da tutte quelle estratte" in t
    assert "Axoutils32.dll ASSENTE" in t and "chiavetta" not in t


def test_rilevamento_dll_di_winwcp_con_axoutils():
    f = dict(ASPI)
    dll = os.path.join(r"C:\WinWCP", "AxDD132x.dll")       # separatore del sistema, come nel programma
    f[dll] = (359936, "00a2606072035dffb8b8924c7c18bab9", "1.0.0.38")
    f[os.path.join(r"C:\WinWCP", "Axoutils32.dll")] = (1, "x", "1")
    amb = AmbienteFinto(file=f, candidati=[dll])
    t = "\n".join(rilevamento.controlla_dll(amb, r"C:\d").righe())
    assert "Axoutils32.dll presente accanto" in t and "di WinWCP" in t


def test_dll_non_cercata_fra_le_copie_della_chiavetta(tmp_path, monkeypatch):
    # nella repo pubblica non ci sono DLL: una vecchia cartella dll\ del programma non si usa
    d = tmp_path / "dll" / "pclamp10_3_2_1"
    d.mkdir(parents=True)
    (d / "AxDD132x.dll").write_bytes(b"MZ")
    monkeypatch.setattr(dd.sysinfo, "cartelle_programmi", lambda: [])
    assert not [p for p in dd.percorsi_candidati_dll("", str(tmp_path)) if "pclamp10" in p]


def test_messaggi_dll_e_winaspi_con_rimedio():
    assert "WinWCP" in dd.RIMEDIO_DLL and "percorso_dll" in dd.RIMEDIO_DLL
    assert "AxoScope" in dd.RIMEDIO_ASPI and "p. 21" in dd.RIMEDIO_ASPI
    sorgente = open(os.path.join(RADICE, "diagnostica_digidata.py")).read()
    assert "aspiinst" not in sorgente and "dll\\\\winaspi" not in sorgente
    assert "RIMEDIO_ASPI" in sorgente and "RIMEDIO_DLL" in sorgente


def test_rilevamento_impostazioni_winwcp(tmp_path):
    imp = WI.leggi(WI.cerca(documenti=[_doc_condivisi(tmp_path)], programmi=[]))
    amb = AmbienteFinto(imp=imp, file=dict(ASPI))
    c = config.Configurazione()
    c.imposta("digidata.canale_ingresso", 0)
    e = rilevamento.controlla_winwcp(amb, c)
    t = "\n".join(e.righe())
    assert e.livello == "OK" and "proposta: digidata.canale_ingresso = 2" in t


def test_rilevamento_errore_imprevisto_non_ferma():
    class Rotto(AmbienteFinto):
        def schermo(self):
            raise RuntimeError("guasto")
    es = rilevamento.tutti(Rotto(file=dict(ASPI)), cfg=config.Configurazione(), cartella_programma="C:\\d",
                           cartella_dati="C:\\x")
    lv = _livelli(es)
    assert lv["Schermo"] == "AVVISO" and "Orologio" in lv


def test_rilevamento_da_riga_di_comando(tmp_path):
    out = tmp_path / "r.txt"
    rilevamento.main(["--uscita", str(out), "--cartella-programma", RADICE, "--cartella-dati", str(tmp_path)])
    t = out.read_text()
    assert "RILEVAMENTO PC" in t and "Orologio" in t


# ---------------------------------------------------------------- comando
COMANDO = os.path.join(RADICE, "docs", "comandi_da_incollare.txt")


def test_comando_formato():
    raw = open(COMANDO, "rb").read()
    raw.decode("ascii")                                  # solo ASCII
    assert b"\r\n" in raw and raw.count(b"\n") == raw.count(b"\r\n")   # CRLF
    t = raw.decode("ascii").lower()
    assert "set /p" not in t and "powershell" not in t and "pause" not in t
    assert "%%" not in t                                 # variabili del for con un solo %
    assert "copiare sulla chiavetta tutta la cartella info_pc_lab" in t
    # nessun comando che modifica il sistema (righe di commento escluse)
    t = "\r\n".join(r for r in t.split("\r\n") if not r.startswith("rem"))
    for vietato in (" del ", "rd ", "rmdir", "move ", "reg add", "reg delete", "attrib", "ren ",
                    "format", "msiexec", "regedit", "sc ", "net stop", "taskkill", "xcopy"):
        assert vietato not in " " + t.replace("\r\n", " \r\n "), vietato


def test_comando_scrive_solo_in_info_pc_lab():
    t = open(COMANDO, "rb").read().decode("ascii")
    assert re.search(r"^set D=%USERPROFILE%\\Desktop\\info_pc_lab\r$", t, re.M)
    assert re.search(r"^set F=%D%\\info_pc_lab.txt\r$", t, re.M)
    for riga in t.splitlines():
        if riga.lower().startswith("rem"):
            continue
        for m in re.finditer(r'(\d?)>>?\s*("?)([^ "&|)]+)\2', riga.replace("2^>nul", "").replace("2>nul", "")):
            dest = m.group(3)
            assert dest in ("%F%", "nul", "&1"), (riga, dest)
        for m in re.finditer(r'\bcopy /y "[^"]+" "([^"]+)"', riga):
            assert m.group(1) == r"%D%\wcp_recenti" + "\\", riga
        for m in re.finditer(r"\bmkdir\s+\"([^\"]+)\"", riga):
            assert m.group(1) in ("%D%", r"%D%\wcp_recenti"), riga


def test_comando_non_raccoglie_cio_che_si_rileva_sul_posto():
    t = open(COMANDO, "rb").read().decode("ascii").lower()
    # rilevati da installa.bat / diagnostica (punto G): non servono prima
    for superfluo in ("systeminfo", "win32_videocontroller", "fontdpi", "control panel\\international",
                      "python --version", "msvcr100", "axdd", "aspi", "uninstall", "driverquery",
                      "net user", "notepad", "tasklist"):
        assert superfluo not in t, superfluo
    # e non cerca piu' i .wcp per nome (25*.wcp): l'orologio del PC e' indietro
    assert "25*.wcp" not in t and "26*.wcp" not in t


# ---------------------------------------------------------------- leggi_info_lab
def _cartella_info(tmp_path, stimolazione=False):
    c = tmp_path / "info_pc_lab"
    (c / "wcp_recenti").mkdir(parents=True)
    sorgente = os.path.join(DATI, "071222_002.1.wcp")
    if os.path.exists(sorgente):
        shutil.copy(sorgente, str(c / "wcp_recenti"))
    else:                               # senza dati: basta che il file ci sia (analizza=False)
        (c / "wcp_recenti" / "071222_002.1.wcp").write_bytes(b"")
    # un canale sull'ingresso 0 (come i file di prova con NC=1: Ch.0)
    xml = _xml([("Vm", "mV", "0,001", "1", 0)])
    log = ("C:\\Documents and Settings\\All Users\\Documenti\\WinWCP\\22-12-2007.log:02:27:59 Recording Started \r\n"
           "C:\\Documents and Settings\\All Users\\Documenti\\WinWCP\\22-12-2007.log:02:35:24 Stopped (1 records)\r\n")
    if stimolazione:
        log += "C:\\...\\23-12-2007.log:10:00:00 Stimulus Protocol: C:\\vprot\\passi.xml\r\n"
    righe = [
        "INFO PC LAB v5 - 22/12/2007 10.00.00,00 - PCLAB",
        "===== 1 SISTEMA", "", "Microsoft Windows XP [Versione 5.1.2600]",
        "! REG.EXE VERSION 3.0", "", "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion",
        "    CSDVersion\tREG_SZ\tService Pack 3", "",
        "PROCESSOR_ARCHITECTURE=x86 PROCESSOR_ARCHITEW6432=%PROCESSOR_ARCHITEW6432%",
        "AMMINISTRATORE=SI", "              12 File        123.456 byte",
        "               5 Dir   8.123.456.789 byte disponibili",
        "===== 2 FILE WCP SUL DISCO C: (data;byte;percorso)",
        "22/12/2007 02.35;898048;C:\\Documents and Settings\\lab\\Documenti\\WinWCP Data\\071222_002.1.wcp",
        "09/12/2007 23.10;3279872;C:\\Documents and Settings\\lab\\Documenti\\WinWCP Data\\071210_001.wcp",
        "===== 3 IMPOSTAZIONI DI WINWCP",
        "----- FILE C:\\Documents and Settings\\All Users\\Documenti\\WinWCP\\winwcp.ini ; 3000 byte ; 22/12/2007 02.36",
    ] + INI.splitlines() + [
        "", "----- FILE C:\\Documents and Settings\\All Users\\Documenti\\SESLABIO\\lab interface settings.xml ; 5000 byte ; 22/12/2007 02.36",
    ] + xml.splitlines() + ["", "===== 4 LOG DI WINWCP (protocolli di stimolazione e registrazioni)"] + \
        log.splitlines() + ["===== 5 FILE COPIATI IN wcp_recenti", " 071222_002.1.wcp",
                            "===== FINE 22/12/2007 10.03.00,00"]
    (c / "info_pc_lab.txt").write_bytes(("\r\n".join(righe) + "\r\n").encode("cp1252"))
    return str(c)


def _leggi_info():
    sys.path.insert(0, os.path.join(RADICE, "strumenti"))
    import leggi_info_lab
    return leggi_info_lab


def test_leggi_info_lab(tmp_path):
    pytest.importorskip("scipy")
    if not os.path.exists(os.path.join(DATI, "071222_002.1.wcp")):
        pytest.skip(SENZA_DATI)
    L = _leggi_info()
    righe, proposte = L.riassumi(_cartella_info(tmp_path))
    t = "\n".join(righe)
    assert "Service Pack: Service Pack 3" in t and "32 bit" in t and "amministratore: si" in t
    assert "Free run" in t and "nessuna traccia di protocolli" in t
    assert "orologio del PC e' indietro" in t
    assert "071222_002.1.wcp" in t and "taglio suggerito" in t
    assert proposte["digidata.canale_ingresso"] == 0
    assert "filtro.taglio_hz" in proposte
    assert "[digidata] canale_ingresso = 0      (ora: 2)" in t
    assert "[calibrazione] nome_canale = Vm" in t


def test_leggi_info_lab_stimolazione(tmp_path):
    L = _leggi_info()
    righe, _ = L.riassumi(_cartella_info(tmp_path, stimolazione=True), analizza=False)
    assert "USA LA STIMOLAZIONE" in "\n".join(righe)


def test_leggi_info_lab_cartella_vuota(tmp_path):
    L = _leggi_info()
    righe, proposte = L.riassumi(str(tmp_path))
    assert "MANCA" in righe[0] and proposte == {}
