# -*- coding: utf-8 -*-
"""Cartella d'installazione senza chiavetta: script .bat, verifica_pacchetto,
guida per il laboratorio, a capo di Windows.

Gli script .bat si provano anche davvero, con il cmd di Wine, se c'e'
l'immagine Docker dlive-wine:pronto (README, "Test"); altrimenti quella
parte si salta.
"""
import io
import os
import re
import shutil
import subprocess
import sys

import pytest

from conftest import RADICE

sys.path.insert(0, os.path.join(RADICE, "strumenti"))
import genera_guida_txt  # noqa: E402
import genera_verifica_pacchetto as GV  # noqa: E402
from dlive import pacchetto  # noqa: E402

BAT = ["installa.bat", "disinstalla.bat", "diagnostica.bat", "verifica_pacchetto.bat", "avvia.bat",
       "avvia_simulazione.bat"]


def _leggi(nome):
    with io.open(os.path.join(RADICE, nome), "rb") as f:
        return f.read()


# ---------------------------------------------------------------- a capo e codifica
def test_file_windows_crlf_e_ascii():
    voci = GV.file_windows(RADICE)
    nomi = [os.path.basename(p) for p in voci]
    for n in BAT + ["crea_collegamenti.vbs", "GUIDA_LABORATORIO.txt", "comandi_da_incollare.txt"]:
        assert n in nomi, n
    for p in voci:
        b = open(p, "rb").read()
        b.decode("ascii")
        assert b.count(b"\n") == b.count(b"\r\n") > 0, p
        assert b.endswith(b"\r\n"), p


def test_gitattributes_vieta_le_conversioni():
    righe = [r.strip() for r in _leggi(".gitattributes").decode("ascii").splitlines()]
    for r in ("* -text", "*.bat -text", "*.txt -text", "*.vbs -text"):
        assert r in righe, r


# ---------------------------------------------------------------- elenco e file scaricati
def test_elenco_di_verifica_pacchetto_aggiornato():
    attuale = _leggi("verifica_pacchetto.bat").decode("ascii")
    assert attuale == GV.testo_aggiornato(RADICE), \
        "lanciare python strumenti/genera_verifica_pacchetto.py"
    voci = dict(pacchetto.elenco_programma(RADICE))
    assert "dlive/gui.py" in voci and "dlive/devices/digidata.py" in voci and "dlive/pacchetto.py" in voci
    assert voci["config.ini"] is None and voci["main.py"] == os.path.getsize(os.path.join(RADICE, "main.py"))


def test_installa_copia_solo_file_controllati():
    t = _leggi("installa.bat").decode("ascii")
    m = re.search(r"for %%f in \(([^)]*)\) do \(\r\n\s*copy /y", t)
    copiati = m.group(1).split()
    voci = dict(pacchetto.elenco_programma(RADICE))
    for f in copiati + ["config.ini", "crea_collegamenti.vbs", "verifica_pacchetto.bat"]:
        assert os.path.isfile(os.path.join(RADICE, f)), f
        assert f in voci or f == "verifica_pacchetto.bat", f
    # disinstalla toglie gli stessi file
    d = _leggi("disinstalla.bat").decode("ascii")
    for f in copiati:
        assert f in d, f


def test_file_scaricati_coerenti_ovunque():
    bat = _leggi("verifica_pacchetto.bat").decode("ascii")
    installa = _leggi("installa.bat").decode("ascii")
    guida = _leggi("GUIDA_LABORATORIO.md").decode("utf-8")
    for nome, dim, h, url, pagina in pacchetto.SCARICAMENTI:
        assert 'call :scaricato "%s" %d %s "%s"' % (nome, dim, h, url) in bat
        assert nome in installa
        assert nome in guida and url in guida and pagina in guida
        assert "{:,}".format(dim).replace(",", ".") in guida
    assert pacchetto.MSI == "python-3.4.4.msi" and pacchetto.WHEEL.startswith("numpy-1.15.")
    assert "cp34" in pacchetto.WHEEL and "win32" in pacchetto.WHEEL


