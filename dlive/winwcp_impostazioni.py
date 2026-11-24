# -*- coding: utf-8 -*-
"""Lettura (SOLO lettura) delle impostazioni di WinWCP sul PC del laboratorio.

Dove WinWCP 5.1.6 salva le impostazioni (dai sorgenti, vedi
docs/analisi_sorgenti.md, sezione B):

  * <Documenti condivisi>\\WinWCP\\winwcp.ini  (WCPFIleUnit.pas,
    DataModuleCreate: SettingsDirectory = CSIDL_COMMON_DOCUMENTS + '\\WinWCP\\',
    da V4.6.3 del 26/08/13; prima nella cartella del programma).  Righe
    CHIAVE=valore (TStringList, ANSI, CR LF): FILE= ultimo file, RF0..RF3 file
    recenti, DDIR= cartella dati, NC=, NSAMP=, RECDUR=, DT=, RECMODE= (0
    protocollo di stimolazione, 1 free run, 2 trigger esterno, 3 eventi),
    FILEVPR= protocollo, VPDIR= cartella dei protocolli, LABINT= (solo se
    manca il file XML);
  * <Documenti condivisi>\\SESLABIO\\lab interface settings.xml
    (SESLabIO.pas, TSESLabIO.Create, dal 20/08/13): LABINTERFACESETTINGS con
    INTERFACETYPE (6 = Digidata 132X), ADCNUMCHANNELS, ADCVOLTAGERANGE e, per
    ogni canale ADCCHANNEL: NAME, UNITS, VOLTSPERUNIT, GAIN, ZEROLEVEL,
    CHANNELOFFSET, INPUTNUMBER (ingresso fisico, mappatura dal 05.12.13);
  * <Documenti condivisi>\\WinWCP\\amplifier settings.xml (AmpModule.pas).

<Documenti condivisi> e' CSIDL_COMMON_DOCUMENTS: su XP in italiano
"C:\\Documents and Settings\\All Users\\Documenti".

Il modulo non scrive MAI nei file o nel registro di WinWCP.
"""
import io
import os
import xml.etree.ElementTree as ET

from .compat import SU_WINDOWS

INTERFACCE = {
    0: "nessuna (12 bit)", 1: "National Instruments", 2: "Digidata 1200", 3: "CED 1401 (12 bit)",
    4: "CED 1401 (16 bit)", 5: "nessuna (16 bit)", 6: "Axon Instruments (Digidata 132X)",
    7: "Instrutech", 8: "ITC-16", 9: "ITC-18", 10: "VP500", 11: "NI DAQmx", 12: "Digidata 1440",
    13: "Tecella Triton", 14: "CED 1401 (10 V)", 15: "Wireless EEG", 16: "Heka EPC9",
    17: "Heka EPC10", 18: "Heka EPC10 plus", 19: "Heka EPC10 USB", 20: "Heka ITC16",
    21: "Heka ITC18", 22: "Heka ITC1600", 23: "Heka LIH88", 24: "Heka ITC18 USB",
    25: "Heka ITC16 USB", 26: "Digidata 1550", 27: "Digidata 1550A", 28: "Heka EPC9 USB",
    29: "Digidata 1550B", 30: "Measurement Computing",
}
DIGIDATA132X = 6
MODI_REGISTRAZIONE = {0: "Stimulus protocol (stimolazione dal Digidata)", 1: "Free run",
                      2: "Ext. triggered (trigger esterno)", 3: "Detect events"}
NOMI_FILE = ("winwcp.ini", "lab interface settings.xml", "amplifier settings.xml")


# ---------------------------------------------------------------------------
# dove cercare
# ---------------------------------------------------------------------------
def documenti_condivisi():
    """Cartelle candidate per CSIDL_COMMON_DOCUMENTS (la prima e' quella
    che usa WinWCP)."""
    cand = []

    def agg(p):
        if p and p not in cand:
            cand.append(p)
    if SU_WINDOWS:
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(520)
            # SHGetFolderPathW(NULL, CSIDL_COMMON_DOCUMENTS=0x2E, NULL, 0, buf)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 0x2E, None, 0, buf) == 0:
                agg(buf.value)
        except Exception:
            pass
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                               r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
            agg(winreg.QueryValueEx(k, "Common Documents")[0])
            winreg.CloseKey(k)
        except Exception:
            pass
    for var, sub in (("ALLUSERSPROFILE", "Documenti"), ("ALLUSERSPROFILE", "Documents"),
                     ("PUBLIC", "Documents")):
        v = os.environ.get(var)
        if v:
            agg(os.path.join(v, sub))
    return cand


