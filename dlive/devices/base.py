# -*- coding: utf-8 -*-
"""Interfaccia astratta dei dispositivi di acquisizione."""


class ErroreDispositivo(Exception):
    """Errore con messaggio chiaro, in italiano, da mostrare all'utente."""

    def __init__(self, messaggio, dettagli=""):
        Exception.__init__(self, messaggio)
        self.messaggio = messaggio
        self.dettagli = dettagli


class Blocco(object):
    """Blocco di campioni consecutivi di UN canale (conteggi ADC int16).

    dati:   array('h'), lista di int o array numpy int16
    indice: indice (dall'avvio) del primo campione del blocco
    persi:  campioni persi (overrun) subito prima di questo blocco
    """
    __slots__ = ("dati", "indice", "persi", "fine_sorgente")

    def __init__(self, dati, indice, persi=0, fine_sorgente=False):
        self.dati = dati
        self.indice = indice
        self.persi = persi
        self.fine_sorgente = fine_sorgente


class Dispositivo(object):
    """Contratto comune a SimulatedDevice e Digidata1322Device.

    Ciclo di vita: apri() -> avvia() -> leggi()... -> ferma() -> chiudi().
    leggi() blocca al massimo 'timeout' secondi e restituisce un Blocco o None.
    """
    modalita = "astratta"
    fs = 0.0                  # frequenza di campionamento (Hz)
    unita = "mV"

    def apri(self):
        raise NotImplementedError

    def avvia(self):
        raise NotImplementedError

    def leggi(self, timeout=0.2):
        raise NotImplementedError

    def ferma(self):
        raise NotImplementedError

    def chiudi(self):
        pass

    def descrizione(self):
        return self.modalita

    def info(self):
        """Dizionario per i metadati."""
        return {"modalita": self.modalita, "fs_hz": self.fs}

    def calibrazione(self):
        """Calibrazione del canale, come nell'intestazione WCP:
        dict(yg=V per unita', yz=zero in conteggi, unita, nome, ad=range V,
        adcmax).  valore = (conteggi - yz) * ad / (adcmax * yg)."""
        raise NotImplementedError
