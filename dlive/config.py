# -*- coding: utf-8 -*-
"""Configurazione: file INI leggibile e commentato in italiano.

Il file viene letto con configparser e riscritto da un modello che conserva
i commenti.  I numeri si possono scrivere con il punto o con la virgola.
"""
import io
import os

import configparser

# (sezione, chiave, valore predefinito, tipo, commento)
VOCI = [
    ("generale", "modalita", "chiedi", "scelta:chiedi,simulazione,digidata",
     "Modalita' all'avvio: chiedi, simulazione oppure digidata.\n"
     "La riga di comando (--simulazione / --digidata) ha la precedenza."),
    ("generale", "cartella_dati", "dati_registrati", "testo",
     "Cartella dove salvare le registrazioni (anche chiavetta o disco esterno,\n"
     "es. E:\\registrazioni).  Un percorso relativo e' relativo alla cartella\n"
     "del programma."),
    ("generale", "cartella_log", "log", "testo",
     "Cartella dei file di log (con rotazione automatica)."),
    ("generale", "spazio_minimo_mb", "200", "intero",
     "Spazio libero minimo (MB) per poter iniziare a registrare.  Sotto\n"
     "questa soglia durante la registrazione compare un avviso."),

    ("digidata", "canale_ingresso", "2", "intero",
     "Ingresso analogico del Digidata da acquisire (BNC 0-15).  Il cavo\n"
     "dall'LPF-8 e' collegato all'ingresso 2."),
    ("digidata", "frequenza_acquisizione_hz", "1000", "reale",
     "Frequenza di acquisizione (Hz).  Il grezzo si salva a questa frequenza."),
    ("digidata", "range_v", "10", "reale",
     "Range di ingresso (V).  Il Digidata 1322A lavora sempre a +/-10 V."),
    ("digidata", "percorso_dll", "", "testo",
     "Percorso completo di AxDD132x.dll.  Vuoto = ricerca automatica nei\n"
     "percorsi tipici (cartella di WinWCP, C:\\Axon\\..., system32, cartella\n"
     "dll del programma)."),
    ("digidata", "uscite_analogiche", "come_winwcp", "scelta:come_winwcp,nessuna",
     "come_winwcp = imposta anche le uscite (DAC0, DAC1, digitali) a 0 V\n"
     "come fa WinWCP durante l'acquisizione; nessuna = solo ingressi."),
    ("digidata", "campioni_buffer", "1000000", "intero",
     "Dimensione del buffer circolare nella memoria del PC (campioni).\n"
     "1 000 000 come WinWCP: a 1000 Hz sono circa 16 minuti di margine."),
    ("digidata", "intervallo_lettura_ms", "50", "intero",
     "Ogni quanto si leggono i nuovi campioni dal buffer (ms)."),
    ("digidata", "impostazioni_winwcp", "chiedi", "scelta:chiedi,usa,ignora",
     "Impostazioni di WinWCP (canale, calibrazione, campionamento) lette da\n"
     "Documenti condivisi\\WinWCP\\winwcp.ini e SESLABIO\\lab interface settings.xml\n"
     "(solo lettura).  chiedi = all'avvio le mostra e chiede se usarle; usa = le\n"
     "usa sempre al posto dei valori di questo file; ignora = usa solo questo file."),
    ("digidata", "chunks_per_second", "0", "intero",
     "Campo uChunksPerSecond del protocollo della DLL Axon.  0 come WinWCP\n"
     "(che non lo imposta: dd1320.pas lo dichiara 'Unused'); l'header Axon\n"
     "suggerisce 20.  Cambiarlo solo se la diagnostica non riceve i campioni."),

    ("simulazione", "cartella", "riferimenti/dati", "testo",
     "Cartella proposta per scegliere i file .wcp da riprodurre."),
    ("simulazione", "file", "", "testo",
     "Ultimo file .wcp riprodotto (vuoto = chiedi)."),
    ("simulazione", "record", "1", "intero", "Record da riprodurre (1 = primo; 0 = tutti in sequenza)."),
    ("simulazione", "canale", "-1", "intero",
     "Canale del file da riprodurre (-1 = scegli automaticamente quello col segnale)."),
    ("simulazione", "velocita", "1", "reale", "Fattore di velocita' (1, 5, 20...)."),
    ("simulazione", "salta_coda", "si", "booleano",
     "Salta la coda costante dei record fermati prima della fine."),
    ("simulazione", "sovracampiona", "no", "booleano",
     "Interpola a frequenza_sovracampionamento_hz per provare la stessa\n"
     "catena della modalita' Digidata."),
    ("simulazione", "frequenza_sovracampionamento_hz", "1000", "reale", ""),
    ("simulazione", "rumore_sintetico", "no", "booleano",
     "Aggiunge rumore sintetico: sinusoidi a 50, 8,7 e 37,4 Hz, banda\n"
     "25-50 Hz e rari picchi di saturazione."),

    ("filtro", "tipo", "bessel", "scelta:bessel,butterworth",
     "Passa-basso: bessel (gradini senza sovraelongazione, predefinito)\n"
     "oppure butterworth (taglia di piu' ma sovraelonga: 11 % al 4 ordine)."),
    ("filtro", "ordine", "4", "intero", "Ordine del passa-basso (1-10)."),
    ("filtro", "taglio_hz", "5", "reale",
     "Frequenza di taglio (-3 dB) del passa-basso digitale (Hz).\n"
     "Regolabile anche dal vivo."),
    ("filtro", "notch_hz", "50", "testo",
     "Frequenze dei notch separate da ';' (es. 50 ; 8,7).  Vuoto = nessuno."),
    ("filtro", "q_notch", "30", "reale",
     "Fattore di qualita' dei notch (30 = banda di 1,7 Hz a 50 Hz)."),
    ("filtro", "soglia_saturazione", "32700", "intero",
     "Conteggi ADC oltre i quali un campione e' considerato saturato:\n"
     "il filtro usa l'ultimo valore valido (il grezzo salvato resta intatto)."),
    ("filtro", "soglia_picchi_mv", "500", "reale",
     "Picchi isolati: campioni che si scostano dall'ultimo valore valido di\n"
     "piu' di questa soglia (mV) vengono trattati come la saturazione, se\n"
     "durano meno di durata_max_picco_ms.  0 = disattivato."),
    ("filtro", "durata_max_picco_ms", "50", "reale",
     "Attesa (ms, 0-500): uno scostamento oltre soglia_picchi_mv che dura meno di\n"
     "cosi' e' un picco e si toglie; se dura di piu' e' segnale vero e passa, ma i\n"
     "suoi primi durata_max_picco_ms sono sostituiti dall'ultimo valore valido.\n"
     "Se il laboratorio dice che gli impulsi veri sono segnale, si abbassa."),

    ("salvataggio", "frequenza_salvataggio_hz", "125", "reale",
     "Frequenza del file filtrato (Hz).  Deve dividere esattamente la\n"
     "frequenza di acquisizione (1000/125 = 8)."),
    ("salvataggio", "durata_record_s", "60", "reale",
     "Durata di ogni record nei file .wcp (s).  La durata effettiva e'\n"
     "arrotondata perche' ogni record occupi un numero intero di settori."),
    ("salvataggio", "intervallo_scrittura_s", "1", "reale",
     "Ogni quanto si scrive su disco con fsync (s): in caso di crash si\n"
     "perde al massimo questo intervallo."),

    ("salvataggio", "separatore_decimale", "auto", "scelta:auto,virgola,punto",
     "Separatore decimale nell'intestazione dei .wcp.  auto = quello delle\n"
     "impostazioni internazionali di Windows, come fa WinWCP (che rilegge\n"
     "comunque sia la virgola sia il punto); fuori da Windows la virgola.\n"
     "virgola = come i file esistenti (PC in italiano); punto = PC inglese."),

    ("calibrazione", "yg", "0,001", "reale",
     "Fattore di calibrazione (V per unita'): 0,001 V/mV come nei file\n"
     "esistenti.  Se il guadagno dell'LPF-8 non e' 1, usare 0,001 x guadagno."),
    ("calibrazione", "yz", "0", "reale", "Livello di zero (conteggi ADC)."),
    ("calibrazione", "unita", "mV", "testo", "Unita' di misura."),
    ("calibrazione", "nome_canale", "AI2", "testo",
     "Nome del canale scritto nei file (max 8 caratteri)."),

    ("lpf8", "taglio_hz", "15", "reale",
     "Frequenza di taglio impostata sul Warner LPF-8 (Hz), da aggiornare\n"
     "a mano quando la si cambia; 0 = Bypass.  Viene salvata nei metadati.\n"
     "Valori dell'LPF-8: 0,1-199,9 Hz a passi di 0,1 Hz, 200-19990 Hz a passi\n"
     "di 10 Hz.  Con 1000 Hz di acquisizione, oltre 150 Hz (o in Bypass) il\n"
     "programma avvisa del rischio di aliasing."),
    ("lpf8", "guadagno", "1", "reale",
     "Guadagno impostato sull'LPF-8 (1, 2, 5, 10, 20, 50, 100, 200).  Non cambia\n"
     "la scala: se non e' 1, la calibrazione yg va moltiplicata per il guadagno."),

    ("grafico", "finestra_s", "30", "reale", "Finestra temporale iniziale (10, 30, 120, 600 s)."),
    ("grafico", "aggiornamento_hz", "5", "reale",
     "Aggiornamenti del grafico al secondo (2, 5 o 10; si cambia anche dalla finestra).\n"
     "5 = circa 4 % di CPU sul PC di sviluppo; 10 e' piu' fluido ma costa ~7 %."),
    ("grafico", "scala_y", "auto", "scelta:auto,fissa", "Scala Y automatica o fissa."),
    ("grafico", "y_min", "-150", "reale", "Limite inferiore della scala fissa."),
    ("grafico", "y_max", "150", "reale", "Limite superiore della scala fissa."),

    ("interfaccia", "dimensione", "auto", "dimensione",
     "Dimensione di testi e controlli della finestra: auto (calcolata da\n"
     "risoluzione e DPI dello schermo) oppure una percentuale, es. 75, 100,\n"
     "125, 150, 200.  100 = font di 12 punti, adatto a 1920x1080; 200 = adatto\n"
     "a uno schermo 4K.  Ha la precedenza sulla scala automatica.  Si cambia\n"
     "anche dalla finestra (Dimensione interfaccia), con effetto immediato."),
]

