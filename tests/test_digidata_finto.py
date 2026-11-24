# -*- coding: utf-8 -*-
"""Digidata1322Device contro la DLL finta: protocollo, lettura continua,
overrun, ricerca della DLL, strutture ctypes."""
import ctypes
import os
import time

import pytest

from dlive.devices import axdd132x as ax
from dlive.devices import digidata as dd
from dlive.devices.dd132x_finto import LibreriaFinta


def _dev(**kw):
    lib = kw.pop("lib", None) or LibreriaFinta()
    d = dd.Digidata1322Device(canale=kw.pop("canale", 2), fs=kw.pop("fs", 1000.0),
                              controlla_processi=False, **kw)
    d.lib = lib
    return d


def test_strutture():
    assert ax.controlla_strutture() == []
    assert ctypes.sizeof(ax.DD132X_Info) == 384
    assert ctypes.sizeof(ax.DD132X_CalibrationData) == 256
    if ctypes.sizeof(ctypes.c_void_p) == 4:
        assert ctypes.sizeof(ax.DD132X_Protocol) == 832
        assert ctypes.sizeof(ax.DATABUFFER) == 24
    # campi nella stessa posizione di dd1320.pas (Delphi)
    assert ax.DD132X_Protocol.dSampleInterval.offset == 4
    assert ax.DD132X_Protocol.anAIChannels.offset == 28
    assert ax.DD132X_CalibrationData.anDACOffset.offset == 72


@pytest.mark.parametrize("uscite", ["come_winwcp", "nessuna"])
def test_protocollo_come_winwcp(uscite, percorso):
    d = _dev(uscite=uscite, campioni_buffer=50000)
    d.apri()
    d.avvia()
    try:
        p = d._proto
        assert p.uLength == ctypes.sizeof(ax.DD132X_Protocol)
        assert p.dSampleInterval == 1000.0
        assert p.eAIDataBits == ax.DD132X_Bit0Tag
        assert p.uAIChannels == 1 and p.anAIChannels[0] == 2
        sub = p.pAIBuffers.contents.uNumSamples
        if uscite == "come_winwcp":
            assert p.uAOChannels == 3
            assert [p.anAOChannels[i] for i in range(3)] == [0, 1, ax.DD132X_PROTOCOL_DIGITALOUTPUT]
            assert sub == 1800
            # valori di riposo: -offset di calibrazione dei DAC, digitali a 0
            assert [d._ao[i] for i in range(6)] == [-3, 2, 0, -3, 2, 0]
        else:
            assert p.uAOChannels == 0 and sub == 600
        assert d.lib.errori_protocollo == []
    finally:
        d.chiudi()


def test_lettura_continua_senza_buchi(percorso):
    d = _dev(campioni_buffer=20000, intervallo_lettura=0.03)
    d.apri()
    d.avvia()
    blocchi = []
    t0 = time.time()
    while time.time() - t0 < 1.5:
        b = d.leggi(0.2)
        if b is not None:
            blocchi.append(b)
    d.chiudi()
    assert blocchi
    for a, b in zip(blocchi, blocchi[1:]):
        assert a.indice + len(a.dati) == b.indice
    n = sum(len(b.dati) for b in blocchi)
    assert 1300 < n < 1700
    assert all(b.persi == 0 for b in blocchi)
    valori = [v for b in blocchi for v in b.dati]
    assert ax.EMPTY_FLAG not in valori
    mv = [v * 10.0 / 32677 / 0.001 for v in valori]
    assert 0 < sum(mv) / len(mv) < 60          # segnale finto 30 +/- 20 mV


def test_overrun_rilevato(percorso):
    d = _dev(fs=5000.0, campioni_buffer=6000)
    d.apri()
    d.avvia()
    time.sleep(0.2)
    d.leggi(0.1)
    time.sleep(2.0)                     # il PC "si blocca": la scheda riscrive il buffer
    b = d.leggi(0.1)
    d.chiudi()
    assert b.persi > 5000 and d.overrun == 1


def test_contatore_incoerente_disattivato():
    d = _dev(lib=LibreriaFinta(posizione_scala=3.0), campioni_buffer=4000)
    d.apri()
    d.avvia()
    t0 = time.time()
    persi = 0
    while time.time() - t0 < 2.0:
        b = d.leggi(0.2)
        if b is not None:
            persi += b.persi
    d.chiudi()
    assert persi == 0 and not d._posizione_affidabile


def test_scheda_non_trovata():
    d = _dev(lib=LibreriaFinta(trovato=False))
    with pytest.raises(dd.ErroreDispositivo) as e:
        d.apri()
    assert "Nessun Digidata trovato" in e.value.messaggio


