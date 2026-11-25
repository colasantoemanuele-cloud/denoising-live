# -*- coding: utf-8 -*-
"""Piccolo emulatore delle regole di cmd.exe in modalita' batch, per trovare
gli errori di sintassi che compaiono solo dopo l'espansione con % (e che il
cmd di Wine non riproduce).

Cosa emula:
  * fase 1, espansione con %, fatta quando la riga viene letta, PRIMA che IF
    venga valutato (anche le righe di un blocco ( ... ) sono lette ed espanse
    tutte prima di eseguirlo):
      %% -> %;  %0-%9, %~mod0-9, %* -> argomenti;
      %NOME% -> valore, o niente se NOME non e' definita;
      %NOME:...% con NOME definita -> sottostringa (~a,b) o sostituzione (a=b, *a=b);
      %NOME:...% con NOME NON definita -> si toglie "%NOME:" e si continua a
      leggere da li' (regola documentata della modalita' batch);
      un % senza chiusura -> tolto;
  * fase 2, lettura della sintassi: virgolette (lo stato "tra virgolette"
    finisce a fine riga), ^ che protegge il carattere seguente, & && || |,
    blocchi ( ... ) che si aprono solo dove inizia un comando (inizio riga,
    dopo &, dopo do, dopo else, dopo la condizione di un IF) e che dentro un
    blocco si chiudono alla prima ) fuori dalle virgolette (anche in un echo);
    sintassi di IF (/i, not, exist, defined, errorlevel, ==, equ...) e di FOR
    (/d /r /l /f, %%x, in ( ... ), do comando).

Limiti (dichiarati): non esegue niente e non valuta le condizioni; non segue i
goto/call (ogni riga e ogni blocco sono controllati con le variabili dello
scenario, tutte definite o tutte non definite); non emula la fase dei ! (non
si usa l'espansione ritardata); i comandi dentro for /f ('...') e le righe
rem/:: non sono analizzati; le regole sono quelle documentate per il cmd di
Windows XP-10 nei casi usati da questi script, non tutte quelle del cmd.
"""
import re


class ErroreSintassi(Exception):
    def __init__(self, riga, messaggio, testo):
        Exception.__init__(self, "riga %d: %s\n    dopo l'espansione: %s" % (riga, messaggio, testo))
        self.riga = riga


# ------------------------------------------------------------------ fase 1
def _argomento(mod, valore):
    """%~mod applicato a un argomento (valore gia' senza virgolette per ~)."""
    if "~" not in mod:
        return valore
    v = valore.strip('"') if valore else valore
    m = mod.replace("~", "")
    if not m:
        return v
    if "d" in m or "p" in m or "n" in m or "x" in m or "f" in m:
        if "f" in m:
            return v
        cartella, _, nome = v.rpartition("\\")
        out = ""
        if "d" in m:
            out += cartella[:2]
        if "p" in m:
            out += cartella[2:] + "\\"
        base, punto, est = nome.rpartition(".")
        if not punto:
            base, est = nome, ""
        if "n" in m:
            out += base
        if "x" in m and punto:
            out += "." + est
        return out
    if "z" in m:
        return "12345"
    return v


OPZIONI = "--opzione --altra 4"
E_COMMERCIALE = "\x01"     # una & arrivata da un valore (percorso): pericolosa fuori dalle virgolette


def _valore(v):
    return v.replace("&", E_COMMERCIALE)