INTESTAZIONE = """\
; =====================================================================
;  denoising_live - file di configurazione
;  Righe che iniziano con ';' sono commenti.  Numeri con punto o virgola.
;  Il programma riscrive questo file quando si cambiano le impostazioni
;  dalla finestra (i commenti vengono conservati).
; =====================================================================
"""


class ErroreConfigurazione(Exception):
    pass


def _converti(valore, tipo, sezione, chiave):
    v = valore.strip()
    try:
        if tipo == "intero":
            return int(float(v.replace(",", ".")))
        if tipo == "reale":
            return float(v.replace(",", "."))
        if tipo == "booleano":
            l = v.lower()
            if l in ("si", "sì", "s", "yes", "y", "true", "1", "vero"):
                return True
            if l in ("no", "n", "false", "0", "falso", ""):
                return False
            raise ValueError("atteso si/no")
        if tipo == "dimensione":
            from .scala import formatta_impostazione, leggi_impostazione
            return formatta_impostazione(leggi_impostazione(v))
        if tipo.startswith("scelta:"):
            scelte = tipo.split(":", 1)[1].split(",")
            if v.lower() not in scelte:
                raise ValueError("valori ammessi: %s" % ", ".join(scelte))
            return v.lower()
        return v
    except ValueError as e:
        raise ErroreConfigurazione("[%s] %s = %r non valido (%s)" % (sezione, chiave, valore, e))


