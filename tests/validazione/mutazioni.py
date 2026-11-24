# -*- coding: utf-8 -*-
"""Prova dei test: introduce un guasto alla volta in una COPIA TEMPORANEA del
programma (mai nel repository) e controlla che almeno un test CRITICO fallisca.

  M1  frequenza di taglio raddoppiata
  M2  stato del filtro azzerato a ogni blocco
  M3  notch a 60 Hz invece di 50 Hz
  M4  un campione saltato ogni 1000 nel salvataggio del grezzo

Uso: python mutazioni.py CARTELLA_USCITA
Scrive CARTELLA_USCITA/risultati_mutazioni.json.
"""
from __future__ import print_function

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(os.path.dirname(QUI))
sys.path.insert(0, QUI)
import catalogo  # noqa: E402

MUTAZIONI = [
    ("M1", "frequenza di taglio raddoppiata", "dlive/filters.py",
     "    wc = K * math.tan(math.pi * fc / fs)         # pre-distorsione\n",
     "    wc = K * math.tan(math.pi * (2.0 * fc) / fs)  # MUTAZIONE M1\n"),
    ("M2", "stato del filtro azzerato a ogni blocco", "dlive/filters.py",
     "        buf = blocco\n        for (b0, b1, b2, a1, a2), st in zip(self.sezioni, self.stato):\n",
     "        self.azzera()  # MUTAZIONE M2\n        buf = blocco\n"
     "        for (b0, b1, b2, a1, a2), st in zip(self.sezioni, self.stato):\n"),
    ("M3", "notch a 60 Hz invece di 50 Hz", "dlive/filters.py",
     "                sez.append(progetta_notch(f0, self.q_notch, fs))\n",
     "                sez.append(progetta_notch(60.0 if f0 == 50.0 else f0, self.q_notch, fs))  # MUTAZIONE M3\n"),
    ("M4", "un campione saltato ogni 1000 nel salvataggio", "dlive/recorder.py",
     "    def scrivi_grezzo(self, campioni):\n        self.raw.aggiungi(campioni)\n",
     "    def scrivi_grezzo(self, campioni):\n        self.raw.aggiungi([v for i, v in enumerate(campioni)  # MUTAZIONE M4\n"
     "                           if (self.campioni_raw + i) % 1000 != 999])\n"),
]

# test critici veloci (quelli in tempo reale, B5/B7/B9, non riguardano i guasti)
SELEZIONE = ["tests/validazione/test_A_filtro.py",
             "tests/validazione/test_B_catena.py::test_B1_grezzo_identico",
             "tests/validazione/test_B_catena.py::test_B2_filtrato_come_riferimento",
             "tests/validazione/test_B_catena.py::test_B3_nessun_campione_perso",
             "tests/validazione/test_B_catena.py::test_B4_nessun_aliasing",
             "tests/validazione/test_B_catena.py::test_B6_file_apribili"]


def copia_programma(dest):
    for nome in ("dlive", "main.py", os.path.join("tests", "validazione")):
        sorg = os.path.join(RADICE, nome)
        d = os.path.join(dest, nome)
        if os.path.isdir(sorg):
            shutil.copytree(sorg, d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(sorg, d)
    rif = os.path.join(dest, "riferimenti")
    os.makedirs(rif)
    for sub in ("dati", "sdk_axon"):
        if os.path.isdir(os.path.join(RADICE, "riferimenti", sub)):
            os.symlink(os.path.join(RADICE, "riferimenti", sub), os.path.join(rif, sub))


def avvia(mut, uscita):
    id_, descr, file_rel, prima, dopo = mut
    dest = tempfile.mkdtemp(prefix="dlive_mut_%s_" % id_)
    copia_programma(dest)
    p = os.path.join(dest, file_rel)
    testo = io.open(p, encoding="utf-8").read()
    if testo.count(prima) != 1:
        return None, dest, "testo da mutare trovato %d volte in %s" % (testo.count(prima), file_rel)
    io.open(p, "w", encoding="utf-8").write(testo.replace(prima, dopo))
    env = dict(os.environ)
    env.update({"DLIVE_AMBIENTE": "mut_" + id_, "DLIVE_VALIDAZIONE_USCITA": uscita,
                "PYTHONDONTWRITEBYTECODE": "1"})
    log = open(os.path.join(uscita, "mutazione_%s.log" % id_), "w")
    pr = subprocess.Popen([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                           "--confcutdir=tests/validazione"] + SELEZIONE,
                          cwd=dest, env=env, stdout=log, stderr=subprocess.STDOUT)
    return pr, dest, ""


def main():
    uscita = os.path.abspath(sys.argv[1])
    t0 = time.time()
    processi = []
    for m in MUTAZIONI:
        pr, dest, err = avvia(m, uscita)
        processi.append((m, pr, dest, err))
    risultati = {}
    for (id_, descr, file_rel, prima, dopo), pr, dest, err in processi:
        if pr is not None:
            pr.wait()
        voce = {"id": id_, "guasto": descr, "file": file_rel, "test_critici_falliti": [],
                "test_falliti": []}
        if err:
            voce["errore"] = err
        else:
            p = os.path.join(uscita, "risultati_mut_%s.json" % id_)
            try:
                ris = json.load(io.open(p, encoding="utf-8"))["risultati"]
            except (IOError, OSError, ValueError) as e:
                ris = {}
                voce["errore"] = "risultati non letti: %s" % e
            for k, v in sorted(ris.items()):
                if v["esito"] == "FAIL":
                    voce["test_falliti"].append(k)
                    if catalogo.critico(k):
                        voce["test_critici_falliti"].append("%s (%s)" % (k, v["misurato"][:140]))
        voce["rilevato"] = bool(voce["test_critici_falliti"])
        risultati[id_] = voce
        shutil.rmtree(dest, ignore_errors=True)
    with io.open(os.path.join(uscita, "risultati_mutazioni.json"), "w", encoding="utf-8") as f:
        t = json.dumps({"durata_s": time.time() - t0, "mutazioni": risultati}, indent=1,
                       ensure_ascii=False)
        f.write(t if isinstance(t, type(u"")) else t.decode("utf-8"))
    for k, v in risultati.items():
        print(k, "rilevato" if v["rilevato"] else "NON RILEVATO", v["test_falliti"], v.get("errore", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
