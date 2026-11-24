# -*- coding: utf-8 -*-
"""Gruppo E (parte senza finestra): vermin e tempo di calcolo.

E1 (Python 3.4 in Docker) e E3/E5 (finestra sotto Xvfb) sono eseguiti da
valida.sh nel contenitore; qui E2 e la parte di E4 sul PC di sviluppo."""
from __future__ import division

import os
import subprocess
import sys
import time

import pytest

import comuni as C

RUNTIME = ["main.py", "diagnostica_digidata.py", "dlive"]


def _vermin():
    for p in (os.path.join(os.path.dirname(sys.executable), "vermin"),):
        if os.path.exists(p):
            return p
    try:
        import shutil
        return shutil.which("vermin")
    except Exception:
        return None


def test_E2_vermin(registra):
    exe = _vermin()
    if exe is None:
        registra("E2", "vermin non installato", None)
        pytest.skip("vermin assente")
    cmd = [exe, "--target=3.4-", "--violations", "--no-tips", "--eval-annotations",
           "--backport", "argparse", "--backport", "enum"] + RUNTIME
    pr = subprocess.Popen(cmd, cwd=C.RADICE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True)
    out, _ = pr.communicate()
    minimo = [r for r in out.splitlines() if r.startswith("Minimum required versions")]
    # vermin stampa sempre un riepilogo; una violazione e' una riga che cita un
    # file .py (con la regola violata sotto) e fa scrivere "Target versions not met"
    violazioni = [r for r in out.splitlines() if ".py" in r and not r.startswith("Analyzing")]
    ok = pr.returncode == 0 and not violazioni and "Target versions not met" not in out
    registra("E2", "codice di uscita %d, %d violazioni; %s" % (
        pr.returncode, len(violazioni), minimo[0] if minimo else ""), ok, {"uscita": out[-2000:]})
    assert ok


def test_E4_tempo_di_calcolo(registra, lavoro):
    """Catena completa senza finestra (lettura, filtro, salvataggio con fsync,
    buffer del grafico) su 10 minuti di segnale a 1000 Hz, 1 canale."""
    s = C.sintetico()
    p = os.path.join(lavoro, "sint.wcp")
    C.scrivi_wcp_semplice(p, s.rumoroso, 0.001)
    cpu0 = time.process_time() if hasattr(time, "process_time") else time.clock()
    t0 = time.time()
    sess, reg, dev = C.esegui_catena(p, lavoro)
    cpu = (time.process_time() if hasattr(time, "process_time") else time.clock()) - cpu0
    durata = reg.campioni_raw / C.FS
    quota = cpu / durata * 100.0
    ok = quota < 5.0
    registra("E4", "%.2f %% (%.2f s di CPU per %.0f s di segnale; Python %s) — senza il disegno "
             "della finestra, misurato a parte con la finestra in E3" % (
                 quota, cpu, durata, sys.version.split()[0]), ok,
             {"quota_%": quota, "cpu_s": cpu, "segnale_s": durata, "secondi_reali": time.time() - t0,
              "python": sys.version.split()[0]})
    assert ok
