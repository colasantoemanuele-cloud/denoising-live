# -*- coding: utf-8 -*-
"""Lettore e scrittore .wcp: file di prova, andata e ritorno, intestazione,
file troncati, resistenza ai crash, limiti dei record."""
import array
import datetime
import os
import struct

import pytest

from conftest import DATI, FILE_PROVA, SENZA_DATI, richiede_dati
from dlive import compat
from dlive import wcpfile

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None
try:
    import neo
except ImportError:
    neo = None


# Lettore di riferimento del documento di progetto (sezione 8), verificato con neo
def _num(s):
    return float(s.replace(",", "."))


def read_wcp_riferimento(path):
    with open(path, "rb") as f:
        raw = f.read()
    txt = raw[:1024].decode("latin-1").split("\x00")[0]
    hdr = {}
    for line in txt.replace("\r", "\n").split("\n"):
        if "=" in line:
            k, v = line.split("=", 1)
            hdr[k.strip()] = v.strip()
    nc, nr = int(hdr["NC"]), int(hdr["NR"])
    nbh, nba, nbd = int(hdr["NBH"]), int(hdr["NBA"]), int(hdr["NBD"])
    adcmax = _num(hdr["ADCMAX"])
    recs = []
    for r in range(nr):
        off = nbh + r * (nba + nbd) * 512
        ab = raw[off:off + nba * 512]
        status = ab[0:8].decode("latin-1")
        rtype = ab[8:12].decode("latin-1")
        group, t, dt = struct.unpack("<fff", ab[12:24])
        vmax = struct.unpack("<" + "f" * nc, ab[24:24 + 4 * nc])
        d = np.frombuffer(raw[off + nba * 512: off + (nba + nbd) * 512], dtype="<i2")
        n = len(d) // nc
        d = d[: n * nc].reshape(n, nc)
        chans = []
        for c in range(nc):
            yo = int(hdr["YO%d" % c])
            yg = _num(hdr["YG%d" % c])
            yz = _num(hdr["YZ%d" % c])
            chans.append((d[:, yo].astype(float) - yz) * vmax[c] / adcmax / yg)
        recs.append(dict(status=status, type=rtype, group=group, time=t, dt=dt,
                         vmax=vmax, data=np.array(chans), adc=d))
    return hdr, recs


@richiede_dati()
@pytest.mark.parametrize("nome", FILE_PROVA)
def test_lettura_file_di_prova(nome, percorso):
    p = os.path.join(DATI, nome)
    w = wcpfile.leggi_wcp(p)
    assert w.nc in (1, 5)
    assert w.nr >= 1
    assert os.path.getsize(p) == 1024 + (w.nr + w.extra) * (2 + w.nbd) * 512
    for r in w.records:
        assert r.stato == "ACCEPTED" and r.tipo == "TEST"
        assert r.n_campioni == w.campioni_per_record
        assert len(r.dati) == w.nc
    if np is not None:
        hdr, recs = read_wcp_riferimento(p)
        if int(hdr["NR"]) == 0:
            assert w.avvisi and "ricalcolato" in w.avvisi[0]
            return
        for mio, rif in zip(w.records, recs):
            for c in range(w.nc):
                assert np.allclose(np.asarray(mio.dati[c]), rif["data"][c])
                assert list(mio.adc[c]) == list(rif["adc"][:, int(hdr["YO%d" % c])])


@pytest.mark.skipif(neo is None or np is None, reason="neo non installato")
@richiede_dati()
@pytest.mark.parametrize("nome", [f for f in FILE_PROVA if "071224" not in f])
def test_lettura_come_neo(nome):
    p = os.path.join(DATI, nome)
    w = wcpfile.leggi_wcp(p)
    bl = neo.io.WinWcpIO(p).read_block()
    assert len(bl.segments) == w.nr
    for seg, rec in zip(bl.segments, w.records):
        colonne = np.concatenate([np.asarray(sig) for sig in seg.analogsignals], axis=1)
        assert colonne.shape[1] == w.nc
        for c in range(w.nc):
            # neo (0.14) non sottrae lo zero YZ: lo si rimette per il confronto
            yz = w.canale(c)["yz"]
            scala = rec.vmax[c] / w.adcmax / w.canale(c)["yg"]
            assert np.allclose(colonne[:, c], np.asarray(rec.dati[c]) + yz * scala, atol=2e-3)


def _scrivi(percorso, n_campioni, dati, dt=0.001, **kw):
    w = wcpfile.ScrittoreWCP(percorso, dt, n_campioni,
                             [{"nome": "AI2", "unita": "mV", "yg": 0.001, "yz": 0}],
                             ora_creazione=datetime.datetime(2007, 12, 10, 0, 39, 53), **kw)
    w.aggiungi(dati)
    return w


