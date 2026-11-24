# -*- coding: utf-8 -*-
"""Rilevamento sul posto delle caratteristiche del PC del laboratorio.

Tutto quello che si puo' sapere girando sul PC (versione di Windows, diritti,
Python, schermo, separatore decimale, disco, DLL Axon e WinASPI, impostazioni
e processi di WinWCP, orologio) si rileva qui, quando il programma, la
diagnostica o installa.bat girano li': il comando da incollare prima della
visita non deve raccoglierlo (vedi docs/comando_laboratorio.md).

Ogni controllo restituisce un Esito(nome, livello, messaggio, dettagli) con
livello "OK", "AVVISO" o "ERRORE".  Le informazioni del sistema arrivano da un
oggetto Ambiente: AmbienteReale legge Windows (ctypes, winreg), i test usano
un ambiente finto con gli stessi metodi.

Uso da riga di comando (lo chiama installa.bat):
    python -m dlive.rilevamento [--uscita FILE] [--cartella-dati DIR]
"""
import datetime
import hashlib
import os
import sys

from .compat import SU_WINDOWS

# MD5 delle DLL estratte (riferimenti/dll/LEGGIMI_DLL.txt)
DLL_NOTE = {
    "da0e698d57c69eb369f6d7aad6d22a9d": "AxDD132x 1.1.1.6 di pCLAMP 10.3.2.1",
    "00a2606072035dffb8b8924c7c18bab9": "AxDD132x 1.0.0.38 di WinWCP (stessa in 5.2.7 e 5.8.1)",
    "323054463929eacdbe50f1cf9435b8d9": "AxDD132x 1.1.0.7 di pCLAMP 9.2.1.9",
    "066dc62c5a1366a8fbf0e1a6ce295b67": "AxDD132x 1.0.0.39 dell'update di pCLAMP 8.2",
    "128ec62ff59a59beb5772e52ed8d3148": "WNASPI32 4.60 (1021) Adaptec",
    "b979979ab8027f7f53fb16ec4229b7db": "ASPI32.SYS 4.60 (1021) Adaptec",
}
# Spazio per le registrazioni: grezzo 7,2 MB/ora a 1000 Hz + filtrato 0,9 MB/ora
MB_PER_ORA_1000HZ = 8.1
ORE_MINIME = 3.0
MB_INSTALLAZIONE = 150.0          # Python 3.4 (~60 MB) + numpy (~30 MB) + programma
ANNO_WINWCP_516 = 2016            # WinWCP 5.1.6 e' del 16/03/2016 (MDIForm.pas)

OK = "OK"
AVVISO = "AVVISO"
ERRORE = "ERRORE"


class Esito(object):
    def __init__(self, nome, livello, messaggio, dettagli=None):
        self.nome = nome
        self.livello = livello
        self.messaggio = messaggio
        self.dettagli = list(dettagli or [])

    def righe(self):
        r = ["[%-6s] %s: %s" % (self.livello, self.nome, self.messaggio)]
        r.extend("         " + d for d in self.dettagli)
        return r

    def __repr__(self):
        return "Esito(%r, %r, %r)" % (self.nome, self.livello, self.messaggio)