def test_niente_piu_chiavetta_dll_ne_winaspi_distribuiti():
    for nome in BAT:
        t = _leggi(nome).decode("ascii").lower()
        for vecchio in ("pacchetti\\", "programma\\", "aspiinst", "pip-19", "verifica_hash", "hash_sha256",
                        "dll\\winaspi", "dll\\pclamp"):
            assert vecchio not in t, (nome, vecchio)
    t = _leggi("installa.bat").decode("ascii")
    assert "AxoScope" in t and "p. 21" in t and "WinASPI" in t
    assert "AxDD132x.dll" in t and "Axoutils32.dll" in t


@pytest.mark.parametrize("nome", BAT)
def test_etichette_dei_bat_esistono(nome):
    t = _leggi(nome).decode("ascii")
    etichette = set(m.lower() for m in re.findall(r"^:(\w+)", t, re.M))
    usate = set(m.lower() for m in re.findall(r"\b(?:goto|call)\s+:?(\w+)", t, re.I))
    usate -= {"eof"}
    usate = set(u for u in usate if re.search(r"(?:goto\s+:?|call\s+:)" + u + r"\b", t, re.I))
    mancanti = usate - etichette
    assert not mancanti, mancanti


@pytest.mark.parametrize("nome", BAT)
def test_parentesi_nei_blocchi(nome):
    """Dentro un blocco ( ... ) una ')' non protetta da ^ chiude il blocco:
    le righe echo dentro i blocchi non devono contenere parentesi nude."""
    livello = 0
    for n, riga in enumerate(_leggi(nome).decode("ascii").splitlines(), 1):
        r = riga.strip()
        if r.lower().startswith("rem") or r.startswith("::"):
            continue
        senza_escape = r.replace("^(", "").replace("^)", "")
        senza_virgolette = re.sub(r'"[^"]*"', '""', senza_escape)
        if livello > 0 and re.match(r"echo\b", senza_virgolette, re.I):
            assert "(" not in senza_virgolette and ")" not in senza_virgolette, (nome, n, riga)
            continue
        livello += senza_virgolette.count("(") - senza_virgolette.count(")")
        assert livello >= 0, (nome, n, riga)
    assert livello == 0, nome


# ---------------------------------------------------------------- dlive.pacchetto
def _cartella_finta(tmp_path, giusti=True):
    c = tmp_path / "pacchetto"
    c.mkdir()
    shutil.copy(os.path.join(RADICE, "verifica_pacchetto.bat"), str(c))
    for rel, dim in pacchetto.elenco_programma(RADICE):
        p = c.joinpath(*rel.split("/"))
        if not p.parent.exists():
            p.parent.mkdir(parents=True)
        p.write_bytes(b"x" * (3 if dim is None else dim))
    for nome, dim, *_ in pacchetto.SCARICAMENTI:
        (c / nome).write_bytes(b"\0" * (dim if giusti else 10))
    return c


def test_pacchetto_completo_senza_hash(tmp_path):
    c = _cartella_finta(tmp_path)
    ok, problemi = pacchetto.verifica(str(c), con_hash=False)
    assert not problemi and any("file del programma" in r for r in ok)


def test_pacchetto_hash_sbagliato(tmp_path):
    c = _cartella_finta(tmp_path)
    ok, problemi = pacchetto.verifica(str(c), con_hash=True)
    assert len(problemi) == 2 and all(p.startswith("SHA-256 ERRATO") for p in problemi)
    assert all("scaricarlo di nuovo da https://" in p for p in problemi)


def test_pacchetto_mancanti_e_dimensioni(tmp_path, capsys):
    c = _cartella_finta(tmp_path, giusti=False)
    os.remove(str(c / "dlive" / "gui.py"))
    os.remove(str(c / pacchetto.WHEEL))
    with open(str(c / "main.py"), "ab") as f:
        f.write(b"\r\n")
    ok, problemi = pacchetto.verifica(str(c))
    testo = "\n".join(problemi)
    assert "DIMENSIONE ERRATA python-3.4.4.msi: 10 byte" in testo
    assert "MANCA %s: scaricarlo da https://files.pythonhosted.org" % pacchetto.WHEEL in testo
    assert "MANCA dlive/gui.py" in testo and "DIMENSIONE ERRATA main.py" in testo
    assert pacchetto.main(["--cartella", str(c)]) == 1
    assert "problemi" in capsys.readouterr().out