def test_andata_e_ritorno(cartella, percorso):
    p = os.path.join(cartella, "prova_raw.wcp")
    dati = [(i * 37) % 6000 - 3000 for i in range(1000 * 3 + 123)]
    w = _scrivi(p, 1024, dati)
    w.chiudi()
    r = wcpfile.leggi_wcp(p)
    assert r.nr == 4 and not r.avvisi
    letti = []
    for rec in r.records:
        letti.extend(list(rec.adc[0]))
    assert letti[:len(dati)] == dati
    assert letti[len(dati):] == [dati[-1]] * (4 * 1024 - len(dati))   # coda come WinWCP
    assert [rec.tempo for rec in r.records] == pytest.approx([0.0, 1.024, 2.048, 3.072], abs=1e-6)
    assert abs(r.records[0].dati[0][1] - dati[1] * 10.0 / 32677 / 0.001) < 1e-9
    assert os.path.getsize(p) == 1024 + 4 * (2 + 4) * 512


@pytest.mark.skipif(neo is None, reason="neo non installato")
def test_andata_e_ritorno_con_neo(cartella):
    p = os.path.join(cartella, "neo_raw.wcp")
    dati = [int(1000 * ((i % 500) / 500.0 - 0.5)) for i in range(5000)]
    w = _scrivi(p, 2048, dati)
    w.chiudi()
    bl = neo.io.WinWcpIO(p).read_block()
    assert len(bl.segments) == 3
    sig = bl.segments[0].analogsignals[0]
    assert abs(float(sig.sampling_rate) - 1000.0) < 0.01
    assert str(sig.units.dimensionality) == "mV"
    v = np.asarray(sig).ravel()
    assert np.allclose(v, np.array(dati[:2048]) * 10.0 / 32677 / 0.001, atol=1e-3)


@richiede_dati()
def test_intestazione_come_file_di_prova(cartella):
    p = os.path.join(cartella, "h.wcp")
    w = _scrivi(p, 256, [0] * 10, dt=0.008)
    w.chiudi()
    mio = wcpfile.leggi_wcp(p, solo_intestazione=True)
    rif = wcpfile.leggi_wcp(os.path.join(DATI, "071210_001.wcp"), solo_intestazione=True)
    chiavi_rif = [k for k in rif.ordine_chiavi]
    assert mio.ordine_chiavi == chiavi_rif
    for k in ("VER", "VERPROG", "NBH", "ADCMAX", "NC", "NBA", "AD", "NZ", "YU0", "YG0", "YZ0", "YR0",
              "TXPERC", "PKPAVG", "NSVCHAN", "NSVALIGN", "NSVTYPR", "NSVS2P", "NSVCUR0", "NSVCUR1"):
        assert mio.hdr[k] == rif.hdr[k], k
    assert mio.hdr["DT"] == "0,008"
    assert mio.hdr["CTIME"] == "10/12/2007 0:39:53"
    with open(p, "rb") as f:
        testa = f.read(1024)
    assert b"\r\n" in testa and testa.split(b"\x00")[0].endswith(b"\r\n")
    assert testa.rstrip(b"\x00") == testa[:len(testa.rstrip(b"\x00"))]
    # blocco di analisi identico come struttura
    with open(os.path.join(DATI, "071210_001.wcp"), "rb") as f:
        f.seek(1024)
        ab_rif = f.read(1024)
    with open(p, "rb") as f:
        f.seek(1024)
        ab = f.read(1024)
    assert ab[:12] == ab_rif[:12] == b"ACCEPTEDTEST"
    assert struct.unpack("<f", ab[24:28]) == struct.unpack("<f", ab_rif[24:28]) == (10.0,)
    vals = struct.unpack("<3f", ab[44:56])
    assert vals == (1.0, 1.0, 0.0)


@richiede_dati()
def test_record_oltre_nr():
    """081024_001.wcp: NR=1 ma il file contiene 2 record (il secondo non e' visibile in WinWCP)."""
    p = os.path.join(DATI, "081024_001.wcp")
    w = wcpfile.leggi_wcp(p)
    assert w.nr == 1 and w.extra == 1 and "oltre NR" in w.avvisi[0]
    w2 = wcpfile.leggi_wcp(p, recupera_extra=True)
    assert w2.nr == 2 and abs(w2.records[1].tempo - 370.5) < 1e-3


def test_numeri_con_la_virgola():
    assert wcpfile.numero_it(0.008795) == "0,008795"
    assert wcpfile.numero_it(0.001) == "0,001"
    assert wcpfile.numero_it(10.0) == "10"
    assert wcpfile.numero_it(0.001, 6) == "0,001"
    assert wcpfile.numero_it_decimali(2443.81) == "2443,81"


def test_file_troncato_leggibile(cartella, percorso):
    p = os.path.join(cartella, "tronco.wcp")
    dati = list(range(-2000, 2000)) * 2
    w = _scrivi(p, 2048, dati)
    w.chiudi()
    dim = os.path.getsize(p)
    with open(p, "rb") as f:
        b = f.read()
    meta = 1024 + 2 * (2 + 8) * 512 + 1024 + 1000     # meta' del terzo record
    with open(p, "wb") as f:
        f.write(b[:meta])
    r = wcpfile.leggi_wcp(p)
    assert r.nr == 3
    assert r.records[2].completo is False
    assert r.records[2].n_campioni == 500
    assert list(r.records[0].adc[0]) == dati[:2048]
    assert any("troncato" in a for a in r.avvisi)
    assert dim > meta


