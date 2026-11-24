# -*- coding: utf-8 -*-
"""Compatibilita' con Python 3.4: vermin --target=3.4- su tutto il codice di runtime."""
import os
import sys

import pytest

from conftest import RADICE, esegui

RUNTIME = ["main.py", "diagnostica_digidata.py", "dlive"]


def test_vermin_34():
    import shutil
    exe = shutil.which("vermin") or os.path.join(os.path.dirname(sys.executable), "vermin")
    if not os.path.exists(exe):
        pytest.skip("vermin non installato")
    cmd = [exe, "--target=3.4-", "--violations", "--no-tips",
           "--eval-annotations", "--backport", "argparse", "--backport", "enum"] + RUNTIME
    codice, out = esegui(cmd, cwd=RADICE)
    print(out)
    assert codice == 0, out


def test_nessuna_fstring_ne_api_numpy_rimosse():
    proibiti = ["np.float(", "np.int(", "np.bool(", "np.object(", "np.complex("]
    for radice, _, files in os.walk(os.path.join(RADICE, "dlive")):
        for f in files:
            if f.endswith(".py"):
                testo = open(os.path.join(radice, f), encoding="utf-8").read()
                for p in proibiti:
                    assert p not in testo, (f, p)
