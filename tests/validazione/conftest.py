# -*- coding: utf-8 -*-
"""Raccolta dei risultati della validazione.

Ogni test chiama registra(id, misurato, esito, ...) con esito True (PASS),
False (FAIL) o None (NON VERIFICABILE); i risultati finiscono in
$DLIVE_VALIDAZIONE_USCITA/risultati_$DLIVE_AMBIENTE.json.  Un test che si
interrompe con un'eccezione prima di registrare viene contato come FAIL.
"""
import io
import json
import os
import platform
import re
import sys
import tempfile
import time
import traceback

import pytest

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(os.path.dirname(QUI))
for p in (QUI, RADICE):
    if p not in sys.path:
        sys.path.insert(0, p)

import catalogo  # noqa: E402

USCITA = os.environ.get("DLIVE_VALIDAZIONE_USCITA") or os.path.join(tempfile.gettempdir(),
                                                                    "dlive_validazione")
AMBIENTE = os.environ.get("DLIVE_AMBIENTE", "locale")
LAVORO = os.path.join(USCITA, "lavoro_" + AMBIENTE)
if os.path.isdir(LAVORO) and os.environ.get("DLIVE_VALIDAZIONE_AGGIUNGI") != "1":
    import shutil
    shutil.rmtree(LAVORO, ignore_errors=True)
if not os.path.isdir(LAVORO):
    os.makedirs(LAVORO)

from dlive import registro  # noqa: E402

PERCORSO_LOG = os.path.join(LAVORO, "log", "validazione.log")
if os.path.exists(PERCORSO_LOG):
    os.remove(PERCORSO_LOG)
registro.configura(os.path.dirname(PERCORSO_LOG), "validazione.log", a_schermo=False)

_RISULTATI = {}
_ORDINE = []


def _salva_risultato(id_, voce):
    if id_ not in _RISULTATI:
        _ORDINE.append(id_)
    _RISULTATI[id_] = voce


@pytest.fixture
def registra(request):
    def f(id_, misurato, esito, dettagli=None, nota=""):
        if esito is not None:
            esito = bool(esito)          # anche numpy.bool_
        stato = "PASS" if esito is True else ("FAIL" if esito is False else "NON VERIFICABILE")
        liv, cosa, soglia = catalogo.TEST[id_]
        _salva_risultato(id_, {
            "id": id_, "livello": liv, "cosa": cosa, "soglia": soglia,
            "misurato": misurato, "esito": stato, "nota": nota,
            "dettagli": dettagli or {}, "ambiente": AMBIENTE,
            "durata_s": round(time.time() - request.node._t0, 2),
        })
        request.node._registrato = True
        return esito
    return f


@pytest.fixture
def lavoro(tmp_path):
    return str(tmp_path)


def pytest_runtest_setup(item):
    item._t0 = time.time()
    item._registrato = False


def _id_da_nome(nome):
    m = re.match(r"test_([A-Z]\d+[a-z]?)_", nome)
    return m.group(1) if m else None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    esito = yield
    rep = esito.get_result()
    if rep.when == "call" and rep.failed:
        id_ = _id_da_nome(item.name)
        if id_ and id_ in catalogo.TEST:
            if not getattr(item, "_registrato", False):
                liv, cosa, soglia = catalogo.TEST[id_]
                testo = str(call.excinfo.value) if call.excinfo else "errore"
                _salva_risultato(id_, {
                    "id": id_, "livello": liv, "cosa": cosa, "soglia": soglia,
                    "misurato": "errore durante il test: %s" % testo[:300], "esito": "FAIL",
                    "nota": "".join(traceback.format_exception_only(call.excinfo.type,
                                                                    call.excinfo.value))[-1500:]
                    if call.excinfo else "", "dettagli": {}, "ambiente": AMBIENTE,
                    "durata_s": round(time.time() - item._t0, 2)})


def pytest_sessionfinish(session, exitstatus):
    if not _RISULTATI:
        return
    percorso = os.path.join(USCITA, "risultati_%s.json" % AMBIENTE)
    vecchi = {}
    if os.environ.get("DLIVE_VALIDAZIONE_AGGIUNGI") == "1" and os.path.exists(percorso):
        with io.open(percorso, encoding="utf-8") as f:
            vecchi = json.load(f).get("risultati", {})
    vecchi.update(_RISULTATI)
    try:
        import numpy
        versione_np = numpy.__version__
    except ImportError:
        versione_np = "assente"
    try:
        import scipy
        versione_sp = scipy.__version__
    except ImportError:
        versione_sp = "assente"
    dati = {"ambiente": AMBIENTE, "python": sys.version.split()[0], "numpy": versione_np,
            "scipy": versione_sp, "piattaforma": platform.platform(),
            "risultati": vecchi}
    testo = json.dumps(dati, indent=1, ensure_ascii=False, default=_json_default)
    with io.open(percorso, "w", encoding="utf-8") as f:
        f.write(testo if isinstance(testo, type(u"")) else testo.decode("utf-8"))


def _json_default(o):
    try:
        import numpy as np
        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
    except ImportError:
        pass
    return str(o)