def espandi(riga, variabili, argomenti):
    """Fase 1 su una riga.  variabili: {NOME_MAIUSCOLO: valore} (le non
    definite mancano); argomenti: lista, argomenti[0] = percorso dello script.
    Le & che arrivano dai valori sono marcate, per riconoscerle in fase 2."""
    out = []
    i = 0
    n = len(riga)
    while i < n:
        c = riga[i]
        if c != "%":
            out.append(c)
            i += 1
            continue
        if i + 1 < n and riga[i + 1] == "%":
            out.append("%")
            i += 2
            continue
        if i + 1 < n and riga[i + 1] == "*":
            out.append(OPZIONI)                    # %* = opzioni dello script (--finto ...)
            i += 2
            continue
        m = re.match(r"%(~[fdpnxsatz$]*)?([0-9])", riga[i:])
        if m and (m.group(1) or True):
            k = int(m.group(2))
            v = argomenti[k] if k < len(argomenti) else ""
            out.append(_valore(_argomento(m.group(1) or "", v)))
            i += m.end()
            continue
        j = riga.find("%", i + 1)
        if j < 0:                                  # % senza chiusura: tolto
            i += 1
            continue
        dentro = riga[i + 1:j]
        if ":" in dentro:
            nome, mod = dentro.split(":", 1)
            if nome.upper() not in variabili:
                i += 1 + len(nome) + 1             # via "%NOME:" e si continua
                continue
            out.append(_valore(_modifica(variabili[nome.upper()], mod)))
            i = j + 1
            continue
        if dentro.upper() in variabili:
            out.append(_valore(variabili[dentro.upper()]))
        i = j + 1                                  # non definita: tolta
    return "".join(out)


def _modifica(valore, mod):
    if mod.startswith("~"):
        parti = mod[1:].split(",")
        try:
            a = int(parti[0]) if parti[0] else 0
            b = int(parti[1]) if len(parti) > 1 else None
        except ValueError:
            return valore
        s = valore[a:] if a >= 0 else valore[a:]
        if b is not None:
            s = s[:b] if b >= 0 else s[:b]
        return s
    if "=" in mod:
        cerca, sost = mod.split("=", 1)
        if cerca.startswith("*"):
            k = valore.lower().find(cerca[1:].lower())
            return valore if k < 0 else sost + valore[k + len(cerca) - 1:]
        if not cerca:
            return valore
        return re.sub(re.escape(cerca), lambda _m: sost, valore, flags=re.I)
    return valore


# ------------------------------------------------------------------ fase 2
class _Lettore(object):
    def __init__(self, testo, righe_di):
        self.t = testo
        self.i = 0
        self.righe_di = righe_di       # posizione -> numero di riga del file

    def riga(self):
        return self.righe_di(self.i)

    def errore(self, msg):
        inizio = self.t.rfind("\n", 0, self.i) + 1
        fine = self.t.find("\n", self.i)
        raise ErroreSintassi(self.riga(), msg,
                             self.t[inizio:fine if fine >= 0 else None].replace(E_COMMERCIALE, "&"))

    def fine(self):
        return self.i >= len(self.t)

    def c(self, k=0):
        return self.t[self.i + k] if self.i + k < len(self.t) else ""

    def spazi(self, a_capo=False):
        while not self.fine() and (self.c() in " \t;,=" or (a_capo and self.c() == "\n")):
            self.i += 1

    def parola(self):
        """Un token: tra virgolette (che devono chiudersi sulla riga) o fino a un separatore."""
        self.spazi()
        if self.c() == '"':
            j = self.t.find('"', self.i + 1)
            k = self.t.find("\n", self.i + 1)
            if j < 0 or (0 <= k < j):
                self.errore("virgolette non chiuse")
            tok = self.t[self.i:j + 1]
            self.i = j + 1
            # un token puo' continuare dopo le virgolette ("a"b)
            while not self.fine() and self.c() not in ' \t\n&|()<>"=;,':
                self.i += 1
            return tok
        inizio = self.i
        while not self.fine() and self.c() not in ' \t\n&|()<>;,=':
            if self.c() == E_COMMERCIALE:
                self.errore("& di un percorso fuori dalle virgolette (spezza il comando)")
            if self.c() == "^":
                self.i += 1
            if self.c() == '"':
                j = self.t.find('"', self.i + 1)
                k = self.t.find("\n", self.i + 1)
                if j < 0 or (0 <= k < j):
                    self.errore("virgolette non chiuse")
                self.i = j
            self.i += 1
        return self.t[inizio:self.i]


