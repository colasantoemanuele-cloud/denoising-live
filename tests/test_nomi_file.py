# -*- coding: utf-8 -*-
"""Il programma non sovrascrive mai una registrazione esistente.

Sul PC del laboratorio l'orologio e' indietro (2007-2008, docs/analisi_sorgenti.md
§ 0) e puo' ripartire sempre dalla stessa data: i nomi AAMMGG_NNN si ripetono.
In tutti i casi nessun file gia' presente nella cartella deve cambiare
(contenuto e data di modifica controllati prima e dopo).

  1. due registrazioni di seguito nello stesso programma -> numero successivo;
  2. registrazione, chiusura del programma, riapertura (processo nuovo), stessa
     data -> il numero viene dai file su disco;
  3. orologio tornato indietro: nella cartella ci sono file con date piu' recenti;
  4. di una registrazione precedente resta un solo file (crash): quel numero non
     si riusa;
  5. file di WinWCP con lo stesso prefisso di data (071210_001.wcp): non toccati;
  6. anche se il calcolo del numero sbagliasse, un file esistente non si apre in
     scrittura: messaggio chiaro, l'acquisizione continua.
Tutto in simulazione, senza finestre.
"""
import datetime
import hashlib
import os
import shutil
import sys
import time

import pytest

from conftest import DATI, RADICE, esegui, richiede_dati
from dlive import filters, recorder, wcpfile
from dlive.acquisizione import Sessione
from dlive.devices.simulated import SimulatedDevice

PAR = filters.ParametriFiltro("bessel", 4, 5.0, [50.0])
SORGENTE = os.path.join(DATI, "071224_003.wcp")        # 16 s di segnale: veloce
DATA_PC = datetime.datetime(2007, 12, 10, 0, 39, 53)   # come i file di prova
VECCHIA = 1197243593                                    # 10/12/2007: mtime dei file "vecchi"


def _impronta(cartella):
    """{nome: (md5, dimensione, mtime_ns)} di tutti i file della cartella."""
    out = {}
    for nome in sorted(os.listdir(cartella)):
        p = os.path.join(cartella, nome)
        if os.path.isfile(p):
            with open(p, "rb") as f:
                h = hashlib.md5(f.read()).hexdigest()
            st = os.stat(p)
            out[nome] = (h, st.st_size, st.st_mtime_ns)
    return out


def _invariati(prima, dopo):
    """Tutti i file di 'prima' esistono ancora identici in 'dopo'."""
    cambiati = [n for n in prima if dopo.get(n) != prima[n]]
    assert not cambiati, "file gia' esistenti modificati o cancellati: %s" % cambiati


def _vecchio(p, contenuto=b"dati precedenti"):
    with open(p, "wb") as f:
        f.write(contenuto)
    os.utime(p, (VECCHIA, VECCHIA))


def _registra(cartella, s_out=None):
    """Una registrazione completa della sorgente (veloce, non in tempo reale).
    Restituisce la Sessione finita."""
    dev = SimulatedDevice(SORGENTE, record=1, tempo_reale=False, ciclo=False, blocco_s=0.05)
    dev.apri()
    s = Sessione(dev, PAR, {"cartella": cartella, "fs_salvataggio": 125.0, "durata_record_s": 60.0})
    s.comandi.put(("avvia_reg", None))
    s.avvia_anteprima()
    t0 = time.time()
    while s.in_corso and time.time() - t0 < 120:
        time.sleep(0.05)
    assert not s.in_corso
    return s


def _messaggi(s):
    out = []
    while not s.messaggi.empty():
        out.append(s.messaggi.get_nowait())
    return out


@pytest.fixture
def data_pc(monkeypatch):
    monkeypatch.setattr(recorder, "_ora", lambda: DATA_PC)


# ------------------------------------------------------------------ 1
@richiede_dati()
def test_1_due_registrazioni_nello_stesso_programma(tmp_path, data_pc):
    c = str(tmp_path)
    s1 = _registra(c)
    assert s1.ultima_registrazione.nome_base == "071210_001"
    prima = _impronta(c)
    s2 = _registra(c)
    assert s2.ultima_registrazione.nome_base == "071210_002"
    _invariati(prima, _impronta(c))
    assert sorted(os.listdir(c)) == ["071210_001.json", "071210_001_filt.wcp", "071210_001_raw.wcp",
                                     "071210_002.json", "071210_002_filt.wcp", "071210_002_raw.wcp"]


# ------------------------------------------------------------------ 2
FIGLIO = r'''
import datetime, sys, time
sys.path.insert(0, %(radice)r)
sys.path.insert(0, %(tests)r)
from dlive import recorder
recorder._ora = lambda: datetime.datetime(2007, 12, 10, 0, 39, 53)
import test_nomi_file as t
s = t._registra(%(cartella)r)
print("NOME=" + s.ultima_registrazione.nome_base)
'''


def _registra_in_un_processo_nuovo(cartella):
    codice = FIGLIO % {"radice": RADICE, "tests": os.path.join(RADICE, "tests"), "cartella": cartella}
    rc, out = esegui([sys.executable, "-c", codice], timeout=180, cwd=RADICE)
    assert rc == 0, out
    return [r for r in out.splitlines() if r.startswith("NOME=")][-1][5:]