def cartelle_programma_winwcp():
    """Cartelle di installazione di WinWCP (le versioni prima della V4.6.3
    tenevano winwcp.ini qui)."""
    import glob
    from . import sysinfo
    out = []
    radici = list(sysinfo.cartelle_programmi()) + ["C:\\"]
    for r in radici:
        for p in sorted(glob.glob(os.path.join(r, "WinWCP*"))):
            if os.path.isdir(p) and p not in out:
                out.append(p)
    return out


def cerca(documenti=None, programmi=None):
    """Percorsi dei file di impostazioni trovati: dict nome -> percorso.
    documenti/programmi: elenchi di cartelle (per i test); None = quelle vere."""
    if documenti is None:
        documenti = documenti_condivisi()
    if programmi is None:
        programmi = cartelle_programma_winwcp()
    trovati = {}
    for d in documenti:
        for nome, sub in (("winwcp.ini", "WinWCP"), ("lab interface settings.xml", "SESLABIO"),
                          ("amplifier settings.xml", "WinWCP")):
            p = os.path.join(d, sub, nome)
            if nome not in trovati and os.path.isfile(p):
                trovati[nome] = p
    for d in programmi:
        for nome in NOMI_FILE:
            p = os.path.join(d, nome)
            if nome not in trovati and os.path.isfile(p):
                trovati[nome] = p
    return trovati


# ---------------------------------------------------------------------------
# lettura
# ---------------------------------------------------------------------------
def _testo(percorso):
    with open(percorso, "rb") as f:            # sola lettura
        raw = f.read()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16", "replace")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", "replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


def numero(s, predefinito=None):
    try:
        return float(("%s" % s).strip().replace(",", "."))
    except (ValueError, TypeError):
        return predefinito


def leggi_ini(percorso):
    """winwcp.ini -> dict CHIAVE (maiuscola) -> valore (testo).  Per le chiavi
    ripetute (NC compare due volte) vale la prima, come GetKeyValue di WinWCP."""
    return leggi_ini_testo(_testo(percorso))


def leggi_ini_testo(testo):
    """Come leggi_ini, dal testo del file."""
    d = {}
    for riga in testo.replace("\x00", "").splitlines():
        if "=" not in riga:
            continue
        k, v = riga.split("=", 1)
        k = k.strip().upper()
        if k and k not in d:
            d[k] = v.strip()
    return d


def _figlio(nodo, nome):
    for c in list(nodo):
        if c.tag.upper() == nome.upper():
            return c
    return None


def _txt(nodo, nome, predefinito=""):
    c = _figlio(nodo, nome)
    return (c.text or "").strip() if c is not None and c.text is not None else predefinito


def leggi_xml_interfaccia(percorso):
    """lab interface settings.xml -> dict (vedi SESLabIO.SaveToXMLFile1)."""
    return leggi_xml_interfaccia_testo(_testo(percorso), percorso)