def _comando(L, prof):
    """Legge un comando (e quelli concatenati con & && || |)."""
    L.spazi()
    while L.c() == "@":
        L.i += 1
    L.spazi()
    if L.c() == "(":
        _blocco(L, prof)
    else:
        inizio = L.i
        p = L.parola().lower()
        if p == "if":
            _if(L, prof)
        elif p == "for":
            _for(L, prof)
        elif p in ("rem", "::") or p.startswith("::"):
            while not L.fine() and L.c() != "\n":
                L.i += 1
            return
        else:
            L.i = inizio
            _semplice(L, prof)
    L.spazi()
    if L.c() == "&" or L.c() == "|":
        while L.c() in "&|":
            L.i += 1
        L.spazi()
        if L.fine() or L.c() == "\n" or (prof and L.c() == ")"):
            L.errore("manca il comando dopo & o |")
        _comando(L, prof)


def _semplice(L, prof):
    """Comando semplice: fino a fine riga, & | o (dentro un blocco) a ) fuori dalle virgolette."""
    virg = False
    while not L.fine():
        c = L.c()
        if c == "\n":
            if virg:
                virg = False
            return
        if c == '"':
            virg = not virg
        elif not virg:
            if c == E_COMMERCIALE:
                L.errore("& di un percorso fuori dalle virgolette (spezza il comando)")
            if c == "^":
                L.i += 2
                continue
            if c in "&|":
                return
            if c == ")" and prof:
                return
        L.i += 1


def _blocco(L, prof):
    L.i += 1                                   # "("
    while True:
        L.spazi(a_capo=True)
        if L.fine():
            L.errore("blocco ( ... ) non chiuso")
        if L.c() == ")":
            L.i += 1
            return
        if L.c() == ":":                       # etichetta/commento dentro un blocco
            while not L.fine() and L.c() != "\n":
                L.i += 1
            continue
        _comando(L, prof + 1)


def _if(L, prof):
    p = L.parola()
    if p.lower() == "/i":
        p = L.parola()
    if p.lower() == "not":
        p = L.parola()
    pl = p.lower()
    if pl in ("exist", "defined"):
        if not L.parola():
            L.errore("IF %s senza argomento" % pl)
    elif pl == "errorlevel":
        if not re.match(r"^-?\d+$", L.parola()):
            L.errore("IF errorlevel senza numero")
    else:
        # confronto: sinistra == destra, oppure sinistra OP destra
        sinistra = p
        if not sinistra:
            L.errore("IF senza termine di sinistra")
        # la parola si e' fermata a "=" (o il termine e' seguito da spazi e ==)
        while not L.fine() and L.c() in " \t":
            L.i += 1
        if L.t.startswith("==", L.i):
            L.i += 2
            while L.c() == "=":
                L.i += 1
            destra = L.parola()
            if not destra:
                L.errore("IF ... == senza termine di destra")
        else:
            op = L.parola().lower()
            if op not in ("equ", "neq", "lss", "leq", "gtr", "geq"):
                L.errore("IF con confronto non valido (%r)" % op)
            if not L.parola():
                L.errore("IF senza termine di destra")
    L.spazi()
    if L.fine() or L.c() in "\n)":
        L.errore("IF senza comando")
    era_blocco = L.c() == "("
    _comando(L, prof)
    L.spazi()
    if L.t[L.i:L.i + 4].lower() == "else":
        if not era_blocco:
            L.errore("else dopo un IF senza blocco")
        L.i += 4
        L.spazi()
        if L.fine() or L.c() == "\n":
            L.errore("else senza comando")
        _comando(L, prof)