@richiede_dati()
def test_2_riapertura_del_programma_stessa_data(tmp_path):
    c = str(tmp_path)
    assert _registra_in_un_processo_nuovo(c) == "071210_001"
    for nome in os.listdir(c):
        os.utime(os.path.join(c, nome), (VECCHIA, VECCHIA))
    prima = _impronta(c)
    assert _registra_in_un_processo_nuovo(c) == "071210_002"
    _invariati(prima, _impronta(c))


# ------------------------------------------------------------------ 3
@richiede_dati()
def test_3_orologio_tornato_indietro(tmp_path, data_pc):
    c = str(tmp_path)
    # registrazioni fatte quando l'orologio segnava date piu' recenti (2026, 2008)
    for base in ("261122_001", "261122_002", "081024_001"):
        for suf in ("_raw.wcp", "_filt.wcp", ".json"):
            _vecchio(os.path.join(c, base + suf))
    # e una del giorno che il PC segna adesso
    for suf in ("_raw.wcp", "_filt.wcp", ".json"):
        _vecchio(os.path.join(c, "071210_001" + suf))
    prima = _impronta(c)
    s = _registra(c)
    assert s.ultima_registrazione.nome_base == "071210_002"
    _invariati(prima, _impronta(c))


# ------------------------------------------------------------------ 4
@richiede_dati()
@pytest.mark.parametrize("resto", ["_raw.wcp", "_filt.wcp", ".json"])
def test_4_resta_un_solo_file_dopo_un_crash(tmp_path, data_pc, resto):
    c = str(tmp_path)
    _vecchio(os.path.join(c, "071210_001" + resto))
    prima = _impronta(c)
    s = _registra(c)
    assert s.ultima_registrazione.nome_base == "071210_002"
    _invariati(prima, _impronta(c))
    assert not any(n.startswith("071210_001") and n != "071210_001" + resto for n in os.listdir(c))


# ------------------------------------------------------------------ 5
@richiede_dati()
def test_5_file_di_winwcp_con_lo_stesso_prefisso(tmp_path, data_pc):
    c = str(tmp_path)
    # file veri di WinWCP 5.1.6 con lo stesso prefisso di data, piu' i suoi file derivati
    shutil.copy(os.path.join(DATI, "071210_001.wcp"), c)
    shutil.copy(os.path.join(DATI, "071210_001.1.wcp"), c)
    for extra in ("071210_001.avg", "071210_001.sub", "071210_003.wcp"):
        _vecchio(os.path.join(c, extra))
    for nome in os.listdir(c):
        os.utime(os.path.join(c, nome), (VECCHIA, VECCHIA))
    prima = _impronta(c)
    s1 = _registra(c)
    s2 = _registra(c)
    s3 = _registra(c)
    assert [s.ultima_registrazione.nome_base for s in (s1, s2, s3)] == \
        ["071210_002", "071210_004", "071210_005"]
    _invariati(prima, _impronta(c))


# ------------------------------------------------------------------ 6
@richiede_dati()
@pytest.mark.parametrize("esistenti", [("_raw.wcp", "_filt.wcp", ".json"), ("_raw.wcp",), ("_filt.wcp",),
                                       (".json",)])
def test_6_file_esistente_mai_aperto_in_scrittura(tmp_path, data_pc, monkeypatch, esistenti):
    c = str(tmp_path)
    for suf in esistenti:
        _vecchio(os.path.join(c, "071210_001" + suf))
    prima = _impronta(c)
    # calcolo del numero sbagliato di proposito: propone un nome gia' usato
    monkeypatch.setattr(wcpfile, "nome_base_libero", lambda cartella, data=None, **kw: "071210_001")
    s = _registra(c)
    # nessun file esistente toccato, nessuna registrazione iniziata con quel nome
    _invariati(prima, _impronta(c))
    assert s.ultima_registrazione is None
    assert sorted(os.listdir(c)) == sorted(prima)
    # messaggio chiaro
    err = [t for liv, t in _messaggi(s) if liv == "errore"]
    assert err and "esiste gia'" in err[0] and "071210_001" in err[0] and "acquisizione continua" in err[0]
    # l'acquisizione e' andata avanti fino alla fine della sorgente senza perdere nulla
    dev = SimulatedDevice(SORGENTE, record=1, tempo_reale=False, ciclo=False)
    dev.apri()
    assert s.campioni == len(dev.sorgente) and s.persi_tot == 0


def test_6_scrittore_rifiuta_un_file_esistente(tmp_path):
    p = str(tmp_path / "a_raw.wcp")
    _vecchio(p)
    prima = _impronta(str(tmp_path))
    with pytest.raises(wcpfile.ErroreScrittura) as e:
        wcpfile.ScrittoreWCP(p, 0.001, 256, [{"nome": "AI2"}])
    assert "esiste gia'" in str(e.value)
    _invariati(prima, _impronta(str(tmp_path)))