def _cartella_file_veri():
    """Cartella con python-3.4.4.msi e la wheel veri (strumenti/prepara_pacchetto.py), o None."""
    for cartella in (RADICE, os.path.join(RADICE, "chiavetta", "pacchetti")):
        if all(os.path.isfile(os.path.join(cartella, n)) for n, *_ in pacchetto.SCARICAMENTI):
            return cartella
    return None


def test_pacchetto_veri_se_presenti():
    """Con i file veri (scaricati con strumenti/prepara_pacchetto.py) lo SHA-256 torna."""
    cartella = _cartella_file_veri()
    if cartella is None:
        pytest.skip("python-3.4.4.msi e la wheel di numpy non sono stati scaricati qui")
    for nome, dim, h, *_ in pacchetto.SCARICAMENTI:
        p = os.path.join(cartella, nome)
        assert os.path.getsize(p) == dim and pacchetto.sha256(p) == h


# ---------------------------------------------------------------- guida
def test_guida_txt_aggiornata_e_leggibile():
    with io.open(os.path.join(RADICE, "GUIDA_LABORATORIO.md"), encoding="utf-8") as f:
        atteso = genera_guida_txt.converti(f.read())
    assert _leggi("GUIDA_LABORATORIO.txt").decode("ascii") == atteso, \
        "lanciare python strumenti/genera_guida_txt.py"
    for riga in atteso.split("\r\n"):
        assert len(riga) <= 78 or "://" in riga, riga


def test_guida_coincide_con_script_e_finestra():
    guida = _leggi("GUIDA_LABORATORIO.md").decode("utf-8")
    sorgenti = "\n".join(_leggi(n).decode("utf-8", "replace") for n in
                         BAT + ["crea_collegamenti.vbs", "main.py", "diagnostica_digidata.py",
                                "dlive/gui.py", "dlive/acquisizione.py", "dlive/devices/digidata.py",
                                "dlive/sysinfo.py", "dlive/recorder.py"])
    # ogni script nominato esiste
    for s in set(re.findall(r"\b(\w+\.bat)\b", guida)):
        assert os.path.isfile(os.path.join(RADICE, s)), s
    # pulsanti, campi, icone e messaggi citati dalla guida esistono davvero
    citati = [
        "Avvia anteprima", "Avvia registrazione", "Ferma", "Aggiungi marker", "Marker:",
        "Aggiornamento (Hz)", "Taglio LPF-8 (Hz)", "Applica", "Filtrato attuale", "Grafico",
        "denoising_live (Digidata)", "Diagnostica Digidata", "denoising_live (simulazione)",
        "denoising_live - %s", "DIGIDATA 1322A", "Persi: %d", "REGISTRAZIONE", "anteprima",
        "Impostazioni di WinWCP", "Scheda occupata", "Driver Digidata", "Campioni persi",
        "Nessun Digidata trovato", "e' gia' in uso da", "Fermare la registrazione in corso?",
        "TUTTO A POSTO: la cartella e' completa.", "SHA-256 verificato", "file del programma, tutti con la "
        "dimensione giusta", "NON TROVO I FILE DEL PROGRAMMA", "MANCA ", "DIMENSIONE ERRATA", "SHA-256 ERRATO",
        "INSTALLAZIONE COMPLETATA.", "INSTALLAZIONE COMPLETATA, MA CI SONO", "INSTALLAZIONE INTERROTTA",
        "AxDD132x.dll: presente", "Axoutils32.dll: presente", "WinASPI: presente", "WinWCP: %WCPDIR%",
        "WinWCP non trovato", "manca AxDD132x.dll", "manca Axoutils32.dll", "WinASPI non installato",
        "numpy non funziona su questo PC", "Python 3.4 non trovato", "WinWCP e' aperto",
        "ESITO: nessun errore. Si puo' passare all'anteprima ^(avvia.bat^).", "ESITO: ci sono errori",
        "Nessun errore: si puo' passare all'anteprima (avvia.bat).", "RIEPILOGO", "WinASPI funziona",
        "Digidata trovato con", "ricevuti %d campioni su %d attesi", "WinASPI non funziona",
        "nessuna AxDD132x.dll trovata", "nessuna copia caricabile", "Digidata non trovato",
        "installa_log.txt", "python_msi_log.txt", "rilevamento_pc.txt", "report_diagnostica.txt",
        "dati_registrati", "Python puro", "M:", "_raw", "_filt", ".json",
    ]
    for c in citati:
        assert c in sorgenti or c in _leggi("config.ini").decode("utf-8"), c
    # e la guida li cita davvero (stesse parole)
    for c in ("Avvia anteprima", "Avvia registrazione", "Aggiungi marker", "Aggiornamento (Hz)",
              "TUTTO A POSTO: la cartella e' completa.", "INSTALLAZIONE COMPLETATA.",
              "ESITO: nessun errore. Si puo' passare all'anteprima (avvia.bat).",
              "Nessun errore: si puo' passare all'anteprima (avvia.bat).", "report_diagnostica.txt",
              "denoising_live (Digidata)", "Diagnostica Digidata", "verifica_pacchetto.bat", "installa.bat"):
        assert c in guida, c
    assert "non è mai stato provato con il Digidata vero" in guida