# ---------------------------------------------------------------------------
# ambiente
# ---------------------------------------------------------------------------
class AmbienteReale(object):
    """Legge il sistema vero (pensato per Windows XP; su Linux restituisce
    quel che puo')."""

    def su_windows(self):
        return SU_WINDOWS

    def env(self, nome, predefinito=None):
        return os.environ.get(nome, predefinito)

    def versione_windows(self):
        """(maggiore, minore, build, service pack testo, nome prodotto)."""
        if not SU_WINDOWS:
            import platform
            return (0, 0, 0, "", platform.platform())
        v = sys.getwindowsversion()
        nome = self.reg_valore("HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "ProductName") or ""
        return (v.major, v.minor, v.build, v.service_pack or "", nome)

    def windows_64bit(self):
        if not SU_WINDOWS:
            return None
        if os.environ.get("PROCESSOR_ARCHITEW6432") or \
                os.environ.get("PROCESSOR_ARCHITECTURE", "").upper() in ("AMD64", "IA64"):
            return True
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            f = getattr(k32, "IsWow64Process", None)
            if f is None:
                return False                       # XP senza la funzione: 32 bit
            r = ctypes.c_int(0)
            if f(k32.GetCurrentProcess(), ctypes.byref(r)):
                return bool(r.value)
        except Exception:
            pass
        return False

    def amministratore(self):
        if not SU_WINDOWS:
            try:
                return os.geteuid() == 0
            except AttributeError:
                return None
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return None

    def reg_valore(self, radice, chiave, valore):
        if not SU_WINDOWS:
            return None
        try:
            import winreg
            r = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}[radice]
            k = winreg.OpenKey(r, chiave)
            try:
                return winreg.QueryValueEx(k, valore)[0]
            finally:
                winreg.CloseKey(k)
        except Exception:
            return None

    def reg_sottochiavi(self, radice, chiave):
        if not SU_WINDOWS:
            return []
        try:
            import winreg
            r = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}[radice]
            k = winreg.OpenKey(r, chiave)
        except Exception:
            return []
        out = []
        i = 0
        while True:
            try:
                out.append(winreg.EnumKey(k, i))
            except OSError:
                break
            i += 1
        winreg.CloseKey(k)
        return out

    def esiste(self, p):
        return os.path.exists(p)

    def elenca(self, cartella):
        try:
            return sorted(os.listdir(cartella))
        except OSError:
            return []

    def dimensione(self, p):
        try:
            return os.path.getsize(p)
        except OSError:
            return None

    def md5(self, p):
        try:
            h = hashlib.md5()
            with open(p, "rb") as f:
                h.update(f.read())
            return h.hexdigest()
        except (IOError, OSError):
            return None

    def versione_file(self, p):
        from .devices import axdd132x as ax
        return ax.versione_file(p)

    def spazio_libero_mb(self, p):
        from . import sysinfo
        return sysinfo.spazio_libero_mb(p)

    def schermo(self):
        """(larghezza, altezza, dpi) o None."""
        if not SU_WINDOWS:
            return None
        try:
            import ctypes
            u = ctypes.windll.user32
            g = ctypes.windll.gdi32
            dc = u.GetDC(None)
            dpi = g.GetDeviceCaps(dc, 88)          # LOGPIXELSX
            u.ReleaseDC(None, dc)
            return (u.GetSystemMetrics(0), u.GetSystemMetrics(1), dpi)
        except Exception:
            return None

    def separatore_decimale(self):
        from . import sysinfo
        return sysinfo.separatore_decimale()

    def processi(self):
        from . import sysinfo
        try:
            return sysinfo.processi_attivi()
        except Exception:
            return []

    def adesso(self):
        return datetime.datetime.now()

    def python(self):
        import struct
        return (sys.version.split()[0], 8 * struct.calcsize("P"), sys.executable)

    def candidati_dll(self, cartella_programma):
        from .devices import digidata as dd
        return dd.percorsi_candidati_dll("", cartella_programma)

    def impostazioni_winwcp(self):
        from . import winwcp_impostazioni
        return winwcp_impostazioni.leggi()

    def cartelle_winwcp(self):
        from . import winwcp_impostazioni
        return winwcp_impostazioni.cartelle_programma_winwcp()


# ---------------------------------------------------------------------------
# controlli
# ---------------------------------------------------------------------------
def controlla_windows(amb):
    if not amb.su_windows():
        return Esito("Windows", AVVISO, "non e' Windows (%s): rilevamento parziale"
                     % amb.versione_windows()[4])
    mag, mi, build, sp, nome = amb.versione_windows()
    bit64 = amb.windows_64bit()
    bit = "64 bit" if bit64 else ("32 bit" if bit64 is not None else "bit non determinati")
    testo = "%s %d.%d build %d %s, %s" % (nome or "Windows", mag, mi, build, sp or "senza Service Pack", bit)
    numero_sp = 0
    for parola in (sp or "").split():
        if parola.isdigit():
            numero_sp = int(parola)
    if (mag, mi) == (5, 1) and numero_sp < 2:
        return Esito("Windows", ERRORE, testo + ": Python 3.4 usa msvcr100.dll, che richiede "
                     "almeno XP Service Pack 2 (EncodePointer); installare SP2 o SP3")
    if (mag, mi) < (5, 1):
        return Esito("Windows", ERRORE, testo + ": Python 3.4 richiede almeno Windows XP")
    return Esito("Windows", OK, testo)


def controlla_amministratore(amb):
    a = amb.amministratore()
    if a is None:
        return Esito("Diritti", AVVISO, "non determinabili")
    if a:
        return Esito("Diritti", OK, "utente amministratore")
    return Esito("Diritti", AVVISO, "utente NON amministratore: installa.bat non puo' installare "
                 "Python per tutti gli utenti ne' scrivere in C:\\ (usare un utente amministratore); "
                 "il programma gia' installato funziona anche senza")