def leggi_xml_interfaccia_testo(testo, origine="(testo)"):
    """Come leggi_xml_interfaccia, dal testo del file."""
    testo = testo.replace("\x00", "").strip()
    radice = ET.fromstring(testo.encode("utf-8") if not testo.lstrip().startswith("<?xml") else
                           testo.split("?>", 1)[1].encode("utf-8"))
    nodo = radice if radice.tag.upper() == "LABINTERFACESETTINGS" else _figlio(radice, "LABINTERFACESETTINGS")
    if nodo is None:
        raise ValueError("manca LABINTERFACESETTINGS in %s" % origine)
    tipo = int(numero(_txt(nodo, "INTERFACETYPE"), -1))
    ranges = {}
    for c in list(nodo):
        if c.tag.upper() == "ADCVOLTAGERANGE" and len(list(c)):
            n = numero(_txt(c, "NUMBER"))
            r = numero(_txt(c, "RANGE"))
            if n is not None and r is not None:
                ranges[int(n)] = r
    indice = int(numero(_txt(nodo, "ADCVOLTAGERANGEINDEX"), 0))
    canali = []
    for c in list(nodo):
        if c.tag.upper() != "ADCCHANNEL":
            continue
        n = int(numero(_txt(c, "NUMBER"), len(canali)))
        canali.append({
            "numero": n,
            "nome": _txt(c, "NAME", "Ch.%d" % n),
            "unita": _txt(c, "UNITS", "mV"),
            "volt_per_unita": numero(_txt(c, "VOLTSPERUNIT"), 0.001),
            "guadagno": numero(_txt(c, "GAIN"), 1.0),
            "zero": int(numero(_txt(c, "ZEROLEVEL"), 0)),
            "offset": int(numero(_txt(c, "CHANNELOFFSET"), n)),
            "ingresso": int(numero(_txt(c, "INPUTNUMBER"), n)),
            "range_v": numero(_txt(c, "ADCVOLTAGERANGE"), None),
        })
    canali.sort(key=lambda c: c["numero"])
    return {"tipo": tipo, "nome_interfaccia": INTERFACCE.get(tipo, "sconosciuta (%d)" % tipo),
            "n_canali": int(numero(_txt(nodo, "ADCNUMCHANNELS"), 0)),
            "n_campioni": int(numero(_txt(nodo, "ADCNUMSamples"), 0)),
            "range_v": ranges.get(indice, ranges.get(0)), "canali": canali}


class Impostazioni(object):
    def __init__(self):
        self.percorsi = {}
        self.ini = None
        self.interfaccia = None
        self.errori = []

    @property
    def trovate(self):
        return bool(self.ini or self.interfaccia)

    def modo_registrazione(self):
        if not self.ini or "RECMODE" not in self.ini:
            return None
        m = numero(self.ini["RECMODE"])
        return int(m) if m is not None else None

    def righe(self):
        """Descrizione leggibile (per log, report e finestra)."""
        r = []
        if not self.percorsi:
            r.append("Impostazioni di WinWCP non trovate (winwcp.ini, lab interface settings.xml).")
            return r
        for nome, p in sorted(self.percorsi.items()):
            r.append("file: %s" % p)
        for e in self.errori:
            r.append("ERRORE di lettura: %s" % e)
        if self.interfaccia:
            i = self.interfaccia
            r.append("interfaccia: %s (tipo %d); canali registrati: %d; range %s V"
                     % (i["nome_interfaccia"], i["tipo"], i["n_canali"], _g(i["range_v"])))
            for c in i["canali"][:max(i["n_canali"], 1)]:
                r.append("  Ch.%d '%s' %s: ingresso AI%d, %s V/%s, guadagno %s, zero %d conteggi"
                         % (c["numero"], c["nome"], c["unita"], c["ingresso"], _g(c["volt_per_unita"]),
                            c["unita"], _g(c["guadagno"]), c["zero"]))
        if self.ini:
            ini = self.ini
            dt = numero(ini.get("DT"))
            r.append("winwcp.ini: NC=%s DT=%s s (%s Hz) NSAMP=%s RECDUR=%s s"
                     % (ini.get("NC", "?"), ini.get("DT", "?"), _g(1.0 / dt) if dt else "?",
                        ini.get("NSAMP", "?"), ini.get("RECDUR", "?")))
            m = self.modo_registrazione()
            if m is not None:
                r.append("modo di registrazione (RECMODE=%d): %s" % (m, MODI_REGISTRAZIONE.get(m, "?")))
            for k in ("FILEVPR", "DDIR", "FILE", "RF0", "RF1", "RF2", "RF3"):
                if ini.get(k):
                    r.append("%s=%s" % (k, ini[k]))
        return r