def _formatta(valore, tipo):
    if tipo == "booleano":
        return "si" if valore else "no"
    if tipo == "reale":
        s = ("%.6g" % valore)
        return s.replace(".", ",")
    return "%s" % (valore,)


class Configurazione(object):
    def __init__(self, percorso=None, base=None):
        self.percorso = percorso
        self.base = base or os.getcwd()
        self.valori = {}
        self.avvisi = []
        for sez, k, default, tipo, _ in VOCI:
            self.valori[(sez, k)] = _converti(default, tipo, sez, k)

    def __getitem__(self, chiave):
        return self.valori[tuple(chiave.split(".", 1))]

    def get(self, chiave, default=None):
        return self.valori.get(tuple(chiave.split(".", 1)), default)

    def imposta(self, chiave, valore):
        sez, k = chiave.split(".", 1)
        tipo = self._tipo(sez, k)
        if isinstance(valore, str) and tipo != "testo":
            valore = _converti(valore, tipo, sez, k)
        self.valori[(sez, k)] = valore

    def _tipo(self, sez, k):
        for s, kk, _, tipo, _ in VOCI:
            if s == sez and kk == k:
                return tipo
        raise KeyError("%s.%s" % (sez, k))

    def carica(self):
        if not self.percorso or not os.path.exists(self.percorso):
            return False
        cp = configparser.RawConfigParser()
        with io.open(self.percorso, "r", encoding="utf-8", errors="replace") as f:
            testo = f.read()
        if testo.startswith(u"\ufeff"):
            testo = testo[1:]
        cp.read_string(testo)
        noti = set((s, k) for s, k, _, _, _ in VOCI)
        for sez in cp.sections():
            for k, v in cp.items(sez):
                if (sez, k) not in noti:
                    self.avvisi.append("chiave sconosciuta ignorata: [%s] %s" % (sez, k))
                    continue
                tipo = self._tipo(sez, k)
                try:
                    self.valori[(sez, k)] = _converti(v, tipo, sez, k)
                except ErroreConfigurazione as e:
                    if tipo != "dimensione":
                        raise
                    # solo estetica: si usa la scala automatica e si avvisa
                    self.avvisi.append("%s: uso auto" % e)
        return True

    def testo(self):
        righe = [INTESTAZIONE]
        sez_corrente = None
        for sez, k, default, tipo, commento in VOCI:
            if sez != sez_corrente:
                righe.append("\n[%s]\n" % sez)
                sez_corrente = sez
            if commento:
                for c in commento.split("\n"):
                    righe.append("; %s\n" % c)
            righe.append("%s = %s\n" % (k, _formatta(self.valori[(sez, k)], tipo)))
        return "".join(righe)

    def salva(self, percorso=None):
        percorso = percorso or self.percorso
        tmp = percorso + ".tmp"
        with io.open(tmp, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(self.testo())
        os.replace(tmp, percorso)

    def percorso_assoluto(self, chiave):
        p = os.path.expanduser(self[chiave])
        if not os.path.isabs(p):
            p = os.path.join(self.base, p)
        return os.path.normpath(p)

    def separatore(self):
        """',' o '.' per l'intestazione dei .wcp (vedi separatore_decimale)."""
        v = self["salvataggio.separatore_decimale"]
        if v == "virgola":
            return ","
        if v == "punto":
            return "."
        from . import sysinfo
        return sysinfo.separatore_decimale() or ","

    def notch(self):
        testo = self["filtro.notch_hz"].strip()
        if not testo:
            return []
        out = []
        for parte in testo.replace("|", ";").split(";"):
            parte = parte.strip()
            if parte:
                out.append(float(parte.replace(",", ".")))
        return out

    def controlla(self):
        """Controlli di coerenza.  Restituisce (errori, avvisi)."""
        errori = []
        avvisi = list(self.avvisi)
        fa = self["digidata.frequenza_acquisizione_hz"]
        fsv = self["salvataggio.frequenza_salvataggio_hz"]
        if not (1 <= fa <= 100000):
            errori.append("Frequenza di acquisizione fuori dai limiti (1-100000 Hz)")
        dec = fa / fsv if fsv > 0 else 0
        if fsv <= 0 or abs(dec - round(dec)) > 1e-6 or round(dec) < 1:
            errori.append("La frequenza di salvataggio (%g Hz) deve dividere esattamente "
                          "quella di acquisizione (%g Hz)" % (fsv, fa))
        us = 1e6 / fa if fa > 0 else 0
        if fa > 0 and abs(us - round(us)) > 1e-6:
            avvisi.append("Con %g Hz il periodo di campionamento (%.3f us) non e' un numero "
                          "intero di microsecondi: il Digidata usera' %d us"
                          % (fa, us, int(round(us))))
        if not (0 <= self["digidata.canale_ingresso"] <= 15):
            errori.append("Canale di ingresso fuori dai limiti (0-15)")
        d = self["salvataggio.durata_record_s"]
        if d < 1:
            errori.append("Durata del record troppo breve (minimo 1 s)")
        if d * fa > 1000000:
            errori.append("Record troppo lungo: %g s x %g Hz = %d campioni (massimo 1 000 000)"
                          % (d, fa, int(d * fa)))
        if not (0 <= self["filtro.durata_max_picco_ms"] <= 500):
            errori.append("[filtro] durata_max_picco_ms = %g fuori dall'intervallo 0-500 ms"
                          % self["filtro.durata_max_picco_ms"])
        from . import lpf8
        e8, a8 = lpf8.controlla(self["lpf8.taglio_hz"], fa, self["lpf8.guadagno"],
                                self["calibrazione.yg"], self["calibrazione.unita"])
        avvisi.extend("[lpf8] %s" % m for m in e8 + a8)
        if self["calibrazione.yg"] == 0:
            errori.append("Fattore di calibrazione YG nullo")
        try:
            self.notch()
        except ValueError:
            errori.append("Elenco dei notch non valido: %r" % self["filtro.notch_hz"])
        return errori, avvisi


def carica_o_crea(percorso, base=None):
    c = Configurazione(percorso, base)
    if os.path.exists(percorso):
        c.carica()
    else:
        try:
            c.salva()
        except (IOError, OSError) as e:
            c.avvisi.append("impossibile creare %s: %s" % (percorso, e))
    return c
