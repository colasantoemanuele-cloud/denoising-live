# -*- coding: utf-8 -*-
"""Genera GUIDA_RAPIDA.txt e GUIDA_COMPLETA.txt (ASCII, a capo CRLF, righe di al
massimo 78 caratteri: leggibili nel Blocco note di Windows XP) dai rispettivi .md.

    python strumenti/genera_guida_txt.py              rigenera
    python strumenti/genera_guida_txt.py --controlla  codice 1 se da rigenerare
"""
import io
import os
import re
import sys
import textwrap

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
LARGHEZZA = 78

ASCII = [("à", "a'"), ("è", "e'"), ("é", "e'"), ("ì", "i'"), ("ò", "o'"), ("ù", "u'"),
         ("À", "A'"), ("È", "E'"), ("É", "E'"), ("→", "->"), ("…", "..."), ("–", "-"), ("—", "-"),
         ("×", "x"), ("“", '"'), ("”", '"'), ("’", "'"), ("‘", "'"), (" ", " ")]


def in_ascii(t):
    for a, b in ASCII:
        t = t.replace(a, b)
    return t


def pulisci(t):
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"(?<![\w*])\*([^*\s][^*]*)\*(?![\w*])", r"\1", t)
    # codice: tra virgolette se contiene spazi (messaggi), altrimenti cosi' com'e' (nomi di file)
    t = re.sub(r"`([^`]*)`", lambda m: '"%s"' % m.group(1) if " " in m.group(1) else m.group(1), t)
    t = re.sub(r"<(https?://[^>]+)>", r"\1", t)
    return in_ascii(t)


def avvolgi(testo, rientro="", rientro_dopo=None):
    if rientro_dopo is None:
        rientro_dopo = rientro
    return textwrap.wrap(testo, LARGHEZZA, initial_indent=rientro, subsequent_indent=rientro_dopo,
                         break_long_words=False, break_on_hyphens=False) or [rientro]


def tabella(righe):
    celle = [[pulisci(c.strip()) for c in r.strip().strip("|").split("|")] for r in righe]
    intest, corpo = celle[0], celle[2:]
    out = []
    for r in corpo:
        out.extend(avvolgi(r[0], "- ", "  "))
        for h, c in zip(intest[1:], r[1:]):
            out.extend(avvolgi("%s: %s" % (h.upper(), c), "    ", "      "))
        out.append("")
    return out[:-1]


def converti(md):
    righe = md.replace("\r\n", "\n").split("\n")
    out = []
    i = 0
    while i < len(righe):
        r = righe[i]
        if r.startswith("|"):
            blocco = []
            while i < len(righe) and righe[i].startswith("|"):
                blocco.append(righe[i])
                i += 1
            out.extend(tabella(blocco))
            continue
        if r.startswith("# ") or r.startswith("## "):
            t = pulisci(r.lstrip("#").strip()).upper() if r.startswith("# ") else pulisci(r.lstrip("#").strip())
            out.extend([t, ("=" if r.startswith("# ") else "-") * len(t)])
            i += 1
            continue
        if r.strip() == "---":
            out.append("=" * LARGHEZZA)
            i += 1
            continue
        if not r.strip():
            out.append("")
            i += 1
            continue
        m = re.match(r"^(\s*)(\* |\d+\. )(.*)$", r)
        if m:
            rientro = " " * len(m.group(1))
            segno = "- " if m.group(2) == "* " else m.group(2)
            testo = [m.group(3)]
            i += 1
            while i < len(righe) and righe[i].startswith(" ") and righe[i].strip() and \
                    not re.match(r"^\s*(\* |\d+\. )", righe[i]):
                testo.append(righe[i].strip())
                i += 1
            out.extend(avvolgi(pulisci(" ".join(testo)), rientro + segno, rientro + " " * len(segno)))
            continue
        testo = [r.strip()]
        i += 1
        while i < len(righe) and righe[i].strip() and not righe[i].startswith(("|", "#", "* ", "---")) \
                and not re.match(r"^\s*(\* |\d+\. )", righe[i]):
            testo.append(righe[i].strip())
            i += 1
        out.extend(avvolgi(pulisci(" ".join(testo))))
    while out and not out[-1]:
        out.pop()
    testo = "\r\n".join(out) + "\r\n"
    testo.encode("ascii")            # solleva un errore se resta un carattere non ASCII
    return testo


GUIDE = ("GUIDA_RAPIDA", "GUIDA_COMPLETA")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    radice = argv[argv.index("--radice") + 1] if "--radice" in argv else RADICE
    codice = 0
    for nome in GUIDE:
        with io.open(os.path.join(radice, nome + ".md"), encoding="utf-8") as f:
            testo = converti(f.read())
        p = os.path.join(radice, nome + ".txt")
        if "--controlla" in argv:
            attuale = io.open(p, "rb").read().decode("ascii") if os.path.exists(p) else ""
            if attuale != testo:
                print("%s.txt NON aggiornata: lanciare python strumenti/genera_guida_txt.py" % nome)
                codice = 1
            else:
                print("%s.txt aggiornata" % nome)
            continue
        with io.open(p, "wb") as f:
            f.write(testo.encode("ascii"))
        print("%s.txt: %d righe" % (nome, testo.count("\r\n")))
    return codice


if __name__ == "__main__":
    sys.exit(main())