def test_readme_rimanda_alla_guida():
    r = _leggi("README.md").decode("utf-8")
    assert "GUIDA_LABORATORIO.md" in r.split("\n## ")[0]
    assert "NON è ancora stato provato con il Digidata vero" in r


# ---------------------------------------------------------------- prova vera con Wine
IMMAGINE_WINE = os.environ.get("DLIVE_WINE_IMMAGINE", "dlive-wine:pronto")


def _wine_disponibile():
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.call(["docker", "image", "inspect", IMMAGINE_WINE], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=30) == 0
    except Exception:
        return False


richiede_wine = pytest.mark.skipif(not _wine_disponibile(),
                                   reason="serve Docker con l'immagine %s (cmd di Wine)" % IMMAGINE_WINE)


def _esegui_bat(cartella, bat, *argomenti):
    """Esegue un .bat con il cmd di Wine (premendo Invio alle pause); (codice, testo)."""
    cmd = ["docker", "run", "--rm", "-i", "-v", "%s:/w" % cartella, "-w", "/w", IMMAGINE_WINE,
           "bash", "-c", '/usr/lib/wine/wine64 cmd /c "$@" 2>/dev/null; echo "@@codice=$?"', "-", bat] + \
        list(argomenti)
    out = subprocess.run(cmd, input=b"\r\n" * 5, stdout=subprocess.PIPE, timeout=120).stdout
    t = out.decode("ascii", "replace").replace("\r", "")
    m = re.search(r"@@codice=(\d+)", t)
    return int(m.group(1)), t


@pytest.fixture
def cartella_reale(tmp_path):
    """Copia della cartella del progetto con i file del programma veri e i
    due file scaricati finti (dimensione giusta)."""
    c = tmp_path / "cartella con spazi"
    c.mkdir()
    for rel, _ in pacchetto.elenco_programma(RADICE):
        dst = c.joinpath(*rel.split("/"))
        if not dst.parent.exists():
            dst.parent.mkdir(parents=True)
        shutil.copy(os.path.join(RADICE, *rel.split("/")), str(dst))
    shutil.copy(os.path.join(RADICE, "verifica_pacchetto.bat"), str(c))
    for nome, dim, *_ in pacchetto.SCARICAMENTI:
        (c / nome).write_bytes(b"\0" * dim)
    # il certutil di Wine calcola lo SHA-256 vero: per i file finti se ne mette uno
    # simulato (nella cartella corrente ha la precedenza) che risponde con l'hash atteso
    righe = ["@echo off", "echo Hash SHA256 di %2:"]
    righe += ['if "%%~2"=="%s" echo %s' % (n, h) for n, _, h, *_ in pacchetto.SCARICAMENTI]
    righe.append("echo CertUtil: Esecuzione comando -hashfile riuscita.")
    (c / "certutil.bat").write_bytes(("\r\n".join(righe) + "\r\n").encode("ascii"))
    return c


@richiede_wine
def test_wine_verifica_pacchetto_tutto_a_posto(cartella_reale):
    codice, t = _esegui_bat(str(cartella_reale), "verifica_pacchetto.bat")
    assert codice == 0, t
    assert "TUTTO A POSTO: la cartella e' completa." in t and "tutti con la dimensione giusta" in t
    assert "ok python-3.4.4.msi  24932352 byte, SHA-256 verificato" in t