def leggi(percorsi=None):
    """Cerca (se percorsi e' None) e legge le impostazioni.  Non solleva:
    gli errori finiscono in Impostazioni.errori."""
    imp = Impostazioni()
    imp.percorsi = cerca() if percorsi is None else dict(percorsi)
    p = imp.percorsi.get("winwcp.ini")
    if p:
        try:
            imp.ini = leggi_ini(p)
        except Exception as e:
            imp.errori.append("%s: %s" % (p, e))
    p = imp.percorsi.get("lab interface settings.xml")
    if p:
        try:
            imp.interfaccia = leggi_xml_interfaccia(p)
        except Exception as e:
            imp.errori.append("%s: %s" % (p, e))
    return imp


# ---------------------------------------------------------------------------
# proposta di valori iniziali per config.ini
# ---------------------------------------------------------------------------
def proposta(imp, canale_attuale=2, fs_acquisizione=1000.0):
    """Valori proposti per config.ini dalle impostazioni di WinWCP.
    Restituisce (valori, note, avvisi): valori = {chiave config: valore}."""
    valori = {}
    note = []
    avvisi = []
    if not imp.trovate:
        return valori, note, avvisi
    m = imp.modo_registrazione()
    if m == 0:
        avvisi.append("WinWCP e' impostato in modalita' 'Stimulus protocol' (RECMODE=0, protocollo %s): "
                      "denoising_live NON genera stimoli (tiene le uscite a 0 V). Chiedere al "
                      "laboratorio se le registrazioni usano la stimolazione."
                      % ((imp.ini or {}).get("FILEVPR") or "?"))
    elif m == 2:
        avvisi.append("WinWCP e' impostato con trigger esterno (RECMODE=2): forse c'e' uno "
                      "stimolatore esterno; denoising_live registra in continuo senza trigger.")
    i = imp.interfaccia
    if i is not None:
        if i["tipo"] != DIGIDATA132X:
            avvisi.append("In WinWCP l'interfaccia selezionata e' '%s', non il Digidata 132X: "
                          "canali e calibrazione di WinWCP potrebbero non riguardare questa scheda."
                          % i["nome_interfaccia"])
        attivi = i["canali"][:max(i["n_canali"], 1)]
        scelto = None
        if len(attivi) == 1:
            scelto = attivi[0]
            note.append("WinWCP registra un solo canale (Ch.%d '%s'): e' quello del segnale"
                        % (scelto["numero"], scelto["nome"]))
        else:
            sul = [c for c in attivi if c["ingresso"] == canale_attuale]
            if sul:
                scelto = sul[0]
                note.append("WinWCP registra %d canali; Ch.%d '%s' e' sull'ingresso AI%d di config.ini"
                            % (len(attivi), scelto["numero"], scelto["nome"], canale_attuale))
            else:
                avvisi.append("WinWCP registra %d canali e nessuno e' sull'ingresso AI%d di config.ini: "
                              "scegliere a mano il canale (%s)"
                              % (len(attivi), canale_attuale,
                                 ", ".join("Ch.%d '%s'=AI%d" % (c["numero"], c["nome"], c["ingresso"])
                                           for c in attivi)))
        if scelto is not None and i["tipo"] == DIGIDATA132X:
            valori["digidata.canale_ingresso"] = scelto["ingresso"]
            # YG del file = VOLTSPERUNIT; WinWCP mette il guadagno nel range del
            # record (AD/GAIN): la scala in unita' e' identica con yg = VPU x GAIN
            g = scelto["guadagno"] or 1.0
            valori["calibrazione.yg"] = scelto["volt_per_unita"] * g
            valori["calibrazione.unita"] = scelto["unita"] or "mV"
            valori["calibrazione.nome_canale"] = (scelto["nome"] or "AI%d" % scelto["ingresso"])[:8]
            valori["calibrazione.yz"] = float(scelto["zero"])
            if g != 1:
                note.append("guadagno %s nel canale di WinWCP: incluso in yg (%s x %s)"
                            % (_g(g), _g(scelto["volt_per_unita"]), _g(g)))
        if i["range_v"] and abs(i["range_v"] - 10.0) > 1e-6 and i["tipo"] == DIGIDATA132X:
            avvisi.append("Range ADC in WinWCP %s V (il Digidata 1322A lavora a 10 V)" % _g(i["range_v"]))
    if imp.ini:
        dt = numero(imp.ini.get("DT"))
        if dt and dt > 0:
            f = 1.0 / dt
            dec = fs_acquisizione / f
            if abs(dec - round(dec)) < 1e-6 and round(dec) >= 1:
                valori["salvataggio.frequenza_salvataggio_hz"] = round(f, 6)
                note.append("campionamento di WinWCP %s Hz (DT=%s s): usato per il file filtrato"
                            % (_g(f), imp.ini.get("DT")))
            else:
                note.append("campionamento di WinWCP %s Hz (DT=%s s): non divide %s Hz, il filtrato "
                            "resta a quello di config.ini" % (_g(f), imp.ini.get("DT"), _g(fs_acquisizione)))
    return valori, note, avvisi