def _for(L, prof):
    p = L.parola()
    while p.lower() in ("/d", "/r", "/l", "/f") or (p.startswith('"') and p.endswith('"')):
        if p.lower() == "/r":
            L.spazi()
            if L.c() != "%":
                L.parola()
        p = L.parola()
    if not re.match(r"^%[A-Za-z]$", p):
        L.errore("FOR senza variabile %%x (trovato %r)" % p)
    if L.parola().lower() != "in":
        L.errore("FOR senza 'in'")
    L.spazi()
    if L.c() != "(":
        L.errore("FOR senza ( ... ) dopo 'in'")
    # insieme: fino alla ) che chiude, rispettando virgolette e apostrofi
    L.i += 1
    virg = False
    apos = False
    while True:
        if L.fine() or (L.c() == "\n"):
            L.errore("insieme del FOR non chiuso")
        c = L.c()
        if c == '"' and not apos:
            virg = not virg
        elif c == "'" and not virg:
            apos = not apos
        elif c == "^" and not virg:
            L.i += 1
        elif c == ")" and not virg and not apos:
            L.i += 1
            break
        L.i += 1
    if L.parola().lower() != "do":
        L.errore("FOR senza 'do'")
    L.spazi()
    if L.fine() or L.c() in "\n)":
        L.errore("FOR ... do senza comando")
    _comando(L, prof)


_SALTO = re.compile(r"(?i)^\s*if\s+not\s+defined\s+([A-Za-z_][A-Za-z0-9_]*)\s+goto\s+:?([A-Za-z_][A-Za-z0-9_]*)\s*$")


