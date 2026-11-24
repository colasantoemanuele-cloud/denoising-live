# -*- coding: utf-8 -*-
"""Interfaccia grafica (tkinter).  Disegna su Canvas al massimo due punti
(minimo e massimo) per colonna di pixel; non chiama mai il dispositivo."""
import math
import os
import time

import queue

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import compat
from . import filters
from . import lpf8
from . import registro
from . import sysinfo
from .acquisizione import Sessione
from .devices.base import ErroreDispositivo
from .devices.simulated import SimulatedDevice
from .scala import SCELTE_PERCENTO, Scala

FINESTRE = [("10 s", 10.0), ("30 s", 30.0), ("2 min", 120.0), ("10 min", 600.0)]
AGGIORNAMENTI_HZ = (2.0, 5.0, 10.0)
PRESET_TAGLIO = (1.0, 2.0, 5.0, 10.0)
COL_GREZZO = "#b8b8b8"
COL_FILTRATO = "#d62728"
COL_SFONDO = "white"
COL_GRIGLIA = "#e6e6e6"


def fmt_num(v, cifre=1):
    if v is None:
        return "-"
    return ("%." + str(cifre) + "f") % v


def fmt_it(v, cifre=1):
    return fmt_num(v, cifre).replace(".", ",")


def leggi_float(testo):
    return float(testo.strip().replace(",", "."))


def _fmt_hz(v):
    return ("%g" % float(v)).replace(".", ",")


