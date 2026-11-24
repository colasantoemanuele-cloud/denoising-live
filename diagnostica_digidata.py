# -*- coding: utf-8 -*-
"""Diagnostica del Digidata 1322A: DA ESEGUIRE PER PRIMA in laboratorio.

Controlla un passo alla volta i prerequisiti e scrive tutto in
report_diagnostica.txt (da mandare se qualcosa non va):

   1. ambiente (Windows, Python a 32 bit, numpy) e rilevamento del PC:
      Service Pack, 32/64 bit, diritti, Python e msvcr100.dll, schermo,
      separatore decimale, disco per 3 ore, DLL Axon e WinASPI, impostazioni
      di WinWCP (lette, mai modificate), WinWCP aperto, orologio; LPF-8
   2. programmi che occupano la scheda (WinWCP, AxoScope, Clampex)
   3. driver WinASPI (wnaspi32.dll, aspi32.sys) e adattatori SCSI
   4. periferiche SCSI e chiavi Axon nel registro
   5. ricerca e caricamento di AxDD132x.dll (tutte le copie trovate)
   6. dimensioni delle strutture ctypes
   7. DD132X_FindDevices: il Digidata e' visto?
   8. apertura, informazioni e calibrazione della scheda
   9. lettura di qualche campione singolo dall'ingresso 2 (e da tutti gli ingressi)
  10. acquisizione continua di 10 s a 1000 Hz: CSV + .wcp + statistiche
  11. analisi del rumore e prova del filtro predefinito

Uso:  python diagnostica_digidata.py [--canale 2] [--secondi 10] [--fs 1000]
      [--dll PERCORSO] [--finto]   (--finto: DLL simulata, solo per provare lo script)
"""
import argparse
import datetime
import hashlib
import math
import os
import sys
import time
import traceback

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)


class Report(object):
    def __init__(self, percorso):
        self.percorso = percorso
        self.righe = []
        self.esiti = []
        try:
            self.f = open(percorso, "w")
        except (IOError, OSError):
            self.f = None

    def scrivi(self, testo=""):
        for riga in ("%s" % testo).split("\n"):
            self.righe.append(riga)
            try:
                print(riga)
            except Exception:
                pass
            if self.f is not None:
                try:
                    self.f.write(riga + "\n")
                    self.f.flush()
                except Exception:
                    pass

    def passo(self, numero, titolo):
        self.scrivi("")
        self.scrivi("=" * 72)
        self.scrivi("PASSO %s - %s" % (numero, titolo))
        self.scrivi("=" * 72)

    def esito(self, numero, ok, testo):
        etichetta = {True: "OK", False: "ERRORE", None: "AVVISO"}[ok]
        self.esiti.append((numero, etichetta, testo))
        self.scrivi(">>> %s: %s" % (etichetta, testo))

    def chiudi(self):
        if self.f is not None:
            self.f.close()


