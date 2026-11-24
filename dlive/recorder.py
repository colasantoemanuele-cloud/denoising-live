# -*- coding: utf-8 -*-
"""Registrazione su disco: file grezzo + file filtrato (.wcp) + metadati JSON."""
import datetime
import io
import json
import os

from . import compat
from . import lpf8
from . import sysinfo
from . import wcpfile

VERSIONE_PROGRAMMA = "1.0"
NOME_PROGRAMMA = "denoising_live"


def _ora():
    return datetime.datetime.now()


def _iso(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S.") + "%03d" % (dt.microsecond // 1000)


def scrivi_json_atomico(percorso, dati):
    tmp = percorso + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        testo = json.dumps(dati, indent=1, ensure_ascii=False, sort_keys=False)
        if not isinstance(testo, type(u"")):  # pragma: no cover
            testo = testo.decode("utf-8")
        f.write(testo)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass
    os.replace(tmp, percorso)


class Registrazione(object):
    """Una registrazione: due file .wcp con lo stesso nome base AAMMGG_NNN
    (_raw e _filt) e un file JSON con i metadati.

    I record grezzi e filtrati coprono esattamente lo stesso intervallo di
    tempo (stesso numero di record, stessa durata): il record N del grezzo
    corrisponde al record N del filtrato.
    """

    def __init__(self, cartella, calibrazione, fs_acq, decimazione, par_filtro,
                 durata_record_s, info_dispositivo, lpf8_taglio, lpf8_guadagno=1.0,
                 campione_inizio=0, nome_base=None, percorso_numpy="", ident_extra="",
                 separatore=","):
        if not os.path.isdir(cartella):
            os.makedirs(cartella)
        self.cartella = cartella
        self.ora_inizio = _ora()
        self.nome_base = nome_base or wcpfile.nome_base_libero(cartella, self.ora_inizio.date())
        self.fs_acq = float(fs_acq)
        self.dec = int(decimazione)
        self.fs_filt = self.fs_acq / self.dec
        self.campione_inizio = int(campione_inizio)
        self.cal = dict(calibrazione)
        n_filt = wcpfile.campioni_per_record(durata_record_s, self.fs_filt, 1)
        n_raw = n_filt * self.dec
        while n_raw > wcpfile.MAX_CAMPIONI_RECORD and n_filt > 256:
            n_filt -= 256
            n_raw = n_filt * self.dec
        self.n_raw = n_raw
        self.n_filt = n_filt
        self.durata_record_effettiva = n_filt / self.fs_filt
        base = os.path.join(cartella, self.nome_base)
        self.percorso_raw = base + "_raw.wcp"
        self.percorso_filt = base + "_filt.wcp"
        self.percorso_json = base + ".json"
        nome = self.cal.get("nome", "AI")
        canale_raw = {"nome": nome[:8], "unita": self.cal.get("unita", "mV"),
                      "yg": self.cal.get("yg", 0.001), "yz": self.cal.get("yz", 0), "yr": -1}
        canale_filt = dict(canale_raw)
        canale_filt["nome"] = (nome[:6] + "_f")
        ident = "%s %s %s LPF-8 %s %s" % (NOME_PROGRAMMA, VERSIONE_PROGRAMMA, "%s",
                                       lpf8.descrizione(lpf8_taglio), ident_extra)
        comuni = dict(ad=self.cal.get("ad", 10.0), adcmax=self.cal.get("adcmax", 32677),
                      ora_creazione=self.ora_inizio, ora_inizio=self.ora_inizio,
                      rtimesecs=sysinfo.secondi_dall_avvio(),
                      separatore=separatore)
        # Nessun file esistente si apre in scrittura (neanche se il nome fosse
        # sbagliato): prima si controllano tutti e tre, poi si creano in modo
        # esclusivo; se uno fallisce si tolgono solo i file appena creati qui.
        esistenti = [p for p in (self.percorso_raw, self.percorso_filt, self.percorso_json)
                     if os.path.exists(p)]
        if esistenti:
            raise wcpfile.ErroreScrittura("il file %s esiste gia': non viene sovrascritto"
                                          % ", ".join(esistenti))
        creati = []
        try:
            fd = os.open(self.percorso_json, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            creati.append(self.percorso_json)
            self.raw = wcpfile.ScrittoreWCP(self.percorso_raw, 1.0 / self.fs_acq, n_raw, [canale_raw],
                                            ident=(ident % "grezzo").strip(), **comuni)
            creati.append(self.percorso_raw)
            self.filt = wcpfile.ScrittoreWCP(self.percorso_filt, 1.0 / self.fs_filt, n_filt,
                                             [canale_filt],
                                             ident=(ident % ("filtrato " + par_filtro.descrizione())).strip(),
                                             **comuni)
        except Exception as e:
            if self.percorso_raw in creati:
                self.raw.chiudi()
            for p in creati:
                try:
                    os.remove(p)
                except OSError:
                    pass
            if isinstance(e, FileExistsError):
                raise wcpfile.ErroreScrittura("il file %s esiste gia': non viene sovrascritto"
                                              % e.filename)
            raise
        self.meta = {
            "programma": "%s %s" % (NOME_PROGRAMMA, VERSIONE_PROGRAMMA),
            "nome_base": self.nome_base,
            "file_grezzo": os.path.basename(self.percorso_raw),
            "file_filtrato": os.path.basename(self.percorso_filt),
            "inizio": _iso(self.ora_inizio),
            "fine": None,
            "chiusura_regolare": False,
            "durata_s": 0.0,
            "dispositivo": info_dispositivo,
            "calibrazione": self.cal,
            "percorso_calcolo": percorso_numpy,
            "acquisizione": {"fs_hz": self.fs_acq, "campione_inizio": self.campione_inizio},
            "salvataggio": {"fs_filtrato_hz": self.fs_filt, "decimazione": self.dec,
                            "campioni_per_record_grezzo": n_raw,
                            "campioni_per_record_filtrato": n_filt,
                            "durata_record_richiesta_s": durata_record_s,
                            "durata_record_effettiva_s": self.durata_record_effettiva},
            "filtro_iniziale": par_filtro.come_dict(),
            "filtro_note": "passa-basso causale (SOS, float64) + notch; campioni saturati "
                           "e picchi isolati sostituiti dall'ultimo valore valido prima del "
                           "filtro; il file grezzo contiene i campioni originali",
            "lpf8": {"taglio_hz": lpf8_taglio, "guadagno": lpf8_guadagno},
            "cambi_parametri": [],
            "marker": [],
            "campioni_persi": 0,
            "eventi_campioni_persi": [],
            "saturazioni": {"campioni": 0, "eventi": 0, "elenco": []},
            "errori_scrittura": [],
            "record_grezzo": 0,
            "record_filtrato": 0,
        }
        self.campioni_raw = 0
        self.campioni_filt = 0
        self._json_sporco = True
        self.errori_json = 0
        self.chiusa = False
        self.scrivi_json()

    # ------------------------------------------------------------------
    def t_rel(self):
        return self.campioni_raw / self.fs_acq

    def numero_record(self):
        return self.campioni_raw // self.n_raw + 1

    def scrivi_grezzo(self, campioni):
        self.raw.aggiungi(campioni)
        self.campioni_raw += len(campioni)

    def scrivi_filtrato(self, campioni):
        self.filt.aggiungi(campioni)
        self.campioni_filt += len(campioni)

    def evento_parametri(self, descrizione, prima, dopo):
        self.meta["cambi_parametri"].append({
            "t_s": round(self.t_rel(), 4), "ora": _iso(_ora()), "record": self.numero_record(),
            "descrizione": descrizione, "prima": prima, "dopo": dopo})
        self._json_sporco = True

    def marker(self, testo):
        t = self.t_rel()
        rec = self.numero_record()
        self.meta["marker"].append({"t_s": round(t, 4), "ora": _iso(_ora()), "record": rec,
                                    "t_nel_record_s": round(t - (rec - 1) * self.durata_record_effettiva, 4),
                                    "testo": testo})
        # il testo compare anche come identificativo del record in WinWCP
        corto = "M:" + testo
        n_nel_rec = sum(1 for m in self.meta["marker"] if m["record"] == rec)
        if n_nel_rec > 1:
            corto = "M%d:%s" % (n_nel_rec, testo)
        self.raw.imposta_ident_record(corto)
        self.filt.imposta_ident_record(corto)
        self._json_sporco = True
        return t, rec

    def campioni_persi(self, n, indice):
        self.meta["campioni_persi"] += int(n)
        ev = self.meta["eventi_campioni_persi"]
        if len(ev) < 1000:
            ev.append({"t_s": round(self.t_rel(), 4), "ora": _iso(_ora()), "campioni": int(n)})
        self._json_sporco = True

    def saturazione(self, campioni_tot, eventi_tot, nuovi):
        s = self.meta["saturazioni"]
        s["campioni"] = int(campioni_tot)
        s["eventi"] = int(eventi_tot)
        for idx, durata, tipo in nuovi:
            if len(s["elenco"]) < 2000:
                s["elenco"].append({"t_s": round((idx - self.campione_inizio) / self.fs_acq, 4),
                                    "campioni": int(durata), "tipo": tipo})
        self._json_sporco = True

    def errori(self):
        e = []
        for w in (self.raw, self.filt):
            if w.ultimo_errore:
                e.append(w.ultimo_errore)
        return e

    def n_errori(self):
        return self.raw.n_errori + self.filt.n_errori + self.errori_json

    def flush(self):
        ok1 = self.raw.flush()
        ok2 = self.filt.flush()
        for w in (self.raw, self.filt):
            if w.ultimo_errore and (not self.meta["errori_scrittura"] or
                                    self.meta["errori_scrittura"][-1].get("errore") != w.ultimo_errore):
                self.meta["errori_scrittura"].append({"ora": _iso(_ora()), "errore": w.ultimo_errore})
        self.meta["record_grezzo"] = self.raw.nr_su_disco
        self.meta["record_filtrato"] = self.filt.nr_su_disco
        self.meta["durata_s"] = round(self.t_rel(), 3)
        self.scrivi_json()
        return ok1 and ok2

    def scrivi_json(self):
        try:
            scrivi_json_atomico(self.percorso_json, self.meta)
            self._json_sporco = False
            return True
        except (IOError, OSError, ValueError, TypeError) as e:
            self.errori_json += 1
            self.ultimo_errore_json = "%s: %s" % (os.path.basename(self.percorso_json), e)
            return False

    def chiudi(self):
        if self.chiusa:
            return
        self.chiusa = True
        durata = self.t_rel()
        ident = None
        resto = durata - (self.numero_record() - 1) * self.durata_record_effettiva
        if self.campioni_raw % self.n_raw:
            ident = "parz %ss" % wcpfile.numero_it(resto, 4)
        self.raw.chiudi(ident)
        self.filt.chiudi(ident)
        self.meta["fine"] = _iso(_ora())
        self.meta["durata_s"] = round(durata, 3)
        self.meta["record_grezzo"] = self.raw.nr_su_disco
        self.meta["record_filtrato"] = self.filt.nr_su_disco
        self.meta["chiusura_regolare"] = True
        if ident:
            self.meta["ultimo_record_parziale_s"] = round(resto, 3)
        for w in (self.raw, self.filt):
            if w.persi_memoria:
                self.meta["errori_scrittura"].append(
                    {"ora": _iso(_ora()), "errore": "%s: %d record non scritti (disco)" %
                     (os.path.basename(w.percorso), w.persi_memoria)})
        self.scrivi_json()

    def stato(self):
        return {"nome": self.nome_base, "durata_s": self.t_rel(),
                "record": self.numero_record(), "errori": self.errori(),
                "n_errori": self.n_errori()}