def differenze(cfg, valori):
    """[(chiave, valore attuale, valore proposto)] per le sole voci diverse."""
    out = []
    for k, v in sorted(valori.items()):
        a = cfg[k]
        if isinstance(v, float) or isinstance(a, float):
            try:
                if abs(float(a) - float(v)) <= 1e-9 * max(1.0, abs(float(v))):
                    continue
            except (TypeError, ValueError):
                pass
        elif a == v:
            continue
        out.append((k, a, v))
    return out


def applica(cfg, valori):
    """Imposta in cfg (in memoria) i valori proposti; restituisce le differenze."""
    diff = differenze(cfg, valori)
    for k, _, v in diff:
        cfg.imposta(k, v)
    return diff


def _g(v):
    if v is None:
        return "?"
    return ("%g" % v).replace(".", ",")


def all_avvio(cfg, log, chiedi=None, imp=None):
    """Da chiamare all'avvio in modalita' Digidata.  Legge le impostazioni di
    WinWCP, le scrive nel log e, secondo [digidata] impostazioni_winwcp:
      * ignora: non cambia nulla;
      * usa:    applica i valori proposti (in memoria);
      * chiedi: chiama chiedi(testo) -> True/False; con True applica e imposta
                'usa', con False imposta 'ignora' (la scelta va salvata in
                config.ini dal chiamante).
    Restituisce (imp, differenze_applicate, avvisi)."""
    if imp is None:
        imp = leggi()
    for r in imp.righe():
        log.info("WinWCP: %s", r)
    if not imp.trovate:
        return imp, [], []
    valori, note, avvisi = proposta(imp, cfg["digidata.canale_ingresso"],
                                    cfg["digidata.frequenza_acquisizione_hz"])
    for n in note:
        log.info("WinWCP: %s", n)
    for a in avvisi:
        log.warning("WinWCP: %s", a)
    diff = differenze(cfg, valori)
    modo = cfg["digidata.impostazioni_winwcp"]
    if not diff or modo == "ignora":
        if diff:
            log.info("WinWCP: valori diversi da config.ini ignorati (impostazioni_winwcp = ignora): %s",
                     ", ".join("%s=%r" % (k, v) for k, _, v in diff))
        return imp, [], avvisi
    if modo == "chiedi":
        testo = ("Ho trovato le impostazioni di WinWCP su questo PC:\n\n%s\n\n"
                 "Valori proposti al posto di quelli di config.ini:\n%s\n\n"
                 "Usarli?  (Si' = usali ora e alle prossime aperture; No = tieni config.ini.  "
                 "Si cambia con [digidata] impostazioni_winwcp in config.ini.)"
                 % ("\n".join(imp.righe()[-12:]),
                    "\n".join("  %s: %s -> %s" % (k, a, v) for k, a, v in diff)))
        if avvisi:
            testo += "\n\nATTENZIONE:\n" + "\n".join("- " + a for a in avvisi)
        si = bool(chiedi(testo)) if chiedi is not None else False
        cfg.imposta("digidata.impostazioni_winwcp", "usa" if si else "ignora")
        if not si:
            log.info("WinWCP: proposta rifiutata, si usa config.ini")
            return imp, [], avvisi
    applicate = applica(cfg, valori)
    for k, a, v in applicate:
        log.info("WinWCP: %s %r -> %r", k, a, v)
    return imp, applicate, avvisi