def controlla_python(amb):
    det = []
    ver, bit, exe = amb.python()
    det.append("in uso: Python %s a %d bit (%s)" % (ver, bit, exe))
    trovati = []
    for radice in ("HKLM", "HKCU"):
        for v in amb.reg_sottochiavi(radice, r"SOFTWARE\Python\PythonCore"):
            p = amb.reg_valore(radice, r"SOFTWARE\Python\PythonCore\%s\InstallPath" % v, "")
            trovati.append("%s %s: %s" % (radice, v, p or "?"))
    for nome in amb.elenca("C:\\"):
        if nome.lower().startswith("python"):
            trovati.append("cartella C:\\%s" % nome)
    det.extend("installato: " + t for t in trovati)
    windir = amb.env("SystemRoot") or amb.env("windir") or "C:\\WINDOWS"
    msvcr = os.path.join(windir, "system32", "msvcr100.dll")
    if amb.esiste(msvcr):
        det.append("msvcr100.dll presente (%s, versione %s)" % (msvcr, amb.versione_file(msvcr) or "?"))
    else:
        det.append("msvcr100.dll assente in system32 (la installa l'MSI di Python 3.4.4)")
    if ver.startswith("3.4") and bit == 32:
        return Esito("Python", OK, "Python %s a 32 bit" % ver, det)
    return Esito("Python", AVVISO, "Python %s a %d bit: per la scheda serve Python 3.4 a 32 bit"
                 % (ver, bit), det)


def controlla_schermo(amb, scelta_config="auto"):
    s = amb.schermo()
    if s is None:
        return Esito("Schermo", AVVISO, "risoluzione e DPI non determinabili")
    w, h, dpi = s
    from .scala import fattore_automatico
    f = fattore_automatico(w, h, dpi)
    testo = "%dx%d, %d DPI (%s): interfaccia al %d %% (font di %d punti)" % (
        w, h, dpi, "caratteri grandi" if dpi >= 115 else "caratteri normali",
        int(round(f * 100)), int(round(12 * f)))
    if scelta_config not in ("auto", "", None):
        testo += "; config.ini impone %s %%" % scelta_config
    if w < 1024 or h < 768:
        return Esito("Schermo", AVVISO, testo + ": sotto 1024x768 provare [interfaccia] dimensione = 75")
    return Esito("Schermo", OK, testo)


def controlla_separatore(amb, scelta_config="auto"):
    sep = amb.separatore_decimale()
    if sep is None:
        return Esito("Separatore decimale", AVVISO, "non determinabile (si usa la virgola)")
    nome = {",": "virgola", ".": "punto"}.get(sep, repr(sep))
    testo = "%s (impostazioni internazionali); nei .wcp: %s" % (
        nome, nome if scelta_config == "auto" else scelta_config)
    if sep not in (",", "."):
        return Esito("Separatore decimale", AVVISO, testo + ": insolito, WinWCP rilegge solo virgola e punto")
    return Esito("Separatore decimale", OK, testo)


def controlla_disco(amb, cartella, fs=1000.0, ore=ORE_MINIME, minimo_config_mb=200.0):
    libero = amb.spazio_libero_mb(cartella)
    if libero is None:
        return Esito("Disco", AVVISO, "spazio libero in %s non determinabile" % cartella)
    servono = max(MB_PER_ORA_1000HZ * fs / 1000.0 * ore, 1.0) + minimo_config_mb
    ore_possibili = max(0.0, (libero - minimo_config_mb)) / (MB_PER_ORA_1000HZ * fs / 1000.0)
    testo = "%s: %.0f MB liberi, bastano per circa %.0f ore di registrazione a %g Hz" % (
        cartella, libero, ore_possibili, fs)
    if libero < servono:
        return Esito("Disco", AVVISO, testo + ": NON bastano per %g ore (servono %.0f MB, compreso il "
                     "minimo di config.ini): scegliere un'altra cartella dati" % (ore, servono))
    return Esito("Disco", OK, testo)