def test_crash_durante_la_registrazione(cartella):
    """Senza chiudere il file (crash): dopo flush() il file e' valido e
    contiene anche il record in corso, completato con l'ultimo valore."""
    p = os.path.join(cartella, "crash.wcp")
    w = _scrivi(p, 1024, list(range(1500)))
    w.flush()
    w.aggiungi([7] * 100)          # non ancora su disco
    # simula il crash: il file non viene chiuso
    r = wcpfile.leggi_wcp(p)
    assert r.nr == 2 and not r.avvisi
    rec2 = list(r.records[1].adc[0])
    assert rec2[:476] == list(range(1024, 1500))
    assert rec2[476:] == [1499] * (1024 - 476)
    w.flush()
    r = wcpfile.leggi_wcp(p)
    assert list(r.records[1].adc[0])[476:576] == [7] * 100
    w.chiudi("parz 0,6s")
    r = wcpfile.leggi_wcp(p)
    assert r.records[1].ident == "parz 0,6s"


class FileRotto(object):
    """Involucro di un file che fallisce in scrittura finche' rotto=True."""

    def __init__(self, f):
        self.f = f
        self.rotto = True

    def write(self, b):
        if self.rotto:
            raise IOError("errore di lettura/scrittura simulato")
        return self.f.write(b)

    def __getattr__(self, nome):
        return getattr(self.f, nome)


def test_errore_di_scrittura_non_ferma(cartella):
    p = os.path.join(cartella, "err.wcp")
    w = _scrivi(p, 256, [1] * 10)
    rotto = FileRotto(w._f)
    w._f = rotto
    w.aggiungi(list(range(600)))          # chiude due record -> errore, nessuna eccezione
    assert not w.flush()
    assert w.n_errori >= 1 and "simulato" in w.ultimo_errore
    assert len(w.in_attesa) == 2          # i dati restano in memoria
    rotto.rotto = False
    assert w.flush()
    assert not w.in_attesa
    w.chiudi()
    r = wcpfile.leggi_wcp(p)
    tutti = []
    for rec in r.records:
        tutti.extend(list(rec.adc[0]))
    assert tutti[:610] == [1] * 10 + list(range(600))


def test_limiti_dei_record():
    """Ogni combinazione ammessa resta ben sotto i 2,24 milioni di campioni
    per record dei file di prova (e sotto il limite prudenziale di 1 milione)."""
    from dlive.config import Configurazione
    for fs in (100.0, 125.0, 250.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0):
        for durata in (1, 10, 30, 60, 120, 300, 600, 1000):
            c = Configurazione()
            c.imposta("digidata.frequenza_acquisizione_hz", fs)
            c.imposta("salvataggio.frequenza_salvataggio_hz", fs / (8 if fs >= 1000 else 1))
            c.imposta("salvataggio.durata_record_s", durata)
            errori, _ = c.controlla()
            n = wcpfile.campioni_per_record(durata, fs)
            if not errori:
                assert n <= wcpfile.MAX_CAMPIONI_RECORD < 2240000
            else:
                assert durata * fs > 1000000
    with pytest.raises(ValueError):
        wcpfile.ScrittoreWCP(os.devnull, 0.001, 1000192, [{"nome": "x"}])


def test_campioni_per_record_multipli_di_settore():
    assert wcpfile.campioni_per_record(60, 125) == 7424
    assert wcpfile.campioni_per_record(60, 1000) == 59904
    for fs in (113.7, 125, 1000, 3000):
        for d in (1, 60, 61.44):
            n = wcpfile.campioni_per_record(d, fs)
            assert (n * 2) % 512 == 0


def test_nome_come_winwcp(cartella):
    d = datetime.date(2026, 11, 18)
    assert wcpfile.nome_base_libero(cartella, d) == "261118_001"
    open(os.path.join(cartella, "261118_001.wcp"), "w").close()      # file di WinWCP
    assert wcpfile.nome_base_libero(cartella, d) == "261118_002"
    open(os.path.join(cartella, "261118_002_raw.wcp"), "w").close()
    assert wcpfile.nome_base_libero(cartella, d) == "261118_003"


def test_interfaccia_riferimento():
    if not FILE_PROVA:
        pytest.skip(SENZA_DATI)
    if np is None:
        pytest.skip("numpy assente")
    hdr, recs = wcpfile.read_wcp(os.path.join(DATI, "071210_001.wcp"))
    assert hdr["NR"] == "4" and len(recs) == 4 and recs[0]["status"] == "ACCEPTED"


def test_separatore_punto(cartella):
    p = os.path.join(cartella, "punto.wcp")
    w = _scrivi(p, 256, [5] * 300, dt=0.008, separatore=".")
    w.chiudi()
    r = wcpfile.leggi_wcp(p)
    assert r.hdr["DT"] == "0.008" and r.hdr["YG0"] == "0.001" and r.hdr["CTIME"] == "10/12/2007 0:39:53"
    assert r.nr == 2 and list(r.records[0].adc[0])[:3] == [5, 5, 5]