def controlla(testo_bat, variabili, argomenti, valori_se_definite=None):
    """Espande tutte le righe con lo scenario dato e controlla la sintassi.
    Le righe dopo "if not defined X goto ETICHETTA" e fino a ETICHETTA (o, per
    goto :eof, fino all'etichetta seguente) cmd le legge solo con X definita:
    li' X vale valori_se_definite[X] (o "1").
    Restituisce l'elenco degli errori (stringhe); vuoto = va bene."""
    valori_se_definite = valori_se_definite or {}
    righe = testo_bat.replace("\r\n", "\n").split("\n")
    espanse = []
    errori = []
    forzate = {}                     # NOME -> etichetta che chiude il salto
    for n, r in enumerate(righe, 1):
        s = r.lstrip()
        if s.lower().startswith("rem") and (len(s) == 3 or s[3] in " \t") or s.startswith("::"):
            espanse.append("")
            continue
        if s.startswith(":"):
            etich = s[1:].split()[0].lower() if s[1:].split() else ""
            for k in [k for k, e in forzate.items() if e == etich or e == "eof"]:
                del forzate[k]
            espanse.append("")             # etichetta
            continue
        var = dict(variabili)
        for k in forzate:
            var.setdefault(k, valori_se_definite.get(k, "1"))
        e = espandi(r, var, argomenti)
        m = _SALTO.match(r)
        if m:
            forzate[m.group(1).upper()] = m.group(2).lower()
        # virgolette bilanciate riga per riga (^" non conta)
        if e.replace('^"', "").count('"') % 2:
            errori.append(str(ErroreSintassi(n, "virgolette sbilanciate", e.replace(E_COMMERCIALE, "&"))))
        espanse.append(e)
    testo = "\n".join(espanse)
    inizi = [0]
    for e in espanse:
        inizi.append(inizi[-1] + len(e) + 1)

    def riga_di(pos):
        lo, hi = 0, len(inizi) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if inizi[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    L = _Lettore(testo, riga_di)
    while not L.fine():
        L.spazi(a_capo=True)
        if L.fine():
            break
        if L.c() == ")":
            L.i += 1
            errori.append("riga %d: ) senza blocco aperto (ignorata da cmd, ma sospetta)" % L.riga())
            continue
        inizio = L.i
        try:
            _comando(L, 0)
        except ErroreSintassi as e:
            errori.append(str(e))
            # si riparte dalla riga dopo
            k = testo.find("\n", max(L.i, inizio))
            L.i = len(testo) if k < 0 else k + 1
            continue
        if L.i == inizio:
            L.i += 1
    return errori


# ------------------------------------------------------------------ scenari
CARTELLE = [
    "C:\\denoising-live-main",
    "C:\\Documents and Settings\\utente\\Desktop\\denoising-live-main",
    "C:\\prova (1)\\denoising-live-main",
    "C:\\denoising-live-main (1)",
    "C:\\ricerca & sviluppo\\denoising-live-main",
    "C:\\Documents and Settings\\D'Angelo\\Desktop\\denoising-live-main",
]
AMBIENTE = {"SYSTEMROOT": "C:\\WINDOWS", "WINDIR": "C:\\WINDOWS", "PROGRAMFILES": "C:\\Programmi",
            "COMPUTERNAME": "PC-LAB", "DATE": "25/11/2026", "TIME": " 9:05:03,12",
            "PROCESSOR_ARCHITECTURE": "x86", "ERRORLEVEL": "0", "OS": "Windows_NT"}


def nomi_variabili(testo_bat):
    """Variabili che lo script stesso imposta (set, set /p, set /a, anche in for e if)."""
    nomi = set()
    for m in re.finditer(r'(?i)\bset\s+(?:/[ap]\s+)?"?([A-Za-z_][A-Za-z0-9_]*)\s*[+\-*/]?=', testo_bat):
        nomi.add(m.group(1).upper())
    return nomi


def variabili_percorso(testo_bat):
    """Variabili che possono contenere un percorso: impostate con un valore che
    contiene \\ o un altro percorso (%~dp0, %CD%, %USERPROFILE%, altre variabili
    percorso), con set /p, o da un for (uscita di reg/dir/wmic).  Punto fisso."""
    assegnazioni = {}
    for m in re.finditer(r'(?i)\bset\s+(/[ap]\s+)?"?([A-Za-z_][A-Za-z0-9_]*)\s*[+\-*/]?=([^\r\n]*)', testo_bat):
        assegnazioni.setdefault(m.group(2).upper(), []).append((m.group(1) or "", m.group(3)))
    percorso = set()
    da_for = set(m.group(1).upper() for m in re.finditer(
        r'(?i)\bdo\s+(?:if [^\r\n]*?\s)?set\s+"?([A-Za-z_][A-Za-z0-9_]*)=%%', testo_bat))
    cambiato = True
    while cambiato:
        cambiato = False
        for nome, valori in assegnazioni.items():
            if nome in percorso:
                continue
            for opz, v in valori:
                rif = set(x.upper() for x in re.findall(r"%([A-Za-z_][A-Za-z0-9_]*)[%:]", v))
                if ("/p" in opz.lower() or "\\" in v or re.search(r"%~?[a-z]*[dpf][a-z]*[0-9]", v, re.I)
                        or rif & (percorso | {"CD", "USERPROFILE", "PROGRAMFILES", "SYSTEMROOT"})
                        or nome in da_for):
                    percorso.add(nome)
                    cambiato = True
                    break
    return percorso


def scenari(testo_bat, nome_bat, argomenti_costanti=False, non_percorsi=()):
    """(descrizione, variabili, argomenti) per ogni cartella: variabili dello script
    tutte NON definite, oppure tutte definite (quelle che possono contenere un
    percorso = la cartella, con spazi, parentesi, & o apostrofi; le altre = "1").
    argomenti_costanti: le subroutine dello script ricevono solo costanti
    (nomi di file senza caratteri speciali), non percorsi."""
    nomi = nomi_variabili(testo_bat) | {"PROCESSOR_ARCHITEW6432"}
    perc = variabili_percorso(testo_bat) - set(x.upper() for x in non_percorsi)
    out = []
    for cart in CARTELLE:
        script = cart + "\\" + nome_bat
        if argomenti_costanti:
            args = [script, "python-3.4.4.msi", "24932352", "abc", "https://esempio/python-3.4.4.msi"]
        else:
            args = [script] + [cart + "\\file prova.txt"] * 4
        amb = dict(AMBIENTE)
        amb["USERPROFILE"] = cart
        amb["CD"] = cart
        definite = dict(amb)
        for k in nomi:
            definite[k] = cart if k in perc else "1"
        out.append(("cartella %r, variabili dello script non definite" % cart,
                    dict((k, v) for k, v in amb.items() if k not in nomi), args, definite))
        out.append(("cartella %r, variabili dello script definite" % cart, definite, args, definite))
    return out
