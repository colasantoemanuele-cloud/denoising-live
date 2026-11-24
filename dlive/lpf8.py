# -*- coding: utf-8 -*-
"""Filtro analogico Warner LPF-8 (manuale "LPF-8 Manual 4-8-98",
riferimenti/doc/LPF-8 manual.pdf): valori ammessi e rischio di aliasing.

Dal manuale:
  * passa-basso di Bessel a 8 poli (p. 1, schema a blocchi p. 4);
  * campo Low 0,1-199,9 Hz a passi di 0,1 Hz; campo High 10 Hz-19,99 kHz a
    passi di 10 Hz (p. 2 e p. 5): 3979 frequenze selezionabili;
  * -3 dB al taglio, -14 dB a 2 volte, -114 dB a 10 volte il taglio, ma
    attenuazione massima 60 dB (p. 1-2);
  * Bypass sul selettore del campo: il filtro e' escluso, guadagno e offset
    restano (p. 5);
  * guadagno 1, 2, 5, 10, 20, 50, 100, 200 (p. 3), applicato prima del filtro;
  * ingresso e uscita +/-10 V (oltre: LED di saturazione, p. 2 e p. 5),
    cioe' lo stesso range dell'ADC del Digidata 1322A.

Il modello dell'attenuazione usa i poli del prototipo di Bessel di ordine 8
normalizzato a -3 dB (gli stessi del filtro digitale, dlive/filters.py) con
il limite di 60 dB del manuale: da' -13,7 dB a 2 volte e -114 dB a 10 volte
il taglio, come il manuale.
"""
import math

from .filters import POLI_BESSEL

GUADAGNI = (1, 2, 5, 10, 20, 50, 100, 200)
ATTENUAZIONE_MASSIMA_DB = 60.0
BYPASS = 0.0          # valore di lpf8.taglio_hz che indica il Bypass
# soglie sull'attenuazione dell'LPF-8 alla frequenza di Nyquist (fs/2)
SOGLIA_OK_DB = 40.0          # sotto l'1 % in ampiezza: nessun aliasing apprezzabile
SOGLIA_FORTE_DB = 20.0       # sotto il 10 %: aliasing certo per il rumore sopra fs/2


def leggi_taglio(testo):
    """Converte il testo del campo "Taglio LPF-8 (Hz)": numero (virgola o
    punto) oppure "bypass"/"b".  Restituisce un float (BYPASS = 0) o solleva
    ValueError."""
    t = ("%s" % testo).strip().lower()
    if t in ("bypass", "byp", "b", "escluso"):
        return BYPASS
    return float(t.replace(",", "."))


def valore_ammesso(fc):
    """None se fc e' un taglio impostabile sull'LPF-8 (o Bypass), altrimenti
    il motivo per cui non lo e'."""
    if fc == BYPASS:
        return None
    if not (fc > 0):
        return "il taglio deve essere positivo (0 = Bypass)"
    if fc < 0.1 - 1e-9:
        return "sotto il minimo dell'LPF-8 (0,1 Hz)"
    if fc > 19990 + 1e-6:
        return "sopra il massimo dell'LPF-8 (19,99 kHz)"
    passi_low = fc / 0.1
    if fc <= 199.9 + 1e-9 and abs(passi_low - round(passi_low)) < 1e-6:
        return None                        # campo Low, passi di 0,1 Hz
    passi_high = fc / 10.0
    if fc >= 10 - 1e-9 and abs(passi_high - round(passi_high)) < 1e-6:
        return None                        # campo High, passi di 10 Hz
    if fc <= 199.9:
        return "nel campo Low il passo e' 0,1 Hz"
    return "sopra 199,9 Hz (campo High) il passo e' 10 Hz"


def guadagno_ammesso(g):
    return any(abs(g - v) < 1e-9 for v in GUADAGNI)


