# -*- coding: utf-8 -*-
"""Informazioni di sistema: spazio su disco, processi attivi (Windows),
periferiche SCSI nel registro, versione di Windows."""
import os
import platform
import shutil
import sys

from .compat import SU_WINDOWS

# Programmi che usano il Digidata: se sono aperti la scheda e' occupata.
PROGRAMMI_CONCORRENTI = ("winwcp.exe", "winedr.exe", "axoscope.exe", "clampex.exe",
                         "axoscope11.exe")


def spazio_libero_mb(percorso):
    """MB liberi sul disco che contiene 'percorso' (None se non determinabile)."""
    p = os.path.abspath(percorso)
    while p and not os.path.exists(p):
        nuovo = os.path.dirname(p)
        if nuovo == p:
            break
        p = nuovo
    try:
        return shutil.disk_usage(p).free / (1024.0 * 1024.0)
    except (OSError, AttributeError):
        return None


def secondi_dall_avvio():
    """Secondi trascorsi dall'avvio del sistema (None se non disponibile).
    Su Windows GetTickCount (presente in XP; ricomincia da 0 dopo 49,7 giorni),
    su Linux /proc/uptime."""
    if SU_WINDOWS:
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.GetTickCount.restype = ctypes.c_uint32
            return k32.GetTickCount() / 1000.0
        except Exception:
            return None
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except (IOError, OSError, ValueError, IndexError):
        return None


def separatore_decimale():
    """Separatore decimale dell'utente (impostazioni internazionali di Windows,
    come lo usa Delphi/WinWCP); None fuori da Windows o se non leggibile."""
    if not SU_WINDOWS:
        return None
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(8)
        # LOCALE_USER_DEFAULT = 0x400, LOCALE_SDECIMAL = 0x0E
        if ctypes.windll.kernel32.GetLocaleInfoW(0x400, 0x0E, buf, 8):
            return buf.value or None
    except Exception:
        pass
    return None


def versione_windows():
    if not SU_WINDOWS:
        return platform.platform()
    try:
        v = sys.getwindowsversion()
        return "Windows %d.%d build %d %s" % (v.major, v.minor, v.build, v.service_pack)
    except Exception:
        return platform.platform()


def processi_attivi():
    """Nomi (minuscoli) degli eseguibili in esecuzione.  Solo Windows;
    usa la Toolhelp32 di kernel32 (presente anche su XP Home)."""
    if not SU_WINDOWS:
        return []
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_void_p),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_char * 260)]

    k32 = ctypes.windll.kernel32
    TH32CS_SNAPPROCESS = 2
    k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == ctypes.c_void_p(-1).value:
        return []
    nomi = []
    try:
        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
        ok = k32.Process32First(ctypes.c_void_p(snap), ctypes.byref(pe))
        while ok:
            nomi.append(pe.szExeFile.decode("mbcs", "replace").lower())
            ok = k32.Process32Next(ctypes.c_void_p(snap), ctypes.byref(pe))
    finally:
        k32.CloseHandle(ctypes.c_void_p(snap))
    return nomi


def programmi_concorrenti_attivi():
    try:
        attivi = processi_attivi()
    except Exception:
        return []
    return sorted(set(p for p in attivi if p in PROGRAMMI_CONCORRENTI))


def _winreg():
    try:
        import winreg
        return winreg
    except ImportError:
        return None


def leggi_chiavi_registro(radice, percorso, profondita=3):
    """Elenco 'percorso\\valore = dato' sotto una chiave (per i report)."""
    wr = _winreg()
    if wr is None:
        return []
    righe = []

    def visita(h, p, livello):
        try:
            k = wr.OpenKey(h, p)
        except OSError:
            return
        try:
            i = 0
            while True:
                try:
                    nome, dato, _ = wr.EnumValue(k, i)
                except OSError:
                    break
                righe.append("%s\\%s = %r" % (p, nome, dato))
                i += 1
            if livello < profondita:
                i = 0
                while True:
                    try:
                        sub = wr.EnumKey(k, i)
                    except OSError:
                        break
                    visita(h, p + "\\" + sub, livello + 1)
                    i += 1
        finally:
            wr.CloseKey(k)

    visita(radice, percorso, 0)
    return righe


def periferiche_scsi():
    """Periferiche SCSI note a Windows (HKLM\\SYSTEM\\CurrentControlSet\\Enum\\SCSI).
    Restituisce lista di (id, descrizione, driver, stato_presente)."""
    wr = _winreg()
    if wr is None:
        return []
    out = []
    base = r"SYSTEM\CurrentControlSet\Enum\SCSI"
    try:
        k = wr.OpenKey(wr.HKEY_LOCAL_MACHINE, base)
    except OSError:
        return out
    i = 0
    while True:
        try:
            dev = wr.EnumKey(k, i)
        except OSError:
            break
        i += 1
        try:
            kd = wr.OpenKey(k, dev)
        except OSError:
            continue
        j = 0
        while True:
            try:
                ist = wr.EnumKey(kd, j)
            except OSError:
                break
            j += 1
            descr = driver = ""
            try:
                ki = wr.OpenKey(kd, ist)
                for nome in ("FriendlyName", "DeviceDesc"):
                    try:
                        descr = wr.QueryValueEx(ki, nome)[0]
                        break
                    except OSError:
                        pass
                try:
                    driver = wr.QueryValueEx(ki, "Service")[0]
                except OSError:
                    pass
                wr.CloseKey(ki)
            except OSError:
                pass
            out.append((dev + "\\" + ist, descr, driver))
        wr.CloseKey(kd)
    wr.CloseKey(k)
    return out


def cartelle_programmi():
    cand = []
    for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        v = os.environ.get(var)
        if v and v not in cand:
            cand.append(v)
    for d in (r"C:\Program Files", r"C:\Programmi", r"C:\Program Files (x86)"):
        if d not in cand:
            cand.append(d)
    return cand