@richiede_wine
def test_wine_verifica_pacchetto_con_certutil_e_file_veri(cartella_reale):
    veri = _cartella_file_veri()
    if veri is None:
        pytest.skip("python-3.4.4.msi e la wheel di numpy non sono stati scaricati qui")
    os.remove(str(cartella_reale / "certutil.bat"))
    for nome, *_ in pacchetto.SCARICAMENTI:
        shutil.copy(os.path.join(veri, nome), str(cartella_reale))
    codice, t = _esegui_bat(str(cartella_reale), "verifica_pacchetto.bat")
    # il certutil di Wine non stampa l'hash: allora non si giudica (mai "SHA-256 ERRATO")
    assert codice == 0 and "SHA-256 ERRATO" not in t, t
    assert "ok python-3.4.4.msi  24932352 byte" in t


@richiede_wine
def test_wine_verifica_pacchetto_certutil_muto(cartella_reale):
    (cartella_reale / "certutil.bat").write_bytes(b"@echo off\r\necho CertUtil: errore strano\r\n")
    codice, t = _esegui_bat(str(cartella_reale), "verifica_pacchetto.bat")
    assert codice == 0 and "SHA-256 ERRATO" not in t and "SHA-256 verificato" not in t, t


@richiede_wine
def test_wine_verifica_pacchetto_problemi(cartella_reale):
    c = cartella_reale
    os.rename(str(c / pacchetto.WHEEL), str(c / pacchetto.WHEEL.replace(".whl", " (1).whl")))
    with open(str(c / pacchetto.MSI), "r+b") as f:
        f.truncate(1000)
    os.remove(str(c / "dlive" / "gui.py"))
    codice, t = _esegui_bat(str(c), "verifica_pacchetto.bat")
    assert codice == 3, t
    assert "DIMENSIONE ERRATA python-3.4.4.msi: 1000 byte invece di 24932352" in t
    assert "MANCA %s" % pacchetto.WHEEL in t and "rinominarlo esattamente" in t
    assert "MANCA dlive\\gui.py" in t and "Download ZIP" in t
    assert "ATTENZIONE: 3 problemi" in t


@richiede_wine
@pytest.mark.parametrize("hash_giusto,formato_win7", [(True, False), (True, True), (False, False)])
def test_wine_verifica_pacchetto_sha256_con_certutil(cartella_reale, hash_giusto, formato_win7):
    """certutil simulato (Wine non lo ha): uscita di Windows 10 e di Windows 7 (byte separati)."""
    righe = ["@echo off", "echo Hash SHA256 di %2:"]
    for nome, _, h, *_ in pacchetto.SCARICAMENTI:
        if not hash_giusto:
            h = "0" * 64
        if formato_win7:
            h = " ".join(h[i:i + 2] for i in range(0, 64, 2))
        righe.append('if "%%~2"=="%s" echo %s' % (nome, h))
    righe.append("echo CertUtil: Esecuzione comando -hashfile riuscita.")
    (cartella_reale / "certutil.bat").write_bytes(("\r\n".join(righe) + "\r\n").encode("ascii"))
    codice, t = _esegui_bat(str(cartella_reale), "verifica_pacchetto.bat")
    if hash_giusto:
        assert codice == 0 and t.count("SHA-256 verificato") == 2, t
    else:
        assert codice == 2 and t.count("SHA-256 ERRATO") == 2, t


@richiede_wine
def test_wine_verifica_pacchetto_zip_non_estratto(tmp_path):
    shutil.copy(os.path.join(RADICE, "verifica_pacchetto.bat"), str(tmp_path))
    codice, t = _esegui_bat(str(tmp_path), "verifica_pacchetto.bat")
    assert codice == 1 and "NON TROVO I FILE DEL PROGRAMMA" in t and "Estrai tutto" in t


@richiede_wine
def test_wine_installa_si_ferma_se_manca_un_file(cartella_reale):
    os.remove(str(cartella_reale / pacchetto.MSI))
    codice, t = _esegui_bat(str(cartella_reale), "installa.bat")
    assert codice == 1, t
    assert "MANCA python-3.4.4.msi" in t and "INSTALLAZIONE INTERROTTA" in t
    assert "GUIDA_LABORATORIO.txt, parte A" in t
    assert "Installo Python" not in t


