# -*- coding: utf-8 -*-
import os
import sys

import pytest

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RADICE not in sys.path:
    sys.path.insert(0, RADICE)

DATI = os.path.join(RADICE, "riferimenti", "dati")
# I dati del laboratorio (riferimenti/: .wcp, sorgenti e header Axon) non sono
# pubblicati: i test che li usano si saltano con questo messaggio, mai FAIL.
SENZA_DATI = "non eseguibile senza i dati del laboratorio"
FILE_PROVA = sorted(f for f in os.listdir(DATI) if f.endswith(".wcp")) if os.path.isdir(DATI) else []

from dlive import compat  # noqa: E402
from dlive import registro  # noqa: E402

registro.configura(os.path.join(RADICE, "log"), "test.log", a_schermo=False)


def esegui(cmd, timeout=120, cwd=None):
    """Come subprocess.run (che non esiste in Python 3.4): (codice, uscita)."""
    import subprocess
    pr = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True, cwd=cwd)
    try:
        out, _ = pr.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        pr.kill()
        out, _ = pr.communicate()
        return -1, out
    return pr.returncode, out


def richiede_dati():
    return pytest.mark.skipif(len(FILE_PROVA) < 7, reason=SENZA_DATI)


@pytest.fixture(params=["numpy", "puro"])
def percorso(request, monkeypatch):
    """Esegue il test con numpy e con il percorso in Python puro."""
    if request.param == "numpy":
        if compat.np is None:
            pytest.skip("numpy non disponibile")
    else:
        monkeypatch.setattr(compat, "np", None)
    return request.param


@pytest.fixture
def cartella(tmp_path):
    return str(tmp_path)


def display_virtuale():
    """True solo sotto un display virtuale dichiarato (xvfb-run con
    DLIVE_DISPLAY_VIRTUALE=1, come in valida.sh e nel Docker del README) o su
    Windows: i test non devono mai aprire finestre sullo schermo di chi li
    lancia, anche se DISPLAY e' impostato."""
    import sys as _sys
    if _sys.platform.startswith("win"):
        return True
    return os.environ.get("DLIVE_DISPLAY_VIRTUALE") == "1" and bool(os.environ.get("DISPLAY"))


richiede_display_virtuale = pytest.mark.skipif(
    not display_virtuale(), reason="serve un display virtuale: xvfb-run con DLIVE_DISPLAY_VIRTUALE=1 "
                                   "(i test non aprono finestre sullo schermo)")