def fmt_durata(s):
    s = int(s)
    return "%d:%02d:%02d" % (s // 3600, (s // 60) % 60, s % 60)


class Grafico(object):
    """Gestisce l'aggregazione in colonne e il disegno sul Canvas.  Margini,
    spessori e testi seguono la scala dell'interfaccia (font DliveAssi)."""

    def __init__(self, canvas, scala):
        self.c = canvas
        self.scala = scala
        self.fnt = scala.font["DliveAssi"]
        self.finestra_s = 30.0
        self.larghezza = 800
        self.altezza = 400
        self._calcola_margini()
        self.dt_secchio = 0.01
        self.colonne = []        # [rmin, rmax, fmin, fmax]
        self.acc = None
        self.acc_n = 0
        self.secchi_per_colonna = 1
        self.n_colonne = 100
        self.contatore = 0
        self.ymin, self.ymax = -150.0, 150.0
        self.auto = True
        self.unita = "mV"
        self.id_grezzo = canvas.create_line(0, 0, 0, 0, fill=COL_GREZZO, width=scala.px(1))
        self.id_filtrato = canvas.create_line(0, 0, 0, 0, fill=COL_FILTRATO, width=max(2, scala.px(2)))
        self.id_griglia = []
        self._ultimo_ridisegno_assi = None
        self._ultima_riduzione = 0.0

    def _calcola_margini(self):
        px = self.scala.px
        f = self.fnt
        self.riga = f.metrics("linespace")
        self.margine_sx = f.measure("-0000,0") + px(8)
        self.margine_dx = max(px(6), f.measure("ora") // 2 + px(3))
        self.margine_alto = self.riga + px(4)
        self.margine_basso = self.riga + px(6)

    def configura(self, finestra_s, dt_secchio):
        self.finestra_s = float(finestra_s)
        self.dt_secchio = float(dt_secchio)
        larg_utile = max(50, self.larghezza - self.margine_sx - self.margine_dx)
        dt_col = max(self.dt_secchio, self.finestra_s / larg_utile)
        self.secchi_per_colonna = max(1, int(round(dt_col / self.dt_secchio)))
        self.n_colonne = int(math.ceil(self.finestra_s / (self.secchi_per_colonna * self.dt_secchio)))
        self.colonne = []
        self.acc = None
        self.acc_n = 0
        self._ultimo_ridisegno_assi = None

    def aggiungi_secchi(self, secchi):
        spc = self.secchi_per_colonna
        acc = self.acc
        n = self.acc_n
        cols = self.colonne
        for s in secchi:
            if acc is None:
                acc = list(s)
                n = 0
            else:
                if s[0] < acc[0]:
                    acc[0] = s[0]
                if s[1] > acc[1]:
                    acc[1] = s[1]
                if s[2] < acc[2]:
                    acc[2] = s[2]
                if s[3] > acc[3]:
                    acc[3] = s[3]
            n += 1
            if n >= spc:
                cols.append(acc)
                acc = None
                n = 0
        self.acc = acc
        self.acc_n = n
        if len(cols) > self.n_colonne:
            del cols[:len(cols) - self.n_colonne]

    def _scala_auto(self):
        if not self.colonne:
            return
        lo = min(c[2] for c in self.colonne)
        hi = max(c[3] for c in self.colonne)
        span = max(hi - lo, 2.0)
        lo -= 0.15 * span
        hi += 0.15 * span
        cur = self.ymax - self.ymin
        ora = time.time()
        if lo < self.ymin or hi > self.ymax:
            self.ymin = min(lo, self.ymin) if (hi - lo) > 0.3 * cur else lo
            self.ymax = max(hi, self.ymax) if (hi - lo) > 0.3 * cur else hi
            self._ultima_riduzione = ora
        elif (hi - lo) < 0.4 * cur and ora - self._ultima_riduzione > 2.0:
            self.ymin, self.ymax = lo, hi
            self._ultima_riduzione = ora

    def disegna(self):
        w = self.larghezza
        h = self.altezza
        x0 = self.margine_sx
        x1 = w - self.margine_dx
        y_alto = self.margine_alto
        y_basso = max(y_alto + 10, h - self.margine_basso)
        if self.auto:
            self._scala_auto()
        ymin, ymax = self.ymin, self.ymax
        if ymax - ymin < 1e-9:
            ymax = ymin + 1.0
        ky = (y_basso - y_alto) / (ymax - ymin)
        kx = (x1 - x0) / float(max(1, self.n_colonne))
        chiave = (w, h, round(ymin, 6), round(ymax, 6), self.finestra_s)
        if chiave != self._ultimo_ridisegno_assi:
            self._disegna_assi(ymin, ymax, ky, y_basso)
            self._ultimo_ridisegno_assi = chiave
        cols = self.colonne
        if not cols:
            self.c.coords(self.id_grezzo, 0, 0, 0, 0)
            self.c.coords(self.id_filtrato, 0, 0, 0, 0)
            return
        # le colonne piu' recenti stanno a destra
        primo = self.n_colonne - len(cols)
        lim_alto = float(y_alto)
        lim_basso = float(y_basso)
        pg = []
        pf = []
        for i, col in enumerate(cols):
            x = x0 + (primo + i) * kx
            a = y_basso - (col[0] - ymin) * ky
            b = y_basso - (col[1] - ymin) * ky
            a = lim_alto if a < lim_alto else (lim_basso if a > lim_basso else a)
            b = lim_alto if b < lim_alto else (lim_basso if b > lim_basso else b)
            if i & 1:
                pg.extend((x, b, x, a))
            else:
                pg.extend((x, a, x, b))
            fa = y_basso - (col[2] - ymin) * ky
            fb = y_basso - (col[3] - ymin) * ky
            fa = lim_alto if fa < lim_alto else (lim_basso if fa > lim_basso else fa)
            fb = lim_alto if fb < lim_alto else (lim_basso if fb > lim_basso else fb)
            pf.extend((x, (fa + fb) * 0.5))
        if len(pg) < 4:
            pg.extend(pg)
        if len(pf) < 4:
            pf.extend(pf)
        self.c.coords(self.id_grezzo, *pg)
        self.c.coords(self.id_filtrato, *pf)

    def _disegna_assi(self, ymin, ymax, ky, y_basso):
        for i in self.id_griglia:
            self.c.delete(i)
        self.id_griglia = []
        c = self.c
        px = self.scala.px
        fnt = self.fnt
        x0 = self.margine_sx
        x1 = self.larghezza - self.margine_dx
        y_alto = self.margine_alto
        span = ymax - ymin
        # al massimo 8 tacche, e mai piu' fitte di una ogni 1,6 righe di testo
        n_max = max(2, min(8, int((y_basso - y_alto) / (self.riga * 1.6))))
        passo = 10 ** math.floor(math.log10(span / 5.0)) if span > 0 else 1
        for m in (1, 2, 5, 10, 20, 50, 100):
            if span / (passo * m) <= n_max:
                passo *= m
                break
        else:
            passo *= 100
        v = math.ceil(ymin / passo) * passo
        while v <= ymax:
            y = y_basso - (v - ymin) * ky
            self.id_griglia.append(c.create_line(x0, y, x1, y, fill=COL_GRIGLIA))
            testo = ("%g" % round(v, 6)).replace(".", ",")
            self.id_griglia.append(c.create_text(x0 - px(4), y, text=testo, anchor="e", font=fnt))
            v += passo
        self.id_griglia.append(c.create_text(x0 + px(4), px(2), text=self.unita, anchor="nw", font=fnt))
        # asse dei tempi (secondi prima di adesso); passo raddoppiato se le
        # scritte non ci stanno
        f = self.finestra_s
        passo_t = {10.0: 2.0, 30.0: 5.0, 120.0: 20.0, 600.0: 60.0}.get(f, f / 5.0)
        larg_scritta = fnt.measure("-%g s" % f) * 1.4
        while passo_t < f and (x1 - x0) * passo_t / f < larg_scritta:
            passo_t *= 2
        t = 0.0
        while t <= f + 1e-9:
            x = x1 - (t / f) * (x1 - x0)
            self.id_griglia.append(c.create_line(x, y_alto, x, y_basso, fill=COL_GRIGLIA))
            self.id_griglia.append(c.create_text(x, y_basso + px(3), text="-%g s" % t if t else "ora",
                                                 anchor="n", font=fnt))
            t += passo_t
        self.id_griglia.append(c.create_line(x0, y_basso, x1, y_basso, fill="#999999"))
        for i in self.id_griglia:
            c.tag_lower(i)


class RigaAdattabile(ttk.Frame):
    """Fila di widget che va a capo quando la finestra e' troppo stretta
    (barra dei pulsanti e barra di stato su schermi piccoli o font grandi).
    I widget devono essere figli di questa cornice e si aggiungono con
    aggiungi(); la disposizione e' fatta con place."""

    def __init__(self, master, spazio=2, margine=2, **kw):
        ttk.Frame.__init__(self, master, **kw)
        self.spazio = spazio
        self.margine = margine
        self.elementi = []
        self._ultima = None
        self._altezza = None
        self.bind("<Configure>", lambda ev: self.disponi())

    def aggiungi(self, w, prima=0):
        self.elementi.append((w, prima))
        return w

    def disponi(self):
        larg = self.winfo_width()
        if larg <= 1:
            larg = self.winfo_toplevel().winfo_width()
        m = self.margine
        larg_utile = max(1, larg - 2 * m)
        righe = []
        corrente = []
        x = 0
        alt = 0
        for w, prima in self.elementi:
            rw, rh = w.winfo_reqwidth(), w.winfo_reqheight()
            sp = (self.spazio + prima) if corrente else 0
            if corrente and x + sp + rw > larg_utile:
                righe.append((corrente, alt))
                corrente, x, alt, sp = [], 0, 0, 0
            x += sp
            corrente.append((w, x, rw, rh))
            x += rw
            alt = max(alt, rh)
        if corrente:
            righe.append((corrente, alt))
        posizioni = []
        y = m
        for riga, alt in righe:
            for w, x, rw, rh in riga:
                posizioni.append((w, m + x, y + (alt - rh) // 2, rw, rh))
            y += alt + self.spazio
        chiave = (larg, tuple((p[1], p[2], p[3], p[4]) for p in posizioni))
        if chiave == self._ultima:
            return
        self._ultima = chiave
        for w, x, yy, rw, rh in posizioni:
            w.place(x=x, y=yy, width=rw, height=rh)
        altezza = y - self.spazio + m if righe else 2 * m
        if altezza != self._altezza:
            self._altezza = altezza
            self.configure(height=altezza)


class PannelloScorrevole(ttk.Frame):
    """Cornice con barra di scorrimento verticale che compare solo quando il
    contenuto e' piu' alto della finestra: nessun controllo resta tagliato."""

    def __init__(self, master, **kw):
        ttk.Frame.__init__(self, master, **kw)
        sfondo = ""
        try:
            sfondo = ttk.Style(self).lookup("TFrame", "background")
        except tk.TclError:
            pass
        if not sfondo:
            sfondo = self.winfo_toplevel().cget("background")
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, background=sfondo)
        self.barra = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.barra.set)
        self.interno = ttk.Frame(self.canvas)
        self.canvas.create_window(0, 0, window=self.interno, anchor="nw")
        self.canvas.pack(side="left", fill="both", expand=True)
        self._barra_visibile = False
        self._larghezza = None
        self.interno.bind("<Configure>", lambda ev: self._aggiorna())
        self.canvas.bind("<Configure>", lambda ev: self._aggiorna())
        self.bind("<Enter>", lambda ev: self._rotella(True))
        self.bind("<Leave>", self._uscita)

    def _aggiorna(self):
        w = self.interno.winfo_reqwidth()
        h = self.interno.winfo_reqheight()
        if w != self._larghezza:
            self._larghezza = w
            self.canvas.configure(width=w)
        self.canvas.configure(scrollregion=(0, 0, w, h))
        serve = h > self.canvas.winfo_height() + 1 and self.canvas.winfo_height() > 1
        if serve and not self._barra_visibile:
            self.barra.pack(side="right", fill="y", before=self.canvas)
            self._barra_visibile = True
        elif not serve and self._barra_visibile:
            self.barra.pack_forget()
            self.canvas.yview_moveto(0)
            self._barra_visibile = False

    def _uscita(self, ev):
        # <Leave> arriva anche entrando in un widget interno: si disattiva la
        # rotella solo se il puntatore e' davvero fuori dal pannello
        try:
            w = self.winfo_containing(ev.x_root, ev.y_root)
        except (KeyError, tk.TclError):
            w = None
        while w is not None:
            if w is self:
                return
            w = w.master
        self._rotella(False)

    def _rotella(self, attiva):
        if attiva:
            self.bind_all("<MouseWheel>", self._scorri)
            self.bind_all("<Button-4>", self._scorri)
            self.bind_all("<Button-5>", self._scorri)
        else:
            for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.unbind_all(ev)

    def _scorri(self, ev):
        if not self._barra_visibile:
            return
        if getattr(ev, "num", None) == 4:
            passi = -1
        elif getattr(ev, "num", None) == 5:
            passi = 1
        else:
            passi = -1 if ev.delta > 0 else 1
        self.canvas.yview_scroll(passi * 3, "units")


def controlli_fuori(root):
    """Widget visibili che escono dalla finestra (esclusi quelli nel pannello
    scorrevole, raggiungibili con la barra).  Usata da test e screenshot."""
    rx, ry = root.winfo_rootx(), root.winfo_rooty()
    rw, rh = root.winfo_width(), root.winfo_height()
    fuori = []

    def visita(w, scorrevole):
        for f in w.winfo_children():
            if f.winfo_class() in ("Toplevel", "Menu"):
                continue
            sc = scorrevole or isinstance(w, PannelloScorrevole)
            if f.winfo_ismapped() and not sc:
                x, y = f.winfo_rootx() - rx, f.winfo_rooty() - ry
                if x < 0 or y < 0 or x + f.winfo_width() > rw + 1 or y + f.winfo_height() > rh + 1:
                    fuori.append("%s %s (%d,%d %dx%d)" % (f.winfo_class(), f, x, y, f.winfo_width(),
                                                          f.winfo_height()))
            visita(f, sc)

    visita(root, False)
    return fuori


def barra_scorrimento_visibile(w):
    if getattr(w, "_barra_visibile", False):
        return True
    return any(barra_scorrimento_visibile(f) for f in w.winfo_children())


class FinestraPrincipale(object):
    def __init__(self, root, cfg, modalita, cartella_programma, dispositivo_digidata=None, scala=None):
        self.root = root
        self.cfg = cfg
        self.modalita = modalita
        self.cartella_programma = cartella_programma
        self.log = registro.get()
        self.scala = scala if scala is not None else Scala(root, cfg["interfaccia.dimensione"])
        self.sessione = None
        self.dev_digidata = dispositivo_digidata
        self.sorgente_sim = None
        self.grafico = None
        self.contatore = 0
        self.ultimo_buffer = None
        self.errori_scrittura = []
        self._dopo_id = None
        self._taglio_dopo = None
        self.chiusura = False
        self.unita = "mV"
        self._t_disco = 0.0
        self._libero = None
        self._avviso = None
        self._testo_sorgente = ""
        self.contenitore = None
        self.par = filters.ParametriFiltro(cfg["filtro.tipo"], cfg["filtro.ordine"],
                                           cfg["filtro.taglio_hz"], cfg.notch(), cfg["filtro.q_notch"])
        root.title("denoising_live - %s" % ("SIMULAZIONE" if modalita == "simulazione" else "DIGIDATA 1322A"))
        root.protocol("WM_DELETE_WINDOW", self.chiudi)
        w, h, x, y = self.scala.geometria_iniziale()
        root.geometry("%dx%d+%d+%d" % (w, h, x, y))
        root.minsize(*self.scala.dimensione_minima())
        self.log.info("Dimensione interfaccia: %s", self.scala.descrizione())
        self._crea_variabili()
        self._costruisci()
        self._aggiorna_pulsanti()
        self._ciclo()

    # ------------------------------------------------------------------ layout
    def _crea_variabili(self):
        """Le variabili sopravvivono alla ricostruzione della finestra
        (cambio della dimensione dell'interfaccia)."""
        cfg = self.cfg
        self.var_marker = tk.StringVar()
        self.var_tipo = tk.StringVar(value=self.par.tipo)
        self.var_ordine = tk.StringVar(value=str(self.par.ordine))
        self.var_taglio = tk.DoubleVar(value=self.par.fc)
        self.var_notch = tk.StringVar(value=" ; ".join(("%g" % f).replace(".", ",") for f in self.par.notch))
        self.var_lpf8 = tk.StringVar(value=lpf8.testo_campo(cfg["lpf8.taglio_hz"]))
        val0 = cfg["grafico.finestra_s"]
        self.var_finestra = tk.StringVar(value=min(FINESTRE, key=lambda f: abs(f[1] - val0))[0])
        self.var_aggiornamento = tk.StringVar(value=_fmt_hz(cfg["grafico.aggiornamento_hz"]))
        self.var_auto = tk.StringVar(value=cfg["grafico.scala_y"])
        self.var_ymin = tk.StringVar(value=fmt_it(cfg["grafico.y_min"], 0))
        self.var_ymax = tk.StringVar(value=fmt_it(cfg["grafico.y_max"], 0))
        self.var_dimensione = tk.StringVar(value=self._nome_dimensione())

    def _nomi_dimensione(self):
        return ["Automatica (%d %%)" % self.scala.percento_auto] + ["%d %%" % p for p in SCELTE_PERCENTO]

    def _nome_dimensione(self):
        if self.scala.manuale is None:
            return "Automatica (%d %%)" % self.scala.percento_auto
        return "%d %%" % self.scala.manuale

    def _costruisci(self):
        r = self.root
        sc = self.scala
        px = sc.px
        fnt = sc.font
        cont = self.contenitore = ttk.Frame(r)
        cont.pack(fill="both", expand=True)

        # barra dei pulsanti: va a capo se la finestra e' stretta
        barra = self.barra = RigaAdattabile(cont, spazio=px(3), margine=px(4))
        barra.pack(side="top", fill="x")
        self.btn_anteprima = barra.aggiungi(ttk.Button(barra, text="Avvia anteprima", command=self.avvia_anteprima))
        self.btn_reg = barra.aggiungi(ttk.Button(barra, text="Avvia registrazione", command=self.avvia_registrazione))
        self.btn_ferma = barra.aggiungi(ttk.Button(barra, text="Ferma", command=self.ferma))
        if self.modalita == "simulazione":
            barra.aggiungi(ttk.Button(barra, text="Sorgente simulazione...", command=self.scegli_sorgente),
                           prima=px(8))
        barra.aggiungi(ttk.Label(barra, text="Marker:"), prima=px(10))
        e = barra.aggiungi(ttk.Entry(barra, textvariable=self.var_marker, width=22))
        e.bind("<Return>", lambda ev: self.aggiungi_marker())
        barra.aggiungi(ttk.Button(barra, text="Aggiungi marker", command=self.aggiungi_marker))
        barra.aggiungi(ttk.Button(barra, text="Cartella dati...", command=self.scegli_cartella), prima=px(10))
        barra.aggiungi(ttk.Label(barra, text="Dimensione interfaccia:"), prima=px(10))
        nomi = self._nomi_dimensione()
        cbd = barra.aggiungi(ttk.Combobox(barra, textvariable=self.var_dimensione, values=nomi,
                                          width=max(len(n) for n in nomi), state="readonly"))
        cbd.bind("<<ComboboxSelected>>", lambda ev: self.cambia_dimensione())

        self.lbl_avviso = tk.Label(cont, text="", bg="#c00000", fg="white", font=fnt["DliveGrassetto"],
                                   anchor="w", justify="left", padx=px(6), pady=px(2))
        self.lbl_avviso.bind("<Button-1>", lambda ev: self._nascondi_avviso())
        cont.bind("<Configure>", lambda ev: self.lbl_avviso.config(wraplength=max(100, ev.width - px(20))))

        # barra di stato (in basso, impacchettata prima del corpo perche'
        # resti visibile anche con la finestra bassa)
        stato_cornice = ttk.Frame(cont, relief="sunken", borderwidth=1)
        stato_cornice.pack(side="bottom", fill="x")
        stato = RigaAdattabile(stato_cornice, spazio=px(6), margine=px(2))
        stato.pack(fill="x")
        self.campi = {}
        for nome, larg in (("modalita", 11), ("reg", 13), ("file", 17), ("tempo", 9), ("persi", 9),
                           ("disco", 15), ("sat", 15), ("lpf8", 13), ("calcolo", 11)):
            self.campi[nome] = stato.aggiungi(ttk.Label(stato, text="", width=larg, anchor="w"))

        corpo = ttk.Frame(cont)
        corpo.pack(side="top", fill="both", expand=True)

        # pannello destro (scorrevole se non ci sta in altezza)
        pannello = PannelloScorrevole(corpo)
        pannello.pack(side="right", fill="y")
        dx = ttk.Frame(pannello.interno, padding=(px(8), px(6), px(8), px(6)))
        dx.pack(fill="both", expand=True)
        a_capo = fnt["DlivePiccolo"].measure("0") * 34      # larghezza dei testi lunghi

        self.canvas = tk.Canvas(corpo, bg=COL_SFONDO, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", self._ridimensiona)
        self.grafico = Grafico(self.canvas, sc)

        ttk.Label(dx, text="Filtrato attuale", font=fnt["DliveGrassetto"]).pack(anchor="w")
        self.lbl_valore = tk.Label(dx, text="- %s" % self.unita, font=fnt["DliveValore"], fg=COL_FILTRATO,
                                   width=9, anchor="e")
        self.lbl_valore.pack(anchor="w", fill="x", pady=(0, px(6)))

        pad_gr = px(6)
        lf = ttk.LabelFrame(dx, text="Filtro digitale", padding=pad_gr)
        lf.pack(fill="x", pady=px(3))
        lf.columnconfigure(3, weight=1)
        ttk.Label(lf, text="Tipo").grid(row=0, column=0, sticky="w", padx=(0, px(6)))
        cb = ttk.Combobox(lf, textvariable=self.var_tipo, values=list(filters.TIPI), width=12, state="readonly")
        cb.grid(row=0, column=1, columnspan=3, sticky="w", pady=px(1))
        cb.bind("<<ComboboxSelected>>", lambda ev: self.applica_filtro())
        ttk.Label(lf, text="Ordine").grid(row=1, column=0, sticky="w", padx=(0, px(6)))
        sp = tk.Spinbox(lf, from_=1, to=filters.ORDINE_MAX, textvariable=self.var_ordine, width=4,
                        command=self.applica_filtro)
        sp.grid(row=1, column=1, sticky="w", pady=px(1))
        sp.bind("<Return>", lambda ev: self.applica_filtro())
        ttk.Label(lf, text="Taglio (Hz)").grid(row=2, column=0, columnspan=4, sticky="w", pady=(px(4), 0))
        self.scala_taglio = tk.Scale(lf, from_=0.5, to=30.0, resolution=0.1, orient="horizontal",
                                     variable=self.var_taglio, length=px(200), width=px(14),
                                     sliderlength=px(28), showvalue=True, command=self._taglio_mosso)
        self.scala_taglio.grid(row=3, column=0, columnspan=4, sticky="we")
        fp = ttk.Frame(lf)
        fp.grid(row=4, column=0, columnspan=4, sticky="w")
        for v in PRESET_TAGLIO:
            ttk.Button(fp, text="%g Hz" % v, width=5,
                       command=lambda v=v: self.imposta_taglio(v)).pack(side="left", padx=(0, px(2)))
        ttk.Label(lf, text="Notch (Hz)").grid(row=5, column=0, sticky="w", padx=(0, px(6)), pady=(px(6), 0))
        en = ttk.Entry(lf, textvariable=self.var_notch, width=10)
        en.grid(row=5, column=1, columnspan=2, sticky="w", pady=(px(6), 0))
        en.bind("<Return>", lambda ev: self.applica_filtro())
        ttk.Button(lf, text="Applica", command=self.applica_filtro).grid(row=5, column=3, sticky="e",
                                                                       padx=(px(4), 0), pady=(px(6), 0))
        self.lbl_filtro_info = ttk.Label(lf, text="", foreground="#555555", wraplength=a_capo,
                                         font=fnt["DlivePiccolo"])
        self.lbl_filtro_info.grid(row=6, column=0, columnspan=4, sticky="w", pady=(px(4), 0))

        lf2 = ttk.LabelFrame(dx, text="Filtro analogico LPF-8", padding=pad_gr)
        lf2.pack(fill="x", pady=px(3))
        lf2.columnconfigure(2, weight=1)
        ttk.Label(lf2, text="Taglio LPF-8 (Hz)").grid(row=0, column=0, sticky="w", padx=(0, px(6)))
        e8 = ttk.Entry(lf2, textvariable=self.var_lpf8, width=6)
        e8.grid(row=0, column=1, sticky="w")
        e8.bind("<Return>", lambda ev: self.applica_lpf8())
        ttk.Button(lf2, text="Applica", command=self.applica_lpf8).grid(row=0, column=2, sticky="e",
                                                                      padx=(px(4), 0))

        lf3 = ttk.LabelFrame(dx, text="Grafico", padding=pad_gr)
        lf3.pack(fill="x", pady=px(3))
        ttk.Label(lf3, text="Finestra").grid(row=0, column=0, sticky="w", padx=(0, px(6)))
        cbf = ttk.Combobox(lf3, textvariable=self.var_finestra, values=[f[0] for f in FINESTRE],
                           width=7, state="readonly")
        cbf.grid(row=0, column=1, columnspan=3, sticky="w", pady=px(1))
        cbf.bind("<<ComboboxSelected>>", lambda ev: self._cambia_finestra())
        ttk.Label(lf3, text="Aggiornamento (Hz)").grid(row=1, column=0, sticky="w", padx=(0, px(6)))
        valori = [_fmt_hz(v) for v in AGGIORNAMENTI_HZ]
        if self.var_aggiornamento.get() not in valori:      # valore diverso scritto in config.ini
            valori.append(self.var_aggiornamento.get())
        cba = ttk.Combobox(lf3, textvariable=self.var_aggiornamento, values=valori, width=7,
                           state="readonly")
        cba.grid(row=1, column=1, columnspan=3, sticky="w", pady=px(1))
        cba.bind("<<ComboboxSelected>>", lambda ev: self.cambia_aggiornamento())
        ttk.Radiobutton(lf3, text="Scala Y automatica", value="auto", variable=self.var_auto,
                        command=self._cambia_scala).grid(row=2, column=0, columnspan=4, sticky="w")
        ttk.Radiobutton(lf3, text="Scala Y fissa:", value="fissa", variable=self.var_auto,
                        command=self._cambia_scala).grid(row=3, column=0, columnspan=4, sticky="w")
        fy = ttk.Frame(lf3)
        fy.grid(row=4, column=0, columnspan=4, sticky="w", padx=(px(20), 0))
        ttk.Label(fy, text="min").pack(side="left")
        e1 = ttk.Entry(fy, textvariable=self.var_ymin, width=6)
        e1.pack(side="left", padx=(px(3), px(8)))
        ttk.Label(fy, text="max").pack(side="left")
        e2 = ttk.Entry(fy, textvariable=self.var_ymax, width=6)
        e2.pack(side="left", padx=(px(3), 0))
        for e_ in (e1, e2):
            e_.bind("<Return>", lambda ev: self._cambia_scala())
        ttk.Label(lf3, text="grigio = grezzo, rosso = filtrato", foreground="#555555",
                  font=fnt["DlivePiccolo"]).grid(row=5, column=0, columnspan=4, sticky="w", pady=(px(4), 0))

        self.lbl_sorgente = ttk.Label(dx, text=self._testo_sorgente, wraplength=a_capo, foreground="#333333",
                                      font=fnt["DlivePiccolo"])
        self.lbl_sorgente.pack(fill="x", pady=(px(6), 0))

        if self._avviso is not None:
            self.mostra_avviso(*self._avviso)
        self._aggiorna_info_filtro()
        self._cambia_scala()

    def _ricostruisci_finestra(self):
        """Ricrea tutti i controlli con la nuova dimensione (le impostazioni e
        l'acquisizione in corso non cambiano: la GUI legge solo il buffer)."""
        vecchio = self.contenitore
        self.ultimo_buffer = None
        if vecchio is not None:
            vecchio.destroy()
        self._costruisci()
        self._aggiorna_pulsanti()
        self._aggiorna()

    def cambia_dimensione(self):
        nome = self.var_dimensione.get()
        if nome.startswith("Automatica"):
            valore = "auto"
        else:
            valore = nome.replace("%", "").strip()
        self.cfg.imposta("interfaccia.dimensione", valore)
        self._salva_config()
        self.scala.imposta(valore)
        self.var_dimensione.set(self._nome_dimensione())
        self.log.info("Dimensione interfaccia: %s", self.scala.descrizione())
        try:
            self._ricostruisci_finestra()
        except Exception:
            self.log.exception("Ricostruzione della finestra non riuscita")
            messagebox.showinfo("Dimensione interfaccia",
                                "La nuova dimensione sara' applicata al prossimo avvio.")

    # ---------------------------------------------------------------- azioni
    def _ridimensiona(self, ev):
        self.grafico.larghezza = ev.width
        self.grafico.altezza = ev.height
        self._ricostruisci_grafico()

    def _finestra_s(self):
        for nome, v in FINESTRE:
            if nome == self.var_finestra.get():
                return v
        return 30.0

    def _cambia_finestra(self):
        self._ricostruisci_grafico()

    def cambia_aggiornamento(self, valore=None):
        """Aggiornamenti del grafico al secondo: effetto al prossimo giro di
        _ciclo (che rilegge la configurazione), valore salvato in config.ini."""
        if valore is not None:
            self.var_aggiornamento.set(_fmt_hz(valore))
        try:
            v = leggi_float(self.var_aggiornamento.get())
        except ValueError:
            return
        if not (0.5 <= v <= 50):
            return
        if v == self.cfg["grafico.aggiornamento_hz"]:
            return
        self.cfg.imposta("grafico.aggiornamento_hz", v)
        self._salva_config()
        self.log.info("Aggiornamento del grafico: %s Hz", _fmt_hz(v))

    def _ricostruisci_grafico(self):
        g = self.grafico
        buf = self.sessione.grafico if self.sessione is not None else None
        g.configura(self._finestra_s(), buf.dt_secchio if buf is not None else 0.01)
        if buf is not None:
            n_secchi = int(self._finestra_s() / buf.dt_secchio) + g.secchi_per_colonna
            c, secchi = buf.preleva(buf.contatore - n_secchi)
            self.contatore = c
            g.aggiungi_secchi(secchi)
        g.disegna()

    def _cambia_scala(self):
        g = self.grafico
        if self.var_auto.get() == "fissa":
            try:
                lo = leggi_float(self.var_ymin.get())
                hi = leggi_float(self.var_ymax.get())
                if hi <= lo:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Scala Y", "Limiti della scala non validi (min < max).")
                return
            g.auto = False
            g.ymin, g.ymax = lo, hi
        else:
            g.auto = True
        g._ultimo_ridisegno_assi = None
        g.disegna()

    def _taglio_mosso(self, valore):
        # applica dopo una breve pausa del cursore (effetto immediato senza
        # riprogettare il filtro a ogni pixel)
        if self._taglio_dopo is not None:
            self.root.after_cancel(self._taglio_dopo)
        self._taglio_dopo = self.root.after(250, self.applica_filtro)

    def imposta_taglio(self, v):
        self.var_taglio.set(v)
        self.applica_filtro()

    def _leggi_parametri(self):
        notch = []
        testo = self.var_notch.get().strip()
        if testo:
            for parte in testo.replace("|", ";").split(";"):
                if parte.strip():
                    notch.append(leggi_float(parte))
        return filters.ParametriFiltro(self.var_tipo.get(), int(float(self.var_ordine.get())),
                                       float(self.var_taglio.get()), notch, self.par.q_notch)

    def _fs_correnti(self):
        if self.sessione is not None and self.sessione.fs:
            return self.sessione.fs, self.sessione.fs / self.sessione.dec
        if self.modalita == "digidata":
            return self.cfg["digidata.frequenza_acquisizione_hz"], self.cfg["salvataggio.frequenza_salvataggio_hz"]
        if self.sorgente_sim is not None and self.sorgente_sim.fs:
            return self.sorgente_sim.fs, min(self.sorgente_sim.fs, self.cfg["salvataggio.frequenza_salvataggio_hz"])
        return 1000.0, self.cfg["salvataggio.frequenza_salvataggio_hz"]

    def applica_filtro(self):
        self._taglio_dopo = None
        try:
            par = self._leggi_parametri()
        except ValueError:
            messagebox.showerror("Filtro", "Valori del filtro non validi (notch: numeri separati da ';').")
            return
        if par == self.par:
            return
        fa, fsv = self._fs_correnti()
        errori, avvisi = filters.controlla_parametri(par, fa, fsv, self._lpf8())
        if errori:
            messagebox.showerror("Filtro", "\n".join(errori))
            self._ripristina_controlli_filtro()
            return
        for a in avvisi:
            self.log.warning("Avviso filtro: %s", a)
        if avvisi:
            self.mostra_avviso("Attenzione: " + " ".join(avvisi), colore="#b36b00")
        self.par = par
        if self.sessione is not None and self.sessione.in_corso:
            self.sessione.imposta_filtro(par)
        else:
            self.log.info("Filtro impostato: %s", par.descrizione())
        self.cfg.imposta("filtro.tipo", par.tipo)
        self.cfg.imposta("filtro.ordine", par.ordine)
        self.cfg.imposta("filtro.taglio_hz", par.fc)
        self.cfg.imposta("filtro.notch_hz", " ; ".join(("%g" % f).replace(".", ",") for f in par.notch))
        self._salva_config()
        self._aggiorna_info_filtro()

    def _ripristina_controlli_filtro(self):
        self.var_tipo.set(self.par.tipo)
        self.var_ordine.set(str(self.par.ordine))
        self.var_taglio.set(self.par.fc)
        self.var_notch.set(" ; ".join(("%g" % f).replace(".", ",") for f in self.par.notch))

    def _aggiorna_info_filtro(self):
        fa, fsv = self._fs_correnti()
        try:
            t50, sovra, _ = filters.ritardo_gradino(self.par, fa)
            att = filters.attenuazione_db(filters.progetta_passabasso(self.par.tipo, self.par.ordine,
                                                                      self.par.fc, fa), 25.0, fa) \
                if 25.0 < fa / 2 else float("nan")
            self.lbl_filtro_info.config(text="ritardo %s ms, sovraelongazione %s %%, -%s dB a 25 Hz" % (
                fmt_it(t50 * 1000, 0), fmt_it(sovra, 1), fmt_it(att, 0)))
        except Exception as e:
            self.lbl_filtro_info.config(text=str(e))

    def _lpf8(self):
        """Taglio LPF-8 dichiarato nel campo (0 = Bypass), None se illeggibile."""
        try:
            return lpf8.leggi_taglio(self.var_lpf8.get())
        except ValueError:
            return None

    def _avvisi_lpf8(self, v):
        fa, _ = self._fs_correnti()
        return lpf8.controlla(v, fa, self.cfg["lpf8.guadagno"], self.cfg["calibrazione.yg"],
                              self.cfg["calibrazione.unita"])

    def applica_lpf8(self):
        v = self._lpf8()
        errori, avvisi = self._avvisi_lpf8(v) if v is not None else (
            ["Valore del taglio LPF-8 non valido: scrivere i Hz (es. 15 oppure 15,5) o Bypass."], [])
        if errori:
            messagebox.showerror("LPF-8", "\n".join(errori) + "\n\nValori dell'LPF-8: 0,1-199,9 Hz a passi "
                                 "di 0,1 Hz; 200-19990 Hz a passi di 10 Hz; Bypass.")
            return
        for a in avvisi:
            self.log.warning("LPF-8: %s", a)
        self.cfg.imposta("lpf8.taglio_hz", v)
        self._salva_config()
        if self.sessione is not None and self.sessione.in_corso:
            self.sessione.imposta_lpf8(v)
        self.log.info("Taglio LPF-8 dichiarato: %s", lpf8.descrizione(v))
        if self.par.passabasso_attivo and v != lpf8.BYPASS and self.par.fc > v:
            avvisi.append("il taglio digitale (%s Hz) e' superiore a quello dell'LPF-8 (%s Hz)"
                          % (fmt_it(self.par.fc), fmt_it(v)))
        if avvisi:
            self.mostra_avviso("Attenzione: " + " ".join(avvisi), colore="#b36b00")

    def _salva_config(self):
        try:
            self.cfg.salva()
        except Exception as e:
            self.log.warning("Impossibile salvare la configurazione: %s", e)

    def scegli_cartella(self):
        if self.sessione is not None and self.sessione.reg is not None:
            messagebox.showinfo("Cartella dati", "Fermare la registrazione prima di cambiare cartella.")
            return
        d = filedialog.askdirectory(initialdir=self._cartella_dati(), title="Cartella dove salvare le registrazioni")
        if d:
            self.cfg.imposta("generale.cartella_dati", d)
            self._salva_config()
            self.log.info("Cartella dati: %s", d)

    def _cartella_dati(self):
        return self.cfg.percorso_assoluto("generale.cartella_dati")

    def scegli_sorgente(self):
        if self.sessione is not None and self.sessione.in_corso:
            messagebox.showinfo("Simulazione", "Fermare l'acquisizione prima di cambiare sorgente.")
            return False
        d = DialogoSorgente(self.root, self.cfg, self.scala)
        if not d.risultato:
            return False
        r = d.risultato
        try:
            dev = SimulatedDevice(r["file"], record=r["record"], canale=r["canale"], velocita=r["velocita"],
                                  salta_coda=r["salta_coda"], sovracampiona=r["sovracampiona"],
                                  fs_sovracampionamento=self.cfg["simulazione.frequenza_sovracampionamento_hz"],
                                  rumore=r["rumore"])
            dev.apri()
        except ErroreDispositivo as e:
            messagebox.showerror("Simulazione", e.messaggio)
            return False
        self.sorgente_sim = dev
        for k, chiave in (("file", "simulazione.file"), ("record", "simulazione.record"),
                          ("canale", "simulazione.canale"), ("velocita", "simulazione.velocita"),
                          ("salta_coda", "simulazione.salta_coda"), ("sovracampiona", "simulazione.sovracampiona"),
                          ("rumore", "simulazione.rumore_sintetico")):
            self.cfg.imposta(chiave, r[k])
        self.cfg.imposta("simulazione.cartella", os.path.dirname(r["file"]))
        self._salva_config()
        self._testo_sorgente = dev.descrizione() + " (durata %s)" % fmt_durata(dev.durata_sorgente())
        self.lbl_sorgente.config(text=self._testo_sorgente)
        self._aggiorna_info_filtro()
        return True

    def _crea_sessione(self):
        if self.modalita == "simulazione":
            if self.sorgente_sim is None:
                f = self.cfg["simulazione.file"]
                if f and os.path.isfile(f):
                    try:
                        dev = SimulatedDevice(f, record=self.cfg["simulazione.record"],
                                              canale=self.cfg["simulazione.canale"],
                                              velocita=self.cfg["simulazione.velocita"],
                                              salta_coda=self.cfg["simulazione.salta_coda"],
                                              sovracampiona=self.cfg["simulazione.sovracampiona"],
                                              fs_sovracampionamento=self.cfg["simulazione.frequenza_sovracampionamento_hz"],
                                              rumore=self.cfg["simulazione.rumore_sintetico"])
                        dev.apri()
                        self.sorgente_sim = dev
                        self._testo_sorgente = dev.descrizione()
                        self.lbl_sorgente.config(text=self._testo_sorgente)
                    except ErroreDispositivo:
                        self.sorgente_sim = None
                if self.sorgente_sim is None and not self.scegli_sorgente():
                    return None
            dev = self.sorgente_sim
        else:
            dev = self.dev_digidata
        c = self.cfg
        return Sessione(dev, self.par,
                        {"cartella": self._cartella_dati(),
                         "fs_salvataggio": c["salvataggio.frequenza_salvataggio_hz"],
                         "durata_record_s": c["salvataggio.durata_record_s"],
                         "separatore": c.separatore()},
                        lpf8_taglio=self._lpf8() if self._lpf8() is not None else c["lpf8.taglio_hz"], lpf8_guadagno=c["lpf8.guadagno"],
                        soglia_saturazione=c["filtro.soglia_saturazione"],
                        soglia_picchi_unita=c["filtro.soglia_picchi_mv"],
                        durata_max_picco_s=c["filtro.durata_max_picco_ms"] / 1000.0,
                        intervallo_scrittura=c["salvataggio.intervallo_scrittura_s"],
                        spazio_minimo_mb=c["generale.spazio_minimo_mb"])

    def avvia_anteprima(self):
        if self.sessione is not None and self.sessione.in_corso:
            return
        s = self._crea_sessione()
        if s is None:
            return
        try:
            self.root.config(cursor="watch")
            self.root.update_idletasks()
            s.avvia_anteprima()
        except ErroreDispositivo as e:
            self.log.error("Avvio fallito: %s", e.messaggio)
            messagebox.showerror("Avvio non riuscito", e.messaggio)
            return
        except Exception as e:
            self.log.exception("Avvio fallito")
            messagebox.showerror("Avvio non riuscito", "%s: %s" % (type(e).__name__, e))
            return
        finally:
            self.root.config(cursor="")
        self.sessione = s
        v8 = self._lpf8()
        if v8 is not None:
            err8, avv8 = self._avvisi_lpf8(v8)
            for a in err8 + avv8:
                self.log.warning("LPF-8: %s", a)
            if err8 + avv8:
                self.mostra_avviso("LPF-8: " + " ".join(err8 + avv8), colore="#b36b00")
        self.unita = s.cal.get("unita", "mV")
        self.grafico.unita = self.unita
        self.errori_scrittura = []
        self._ricostruisci_grafico()
        self._aggiorna_pulsanti()
        self._aggiorna_info_filtro()

    def avvia_registrazione(self):
        cartella = self._cartella_dati()
        libero = sysinfo.spazio_libero_mb(cartella)
        minimo = self.cfg["generale.spazio_minimo_mb"]
        if libero is not None and libero < minimo:
            messagebox.showerror("Spazio insufficiente",
                                 "Nella cartella %s ci sono solo %.0f MB liberi (minimo %d MB).\n"
                                 "Scegliere un'altra cartella (Cartella dati...)." % (cartella, libero, minimo))
            return
        try:
            if not os.path.isdir(cartella):
                os.makedirs(cartella)
            prova = os.path.join(cartella, "_prova_scrittura.tmp")
            with open(prova, "wb") as f:
                f.write(b"x")
            os.remove(prova)
        except (IOError, OSError) as e:
            messagebox.showerror("Cartella non scrivibile", "Impossibile scrivere in %s:\n%s" % (cartella, e))
            return
        if self.sessione is None or not self.sessione.in_corso:
            self.avvia_anteprima()
            if self.sessione is None or not self.sessione.in_corso:
                return
        self.sessione.avvia_registrazione()
        self._aggiorna_pulsanti()

    def ferma(self):
        if self.sessione is None:
            return
        if self.sessione.reg is not None:
            if not messagebox.askyesno("Ferma", "Fermare la registrazione in corso?"):
                return
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        try:
            self.sessione.ferma()
        finally:
            self.root.config(cursor="")
        self._svuota_messaggi()
        self._aggiorna_pulsanti()

    def aggiungi_marker(self):
        testo = self.var_marker.get().strip()
        if not testo:
            testo = time.strftime("%H:%M:%S")
        if self.sessione is None or not self.sessione.in_corso:
            messagebox.showinfo("Marker", "Il marker si aggiunge durante l'anteprima o la registrazione.")
            return
        self.sessione.marker(testo)
        self.var_marker.set("")

    def mostra_avviso(self, testo, colore="#c00000"):
        self._avviso = (testo, colore)
        self.lbl_avviso.config(text=testo + "   (clic per nascondere)", bg=colore)
        if not self.lbl_avviso.winfo_ismapped():
            self.lbl_avviso.pack(side="top", fill="x", after=self.barra)

    def _nascondi_avviso(self):
        self._avviso = None
        self.lbl_avviso.pack_forget()

    def _aggiorna_pulsanti(self):
        attiva = self.sessione is not None and self.sessione.in_corso
        reg = attiva and (self.sessione.reg is not None or self.sessione._reg_pendente)
        self.btn_anteprima.config(state="disabled" if attiva else "normal")
        self.btn_reg.config(state="disabled" if reg else "normal")
        self.btn_ferma.config(state="normal" if attiva else "disabled")

    def _svuota_messaggi(self):
        if self.sessione is None:
            return
        while True:
            try:
                tipo, testo = self.sessione.messaggi.get_nowait()
            except queue.Empty:
                break
            if tipo == "errore":
                self.mostra_avviso(testo)
                if not (self.sessione and self.sessione.in_corso):
                    messagebox.showerror("Errore", testo)
            elif tipo == "errore_scrittura":
                self.errori_scrittura.append(testo)
                self.mostra_avviso("ERRORE DI SCRITTURA SU DISCO: %s  - l'acquisizione continua, i dati "
                                   "restano in memoria e si riprova; controllare il disco o fermare e "
                                   "cambiare cartella." % testo)
            elif tipo == "avviso_disco":
                self.mostra_avviso(testo, colore="#b36b00")
            elif tipo == "persi":
                self.mostra_avviso("Campioni persi: %d (il PC non ha letto in tempo il buffer della scheda)" % testo,
                                   colore="#b36b00")

    # ------------------------------------------------------------------ ciclo
    def _ciclo(self):
        if self.chiusura:
            return
        t0 = time.time()
        try:
            self._aggiorna()
        except Exception:
            self.log.exception("Errore nell'aggiornamento della finestra")
        dt = 1000.0 / max(1.0, self.cfg["grafico.aggiornamento_hz"])
        trascorso = (time.time() - t0) * 1000.0
        self._dopo_id = self.root.after(int(max(20, dt - trascorso)), self._ciclo)

    def _aggiorna(self):
        s = self.sessione
        self._svuota_messaggi()
        if s is not None and s.grafico is not None:
            buf = s.grafico
            if buf is not self.ultimo_buffer:
                self.ultimo_buffer = buf
                self._ricostruisci_grafico()
            c, nuovi = buf.preleva(self.contatore)
            self.contatore = c
            if nuovi:
                self.grafico.aggiungi_secchi(nuovi)
                self.grafico.disegna()
            if buf.ultimo_filtrato is not None:
                self.lbl_valore.config(text="%s %s" % (fmt_it(buf.ultimo_filtrato, 1), self.unita))
        st = s.stato() if s is not None else {}
        attiva = bool(st.get("in_corso"))
        self.campi["modalita"].config(text="SIMULAZIONE" if self.modalita == "simulazione" else "DIGIDATA")
        if attiva and st.get("registrazione"):
            self.campi["reg"].config(text="REGISTRAZIONE", foreground="#c00000")
        elif attiva:
            self.campi["reg"].config(text="anteprima", foreground="#006000")
        else:
            self.campi["reg"].config(text="fermo", foreground="#000000")
        self.campi["file"].config(text=("File: %s" % st["file"]) if st.get("file") else "File: -")
        tempo = st.get("tempo_reg_s") if st.get("registrazione") else st.get("tempo_s")
        self.campi["tempo"].config(text="t %s" % fmt_durata(tempo or 0))
        persi = st.get("persi", 0)
        self.campi["persi"].config(text="Persi: %d" % persi, foreground="#c00000" if persi else "#000000")
        libero = st.get("spazio_libero_mb")
        if libero is None:
            if time.time() - self._t_disco > 5.0:
                self._t_disco = time.time()
                self._libero = sysinfo.spazio_libero_mb(self._cartella_dati())
            libero = self._libero
        self.campi["disco"].config(text="Disco: %s MB" % (fmt_num(libero, 0) if libero is not None else "?"),
                                   foreground="#c00000" if (libero is not None and
                                                            libero < self.cfg["generale.spazio_minimo_mb"]) else "#000000")
        self.campi["sat"].config(text="Saturazioni: %d" % st.get("saturazioni", 0))
        v8 = self._lpf8()
        self.campi["lpf8"].config(text="LPF-8 %s" % (lpf8.descrizione(v8) if v8 is not None else "?"))
        self.campi["calcolo"].config(text="numpy" if compat.ha_numpy() else "Python puro")
        self._aggiorna_pulsanti()

    def chiudi(self):
        if self.sessione is not None and self.sessione.in_corso:
            msg = "Registrazione in corso: fermarla e uscire?" if self.sessione.reg is not None \
                else "Fermare l'acquisizione e uscire?"
            if not messagebox.askyesno("Uscita", msg):
                return
        self.chiudi_senza_conferma()

    def chiudi_senza_conferma(self):
        if self.sessione is not None and self.sessione.in_corso:
            self.sessione.ferma()
        self.chiusura = True
        if self._dopo_id is not None:
            try:
                self.root.after_cancel(self._dopo_id)
            except Exception:
                pass
        self.log.info("Finestra chiusa")
        self.root.destroy()


class DialogoSorgente(object):
    """Scelta di file, record e canale per la simulazione."""

    def __init__(self, parent, cfg, scala=None):
        self.cfg = cfg
        px = scala.px if scala is not None else (lambda n: n)
        self.risultato = None
        t = self.top = tk.Toplevel(parent)
        t.title("Sorgente della simulazione")
        t.transient(parent)
        f = ttk.Frame(t, padding=px(10))
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)
        self.var_file = tk.StringVar(value=cfg["simulazione.file"])
        ttk.Label(f, text="File .wcp").grid(row=0, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.var_file, width=40).grid(row=0, column=1, sticky="we")
        ttk.Button(f, text="Sfoglia...", command=self._sfoglia).grid(row=0, column=2, padx=px(4))
        self.lbl_info = ttk.Label(f, text="", foreground="#333333", wraplength=px(480))
        self.lbl_info.grid(row=1, column=0, columnspan=3, sticky="w", pady=px(4))
        ttk.Label(f, text="Record (0 = tutti)").grid(row=2, column=0, sticky="w")
        self.var_record = tk.StringVar(value=str(cfg["simulazione.record"]))
        tk.Spinbox(f, from_=0, to=9999, textvariable=self.var_record, width=6).grid(row=2, column=1, sticky="w")
        ttk.Label(f, text="Canale (-1 = automatico)").grid(row=3, column=0, sticky="w")
        self.var_canale = tk.StringVar(value=str(cfg["simulazione.canale"]))
        tk.Spinbox(f, from_=-1, to=15, textvariable=self.var_canale, width=6).grid(row=3, column=1, sticky="w")
        ttk.Label(f, text="Velocita'").grid(row=4, column=0, sticky="w")
        self.var_vel = tk.StringVar(value="%gx" % cfg["simulazione.velocita"])
        ttk.Combobox(f, textvariable=self.var_vel, values=["1x", "5x", "20x"], width=6).grid(row=4, column=1, sticky="w")
        self.var_coda = tk.BooleanVar(value=cfg["simulazione.salta_coda"])
        self.var_sovra = tk.BooleanVar(value=cfg["simulazione.sovracampiona"])
        self.var_rumore = tk.BooleanVar(value=cfg["simulazione.rumore_sintetico"])
        ttk.Checkbutton(f, text="Salta la coda costante dei record fermati prima", variable=self.var_coda).grid(
            row=5, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(f, text="Sovracampiona a %g Hz (stessa catena della modalita' Digidata)" %
                        cfg["simulazione.frequenza_sovracampionamento_hz"], variable=self.var_sovra).grid(
            row=6, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(f, text="Aggiungi rumore sintetico (50, 8,7, 37,4 Hz, banda 25-50 Hz, picchi)",
                        variable=self.var_rumore).grid(row=7, column=0, columnspan=3, sticky="w")
        b = ttk.Frame(f)
        b.grid(row=8, column=0, columnspan=3, pady=(px(10), 0))
        ttk.Button(b, text="OK", command=self._ok).pack(side="left", padx=px(4))
        ttk.Button(b, text="Annulla", command=t.destroy).pack(side="left", padx=px(4))
        self.var_file.trace("w", lambda *a: self._info())
        self._info()
        t.grab_set()
        parent.wait_window(t)

    def _sfoglia(self):
        cartella = self.cfg.percorso_assoluto("simulazione.cartella")
        p = filedialog.askopenfilename(parent=self.top, initialdir=cartella, title="File .wcp da riprodurre",
                                       filetypes=[("File WinWCP", "*.wcp"), ("Tutti i file", "*.*")])
        if p:
            self.var_file.set(p)

    def _info(self):
        p = self.var_file.get()
        if not p or not os.path.isfile(p):
            self.lbl_info.config(text="Scegliere un file .wcp (dati di prova in riferimenti/dati)")
            return
        try:
            from . import wcpfile
            w = wcpfile.leggi_wcp(p, solo_intestazione=True)
            self.lbl_info.config(text="%d canali, %d record, %.4g Hz, %d campioni per record" % (
                w.nc, w.nr, 1.0 / w.dt if w.dt else 0, w.campioni_per_record))
        except Exception as e:
            self.lbl_info.config(text="File non leggibile: %s" % e)

    def _ok(self):
        try:
            vel = float(self.var_vel.get().lower().replace("x", "").replace(",", "."))
            self.risultato = {"file": self.var_file.get(), "record": int(self.var_record.get()),
                              "canale": int(self.var_canale.get()), "velocita": vel,
                              "salta_coda": bool(self.var_coda.get()),
                              "sovracampiona": bool(self.var_sovra.get()),
                              "rumore": bool(self.var_rumore.get())}
        except ValueError:
            messagebox.showerror("Simulazione", "Valori non validi", parent=self.top)
            return
        if not os.path.isfile(self.risultato["file"]):
            messagebox.showerror("Simulazione", "File non trovato", parent=self.top)
            self.risultato = None
            return
        self.top.destroy()


def chiedi_modalita(root, scala=None):
    """Finestra iniziale: simulazione o Digidata."""
    px = scala.px if scala is not None else (lambda n: n)
    scelta = {"v": None}
    t = tk.Toplevel(root)
    t.title("denoising_live")
    f = ttk.Frame(t, padding=px(16))
    f.pack()
    titolo = scala.font["DliveTitolo"] if scala is not None else ("TkDefaultFont", 11, "bold")
    ttk.Label(f, text="Scegliere la modalita'", font=titolo).pack(pady=(0, px(10)))

    def scegli(v):
        scelta["v"] = v
        t.destroy()

    ttk.Button(f, text="Digidata 1322A (PC del laboratorio)", width=36,
               command=lambda: scegli("digidata")).pack(pady=px(3), fill="x")
    ttk.Button(f, text="Simulazione (riproduce file .wcp)", width=36,
               command=lambda: scegli("simulazione")).pack(pady=px(3), fill="x")
    t.protocol("WM_DELETE_WINDOW", t.destroy)
    t.grab_set()
    root.wait_window(t)
    return scelta["v"]