@richiede_wine
def test_wine_diagnostica_senza_python(cartella_reale):
    codice, t = _esegui_bat(str(cartella_reale), "diagnostica.bat")
    assert codice == 1 and "Python 3.4 non trovato" in t and "installa.bat" in t


@richiede_wine
def test_wine_disinstalla_senza_installazione(cartella_reale):
    codice, t = _esegui_bat(str(cartella_reale), "disinstalla.bat")
    assert codice == 0 and "non risulta installato" in t and "Fine." in t


# ---------------------------------------------------------------- installazione vera (Wine a 32 bit)
IMMAGINE_WINE32 = os.environ.get("DLIVE_WINE32_IMMAGINE", "dlive-wine32")
SCRIPT_INSTALLA = r'''
trap 'chmod -R a+rwX /w' EXIT
cd "/w/cartella con spazi"
wine reg add "HKCU\\Software\\Wine" /v Version /d winxp /f >/dev/null 2>&1
C="$WINEPREFIX/drive_c"
mkdir -p "$C/WinWCP" && touch "$C/WinWCP/WinWCP.exe" "$C/WinWCP/AxDD132x.dll" "$C/WinWCP/Axoutils32.dll"
touch "$C/windows/system32/drivers/aspi32.sys"
printf '\r\n\r\n\r\n' | xvfb-run -a wine cmd /c installa.bat 2>/dev/null | tr -d '\r' > /w/installa.txt || true
cd "$C/denoising_live"
printf '\r\n\r\n' | xvfb-run -a wine cmd /c diagnostica.bat --finto 2>/dev/null | tr -d '\r' > /w/diagnostica.txt || true
tr -d '\r' < report_diagnostica.txt > /w/report.txt
ls > /w/installati.txt
'''


def _wine32_e_file_veri():
    c = _cartella_file_veri()
    if c is None:
        return None
    if not shutil.which("docker") or subprocess.call(["docker", "image", "inspect", IMMAGINE_WINE32],
                                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
        return None
    return c


@pytest.mark.skipif(_wine32_e_file_veri() is None,
                    reason="servono l'immagine Docker %s (Wine a 32 bit) e i due file scaricati "
                           "(strumenti/prepara_pacchetto.py)" % IMMAGINE_WINE32)
def test_wine32_installazione_completa_e_diagnostica(cartella_reale, tmp_path):
    """installa.bat per intero con il vero MSI di Python 3.4.4 e la vera wheel di numpy,
    poi diagnostica.bat con la DLL simulata, nel Python 3.4 a 32 bit installato."""
    for nome, *_ in pacchetto.SCARICAMENTI:
        shutil.copy(os.path.join(_wine32_e_file_veri(), nome), str(cartella_reale))
    w = str(cartella_reale.parent)
    subprocess.run(["docker", "run", "--rm", "-v", "%s:/w" % w, IMMAGINE_WINE32, "bash", "-c", SCRIPT_INSTALLA],
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
    inst = open(os.path.join(w, "installa.txt")).read()
    assert "Python OK: 3.4.4" in inst and "32 bit" in inst, inst
    assert "Pacchetto completo e integro." in inst and "SHA-256 46c8f9f6" in inst
    assert "numpy 1.15.4 OK" in inst
    assert "Programma copiato in C:\\denoising_live" in inst
    assert "WinWCP: C:\\WinWCP" in inst and "Axoutils32.dll: presente" in inst and "WinASPI: presente" in inst
    assert "INSTALLAZIONE COMPLETATA." in inst and "INTERROTTA" not in inst
    installati = open(os.path.join(w, "installati.txt")).read().split()
    for f in ("main.py", "dlive", "config.ini", "diagnostica.bat", "GUIDA_LABORATORIO.txt", "rilevamento_pc.txt"):
        assert f in installati, f
    rep = open(os.path.join(w, "report.txt")).read()
    assert "passo 7: Digidata trovato con <finta>" in rep
    assert "passo 10: ricevuti 10000 campioni su 10000 attesi" in rep
