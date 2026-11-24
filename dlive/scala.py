# -*- coding: utf-8 -*-
"""Dimensione dell'interfaccia: fattore di scala automatico o scelto a mano.

Convenzione (come la "scala" di Windows): 100 % e' la dimensione standard
per uno schermo 1920x1080 a 96 DPI, con font di base di 12 punti; 200 % e'
il doppio (adatto a uno schermo 4K).  Tutti i font sono in punti; le
distanze in pixel (margini, spessori, lunghezze) si moltiplicano per il
fattore con px().

Scala automatica: il fattore e' il maggiore tra
  * risoluzione: min(larghezza / 1920, altezza / 1080), limitato a
    0,8 - 4 (quindi 80 % a 1024x768 e 1280x1024, 200 % a 3840x2160);
  * DPI dichiarati dal sistema (``tk scaling`` x 72 / 96), se almeno 115:
    cioe' quando il sistema e' impostato apposta per uno schermo ad alta
    densita' (Windows con scala al 150 % -> 150 %).  Molti sistemi Linux
    dichiarano sempre 96 DPI anche su schermi 4K: li corregge la risoluzione.
La chiave ``[interfaccia] dimensione`` di config.ini ha la precedenza.
tkinter si importa solo dentro la classe: config.py usa le funzioni di
lettura anche senza interfaccia grafica.
"""
FONT_BASE_PT = 12.0
DPI_RIF = 96.0
RIS_RIF = (1920.0, 1080.0)
FATTORE_MIN_AUTO = 0.8
FATTORE_MAX = 4.0
SOGLIA_DPI = 1.2       # i DPI contano solo da 115 in su (120 = "caratteri grandi" di XP)
PERCENTO_MIN = 50
PERCENTO_MAX = 400
SCELTE_PERCENTO = (75, 100, 125, 150, 175, 200, 250, 300)

# font standard di Tk: tutti i widget (anche dialoghi e menu) li usano
FONT_STANDARD = ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont",
                 "TkSmallCaptionFont", "TkIconFont", "TkTooltipFont", "TkFixedFont")


def fattore_automatico(larghezza, altezza, dpi):
    """Fattore di scala (1,0 = 100 %) dalla risoluzione e dai DPI dello schermo."""
    f_ris = min(float(larghezza) / RIS_RIF[0], float(altezza) / RIS_RIF[1])
    f_ris = max(FATTORE_MIN_AUTO, min(FATTORE_MAX, f_ris))
    f_dpi = min(FATTORE_MAX, float(dpi) / DPI_RIF)
    if f_dpi < SOGLIA_DPI:      # 96-110 DPI: valore generico, non una scelta di scala
        f_dpi = 0.0
    return max(f_ris, f_dpi)


def percento_da_fattore(f):
    """Arrotonda al 5 % piu' vicino."""
    return int(round(f * 20.0)) * 5


def leggi_impostazione(valore):
    """'auto' (o vuoto) -> None; '150', '150%', '150 %', '1,5' (fattore) -> 150.
    Solleva ValueError se non valido."""
    v = ("%s" % (valore,)).strip().lower().replace("%", "").replace(",", ".").strip()
    if v in ("", "auto", "automatica", "automatico"):
        return None
    n = float(v)
    if n <= 10:          # scritto come fattore (1,5)
        n *= 100.0
    p = int(round(n))
    if not (PERCENTO_MIN <= p <= PERCENTO_MAX):
        raise ValueError("ammessi auto oppure %d-%d %%" % (PERCENTO_MIN, PERCENTO_MAX))
    return p


def formatta_impostazione(percento):
    return "auto" if percento is None else "%d" % percento