def controlla_disco_installazione(amb, cartella="C:\\"):
    libero = amb.spazio_libero_mb(cartella)
    if libero is None:
        return Esito("Disco (installazione)", AVVISO, "spazio libero non determinabile")
    if libero < MB_INSTALLAZIONE:
        return Esito("Disco (installazione)", ERRORE, "%.0f MB liberi in %s: ne servono circa %.0f "
                     "per Python, numpy e il programma" % (libero, cartella, MB_INSTALLAZIONE))
    return Esito("Disco (installazione)", OK, "%.0f MB liberi in %s" % (libero, cartella))


RIMEDIO_DLL = ("denoising_live usa la AxDD132x.dll di WinWCP (nella cartella di winwcp.exe, insieme ad "
               "Axoutils32.dll): controllare che WinWCP sia installato e che in quella cartella ci siano "
               "le due DLL, altrimenti reinstallare WinWCP; se sono altrove, scriverne il percorso in "
               "config.ini, [digidata] percorso_dll")
RIMEDIO_ASPI = ("installare AxoScope (dall'installatore di Axon del laboratorio): installa WinASPI e il "
                "driver SCSI (guida di WinWCP, p. 21); poi riavviare il PC")


def controlla_dll(amb, cartella_programma):
    if not amb.su_windows():
        return Esito("DLL Axon e WinASPI", AVVISO, "saltato (non Windows)")
    det = []
    installate = []
    for p in amb.candidati_dll(cartella_programma):
        if not amb.esiste(p):
            continue
        h = amb.md5(p)
        nota = DLL_NOTE.get(h, "copia diversa da tutte quelle estratte")
        det.append("%s: %s byte, versione %s, md5 %s (%s)" % (
            p, amb.dimensione(p), amb.versione_file(p) or "?", h, nota))
        installate.append(p)
    if installate:
        cartella = os.path.dirname(installate[0])
        utils = [os.path.join(cartella, n) for n in ("Axoutils32.dll", "AxoUtils32.dll", "axoutils32.dll")]
        if any(amb.esiste(u) for u in utils):
            det.append("Axoutils32.dll presente accanto a %s" % installate[0])
        else:
            det.append("Axoutils32.dll ASSENTE in %s (la versione di WinWCP 1.0.0.38 ne ha bisogno)" % cartella)
    windir = amb.env("SystemRoot") or amb.env("windir") or "C:\\WINDOWS"
    aspi = []
    for p in (os.path.join(windir, "system32", "wnaspi32.dll"),
              os.path.join(windir, "system32", "drivers", "aspi32.sys")):
        if amb.esiste(p):
            h = amb.md5(p)
            aspi.append(p)
            det.append("%s: versione %s, md5 %s (%s)" % (p, amb.versione_file(p) or "?", h,
                                                       DLL_NOTE.get(h, "altra versione")))
        else:
            det.append("%s: ASSENTE" % p)
    if not installate:
        return Esito("DLL Axon e WinASPI", ERRORE, "AxDD132x.dll non trovata sul PC. " + RIMEDIO_DLL, det)
    if not aspi:
        return Esito("DLL Axon e WinASPI", ERRORE, "WinASPI (wnaspi32.dll, aspi32.sys) assente: il "
                     "Digidata 1322A non puo' comunicare. Rimedio: " + RIMEDIO_ASPI, det)
    return Esito("DLL Axon e WinASPI", OK, "AxDD132x.dll installata: %s" % installate[0], det)


def controlla_winwcp(amb, cfg=None):
    from . import winwcp_impostazioni as wi
    det = ["cartella di WinWCP: %s" % c for c in amb.cartelle_winwcp()]
    try:
        imp = amb.impostazioni_winwcp()
    except Exception as e:
        return Esito("Impostazioni di WinWCP", AVVISO, "lettura non riuscita: %s" % e, det)
    det.extend(imp.righe())
    if not imp.trovate:
        return Esito("Impostazioni di WinWCP", AVVISO, "non trovate: si usa config.ini", det)
    canale = cfg["digidata.canale_ingresso"] if cfg is not None else 2
    fs = cfg["digidata.frequenza_acquisizione_hz"] if cfg is not None else 1000.0
    valori, note, avvisi = wi.proposta(imp, canale, fs)
    det.extend("nota: " + n for n in note)
    if cfg is not None:
        diff = wi.differenze(cfg, valori)
        det.extend("proposta: %s = %r (config.ini: %r)" % (k, v, a) for k, a, v in diff)
        if not diff:
            det.append("config.ini coincide gia' con WinWCP")
    if avvisi:
        return Esito("Impostazioni di WinWCP", AVVISO, " ".join(avvisi), det)
    return Esito("Impostazioni di WinWCP", OK, "lette (sola lettura)", det)