def attenuazione_db(f, fc):
    """Attenuazione (dB, positiva) dell'LPF-8 con taglio fc alla frequenza f.
    Bypass (fc = 0): 0 dB."""
    if fc == BYPASS or f <= 0:
        return 0.0
    r = float(f) / fc
    g = 1.0
    for re, im in POLI_BESSEL[8]:
        if im == 0.0:
            g *= abs(re) / abs(complex(-re, r))
        else:
            p = complex(re, im)
            q = complex(re, -im)
            g *= abs(p * q) / abs((1j * r - p) * (1j * r - q))
    att = -20.0 * math.log10(max(g, 1e-30))
    return min(att, ATTENUAZIONE_MASSIMA_DB)


def taglio_massimo_senza_aliasing(fs, soglia_db=SOGLIA_OK_DB):
    """Taglio massimo dell'LPF-8 con attenuazione >= soglia_db a fs/2."""
    lo, hi = 0.1, fs / 2.0
    for _ in range(60):
        m = 0.5 * (lo + hi)
        if attenuazione_db(fs / 2.0, m) >= soglia_db:
            lo = m
        else:
            hi = m
    return lo


def controlla(fc, fs, guadagno=1.0, yg=None, unita="mV"):
    """Controlli sull'LPF-8 dichiarato.  Restituisce (errori, avvisi):
    errori = valore impossibile sull'LPF-8; avvisi = rischio di aliasing o
    calibrazione da controllare."""
    errori = []
    avvisi = []
    motivo = valore_ammesso(fc)
    if motivo:
        errori.append("Taglio LPF-8 %s Hz non impostabile: %s" % (_it(fc), motivo))
        return errori, avvisi
    nyq = fs / 2.0
    att = attenuazione_db(nyq, fc)
    if fc == BYPASS:
        avvisi.append("LPF-8 in Bypass: nessun filtro analogico prima del Digidata, il rumore "
                      "sopra %s Hz si ripiega (aliasing) nel grezzo a %s Hz" % (_it(nyq), _it(fs)))
    elif att < SOGLIA_FORTE_DB:
        avvisi.append("Rischio di aliasing: con l'LPF-8 a %s Hz il rumore a %s Hz (meta' della "
                      "frequenza di acquisizione) e' attenuato solo di %s dB; per non avere "
                      "aliasing tenere il taglio sotto %s Hz"
                      % (_it(fc), _it(nyq), _it(att, 0), _it(taglio_massimo_senza_aliasing(fs), 0)))
    elif att < SOGLIA_OK_DB:
        avvisi.append("Possibile aliasing: con l'LPF-8 a %s Hz l'attenuazione a %s Hz e' di %s dB "
                      "(sotto %s dB); consigliato un taglio fino a %s Hz"
                      % (_it(fc), _it(nyq), _it(att, 0), _it(SOGLIA_OK_DB, 0),
                         _it(taglio_massimo_senza_aliasing(fs), 0)))
    if not guadagno_ammesso(guadagno):
        avvisi.append("Guadagno LPF-8 %s non previsto dal manuale (1, 2, 5, 10, 20, 50, 100, 200)"
                      % _it(guadagno))
    elif yg is not None and guadagno != 1 and unita == "mV" and abs(yg - 0.001) < 1e-12:
        avvisi.append("Guadagno LPF-8 %s ma calibrazione yg = 0,001 V/mV: i valori in mV saranno "
                      "%s volte quelli veri (usare yg = 0,001 x %s)" % (_it(guadagno), _it(guadagno),
                                                                      _it(guadagno)))
    return errori, avvisi


def descrizione(fc):
    return "Bypass" if fc == BYPASS else "%s Hz" % _it(fc)


def _it(v, cifre=None):
    if cifre is None:
        s = "%g" % v
    else:
        s = ("%." + str(cifre) + "f") % v
    return s.replace(".", ",")


def testo_campo(fc):
    """Testo per il campo della finestra: 'Bypass' oppure il numero con la virgola."""
    if fc == BYPASS:
        return "Bypass"
    s = ("%.1f" % fc) if fc < 200 else ("%.0f" % fc)
    return s.replace(".", ",")