def md5(percorso):
    h = hashlib.md5()
    with open(percorso, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def info_file(percorso):
    try:
        st = os.stat(percorso)
        from dlive.devices import axdd132x as ax
        return "%d byte, modificato %s, versione %s, md5 %s" % (
            st.st_size, datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
            ax.versione_file(percorso) or "?", md5(percorso))
    except Exception as e:
        return "(%s)" % e


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--canale", type=int, default=None)
    ap.add_argument("--secondi", type=float, default=10.0)
    ap.add_argument("--fs", type=float, default=1000.0)
    ap.add_argument("--dll", default=None)
    ap.add_argument("--finto", action="store_true", help="usa la DLL simulata (prova dello script)")
    ap.add_argument("--uscita", default=QUI, help="cartella per report, CSV e .wcp")
    args = ap.parse_args(argv)

    from dlive import verifica_numpy
    esito_numpy = verifica_numpy.verifica(QUI, forza=True)
    from dlive import compat, config, registro, sysinfo, wcpfile, filters
    from dlive.devices import axdd132x as ax
    from dlive.devices.base import ErroreDispositivo
    from dlive.devices import digidata as dd

    os.chdir(QUI)
    if not os.path.isdir(args.uscita):
        os.makedirs(args.uscita)
    rep = Report(os.path.join(args.uscita, "report_diagnostica.txt"))
    registro.configura(os.path.join(QUI, "log"), "diagnostica.log", a_schermo=False)
    cfg = config.carica_o_crea(os.path.join(QUI, "config.ini"), base=QUI)
    canale = args.canale if args.canale is not None else cfg["digidata.canale_ingresso"]
    dll_cfg = args.dll if args.dll is not None else cfg["digidata.percorso_dll"]
    ora = datetime.datetime.now()
    rep.scrivi("REPORT DIAGNOSTICA DIGIDATA 1322A - denoising_live")
    rep.scrivi("Data: %s" % ora.strftime("%d/%m/%Y %H:%M:%S"))
    rep.scrivi("Cartella del programma: %s" % QUI)
    if args.finto:
        rep.scrivi("*** MODALITA' DI PROVA CON DLL FINTA: i risultati NON riguardano una scheda vera ***")

    # ------------------------------------------------------------------ 1
    rep.passo(1, "Ambiente")
    rep.scrivi("Sistema: %s" % sysinfo.versione_windows())
    rep.scrivi("Python: %s" % compat.versione_python())
    rep.scrivi("Eseguibile: %s" % sys.executable)
    rep.scrivi("Calcolo: %s" % compat.descrizione_percorso())
    rep.scrivi("Verifica di numpy in un processo separato: %s" % esito_numpy[1])
    try:
        import tkinter
        rep.scrivi("tkinter: Tk %s" % tkinter.TkVersion)
    except Exception as e:
        rep.scrivi("tkinter NON disponibile: %s" % e)
    import locale
    try:
        rep.scrivi("Impostazioni internazionali: %s, separatore decimale %r" % (
            locale.getdefaultlocale(), locale.localeconv().get("decimal_point")))
    except Exception:
        pass
    a32 = sys.maxsize <= 2 ** 32
    if not compat.SU_WINDOWS and not args.finto:
        rep.esito(1, False, "Non e' Windows: la scheda vera si puo' provare solo sul PC del laboratorio")
    elif not a32 and not args.finto:
        rep.esito(1, False, "Python a 64 bit: la DLL Axon e' a 32 bit, installare Python 3.4.4 a 32 bit")
    else:
        rep.esito(1, True, "ambiente adatto")
    errori, avvisi = cfg.controlla()
    for e in errori:
        rep.esito(1, False, "config.ini: %s" % e)
    for a in avvisi:
        rep.esito(1, None, "config.ini: %s" % a)

    # ------------------------------------------------------------------ 1b
    rep.passo("1b", "Rilevamento del PC e impostazioni di WinWCP")
    from dlive import rilevamento, winwcp_impostazioni
    for e in rilevamento.tutti(cfg=cfg, cartella_programma=QUI):
        for riga in e.righe():
            rep.scrivi(riga)
        if e.livello != rilevamento.OK:
            rep.esito("1b", False if e.livello == rilevamento.ERRORE else None,
                      "%s: %s" % (e.nome, e.messaggio))
    if args.canale is None and cfg["digidata.impostazioni_winwcp"] != "ignora":
        try:
            imp = winwcp_impostazioni.leggi()
            valori, _, _ = winwcp_impostazioni.proposta(imp, canale, args.fs)
            c_wcp = valori.get("digidata.canale_ingresso")
            if c_wcp is not None and c_wcp != canale:
                rep.esito("1b", None, "WinWCP acquisisce il segnale dall'ingresso AI%d, config.ini "
                                      "dall'AI%d: la diagnostica usa AI%d (quello di WinWCP)"
                          % (c_wcp, canale, c_wcp))
                canale = c_wcp
        except Exception as ex:
            rep.scrivi("impostazioni di WinWCP non leggibili: %s" % ex)
    from dlive import lpf8
    e8, a8 = lpf8.controlla(cfg["lpf8.taglio_hz"], args.fs, cfg["lpf8.guadagno"],
                            cfg["calibrazione.yg"], cfg["calibrazione.unita"])
    rep.scrivi("LPF-8 dichiarato in config.ini: %s, guadagno %g; attenuazione a %g Hz: %.0f dB"
               % (lpf8.descrizione(cfg["lpf8.taglio_hz"]), cfg["lpf8.guadagno"], args.fs / 2,
                  lpf8.attenuazione_db(args.fs / 2, cfg["lpf8.taglio_hz"])))
    for m in e8 + a8:
        rep.esito("1b", None, "LPF-8: %s" % m)

    # ------------------------------------------------------------------ 2
    rep.passo(2, "Programmi che usano la scheda")
    try:
        conc = sysinfo.programmi_concorrenti_attivi()
        if conc:
            rep.esito(2, False, "aperti: %s - chiuderli e rilanciare la diagnostica" % ", ".join(conc))
        else:
            rep.esito(2, True, "nessuno (WinWCP, WinEDR, AxoScope, Clampex chiusi)")
    except Exception as e:
        rep.esito(2, None, "impossibile elencare i processi: %s" % e)

    # ------------------------------------------------------------------ 3
    rep.passo(3, "Driver WinASPI (il Digidata 1322A comunica via SCSI/ASPI)")
    if compat.SU_WINDOWS:
        windir = os.environ.get("SystemRoot", r"C:\WINDOWS")
        for p in (os.path.join(windir, "system32", "wnaspi32.dll"),
                  os.path.join(windir, "system32", "drivers", "aspi32.sys"),
                  os.path.join(windir, "system", "wnaspi32.dll")):
            rep.scrivi("%s: %s" % (p, info_file(p) if os.path.exists(p) else "ASSENTE"))
        r = ax.controlla_aspi()
        rep.scrivi("GetASPI32SupportInfo: stato=%s adattatori=%s %s" % (
            r["stato"], r["adattatori"], r["errore"]))
        if r["ok"] and r["adattatori"] > 0:
            rep.esito(3, True, "WinASPI funziona, %d adattatori SCSI" % r["adattatori"])
        elif r["ok"]:
            rep.esito(3, False, "WinASPI funziona ma non vede adattatori SCSI: driver del controller SCSI?")
        else:
            rep.esito(3, False, "WinASPI non funziona (%s): %s" % (r["errore"], dd.RIMEDIO_ASPI))
        for riga in sysinfo.leggi_chiavi_registro(_hklm(), r"SYSTEM\CurrentControlSet\Services\Aspi32", 1):
            rep.scrivi("  " + riga)
    else:
        rep.esito(3, None, "saltato (non Windows)")

    # ------------------------------------------------------------------ 4
    rep.passo(4, "Periferiche SCSI e registro Axon")
    if compat.SU_WINDOWS:
        per = sysinfo.periferiche_scsi()
        trovato = False
        for ident, descr, driver in per:
            rep.scrivi("  SCSI: %s | %s | servizio=%s" % (ident, descr, driver))
            if "axon" in ident.lower() or "digidata" in ident.lower() or "digidata" in (descr or "").lower():
                trovato = True
        if trovato:
            rep.esito(4, True, "Windows conosce un dispositivo Axon/Digidata sul bus SCSI")
        else:
            rep.esito(4, None, "nessun Digidata registrato in Enum\\SCSI (normale se mai collegato "
                               "da quando Windows e' stato reinstallato; controllare acceso/cavo/terminatore)")
        for radice in (r"SOFTWARE\Axon Instruments", r"SOFTWARE\Axon", r"SOFTWARE\Molecular Devices"):
            for riga in sysinfo.leggi_chiavi_registro(_hklm(), radice, 2)[:60]:
                rep.scrivi("  " + riga)
    else:
        rep.esito(4, None, "saltato (non Windows)")

    # ------------------------------------------------------------------ 5
    rep.passo(5, "Ricerca e caricamento di AxDD132x.dll")
    librerie = []
    if args.finto:
        from dlive.devices.dd132x_finto import LibreriaFinta
        librerie.append(("<finta>", LibreriaFinta()))
        rep.esito(5, True, "DLL finta caricata")
    else:
        cand = dd.percorsi_candidati_dll(dll_cfg, QUI)
        if not cand:
            rep.esito(5, False, "nessuna AxDD132x.dll trovata. " + dd.RIMEDIO_DLL)
        for p in cand:
            rep.scrivi("Candidata: %s" % p)
            if not os.path.isfile(p):
                rep.scrivi("   non esiste")
                continue
            rep.scrivi("   %s" % info_file(p))
            if not compat.SU_WINDOWS:
                continue
            try:
                lib = ax.LibreriaDD132x(p).carica()
                rep.scrivi("   caricata; funzioni assenti: %s" % (", ".join(lib.mancanti) or "nessuna"))
                for n in lib.note:
                    rep.scrivi("   " + n)
                librerie.append((p, lib))
            except Exception as e:
                rep.scrivi("   NON caricabile: %s" % e)
        if librerie:
            rep.esito(5, True, "%d copie caricabili; si prova per prima %s" % (len(librerie), librerie[0][0]))
        elif compat.SU_WINDOWS:
            rep.esito(5, False, "nessuna copia caricabile (vedere i messaggi qui sopra). " + dd.RIMEDIO_DLL)

    # ------------------------------------------------------------------ 6
    rep.passo(6, "Strutture ctypes")
    err = ax.controlla_strutture()
    import ctypes
    rep.scrivi("DD132X_Info=%d Protocol=%d CalibrationData=%d DATABUFFER=%d (puntatori a %d bit)" % (
        ctypes.sizeof(ax.DD132X_Info), ctypes.sizeof(ax.DD132X_Protocol),
        ctypes.sizeof(ax.DD132X_CalibrationData), ctypes.sizeof(ax.DATABUFFER),
        8 * ctypes.sizeof(ctypes.c_void_p)))
    rep.esito(6, not err, "dimensioni corrette" if not err else "; ".join(err))

    # ------------------------------------------------------------------ 7-8
    dev = None
    lib_ok = None
    for percorso, lib in librerie:
        rep.passo(7, "DD132X_FindDevices con %s" % percorso)
        info = ax.DD132X_Info()
        info.uLength = ctypes.sizeof(info)
        info.byAdaptor = 255
        info.byTarget = 255
        e = ctypes.c_int(0)
        try:
            n = lib.DD132X_FindDevices(ctypes.byref(info), 1, ctypes.byref(e))
        except Exception as ex:
            rep.esito(7, False, "chiamata fallita: %s" % ex)
            continue
        rep.scrivi("Dispositivi trovati: %d, errore %d (%s)" % (n, e.value, ax.ERRORI.get(e.value, "")))
        if n >= 1:
            rep.scrivi("Nome=%r Produttore=%r Firmware=%r Versione=%r Serie=%d Adattatore=%d Target=%d" % (
                info.szName, info.szManufacturer, info.szFirmwareVersion, info.szProductVersion,
                info.uSerialNumber, info.byAdaptor, info.byTarget))
            rep.scrivi("Buffer ingresso=%d uscita=%d clock=%d tick min=%d max=%d" % (
                info.uInputBufferSize, info.uOutputBufferSize, info.uClockResolution,
                info.uMinClockTicks, info.uMaxClockTicks))
            rep.esito(7, True, "Digidata trovato con %s" % percorso)
            lib_ok = (percorso, lib)
            break
        rep.esito(7, False, "nessun Digidata trovato con questa DLL")
    if lib_ok is None:
        rep.passo("7-11", "interrotto")
        rep.esito(7, False, "Digidata non trovato: controllare che sia acceso prima di accendere il PC, "
                            "il cavo SCSI, il terminatore e il driver del controller SCSI (passi 3-4)")
        return _riepilogo(rep, cfg)

    rep.passo(8, "Apertura della scheda e calibrazione")
    try:
        dev = dd.Digidata1322Device(canale=canale, fs=args.fs, range_v=cfg["digidata.range_v"],
                                    cartella_programma=QUI, uscite=cfg["digidata.uscite_analogiche"],
                                    campioni_buffer=cfg["digidata.campioni_buffer"],
                                    chunks_per_second=cfg["digidata.chunks_per_second"],
                                    controlla_processi=not args.finto,
                                    calibrazione={"yg": cfg["calibrazione.yg"], "yz": cfg["calibrazione.yz"],
                                                  "unita": cfg["calibrazione.unita"],
                                                  "nome": cfg["calibrazione.nome_canale"]})
        dev.lib = lib_ok[1]
        dev.percorso_dll = lib_ok[0]
        dev.apri()
        for k, v in sorted(dev.info().items()):
            rep.scrivi("  %s = %s" % (k, v))
        if dev.cal_dati is not None:
            c = dev.cal_dati
            rep.scrivi("  stato apparecchiatura = 0x%08X" % c.uEquipmentStatus)
            rep.scrivi("  offset DAC = %s" % [c.anDACOffset[i] for i in range(8)])
        rep.esito(8, True, "scheda aperta")
    except ErroreDispositivo as ex:
        rep.esito(8, False, ex.messaggio)
        return _riepilogo(rep, cfg)
    except Exception:
        rep.esito(8, False, "eccezione:\n%s" % traceback.format_exc())
        return _riepilogo(rep, cfg)

    conv = 10.0 / 32677 / cfg["calibrazione.yg"]
    rep.passo(9, "Campioni singoli (DD132X_GetAIValue)")
    try:
        vals = [dev.leggi_valore_singolo(canale) for _ in range(10)]
        rep.scrivi("AI%d: %s conteggi = %s mV" % (canale, vals, ["%.1f" % (v * conv) for v in vals]))
        for ch in range(16):
            v = dev.leggi_valore_singolo(ch)
            rep.scrivi("  AI%-2d = %6d conteggi = %8.1f mV" % (ch, v, v * conv))
        rep.esito(9, True, "lettura singola riuscita")
    except Exception as ex:
        rep.esito(9, None, "lettura singola non riuscita (%s); si prova comunque l'acquisizione" % ex)

    rep.passo(10, "Acquisizione continua: %g s a %g Hz da AI%d" % (args.secondi, args.fs, canale))
    dati = None
    modi = [cfg["digidata.uscite_analogiche"]]
    modi.append("nessuna" if modi[0] == "come_winwcp" else "come_winwcp")
    for modo in modi:
        dev.uscite = modo
        rep.scrivi("Modalita' uscite: %s" % modo)
        try:
            dati, stat = _acquisisci(dev, args.secondi, rep)
            if dati is not None and len(dati) > 0.9 * args.secondi * args.fs:
                rep.esito(10, True, "ricevuti %d campioni su %d attesi (uscite=%s)" % (
                    len(dati), int(args.secondi * args.fs), modo))
                if modo != cfg["digidata.uscite_analogiche"]:
                    rep.esito(10, None, "funziona solo con uscite_analogiche = %s: impostarlo in config.ini" % modo)
                break
            rep.esito(10, False, "ricevuti solo %d campioni (uscite=%s)" % (0 if dati is None else len(dati), modo))
        except ErroreDispositivo as ex:
            rep.esito(10, False, "%s (uscite=%s)" % (ex.messaggio, modo))
        except Exception:
            rep.esito(10, False, "eccezione (uscite=%s):\n%s" % (modo, traceback.format_exc()))
        dati = None
    try:
        dev.chiudi()
    except Exception:
        pass

    if dati:
        nome = "diagnostica_%s" % ora.strftime("%y%m%d_%H%M%S")
        # l'orologio del PC del laboratorio puo' ripartire dalla stessa data:
        # mai sovrascrivere una diagnostica precedente
        base, k = nome, 1
        while any(os.path.exists(os.path.join(args.uscita, nome + e)) for e in (".csv", ".wcp")):
            k += 1
            nome = "%s_%d" % (base, k)
        p_csv = os.path.join(args.uscita, nome + ".csv")
        with open(p_csv, "w") as f:
            f.write("tempo_s;conteggi;mV\n")
            for i, v in enumerate(dati):
                f.write(("%.4f;%d;%.3f\n" % (i / dev.fs, v, v * conv)).replace(".", ","))
        rep.scrivi("Salvato %s" % p_csv)
        p_wcp = os.path.join(args.uscita, nome + ".wcp")
        n = wcpfile.campioni_per_record(args.secondi, dev.fs)
        w = wcpfile.ScrittoreWCP(p_wcp, 1.0 / dev.fs, max(n, 256), [{
            "nome": cfg["calibrazione.nome_canale"], "unita": cfg["calibrazione.unita"],
            "yg": cfg["calibrazione.yg"], "yz": cfg["calibrazione.yz"]}], ident="diagnostica denoising_live")
        w.aggiungi(dati)
        w.chiudi()
        rep.scrivi("Salvato %s (da aprire con WinWCP per verificare il formato)" % p_wcp)
        _analisi(rep, dati, dev.fs, conv, cfg)
    return _riepilogo(rep, cfg)


def _hklm():
    import winreg
    return winreg.HKEY_LOCAL_MACHINE


def _acquisisci(dev, secondi, rep):
    dev.avvia()
    t0 = time.time()
    dati = []
    blocchi = 0
    persi = 0
    indice_atteso = 0
    discontinuita = 0
    while time.time() - t0 < secondi + 0.5 and len(dati) < secondi * dev.fs:
        b = dev.leggi(0.2)
        if b is None:
            continue
        blocchi += 1
        persi += b.persi
        if b.indice != indice_atteso and not b.persi:
            discontinuita += 1
        indice_atteso = b.indice + len(b.dati)
        dati.extend(b.dati)
    pos = dev.posizione()
    dur = time.time() - t0
    dev.ferma()
    dati = dati[:int(secondi * dev.fs)]
    rep.scrivi("Durata %.2f s, blocchi %d, campioni %d, persi %d, discontinuita' %d" % (
        dur, blocchi, len(dati), persi, discontinuita))
    rep.scrivi("GetAcquisitionPosition alla fine: %s (letti %d, attesi circa %d)" % (
        pos, indice_atteso, int(dur * dev.fs)))
    if pos is not None and indice_atteso:
        rep.scrivi("Rapporto posizione/letti = %.3f (circa 1 = contatore coerente)" % (pos / float(indice_atteso)))
    vuoti = sum(1 for v in dati if v == 32767)
    dispari = sum(1 for v in dati if v & 1)
    rep.scrivi("Campioni uguali al valore 'vuoto' 32767: %d; con bit 0 (TAG) a 1: %d" % (vuoti, dispari))
    return dati, {"persi": persi}


def _analisi(rep, dati, fs, conv, cfg):
    from dlive import compat, filters
    rep.passo(11, "Segnale, rumore e filtro predefinito")
    x = [v * conv for v in dati]
    n = len(x)
    m = sum(x) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in x) / n)
    rep.scrivi("Media %.2f mV, deviazione standard %.2f mV, min %.1f, max %.1f mV" % (m, sd, min(x), max(x)))
    sat = sum(1 for v in dati if v >= 32700 or v <= -32701)
    rep.scrivi("Campioni saturati: %d" % sat)
    par = filters.ParametriFiltro(cfg["filtro.tipo"], cfg["filtro.ordine"], cfg["filtro.taglio_hz"],
                                  cfg.notch(), cfg["filtro.q_notch"])
    y = filters.filtra_causale(par, x, fs)
    coda = y[int(fs):]
    mf = sum(coda) / len(coda)
    sdf = math.sqrt(sum((v - mf) ** 2 for v in coda) / len(coda))
    rep.scrivi("Dopo il filtro predefinito (%s): deviazione standard %.2f mV" % (par.descrizione(), sdf))
    np = compat.np
    if np is not None and n > 256:
        a = np.asarray(x) - m
        seg = 1024 if n >= 4096 else 256
        fin = np.hanning(seg)
        spettri = [np.abs(np.fft.rfft(a[i:i + seg] * fin)) ** 2 for i in range(0, n - seg + 1, seg // 2)]
        P = np.mean(spettri, axis=0) / (fs * (fin ** 2).sum()) * 2
        f = np.fft.rfftfreq(seg, 1.0 / fs)
        df = f[1] - f[0]

        def banda(lo, hi):
            sel = (f >= lo) & (f < hi)
            return float(np.sqrt(P[sel].sum() * df))
        rep.scrivi("RMS per banda (mV): 0-2 Hz %.2f | 2-20 Hz %.2f | 20-25 %.2f | 25-50 %.2f | 49-51 %.2f | 50-500 %.2f" % (
            banda(0, 2), banda(2, 20), banda(20, 25), banda(25, 50), banda(49, 51), banda(50, fs / 2)))
        idx = np.argsort(P * (f > 1.0))[-8:][::-1]
        rep.scrivi("Righe piu' forti: " + ", ".join("%.1f Hz" % f[i] for i in idx))
        rep.scrivi("(Con l'LPF-8 a %g Hz il rumore sopra 25 Hz dovrebbe essere molto attenuato: "
                   "se non lo e', entra dopo il filtro analogico.)" % cfg["lpf8.taglio_hz"])


def _riepilogo(rep, cfg):
    rep.scrivi("")
    rep.scrivi("#" * 72)
    rep.scrivi("RIEPILOGO")
    rep.scrivi("#" * 72)
    errori = 0
    for numero, etichetta, testo in rep.esiti:
        rep.scrivi("[%-6s] passo %s: %s" % (etichetta, numero, testo.split("\n")[0]))
        if etichetta == "ERRORE":
            errori += 1
    rep.scrivi("")
    if errori:
        rep.scrivi("Ci sono %d errori.  Mandare il file %s e la cartella log." % (errori, rep.percorso))
    else:
        rep.scrivi("Nessun errore: si puo' passare all'anteprima (avvia.bat).")
    rep.chiudi()
    return 1 if errori else 0


if __name__ == "__main__":
    try:
        codice = main()
    except Exception:
        traceback.print_exc()
        try:
            with open(os.path.join(QUI, "report_diagnostica.txt"), "a") as f:
                f.write("\nERRORE NON PREVISTO NELLO SCRIPT:\n" + traceback.format_exc())
        except Exception:
            pass
        codice = 99
    sys.exit(codice)