def controlla_processi(amb):
    from .sysinfo import PROGRAMMI_CONCORRENTI
    attivi = sorted(set(p for p in amb.processi() if p in PROGRAMMI_CONCORRENTI))
    if attivi:
        return Esito("WinWCP in esecuzione", AVVISO, "aperti: %s - chiuderli prima di usare la scheda"
                     % ", ".join(attivi))
    return Esito("WinWCP in esecuzione", OK, "no (WinWCP, WinEDR, AxoScope, Clampex chiusi)")


def controlla_orologio(amb):
    t = amb.adesso()
    testo = "data e ora del PC: %s" % t.strftime("%d/%m/%Y %H:%M")
    if t.year < ANNO_WINWCP_516:
        return Esito("Orologio", AVVISO, testo + ": anteriore all'uscita di WinWCP 5.1.6 (2016), quindi "
                     "sbagliata (come nei file di prova, datati 2007-2008 ma scritti dalla 5.1.6). "
                     "I nomi AAMMGG dei file seguono questa data, come in WinWCP")
    return Esito("Orologio", OK, testo)


def tutti(amb=None, cfg=None, cartella_programma=None, cartella_dati=None, installazione=False):
    """Esegue tutti i controlli; ognuno e' protetto: un errore imprevisto
    diventa un AVVISO e non ferma gli altri."""
    amb = amb or AmbienteReale()
    if cartella_dati is None:
        cartella_dati = cfg.percorso_assoluto("generale.cartella_dati") if cfg is not None else \
            (cartella_programma or os.getcwd())
    fs = cfg["digidata.frequenza_acquisizione_hz"] if cfg is not None else 1000.0
    minimo = cfg["generale.spazio_minimo_mb"] if cfg is not None else 200.0
    dim = cfg["interfaccia.dimensione"] if cfg is not None else "auto"
    sep = cfg["salvataggio.separatore_decimale"] if cfg is not None else "auto"
    passi = [
        ("Windows", lambda: controlla_windows(amb)),
        ("Diritti", lambda: controlla_amministratore(amb)),
        ("Python", lambda: controlla_python(amb)),
        ("Schermo", lambda: controlla_schermo(amb, dim)),
        ("Separatore decimale", lambda: controlla_separatore(amb, sep)),
    ]
    if installazione:
        passi.append(("Disco (installazione)", lambda: controlla_disco_installazione(amb)))
    passi += [
        ("Disco", lambda: controlla_disco(amb, cartella_dati, fs, ORE_MINIME, minimo)),
        ("DLL Axon e WinASPI", lambda: controlla_dll(amb, cartella_programma)),
        ("Impostazioni di WinWCP", lambda: controlla_winwcp(amb, cfg)),
        ("WinWCP in esecuzione", lambda: controlla_processi(amb)),
        ("Orologio", lambda: controlla_orologio(amb)),
    ]
    esiti = []
    for nome, f in passi:
        try:
            esiti.append(f())
        except Exception as e:
            esiti.append(Esito(nome, AVVISO, "controllo non riuscito: %s: %s" % (type(e).__name__, e)))
    return esiti


def testo(esiti):
    righe = []
    for e in esiti:
        righe.extend(e.righe())
    return "\n".join(righe)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Rilevamento delle caratteristiche del PC")
    ap.add_argument("--uscita", default="", help="file di testo dove scrivere il risultato")
    ap.add_argument("--cartella-programma", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--cartella-dati", default=None)
    ap.add_argument("--installazione", action="store_true", help="aggiunge il controllo dello spazio per installare")
    a = ap.parse_args(argv)
    cfg = None
    p_cfg = os.path.join(a.cartella_programma, "config.ini")
    try:
        from . import config
        cfg = config.Configurazione(p_cfg, base=a.cartella_programma)
        cfg.carica()
    except Exception:
        cfg = None
    esiti = tutti(cfg=cfg, cartella_programma=a.cartella_programma, cartella_dati=a.cartella_dati,
                  installazione=a.installazione)
    t = "RILEVAMENTO PC - %s\n%s\n" % (datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"), testo(esiti))
    try:
        print(t)
    except Exception:
        pass
    if a.uscita:
        with open(a.uscita, "a") as f:
            f.write(t + "\n")
    return 1 if any(e.livello == ERRORE for e in esiti) else 0


if __name__ == "__main__":
    sys.exit(main())