class Scala(object):
    """Fattore di scala dell'interfaccia e font con nome (si aggiornano dal vivo)."""

    def __init__(self, root, impostazione="auto", schermo=None):
        """schermo=(larghezza, altezza) sostituisce quello vero (solo per i test)."""
        self.root = root
        self.tk_scaling = float(root.tk.call("tk", "scaling"))      # pixel per punto
        self.dpi = self.tk_scaling * 72.0
        self.schermo = schermo or (root.winfo_screenwidth(), root.winfo_screenheight())
        self.percento_auto = percento_da_fattore(fattore_automatico(self.schermo[0], self.schermo[1],
                                                                    self.dpi))
        self.font = {}
        self.manuale = None
        self.percento = self.percento_auto
        self.imposta(impostazione)

    @property
    def fattore(self):
        return self.percento / 100.0

    def imposta(self, impostazione):
        """impostazione: 'auto', un numero (percento) o None (= auto)."""
        try:
            self.manuale = leggi_impostazione("auto" if impostazione is None else impostazione)
        except ValueError:
            self.manuale = None
        self.percento = self.manuale if self.manuale is not None else self.percento_auto
        self._applica()

    def descrizione(self):
        if self.manuale is None:
            return "automatica %d %% (schermo %dx%d, %.0f DPI)" % (self.percento, self.schermo[0],
                                                                 self.schermo[1], self.dpi)
        return "%d %% scelta a mano (automatica sarebbe %d %%)" % (self.percento, self.percento_auto)

    # ------------------------------------------------------------ conversioni
    def pt(self, punti_a_100):
        """Dimensione di un font in punti: punti_a_100 al 100 %, scalata e
        corretta per i DPI che Tk usa per convertire i punti in pixel."""
        return max(6, int(round(punti_a_100 * self.fattore * DPI_RIF / self.dpi)))

    def px(self, pixel_a_100):
        """Distanza in pixel (margini, spessori) scalata."""
        if pixel_a_100 <= 0:
            return 0
        return max(1, int(round(pixel_a_100 * self.fattore)))

    # ------------------------------------------------------------------ font
    def _font(self, nome, **opzioni):
        import tkinter.font as tkfont
        f = self.font.get(nome)
        if f is None:
            fam = tkfont.Font(root=self.root, name="TkDefaultFont", exists=True).actual("family")
            f = tkfont.Font(root=self.root, name=nome, exists=False, family=fam, **opzioni)
            self.font[nome] = f
        else:
            f.configure(**opzioni)
        return f

    def _applica(self):
        import tkinter.font as tkfont
        base = self.pt(FONT_BASE_PT)
        self.base_pt = base
        for nome in FONT_STANDARD:
            try:
                tkfont.Font(root=self.root, name=nome, exists=True).configure(size=base)
            except Exception:
                pass
        piccolo = max(6, int(round(base * 11.0 / 12.0)))
        self._font("DliveNormale", size=base)
        self._font("DliveGrassetto", size=base, weight="bold")
        self._font("DlivePiccolo", size=piccolo)
        self._font("DliveAssi", size=piccolo)
        self._font("DliveTitolo", size=int(round(base * 1.25)), weight="bold")
        # valore del filtrato: 3 volte il font di base
        self._font("DliveValore", size=3 * base, weight="bold")
        self._stili()

    def _stili(self):
        """Frecce e indicatori dei temi ttk disegnati da Tk (Linux); sui temi
        nativi di Windows non hanno effetto e restano quelli del sistema."""
        try:
            from tkinter import ttk
            s = ttk.Style(self.root)
            freccia = self.px(12)
            for st in ("TCombobox", "TSpinbox", "Vertical.TScrollbar", "Horizontal.TScrollbar"):
                s.configure(st, arrowsize=freccia)
            ind = self.px(11)
            for st in ("TCheckbutton", "TRadiobutton"):
                s.configure(st, indicatordiameter=ind, indicatorsize=ind)
        except Exception:
            pass

    # ------------------------------------------------------------- finestra
    def geometria_iniziale(self):
        """(larghezza, altezza, x, y) della finestra principale: mai piu'
        grande dello schermo (lascia spazio a barra del titolo e applicazioni)."""
        sw, sh = self.schermo
        if sw <= 1440 or sh <= 900:
            w, h = sw - 8, sh - 64
            return w, h, 0, 0
        w, h = int(sw * 0.85), int(sh * 0.85)
        return w, h, (sw - w) // 2, max(0, (sh - h) // 2 - 20)

    def dimensione_minima(self):
        sw, sh = self.schermo
        return min(640, sw - 8), min(480, sh - 64)