def test_scheda_occupata():
    d = _dev(lib=LibreriaFinta(apribile=False))
    with pytest.raises(dd.ErroreDispositivo) as e:
        d.apri()
    assert "WinWCP" in e.value.messaggio


def test_ricerca_dll(tmp_path):
    prog = tmp_path / "prog"
    (prog / "dll" / "pclamp10_3_2_1").mkdir(parents=True)
    (prog / "dll" / "pclamp10_3_2_1" / "AxDD132x.dll").write_bytes(b"MZ")
    conf = tmp_path / "altrove" / "AxDD132x.dll"
    conf.parent.mkdir()
    conf.write_bytes(b"MZ")
    cand = dd.percorsi_candidati_dll(str(conf), str(prog))
    assert cand[0] == str(conf)
    # le vecchie copie della chiavetta (dll\...) non si usano piu': la DLL e' quella di WinWCP
    assert not [c for c in cand if "pclamp10_3_2_1" in c]
    # una cartella al posto del file
    cand = dd.percorsi_candidati_dll(str(conf.parent), str(prog))
    assert cand[0] == str(conf)


def test_non_windows_messaggio_chiaro():
    from dlive import compat
    if compat.SU_WINDOWS:
        pytest.skip("solo fuori da Windows")
    d = dd.Digidata1322Device(controlla_processi=False)
    with pytest.raises(dd.ErroreDispositivo) as e:
        d.carica_dll()
    assert "simulazione" in e.value.messaggio


def test_frequenza_nota_dopo_apri_e_sessione_avviabile(tmp_path):
    """Regressione (validazione D2): la Sessione legge dev.fs subito dopo
    apri() per progettare il filtro; prima valeva 0 e l'anteprima falliva."""
    from dlive import filters
    from dlive.acquisizione import Sessione
    d = _dev(campioni_buffer=20000)
    s = Sessione(d, filters.ParametriFiltro(), {"cartella": str(tmp_path), "fs_salvataggio": 125.0,
                                                "durata_record_s": 60.0})
    s.comandi.put(("avvia_reg", None))
    s.avvia_anteprima()
    try:
        assert d.fs == 1000.0
        time.sleep(1.0)
    finally:
        s.ferma()
    assert s.errore_fatale is None
    assert s.ultima_registrazione is not None and s.ultima_registrazione.campioni_raw > 500


class _LibreriaRigorosa(LibreriaFinta):
    """Come un driver vero: rifiuta di aprire una scheda gia' aperta."""

    def __init__(self, **kw):
        self.aperti = 0
        LibreriaFinta.__init__(self, **kw)

    def _DD132X_OpenDevice(self, a, t, perr):
        from dlive.devices.dd132x_finto import _obj
        if self.aperti:
            _obj(perr).value = 9999
            return None
        self.aperti += 1
        return LibreriaFinta._DD132X_OpenDevice(self, a, t, perr)

    def _DD132X_CloseDevice(self, h, perr):
        self.aperti = max(0, self.aperti - 1)
        return LibreriaFinta._DD132X_CloseDevice(self, h, perr)


def test_avvio_fallito_dopo_apertura_richiude_la_scheda(tmp_path, monkeypatch):
    """Regressione (validazione E7): un errore nella Sessione dopo apri()
    lasciava la scheda aperta e ogni nuovo avvio falliva."""
    from dlive import filters
    from dlive.acquisizione import Sessione
    lib = _LibreriaRigorosa()
    d = _dev(lib=lib, campioni_buffer=20000)
    originale = filters.Elaboratore

    def guasto(*a, **k):
        raise RuntimeError("errore simulato")
    monkeypatch.setattr(filters, "Elaboratore", guasto)
    s = Sessione(d, filters.ParametriFiltro(), {"cartella": str(tmp_path)})
    with pytest.raises(RuntimeError):
        s.avvia_anteprima()
    assert lib.aperti == 0 and not s.in_corso
    monkeypatch.setattr(filters, "Elaboratore", originale)
    s2 = Sessione(d, filters.ParametriFiltro(), {"cartella": str(tmp_path)})
    s2.avvia_anteprima()
    try:
        time.sleep(0.5)
        assert s2.errore_fatale is None and s2.campioni > 0
    finally:
        s2.ferma()
    assert lib.aperti == 0


def test_riapertura_e_stato_azzerato():
    lib = _LibreriaRigorosa()
    d = _dev(lib=lib, campioni_buffer=20000)
    d.apri()
    d.apri()                         # seconda apertura senza chiudere: non deve fallire
    assert lib.aperti == 1
    d.overrun = 3
    d._posizione_affidabile = False
    d.avvia()
    try:
        assert d.overrun == 0 and d._posizione_affidabile
    finally:
        d.chiudi()
    assert lib.aperti == 0
