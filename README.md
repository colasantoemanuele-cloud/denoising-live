# denoising_live

> **Sei in laboratorio? Leggi solo questa: [GUIDA_RAPIDA.md](GUIDA_RAPIDA.md)** (una pagina;
> da stampare o da aprire nel Blocco note: `GUIDA_RAPIDA.txt`).

Acquisizione con **denoising in tempo reale** per il digitalizzatore **Axon Digidata 1322A**
(PC del laboratorio con Windows XP). Sostituisce WinWCP **solo durante la registrazione**:
legge l'ingresso analogico 2, filtra il segnale dal vivo, mostra grezzo e filtrato
sovrapposti e salva **entrambi** in file `.wcp` che WinWCP 5.1.6 apre come i suoi.
WinWCP resta lo strumento di analisi.

> **Ogni passo spiegato, e cosa fare se qualcosa va storto: [GUIDA_COMPLETA.md](GUIDA_COMPLETA.md)**
> (anche in `GUIDA_COMPLETA.txt` per il Blocco note di Windows XP).

> **Attenzione: il programma NON è ancora stato provato con il Digidata vero.** È validato in
> simulazione (§ 11), con una DLL finta e con Python 3.4 a 32 bit; la prima prova con la scheda
> è quella descritta nelle guide.

Due modalità, stesso codice:

| modalità | dove | sorgente |
|---|---|---|
| **Simulazione** | PC di sviluppo (Linux) o anche XP | rilegge i `.wcp` di prova in tempo reale (1×, 5×, 20×) |
| **Digidata** | PC del laboratorio (XP, Python 3.4.4 32 bit) | la scheda vera, tramite `AxDD132x.dll` |

> **Cosa contiene questa repository.** Il programma (`dlive/`, `main.py`,
> `diagnostica_digidata.py`), gli script per Windows, gli strumenti, i test, la guida per il
> laboratorio e in `docs/` l'analisi dei sorgenti di WinWCP, il comando di raccolta e il
> rapporto di validazione ufficiale in testo (`docs/validazione/rapporto_validazione.md`).
> **Non contiene** (e il testo qui sotto li cita solo per completezza): i dati del laboratorio
> (`riferimenti/dati/`, i file `.wcp`, la cartella `info_pc_lab`), il resto di `riferimenti/`
> (sorgenti e header Axon, manuali, guida di WinWCP, installatori, DLL, WinASPI), la vecchia
> cartella `chiavetta/`, le figure e le versioni HTML dei rapporti, i rapporti delle fasi
> precedenti, i risultati grezzi della validazione e le schermate in `docs/screenshot/`
> (ricavate da dati reali). I test che hanno bisogno di quei file vengono **saltati** con il
> messaggio "non eseguibile senza i dati del laboratorio", mai FAIL; `./valida.sh` esegue
> solo la parte riproducibile (§ 11).

> **Funziona?** `./valida.sh` esegue la validazione oggettiva (soglie numeriche fissate,
> PASS/FAIL, verdetto chiaro per chi non è esperto). Il rapporto **ufficiale**, ottenuto con i
> dati reali del laboratorio, è `docs/validazione/rapporto_validazione.md` (PRONTO PER LA PROVA
> IN LABORATORIO); qui, senza quei dati, `./valida.sh` esegue solo la parte riproducibile, scrive
> `validazione_uscita/rapporto_riproducibile/` e, se non fallisce nulla, dà il verdetto
> «PARZIALE: 0 FAIL, N test non eseguibili senza i dati del laboratorio». Vedi [§ 11](#11-come-validare-il-programma).

> **Prima della visita in laboratorio** (facoltativo): il collega incolla `docs/comandi_da_incollare.txt`
> nel Prompt dei comandi del PC del laboratorio e riporta la cartella `info_pc_lab`; cosa farne:
> [§ 9](#9-quando-torna-la-cartella-info_pc_lab). Tutto il resto (Windows, diritti, Python,
> schermo, DLL, impostazioni di WinWCP…) il programma, `installa.bat` e la diagnostica lo
> rilevano da soli sul posto.

> **Cosa si è ricavato dai sorgenti di WinWCP** (fase 5): [`docs/analisi_sorgenti.md`](docs/analisi_sorgenti.md).
> In breve: i vecchi file di prova sono datati 2007-2008, prima dell'uscita della 5.1.6 (2016): il PC
> che li ha registrati aveva l'orologio indietro. **Ora l'orologio del PC del laboratorio è giusto**
> (report del 24/11/2026); la diagnostica avvisa comunque se la data del PC è anteriore al 2016.
> I file di prova non mostrano stimolazione; il protocollo ora manda
> `uChunksPerSecond = 0` come WinWCP; il programma legge (senza mai scriverle) le impostazioni di
> WinWCP e le propone come valori iniziali.

---

## 1. Uso in simulazione (PC Linux)

Ambiente conda dedicato `denoising_live` (per crearlo: `conda env create -f environment.yml`;
negli esempi `python` è il Python di quell'ambiente):

```bash
cd denoising-live
./avvia_simulazione.sh                       # usa l'ambiente conda denoising_live
# oppure, esplicito:
python main.py --simulazione
# con un file già scelto:
./avvia_simulazione.sh --file riferimenti/dati/071210_001.wcp
# provare il percorso senza numpy (quello di ripiego per XP):
./avvia_simulazione.sh --senza-numpy
```

Nella finestra:

1. **Sorgente simulazione…**: file, record (0 = tutti in sequenza), canale (−1 = sceglie
   quello col segnale), velocità 1×/5×/20×, salta la coda costante, sovracampiona a
   1000 Hz (stessa catena della modalità Digidata), rumore sintetico (50 / 8,7 / 37,4 Hz,
   banda 25–50 Hz, picchi di saturazione).
2. **Avvia anteprima** (non salva) oppure **Avvia registrazione** (salva).
3. Durante l'acquisizione si possono cambiare tipo/ordine/taglio del filtro (cursore o
   preset 1, 2, 5, 10 Hz), i notch, il taglio dichiarato dell'LPF-8, gli aggiornamenti del
   grafico al secondo (**Aggiornamento (Hz)**: 2, 5 predefinito, 10; effetto immediato,
   salvato in `config.ini`), la finestra (10 s,
   30 s, 2 min, 10 min), la scala Y; si inseriscono marker con l'ora (Invio).
4. **Ferma**.

File utili per vedere il filtro: `071210_001.wcp` record 2 (rumore 25–50 Hz fortissimo),
`071211_001.1.wcp` canale 0 (gradini e saturazioni), `071222_002.1.wcp` (gradini puliti).

Le registrazioni vanno in `dati_registrati/` (configurabile, pulsante **Cartella dati…**),
i log in `log/`.

### Dimensione dell'interfaccia (testi troppo piccoli o troppo grandi)

La dimensione di testi e controlli si adatta da sola allo schermo: **100 %** = font di
base di 12 punti, pensato per 1920×1080; più grande sugli schermi ad alta risoluzione
(**200 %** a 3840×2160), **80 %** (10 punti) a 1024×768 e 1280×1024 perché tutto ci stia.
Il valore **Filtrato attuale** è sempre 3 volte il font di base. Per cambiarla:

* **dalla finestra**: menu a tendina **Dimensione interfaccia** nella barra in alto
  (*Automatica*, 75 %, 100 %, 125 %, 150 %, 175 %, 200 %, 250 %, 300 %). La finestra si
  ridisegna **subito**, anche durante una registrazione (che non viene toccata); la scelta
  è salvata in `config.ini`;
* **da `config.ini`**: `[interfaccia] dimensione = auto` oppure una percentuale
  (`dimensione = 150`). Un valore scritto qui ha la precedenza sulla scala automatica; un
  valore non valido viene ignorato (avviso nel log) e si usa `auto`.

Come si calcola la scala automatica (`dlive/scala.py`): il maggiore tra
`min(larghezza/1920, altezza/1080)` (limitato a 0,8–4) e i DPI dichiarati dal sistema
divisi per 96, se sono almeno 115 (Windows con scala al 150 % → 150 %; XP con "caratteri
grandi" a 120 DPI → 125 %). I DPI tra 96 e 110 si ignorano perché molti sistemi Linux
dichiarano 96 anche su schermi 4K. Tutti i font sono in punti; margini e spessori in pixel
sono moltiplicati per lo stesso fattore. La percentuale in uso è scritta nel log
all'avvio.

Su schermi piccoli o con dimensione grande la barra dei pulsanti e la barra di stato vanno a
capo invece di tagliare i controlli, e il pannello destro mostra una barra di scorrimento
se non ci sta in altezza. La finestra non supera mai lo schermo: sotto 1440×900 occupa
tutto lo schermo meno 64 pixel in basso (barra delle applicazioni di XP), altrimenti
l'85 %.

Screenshot (Python 3.4 su Xvfb, simulazione di `071222_002.1.wcp`; non pubblicati perché mostrano dati reali) in `docs/screenshot/`:
`gui_1024x768.png`, `gui_1280x1024.png`, `gui_1920x1080.png`, `gui_3840x2160.png` (scala
automatica) e `gui_1024x768_manuale_150.png` (150 % scelto a mano su 1024×768: barre a capo
e pannello con barra di scorrimento). Si rifanno con
`strumenti/screenshot_gui.py` (istruzioni in testa al file), che controlla anche che
nessun controllo esca dalla finestra.

### Test

```bash
python -m pytest tests --ignore=tests/validazione -q   # ~7 minuti, 375 test
DLIVE_TEST_VELOCI=1 python -m pytest tests -q   # senza il test di 3 ore
vermin -t=3.4- --violations main.py diagnostica_digidata.py dlive
python strumenti/prestazioni.py     # tempo CPU
python strumenti/valuta_filtri.py --dettaglio   # confronto filtri
```

I test non aprono **mai** finestre sullo schermo di chi li lancia: quelli della GUI partono
solo sotto un display virtuale dichiarato (`xvfb-run` con `DLIVE_DISPLAY_VIRTUALE=1`, come
in Docker, § 8, e in `./valida.sh`), altrimenti vengono saltati anche se `DISPLAY` è
impostato. La validazione completa è `./valida.sh` (§ 11).

Test con Python 3.4 + numpy 1.15 (Docker, GUI con display virtuale): vedi § 8.

---

## 2. Struttura

```
main.py                    avvio (--simulazione / --digidata / chiede)
diagnostica_digidata.py    diagnostica passo-passo della scheda (da eseguire per prima in lab)
config.ini                 configurazione commentata in italiano (creata al primo avvio)
avvia.bat  avvia_simulazione.bat  diagnostica.bat  avvia_simulazione.sh
prepara.bat                sul PC con internet: scarica i due file e controlla la cartella (§ 3)
installa.bat  disinstalla.bat  crea_collegamenti.vbs   installazione sul PC del laboratorio (§ 3)
verifica_pacchetto.bat     controlla la cartella d'installazione (lo chiamano prepara.bat e installa.bat)
raccogli_risultati.bat     copia sul Desktop i risultati della prova (icona "Raccogli risultati")
GUIDA_RAPIDA.md/.txt       la prova in laboratorio in una pagina
GUIDA_COMPLETA.md/.txt     ogni passo spiegato, problemi e rimedi
.gitattributes             nessuna conversione degli a capo (i .bat restano CRLF anche nel ZIP)
dlive/
  compat.py                numpy sì/no (percorso veloce o Python puro)
  verifica_numpy.py        prova numpy in un processo separato prima di importarlo
  config.py  registro.py   configurazione INI, log con rotazione
  lpf8.py                  filtro analogico LPF-8: valori ammessi, Bypass, rischio di aliasing
  winwcp_impostazioni.py   lettura (solo lettura) di winwcp.ini e lab interface settings.xml
  rilevamento.py           rilevamento sul posto (Windows, diritti, Python, schermo, disco, DLL, WinWCP...)
  scala.py                 dimensione dell'interfaccia (scala automatica / manuale, font)
  wcpfile.py               lettore/scrittore .wcp (WinWCP V9 / 5.1.6), con e senza numpy
  filters.py               progettazione (bilineare, senza scipy) e filtraggio SOS in tempo reale
  acquisizione.py          Sessione: thread di acquisizione + thread di elaborazione, coda
  recorder.py              registrazione: _raw.wcp + _filt.wcp + .json
  gui.py                   interfaccia tkinter (Canvas, min/max per pixel)
  sysinfo.py               disco libero, processi (WinWCP aperto?), periferiche SCSI
  devices/base.py          interfaccia astratta Dispositivo
  devices/simulated.py     SimulatedDevice
  devices/digidata.py      Digidata1322Device
  devices/axdd132x.py      UNICO modulo con le firme ctypes della DLL Axon (+ WinASPI)
  devices/dd132x_finto.py  DLL finta in Python, solo per i test
  pacchetto.py             controllo della cartella d'installazione (nomi, dimensioni, SHA-256)
tests/                     pytest
tests/validazione/         validazione oggettiva con soglie fisse (§ 11); valida.sh la esegue tutta
docs/validazione/          rapporti di validazione (iniziale e finale), figure, risultati grezzi
strumenti/                 valuta_filtri.py, prestazioni.py, prepara_pacchetto.py (scarica MSI e wheel),
                           genera_verifica_pacchetto.py, genera_guida_txt.py, prepara_riferimenti.sh,
                           screenshot_gui.py, leggi_info_lab.py (riassume la cartella info_pc_lab)
docs/analisi_sorgenti.md   cosa si ricava dai sorgenti di WinWCP, dalla guida e dal manuale LPF-8 (fase 5)
docs/comando_laboratorio.md  motivazione di ogni riga di docs/comandi_da_incollare.txt
docs/screenshot/           la finestra a 1024×768, 1280×1024, 1920×1080, 3840×2160
riferimenti/               dati di prova, DLL estratte, sorgenti chiave di WinWCP, header Axon, manuali,
                           winwcp5_2_7/ (cosa conferma l'installatore di WinWCP 5.2.7)
```

`riferimenti/winwcp_sorgenti/` (408 MB, sorgenti completi estratti dagli zip) e i `.wcp` di
prova sono fuori da git: si ricreano con `strumenti/prepara_riferimenti.sh`. In git restano
i file chiave (`riferimenti/winwcp_chiave/WCPFIleUnit.pas`, `dd1320.pas`, `SESLabIO.pas`)
e l'header ufficiale `riferimenti/sdk_axon/AxDD132x.h`.

---

## 3. Installazione su Windows XP

Non c'è più una cartella `chiavetta/` da preparare: chi va in laboratorio scarica il progetto
da GitHub (**Code → Download ZIP**), fa doppio clic su `prepara.bat`, che scarica **due file
a parte** e controlla tutto, e copia la cartella su una chiavetta. Procedura per chi non è
esperto: [GUIDA_RAPIDA.md](GUIDA_RAPIDA.md); dettagli: [GUIDA_COMPLETA.md](GUIDA_COMPLETA.md).

| file da scaricare (nella cartella del progetto) | dimensione | SHA-256 | fonte |
|---|---|---|---|
| `python-3.4.4.msi` — Python 3.4.4 Windows x86 (32 bit), l'ultimo per XP | 24 932 352 byte | `46c8f9f63cf02987e8bf23934b2f471e1868b24748c5bb551efcf4863b43ca6c` | <https://www.python.org/ftp/python/3.4.4/python-3.4.4.msi> (pagina <https://www.python.org/downloads/release/python-344/>, MD5 `e96268f7042d2a3d14f7e23b2535738b`) |
| `numpy-1.15.4-cp34-none-win32.whl` — l'ultima numpy con wheel cp34 win32 (la 1.16 non ne ha) | 9 932 905 byte | `df04f4bad8a359daa2ff74f8108ea051670cafbca533bb2636c58b16e962989e` | <https://files.pythonhosted.org/packages/e6/10/798bd58c97068aad4cb24e9ba60dcc7ce2e8aac7a871ea493708039a8100/numpy-1.15.4-cp34-none-win32.whl> (SHA-256 pubblicato da PyPI) |

Su Linux li scarica e verifica `python strumenti/prepara_pacchetto.py` (sono esclusi da git).
pip non serve scaricarlo: si usa il pip 7.1.2 incluso nell'MSI di Python 3.4.4.

**Non sono nella repository** e non servono: la **DLL Axon** (`AxDD132x.dll` e
`Axoutils32.dll`) si usa quella di **WinWCP già installato** sul PC, nella cartella di
`winwcp.exe`, dove il programma la cerca già (`docs/analisi_sorgenti.md`, riga "DLL");
**WinASPI** e il driver SCSI vengono dall'installazione di **AxoScope** (guida di WinWCP,
p. 21). Se mancano, gli script lo dicono con il rimedio.

**Gli script** (tutti con messaggi in italiano e un rimedio per ogni cosa che manca):

| script | cosa fa |
|---|---|
| `prepara.bat` | **sul PC con internet** (Windows 10/11): scarica i due file con `curl.exe` (o con PowerShell se `curl` non c'è) in `.part` e li rinomina solo se la dimensione è giusta, poi chiama `verifica_pacchetto.bat /prepara`; finisce con `TUTTO A POSTO: copia questa cartella sulla chiavetta` oppure, se il download non riesce, dà i due link da scaricare a mano. Su XP dice che va usato sul PC con internet; se il ZIP non è estratto lo dice |
| `verifica_pacchetto.bat` | (non serve lanciarlo a mano: lo chiamano `prepara.bat` e `installa.bat`) controlla che nella cartella ci siano i due file scaricati e i 36 file del programma con **nome e dimensione giusti** (le dimensioni le scrive `strumenti/genera_verifica_pacchetto.py`, un test controlla che siano aggiornate); su Windows 10/11 verifica anche lo **SHA-256** con `certutil` (Windows 7: byte separati da spazi; XP non ha `certutil`: lo fa poi `installa.bat`). Riconosce il ZIP non estratto e i file scaricati due volte (`python-3.4.4 (1).msi`). Non modifica nulla; funziona su XP e su Windows 10/11 |
| `installa.bat` | **rileva** Windows, Service Pack (avvisa sotto XP SP2), 32/64 bit, diritti, spazio su C:, Python già presenti (se è registrato un Python 3.4 fuori da `C:\Python34` usa quello), tutto in `installa_log.txt` → `verifica_pacchetto.bat /installa` → installa Python 3.4.4 in `C:\Python34` (se non c'è già; log in `python_msi_log.txt`; spiega i codici d'errore di msiexec) → controlla che sia 3.4 a 32 bit con tkinter e ctypes → **SHA-256** dei due file con Python (`python -m dlive.pacchetto`) → installa numpy con il pip incluso e **prova a usarlo** (se non funziona lo toglie: il programma userà il percorso senza numpy) → copia il programma in `C:\denoising_live` **conservando un `config.ini` già presente** → tre collegamenti sul desktop → cerca **WinWCP** (`C:\WinWCP*`, `Programmi\WinWCP*`, `Programmi\Strathclyde*\WinWCP*`), **`AxDD132x.dll` e `Axoutils32.dll`** nella sua cartella e **WinASPI** (`wnaspi32.dll`, `aspi32.sys`) → **rilevamento completo** (`python -m dlive.rilevamento`, § 4 passo 1b) in `C:\denoising_live\rilevamento_pc.txt`. Alla fine dice `INSTALLAZIONE COMPLETATA.` oppure quante ATTENZIONI ci sono |
| `diagnostica.bat` | usa il Python scritto da `installa.bat` in `C:\denoising_live\python_percorso.txt` (anche fuori da `C:\Python34`), altrimenti `C:\Python34`; se manca Python o lo script lo dice; avvisa se WinWCP è aperto; esegue `diagnostica_digidata.py` (§ 4) e riassume l'esito (`ESITO: nessun errore…` / `ci sono errori…`) |
| `raccogli_risultati.bat` | icona **Raccogli risultati** (la crea `installa.bat`), oppure doppio clic nella cartella del progetto: copia in `risultati_prova_AAMMGG_HHMM` sul Desktop report della diagnostica, `log`, `dati_registrati` (registrazioni e JSON), `diagnostica_*.wcp/.csv`, `rilevamento_pc.txt`, `config.ini` (e `.bak`), `installa_log.txt`, `python_msi_log.txt` e un `elenco.txt`; copia quello che c'è anche se installazione o prova si sono fermate a metà; non cancella nulla. Data e ora da `wmic` (altrimenti dalla data di Windows), Desktop dal registro |
| `disinstalla.bat` | dalla cartella d'installazione: chiede conferma, toglie i collegamenti e i file del programma, **conserva** `dati_registrati\`, `log\`, `config.ini` e i file della diagnostica, e propone di disinstallare Python **solo se** l'aveva installato `installa.bat` (file `python_installato_da_denoising_live.txt`) |

**Regole comuni a tutti i `.bat`** (dopo il guasto in laboratorio: `installa.bat` si chiudeva
da solo dopo "Disco C:"). Il cmd vero espande `%VAR%` quando **legge** la riga, o l'intero
blocco `( ... )`, prima di valutare gli IF; con una variabile non definita `%X:~-1%` diventa un
pezzo di testo e l'IF resta con le virgolette sbilanciate (era `installa.bat` riga 73, con
Python non ancora installato). Quindi: **nessun blocco `( ... )` con variabili dentro**
(si usano `goto` ed etichette); **percorsi sempre tra virgolette**, anche negli `echo` e nei
`set "X=..."` (una cartella `denoising-live-main (1)`, `C:\ricerca & sviluppo` o un utente
`D'Angelo` non rompono niente); **nessun `%X:~...%`, `%X:*...=%`, `%X:a=b%` su una variabile che
può mancare** (prima `if not defined X goto ...`); PowerShell riceve i percorsi da variabili
d'ambiente (`$env:DLIVE_DEST`). **Le finestre non si chiudono mai da sole**: lanciati con
doppio clic, `installa`, `diagnostica`, `raccogli_risultati`, `prepara`, `disinstalla` e
`avvia` si rilanciano dentro `cmd /k call "%~f0" %*` (la variabile `DLIVE_FINESTRA` evita di farlo
due volte e lascia intatti gli argomenti, che `diagnostica.bat` passa al Python);
`verifica_pacchetto.bat`, chiamato con `call`, no. **Versione**: la prima riga a schermo di ogni
`.bat` (e il log di `installa.bat`, l'`elenco.txt` dei risultati, il report della diagnostica e il
log del programma) dice `denoising_live versione AAAA-MM-GG`; la scrive
`python strumenti/versione.py` (un test controlla che coincida ovunque). L'icona
"denoising_live (simulazione)" non si crea più (nella repository non ci sono i file di prova);
`disinstalla.bat` la toglie se è rimasta.

**Emulatore delle regole di cmd** (`tests/emula_cmd.py`, `tests/test_bat_espansione.py`): espande
ogni riga di ogni `.bat` come il cmd in modalità batch (variabile non definita tolta, `%X:...%`
non definita: via `%X:` e si continua; `%~dp0` e `%~1` come percorsi; righe dopo
`if not defined X goto` lette solo con X definita) con le variabili dello script tutte definite
o tutte non definite e la cartella con spazi, `(1)`, `&` e apostrofo, e controlla virgolette,
blocchi, IF, FOR e `&` dei percorsi fuori dalle virgolette. Sulla versione di prima trova
`installa.bat` riga 73, `raccogli_risultati.bat` riga 23 e i blocchi chiusi in anticipo da una
`)` del percorso (copie in `tests/bat_prima_della_correzione/`). **Limiti**: non esegue niente e
non valuta le condizioni; segue solo i salti `if not defined X goto`, non gli altri `goto`/`call`;
non emula l'espansione ritardata con `!` (non usata) né i comandi dentro `for /f ('...')`; copre
le regole documentate nei casi usati da questi script, non tutto il cmd.

**Come sono stati provati**: oltre ai test statici (`tests/test_pacchetto.py`: a capo CRLF,
etichette, parentesi nei blocchi, elenco dei file aggiornato, guida coerente con script e
finestra), gli script sono stati **eseguiti con il cmd di Wine** (immagini Docker
`dlive-wine:pronto` e `dlive-wine32`, § 8): `verifica_pacchetto.bat` in tutti i casi (completo,
file mancanti, dimensioni errate, ZIP non estratto, SHA-256 giusto e sbagliato in formato
Windows 10 e 7); `installa.bat` **per intero** con il vero MSI e la vera wheel (Python 3.4.4 a
32 bit installato, SHA-256, numpy 1.15.4 funzionante, copia, collegamenti, WinWCP trovato in
`C:\WinWCP` e in `Programmi\Strathclyde…`, DLL e WinASPI assenti/presenti); `diagnostica.bat
--finto` nel Python installato; `disinstalla.bat`; tutto il percorso della guida rapida anche
in una cartella `denoising-live-main (1)` e con il rilancio vero dentro `cmd /k`. Wine non è
Windows XP (e non espande `%` come il cmd vero, vedi l'emulatore qui sopra): `fsutil`, `find /i`,
`findstr` e `||` dopo una redirezione si comportano diversamente, e gli script evitano le
costruzioni che differiscono (per esempio i caratteri jolly tra virgolette nei `for`).

**Dove scrive `installa.bat`** (revisione delle tabelle dell'MSI di Python e prova con Wine):

| dove | cosa | perché |
|---|---|---|
| `C:\denoising_live\` | il programma (`dlive\`, `.bat`, `README.md`, `GUIDA_RAPIDA.txt`, `GUIDA_COMPLETA.txt`, `config.ini`, `cartella_installazione.txt` con il percorso della cartella del progetto, `python_percorso.txt` con la cartella del Python usato); poi, all'uso, `dati_registrati\`, `log\`, report della diagnostica, `rilevamento_pc.txt` | cartella del programma |
| `C:\Python34\` | Python 3.4.4, pip 7.1.2 e numpy 1.15.4 (in `Lib\site-packages`) | solo se Python non c'è già; se c'è, vi aggiunge numpy |
| `C:\WINDOWS\system32\` | `python34.dll` e, **se manca**, `msvcr100.dll` (libreria C Microsoft) | lo fa l'installatore di Python "per tutti gli utenti" (azioni `SetDLLDirToSystem32` e `SharedCRT` dell'MSI); non sostituisce DLL esistenti |
| registro | `HKLM\Software\Python\PythonCore\3.4` e la voce in *Installazione applicazioni* | registrazione standard di Python (serve anche a disinstallarlo) |
| menu Start | gruppo "Python 3.4" | creato dall'MSI |
| desktop dell'utente | tre collegamenti `.lnk` (Digidata, Diagnostica, Raccogli risultati); poi la cartella `risultati_prova_…` se si lancia `raccogli_risultati.bat` | `crea_collegamenti.vbs` |
| cartella d'installazione | `installa_log.txt`, `python_msi_log.txt` | log del rilevamento e dell'installazione di Python |

**Non tocca**: WinWCP e le sue cartelle, le DLL Axon (`AxDD132x.dll` resta dove è), WinASPI,
il `PATH` di sistema e le associazioni dei file `.py`. Per questo l'installazione di Python usa
`ADDLOCAL=DefaultFeature,SharedCRT,PrivateCRT,TclTk,pip_feature` invece di `ADDLOCAL=ALL`, che
aggiungeva `PrependPath` (Python nel `PATH` di sistema), `Extensions` (associazioni `.py`),
documentazione, strumenti e test. pip si usa con `--no-index --no-cache-dir
--disable-pip-version-check`: nessuna rete, niente nel profilo dell'utente.

**A capo**: i `.bat`, il `.vbs` e i `.txt` sono nel repository già con a capo CRLF e
`.gitattributes` vieta ogni conversione (`* -text`, `*.bat -text`, `*.txt -text`…), così il ZIP
di GitHub li consegna identici e `verifica_pacchetto.bat` può controllarne le dimensioni.
Dopo una modifica a uno dei file dell'elenco: `python strumenti/genera_verifica_pacchetto.py`
(e, se cambia la guida, `python strumenti/genera_guida_txt.py`).

---

## 4. Collaudo in laboratorio, passo per passo

Ogni giro in laboratorio è costoso: seguire l'ordine e, se un passo fallisce, fermarsi e
mandare i file indicati in § 5.

**0. Prima di tutto** — Digidata acceso *prima* del PC (le schede SCSI vedono le
periferiche all'avvio), cavo SCSI e terminatore collegati, LPF-8 acceso. **Chiudere
WinWCP** (la scheda si usa da un solo programma alla volta).

**1. Diagnostica** — desktop → *Diagnostica Digidata* (o `C:\denoising_live\diagnostica.bat`).
Dura ~30 s e scrive `C:\denoising_live\report_diagnostica.txt` con un passo per riga:

| passo | controlla |
|---|---|
| 1 | Windows, Python 3.4 a 32 bit, numpy (provato in un processo separato), separatore decimale |
| 1b | **rilevamento del PC** (`dlive/rilevamento.py`): Service Pack, 32/64 bit, diritti, Python e `msvcr100.dll`, schermo e scala dell'interfaccia, separatore decimale, spazio per 3 ore di registrazione, DLL Axon e WinASPI con md5, **impostazioni di WinWCP** (lette, mai modificate: canale ↔ ingresso, V/unità, campionamento, modo di registrazione; se WinWCP acquisisce da un altro ingresso la diagnostica usa quello), WinWCP aperto, orologio del PC; controlli dell'LPF-8 (aliasing) |
| 2 | WinWCP/WinEDR/AxoScope/Clampex aperti? |
| 3 | WinASPI: `wnaspi32.dll`, `aspi32.sys`, `GetASPI32SupportInfo` (stato e n. adattatori SCSI) |
| 4 | periferiche SCSI note a Windows, chiavi Axon nel registro |
| 5 | tutte le `AxDD132x.dll` trovate: percorso, dimensione, data, versione, MD5, caricabile? |
| 6 | dimensioni delle strutture ctypes (384 / 832 / 256 / 24 byte) |
| 7 | `DD132X_FindDevices`: nome, firmware, numero di serie della scheda |
| 8 | apertura, calibrazione (offset ADC/DAC, stato) |
| 9 | 10 campioni singoli dall'ingresso di `config.ini` e 5 da **ognuno** degli ingressi 0–15; dice **su quale ingresso c'è il segnale** (mediana o ampiezza oltre 20 conteggi; scollegati ±2) e se coincide con `config.ini`: `segnale trovato sull'ingresso AIn; config.ini usa AIm`. Se il segnale è su **un solo** ingresso diverso chiede `Il segnale arriva sull'ingresso AIn. Vuoi usarlo? (S/N)`: con S cambia solo la riga `canale_ingresso` di `config.ini` (copia in `config.ini.bak`, ASCII con CRLF), lo scrive nel log e nel report e usa quell'ingresso per il passo 10; con N, nessun ingresso o più ingressi non cambia nulla e lo dice |
| 10 | **10 s a 1000 Hz da AI2**: campioni ricevuti/attesi, persi, coerenza del contatore di posizione; salva `diagnostica_AAMMGG_HHMMSS.csv` e `.wcp`. Se fallisce riprova con le uscite analogiche escluse e lo dice |
| 11 | media, deviazione standard, saturazioni, RMS per banda (0–2, 2–20, 25–50, 49–51 Hz…), righe più forti, effetto del filtro predefinito |

In fondo c'è un **riepilogo OK / AVVISO / ERRORE**.

**2. Il `.wcp` della diagnostica in WinWCP** — chiudere la diagnostica, aprire
`C:\denoising_live\diagnostica_….wcp` con WinWCP: deve aprirsi, mostrare 10 s a 1 kHz in mV
con i valori attesi. Poi chiudere WinWCP.

**3. Anteprima** — desktop → *denoising_live (Digidata)* → **Avvia anteprima**. Controllare:
traccia grigia (grezzo) e rossa (filtrato), valore in mV plausibile, barra di stato con
*Persi: 0*, spazio su disco. Inserire nel campo **Taglio LPF-8 (Hz)** il valore impostato
sull'LPF-8 (oppure `Bypass`) e premere *Applica*: il campo accetta solo i valori che l'LPF-8 può
avere e avvisa se c'è rischio di aliasing. Provare i preset 1/2/5/10 Hz: il filtrato cambia subito
senza salti.

**4. Registrazione breve** — **Cartella dati…** (disco affidabile o chiavetta) → **Avvia
registrazione** → dopo ~2 minuti scrivere un marker e premere Invio → dopo altri 2 minuti
**Ferma**. Nella cartella ci sono `AAMMGG_NNN_raw.wcp`, `AAMMGG_NNN_filt.wcp`,
`AAMMGG_NNN.json`.

**5. Apertura in WinWCP** — aprire `…_raw.wcp` e `…_filt.wcp`: record da ~59,4 s, il record
N del grezzo copre lo stesso tempo del record N del filtrato; il marker compare come
identificativo del record ("M:testo"); l'ultimo record è completato con l'ultimo valore
(come gli sweep fermati prima in WinWCP) e ha identificativo "parz …s".

**6. (facoltativo) Prova di crash** — durante una registrazione staccare la spina o
terminare `python.exe` dal Task Manager: il file deve riaprirsi in WinWCP con al massimo
~1 s di dati in meno.

---

## 5. Se qualcosa va storto

| sintomo | causa probabile | cosa fare |
|---|---|---|
| "La scheda Digidata è già in uso da: winwcp.exe" | WinWCP aperto | chiuderlo |
| all'avvio: "Ho trovato le impostazioni di WinWCP…" | `[digidata] impostazioni_winwcp = chiedi` | Sì = usa canale/calibrazione di WinWCP (anche le volte successive); No = tieni `config.ini` |
| avviso "WinWCP è impostato in modalità Stimulus protocol" | WinWCP stimola dal Digidata | denoising_live non genera stimoli: chiedere al laboratorio prima di registrare |
| avviso "Rischio di aliasing" / "LPF-8 in Bypass" | taglio dell'LPF-8 sopra ~150 Hz o Bypass | abbassare il taglio dell'LPF-8 (il laboratorio usa 15 Hz) |
| passo 1b: orologio "anteriore all'uscita di WinWCP 5.1.6" | data del PC sbagliata (come quando furono registrati i vecchi file di prova del 2007-2008; il 24/11/2026 era giusta) | annotarlo e segnalarlo (la data di Windows si corregge solo con l'ok del laboratorio); nessun effetto sul programma: i nomi `AAMMGG` seguono la data del PC, come in WinWCP |
| passo 3: WinASPI non funziona / 0 adattatori | ASPI mancante dopo la reinstallazione di Windows, o driver del controller SCSI | installare AxoScope (installa WinASPI e il driver SCSI, guida di WinWCP p. 21), riavviare; controllare il controller SCSI in Gestione periferiche |
| passo 7: nessun Digidata | scheda accesa dopo il PC, cavo, terminatore, ID SCSI | spegnere tutto, accendere prima il Digidata, poi il PC |
| passo 5: nessuna DLL caricabile | WinWCP non installato, o senza `AxDD132x.dll`/`Axoutils32.dll` nella sua cartella | reinstallare WinWCP; se le DLL sono altrove, `percorso_dll` in `config.ini`. Le DLL non sono nella repository |
| passo 10 OK solo con "uscite = nessuna" | il driver non accetta il protocollo con le uscite | `uscite_analogiche = nessuna` in `config.ini` |
| "Persi: N" in rosso | il PC non ha letto in tempo il buffer (16 min di margine!) | mandare il log |
| banda rossa "ERRORE DI SCRITTURA" | disco guasto/pieno | l'acquisizione continua e i dati restano in memoria; fermare, scegliere un'altra cartella |
| numpy non funziona | CPU/libreria | nessun intervento: il programma usa il percorso in Python puro (barra di stato: "Python puro") |

**File da mandare** (sono tutti di testo tranne i `.wcp`):

* `C:\denoising_live\report_diagnostica.txt`
* la cartella `C:\denoising_live\log\` (log con rotazione, 10 × 2 MB al massimo)
* `C:\denoising_live\config.ini`
* per un problema di registrazione: i tre file `AAMMGG_NNN_raw.wcp`, `_filt.wcp`, `.json`
* i `diagnostica_*.csv` / `.wcp` (registrazione di 10 s col setup attuale: servono anche
  per rifare l'analisi del rumore, § 7.1)

---

## 6. Scelte fatte

### 6.1 Filtro: Bessel di 4° ordine a 5 Hz + notch 50 Hz (Q = 30)

Confronto sui 7 tratti con segnale dei file di prova (`strumenti/valuta_filtri.py`): rumore
residuo RMS nelle finestre "quiete" di 4 s (1424 finestre in cui il segnale stimato a fase
zero è piatto entro 2 mV), sovraelongazione e ritardo sul gradino, taglio 5 Hz, a 1000 Hz
(catena Digidata; alla frequenza originale dei file i numeri sono praticamente uguali):

| filtro (+ notch 50 Hz) | rumore residuo mediana / 90° perc. | sovraelongazione | ritardo al 50 % | attenuazione a 8,7 / 25 / 37,4 / 50 Hz (solo passa-basso) |
|---|---|---|---|---|
| Bessel 2 | 0,59 / 0,87 mV | 0,4 % | 39 ms | 8 / 24 / 31 / 36 dB |
| **Bessel 4 (predefinito)** | **0,56 / 0,84 mV** | **0,8 %** | **65 ms** | 10 / 42 / 56 / 66 dB |
| Bessel 6 | 0,56 / 0,84 mV | 0,7 % | 85 ms | 10 / 56 / 77 / 92 dB |
| Bessel 8 | 0,56 / 0,84 mV | 0,4 % | 101 ms | 10 / 67 / 95 / 115 dB |
| Butterworth 2 | 0,58 / 0,86 mV | 4,3 % | 45 ms | 10 / 28 / 35 / 40 dB |
| Butterworth 4 | 0,56 / 0,84 mV | **10,8 %** ✗ | 89 ms | 19 / 56 / 70 / 80 dB |

* Il rumore residuo è uguale per tutti (≈0,6 mV, sotto i 2 mV richiesti): quello che resta è
  nella banda passante (sotto 5 Hz), che nessun 5 Hz può togliere. Il rumore 25–50 Hz (fino
  a 55 mV RMS nel record peggiore) è già ridotto a ~0,4 mV dal Bessel 4.
* **Butterworth 4 è escluso**: sovraelonga dell'11 % sui gradini (criterio < 5 %).
* Tra i Bessel il 4° ordine ha il ritardo minore a parità di rumore, ed è il più leggero.
  Bessel 6 resta disponibile (stesso rumore, +14 dB a 25 Hz, +20 ms).
* Al taglio 1 Hz il ritardo sale a 0,33 s (dentro gli 0,5 s accettati); a 2 Hz 0,16 s, a
  10 Hz 0,03 s. La finestra mostra ritardo, sovraelongazione e attenuazione del filtro
  scelto.
* Unico tratto oltre i 2 mV al 90° percentile: `071210_001.wcp` record 2 (2,2 mV), dominato
  dalla **riga a 8,7 Hz**, che passa anche dall'LPF-8 a 15 Hz. Aggiungendo un notch a 8,7 Hz
  (`notch_hz = 50 ; 8,7`) scende a 1,46 mV (sovraelongazione 1,8 %). Non è nel predefinito
  perché il default confermato è "notch a 50 Hz": va deciso guardando una registrazione
  recente (§ 7.1).
* Sul segnale vero si verifica: risposta in frequenza identica a `scipy.signal.bessel/butter`
  (errore < 1e-9) e notch identico a `scipy.signal.iirnotch`.
* **Cambio dei parametri dal vivo senza buchi**: il nuovo filtro parte dallo stato di regime
  al livello attuale del filtrato e la sua uscita viene miscelata con quella del vecchio per
  0,25–2 s. Ogni cambio va nel log e nel JSON con ora e istante nel segnale.
* **Saturazione**: i campioni oltre ±32700 conteggi sono sostituiti dall'ultimo valore valido
  prima del filtro (il grezzo salvato resta intatto), con evento nel log e nel JSON.
* **Picchi isolati (aggiunta)**: nei file di prova ci sono picchi di 1–2 campioni **non
  saturati** (−1160 mV, +5595 mV, −4981 mV) che farebbero "suonare" il filtro. Uno
  scostamento > 500 mV dall'ultimo valore valido che dura ≤ 50 ms viene trattato come la
  saturazione (sostituito dall'ultimo valore valido); se dura di più passa, ma i suoi primi
  50 ms restano sostituiti dall'ultimo valore valido, quindi entra nel filtro con **50 ms di
  ritardo** (e con 50 ms di ritardo ne esce, al ritorno). Configurabile: `soglia_picchi_mv`
  (500; 0 lo disattiva) e `durata_max_picco_ms` (l'attesa: 50 ms, intervallo 0–500, un
  valore fuori intervallo blocca l'avvio con un messaggio chiaro).
* **Il ritardo di 50 ms è una scelta voluta.** Far "recuperare" al filtro i 50 ms trattenuti
  (ripassandoglieli quando l'escursione si rivela lunga) peggiorerebbe la reiezione degli
  artefatti: il filtro integrerebbe l'intera escursione (per esempio 104 ms) invece dei soli
  54 ms accettati e nel filtrato comparirebbe una gobba più grande. Nei file di prova le
  escursioni oltre 500 mV valgono circa 5 V, cioè 50 volte il segnale utile (≈ 100 mV): sono
  artefatti, non segnale fisiologico. **Il laboratorio deve confermarlo**: se quegli impulsi
  fossero eventi veri, l'attesa di 50 ms ne deforma l'inizio. Se il laboratorio dice che gli
  impulsi veri sono segnale, si abbassa `durata_max_picco_ms` in `config.ini`.
* **Sovracampionamento in simulazione**: i `.wcp` di prova (114–125 Hz) si riproducono a
  1000 Hz per interpolazione lineare, tranne le saturazioni e i salti tra due campioni più
  grandi di 500 unità, che restano bruschi: un picco di 1 campione interpolato diventerebbe
  una rampa di ~17 ms che il rilevatore dei picchi non riconosce (trovato dalla validazione,
  C4).
* **Sovracampionamento**: in modalità Digidata si acquisisce a 1000 Hz e il filtrato si salva
  a 125 Hz prendendo un campione ogni 8 dopo il filtro, che fa da anti-aliasing (−74 dB a
  62,5 Hz).
* Il nucleo ricorsivo del filtro è in Python puro **in entrambi i percorsi**: un IIR non si
  vettorializza con numpy senza scipy, ed è comunque leggero (§ 6.6). numpy accelera lettura
  e scrittura dei file, il buffer della scheda e le statistiche.

### 6.2 Formato dei file

* Intestazione **identica** a quella dei file di prova scritti da WinWCP 5.1.6: stesse chiavi
  nello stesso ordine (`VER=9`, `VERPROG=V5.1.6`, `CTIME`, `RTIMESECS`, `RTIME`, `NBH=1024`,
  `ADCMAX=32677`, `NC`, `NBA=2`, `NBD`, `AD`, `NR`, `DT`, `NZ`, `YO/YU/YN/YG/YZ/YR`, `TXPERC`,
  `PKPAVG`, `NSV…`, `ID`), righe CR LF, NUL fino a 1024 byte, **virgola decimale**, date come
  `10/12/2007 0:39:53`. Blocco di analisi come in `PutRecordHeaderOnly` (ACCEPTED, TEST,
  gruppo, tempo d'inizio del record, dt, range 10 V, identificativo di 16 caratteri, valori di
  analisi [n. record, gruppo, tempo]). Verificato con un test che confronta chiave per chiave
  con `071210_001.wcp` e con la lettura di `neo`.
* `RTIMESECS` = secondi dall'avvio di Windows all'inizio della registrazione, come WinWCP 5.1.6
  (guida V5.2.4 p. 163; nei file di prova non coincide con l'ora di `RTIME`). Separatore decimale:
  quello delle impostazioni internazionali di Windows (`separatore_decimale = auto`), come WinWCP,
  che rilegge comunque sia la virgola sia il punto.
* `ID=` dice chi ha scritto il file: `denoising_live 1.0 grezzo LPF-8 15 Hz` /
  `… filtrato Bessel ord.4 5 Hz, notch 50 Hz`.
* Calibrazione come nei file esistenti: `YG=0,001` V/mV, `YZ=0`, mV, `AD=10`. I conteggi del
  grezzo sono quelli della scheda, scalati come fa WinWCP (`ADCMAX=32677`); il filtrato è
  salvato con la stessa scala.
* **Record da 60 s → 59,392 s effettivi**: WinWCP vuole che i dati di un record occupino un
  numero intero di settori da 512 byte, quindi i campioni per record sono multipli di 256.
  Il filtrato ha 7424 campioni (125 Hz), il grezzo 59 392 (1000 Hz): i record N dei due file
  coprono **esattamente** lo stesso intervallo. La registrazione parte su un campione multiplo
  di 8 per allineare grezzo e filtrato.
* **Limite di campioni per record**: `MaxADCSamples` non è nei sorgenti di WinWCP; nel
  componente SESLabIO pubblico vale 1048576×16 (versioni dal 2014) e in `dd1320.pas`
  `DD132X_MaxADCSamples = 1048576`. I file di prova arrivano a 2 240 000 campioni per record.
  Il programma rifiuta qualunque combinazione durata × frequenza oltre **1 000 000** campioni
  per record (test su tutte le combinazioni); col default si è a 59 392.
* **Nomi dei file e nessuna sovrascrittura.** Ogni registrazione è `AAMMGG_NNN_raw.wcp`,
  `AAMMGG_NNN_filt.wcp`, `AAMMGG_NNN.json`, come i nomi di WinWCP: `AAMMGG` è la data **del PC**
  all'inizio della registrazione, `NNN` (001, 002…) il numero più basso tale che nella cartella dati
  **non esista nessuno** di `AAMMGG_NNN_raw.wcp`, `AAMMGG_NNN_filt.wcp`, `AAMMGG_NNN.json`,
  `AAMMGG_NNN.wcp` (il file di WinWCP con quel nome). Il numero si ricalcola **dai file su disco**
  a ogni registrazione, mai dalla memoria: vale anche dopo aver chiuso e riaperto il programma e
  se l'orologio del PC fosse sbagliato o ripartisse sempre dalla stessa data (era indietro quando
  furono registrati i vecchi file di prova, 2007-2008; dal report del 24/11/2026 è giusto). Un numero di cui resta anche un solo file (per esempio solo `_raw.wcp` dopo un crash) non
  si riusa; i file di WinWCP (`071210_001.wcp`, `071210_001.1.wcp`, `.avg`…) non si toccano mai.
  **In più, all'apertura**: i tre file si creano solo se non esistono (apertura esclusiva, `x` /
  `O_EXCL`), quindi anche se il calcolo del numero sbagliasse un file esistente non verrebbe mai
  aperto in scrittura: la registrazione non parte, compare il messaggio "il file … esiste già:
  non viene sovrascritto… l'acquisizione continua (anteprima)" e l'anteprima va avanti senza
  perdere campioni; si preme di nuovo *Avvia registrazione* (il numero si ricalcola) o si sceglie
  un'altra cartella. Test: `tests/test_nomi_file.py` (due registrazioni di seguito, riapertura
  in un processo nuovo, orologio tornato indietro, file rimasti da un crash, file di WinWCP,
  nome sbagliato di proposito; per ognuno contenuto e data di modifica di tutti i file già
  presenti restano identici). Le diagnostiche `diagnostica_AAMMGG_HHMMSS` con lo stesso nome
  prendono il suffisso `_2`, `_3`…
* Il JSON contiene: modalità e dispositivo (DLL, versione, firmware, numero di serie,
  calibrazione), frequenze, durata dei record, filtro iniziale e **tutti i cambi** (ora,
  istante, record, prima/dopo), **taglio LPF-8 dichiarato** e i suoi cambi, marker (ora,
  istante, record, istante nel record, testo), campioni persi (totale ed eventi), saturazioni
  e picchi (conteggi ed elenco), errori di scrittura, percorso di calcolo,
  `chiusura_regolare` (false se il programma si è interrotto).

### 6.3 Resistenza ai crash e disco poco affidabile

Scelta: **il record in corso è sempre su disco, intero, e già contato in `NR`**. Ogni secondo
(`intervallo_scrittura_s`) si riscrive il record in corso: i campioni acquisiti seguiti dalla
ripetizione dell'ultimo valore fino alla fine del record (lo stesso riempimento che WinWCP fa
negli sweep fermati prima), si aggiorna l'intestazione e si fanno `flush` + `os.fsync`.
Motivazione: i ricercatori sfogliano i dati in WinWCP per record; dopo un crash trovano un
file **valido e già completo** in cui l'ultimo record ha una coda costante, cosa che conoscono
già, e perdono al massimo ~1 s. L'alternativa (contare in `NR` solo i record chiusi)
perderebbe fino a 60 s, e lasciare il file più corto di `NR` lo renderebbe illeggibile.

Il costo è riscrivere al più un record al secondo (120 kB per il grezzo a 1000 Hz),
irrilevante anche su chiavetta USB 2.

Curiosità che conferma la scelta: **`081024_001.wcp` contiene due record ma l'intestazione
dice `NR=1`**, quindi WinWCP mostra solo il primo; il secondo (534 s di dati, iniziato a
370,5 s) è lì ma invisibile. Il lettore del programma lo segnala e lo recupera con
`leggi_wcp(…, recupera_extra=True)`.

Disco: cartella configurabile (anche chiavetta/disco esterno); spazio libero controllato
prima di iniziare (minimo 200 MB) e ogni 5 s durante (banda arancione sotto il minimo);
scrittura di prova prima di iniziare; ogni errore di scrittura compare subito in una banda
rossa, **l'acquisizione continua**, i record non scritti restano in memoria (fino a 400 per
file, oltre 6 ore) e si riprova al flush successivo. Il grezzo viene scritto **prima** di
filtro e grafico: un errore in questi non tocca il grezzo.

Spazio occupato: grezzo 7,2 MB/ora a 1000 Hz, filtrato 0,9 MB/ora.

### 6.4 Driver del Digidata (la parte più incerta)

Fonti, nell'ordine:

1. **header ufficiale Axon `AXDD132X.HPP`** (trovato nel progetto pubblico *clampy* su
   GitHub, copiato in `riferimenti/sdk_axon/AxDD132x.h`): strutture, enumerazioni, firme
   `WINAPI` (stdcall), codici d'errore;
2. **`dd1320.pas` di John Dempster** (repository pubblico `johndempster/SESComponents(XE)`,
   copiato in `riferimenti/winwcp_chiave/`): il codice con cui **WinWCP pilota questa scheda**;
   non era negli zip di WinWCP;
3. export delle DLL estratte (con `pefile`).

Le due fonti concordano su tutto quello che si usa. Il metodo di acquisizione **ricalca
WinWCP**: buffer circolare di ~1 000 000 campioni nella memoria del PC diviso in
sotto-buffer `DATABUFFER` collegati ad anello (600 × canali in × canali out campioni);
buffer riempito con 32767 e `eAIDataBits = DD132X_Bit0Tag` (il bit 0 è l'ingresso TAG,
quindi 32767 non può comparire nei dati): i campioni nuovi sono quelli diversi da 32767,
che dopo la lettura si rimettono a 32767; uscite DAC0/DAC1/digitali nel protocollo e tenute
a 0 V (meno l'offset di calibrazione) come fa WinWCP; `OpenDevice` tentata due volte come
WinWCP. **In più**: `DD132X_GetAcquisitionPosition` per accorgersi degli overrun
(campioni persi → contati, segnalati, sostituiti con l'ultimo valore per non spostare la
base dei tempi).

**Cosa resta incerto (verificato passo per passo dalla diagnostica):**

| punto | scelta | come lo controlla la diagnostica |
|---|---|---|
| `uChunksPerSecond` | **0 come WinWCP** (fase 5: in `dd1320.pas` il campo è "Unused", quindi WinWCP manda 0; l'header suggerisce 20; `[digidata] chunks_per_second`) | passo 10 (campioni ricevuti) |
| uscite nel protocollo | come WinWCP (config `uscite_analogiche`) | passo 10 riprova senza uscite se fallisce |
| significato di `GetAcquisitionPosition` (campioni dall'avvio) | se non è coerente col tempo trascorso viene ignorato e il rilevamento overrun usa solo il buffer pieno | passo 10: "rapporto posizione/letti ≈ 1" |
| `CalibrationData`: 16 DAC (header) o 8 (Delphi) | solo campi comuni (ADC, offset dei primi DAC) | passo 8 stampa i valori |
| valore 32767 come "vuoto" | come WinWCP | passo 10 conta i 32767 e i campioni col bit TAG |
| `GetAIValue` | solo diagnostica | passo 9 |

**Quale DLL** (dettagli in `riferimenti/dll/LEGGIMI_DLL.txt`):

| copia | versione | dipendenze |
|---|---|---|
| pCLAMP 10.3.2.1 (2013) | 1.1.1.6 | solo DLL di sistema |
| WinWCP 5.8.1 (installatore) | 1.0.0.38 (2001) + `axoutils32.dll` | quella che **WinWCP carica dalla propria cartella** (da `dd1320.pas`: "Problems using axDD132x.DLL supplied with pCLAMP/AxoScope V9 — now uses older axDD132x.DLL supplied with WinWCP") |
| pCLAMP 9.2.1.9 (2007) | 1.1.0.7 | solo sistema |
| update pCLAMP 8.2 (2003) | 1.0.0.39 + `axoutils32.dll` | |
| AxoScope 11.1 (2019) | `DD132x.dll` 1.1.1.5, richiede MSVCR100 | non usata |

Tutte esportano le funzioni usate (la 1.0.0.39 non ha le funzioni *ReadLast*, non usate) e
tutte parlano con la scheda via **WinASPI** (`wnaspi32.dll`, Adaptec 4.60), che si installa
con AxoScope. **Nessuna di queste DLL è distribuita** con il programma: si usa quella installata
sul PC (di norma quella di WinWCP).

Ordine di ricerca: `percorso_dll` di `config.ini` → cartella del programma → **cartelle di
WinWCP** (la DLL che WinWCP usa già con successo su questo PC) → pCLAMP/AxoScope
(`C:\Axon\…`, `Programmi\Molecular Devices\…`) → `system32`. Questa è una piccola deviazione
dal documento di progetto ("preferisci pCLAMP 10.3"): una DLL già installata e usata da WinWCP
sul PC ha la precedenza. La diagnostica prova **tutte** le copie
trovate e dice quale vede la scheda. La DLL viene caricata con `LoadLibraryEx` e
`LOAD_WITH_ALTERED_SEARCH_PATH` (e `axoutils32.dll` precaricata) perché le dipendenze
vengano cercate nella sua cartella.

WinWCP e il programma non possono girare insieme: all'avvio e prima di aprire la scheda si
cercano `winwcp.exe`, `winedr.exe`, `axoscope.exe`, `clampex.exe` tra i processi
(Toolhelp32, funziona anche su XP Home) con un messaggio chiaro; se `OpenDevice` fallisce il
messaggio cita di nuovo questi programmi.

### 6.5 Architettura e GUI

Thread di acquisizione (legge la scheda ogni 50 ms e mette i blocchi in coda) → thread di
elaborazione (grezzo su disco, filtro, filtrato su disco, buffer del grafico) → la GUI legge
solo lo stato e il buffer del grafico ogni 100 ms (10 Hz) e manda comandi in coda: **non
chiama mai la scheda** e non può bloccare l'acquisizione. Il grafico tiene min/max ogni
10 ms per 10 minuti e disegna al massimo un segmento verticale (min–max) per colonna di
pixel con due sole linee del Canvas aggiornate con `coords`.

### 6.6 Prestazioni (`strumenti/prestazioni.py`, 1000 Hz, filtro predefinito)

| | Python 3.12 + numpy 2.5 | Python 3.12 puro | **Python 3.4.10 + numpy 1.15.4** | **Python 3.4.10 puro** |
|---|---|---|---|---|
| filtro (saturazione, notch, Bessel, decimazione) | 0,48 ms | 0,49 ms | 1,05 ms | 1,06 ms |
| buffer del grafico | 0,13 | 0,13 | 0,30 | 0,31 |
| scrittura con fsync ogni secondo | 0,29 | 0,32 | 0,43 | 0,41 |
| disegno (10 Hz, 1000 px) | 7,6 | 7,3 | 14,0 | 10,1 |
| **totale per secondo di segnale** | **0,8 %** CPU | 0,8 % | **1,6 %** | 1,2 % |

Stima prudenziale per un PC con XP di ~15 anni fa (×10 rispetto a questo PC con Python 3.4):
**12–16 % di CPU**, quasi tutto per il disegno. Se servisse, `aggiornamento_hz = 5` in
`config.ini` dimezza il costo. Il test di 3 ore (10,8 milioni di campioni, 182 record) gira
senza degrado e con memoria stabile.

**Misura del programma intero (validazione, E4)**: la tabella sopra conta il tempo del codice
Python; misurando la CPU di tutto il processo con la finestra sotto Xvfb (1280×1024) si
ottiene, con il grafico a **5 aggiornamenti al secondo (predefinito)**, il **3,3–3,6 %** con
Python 3.12 e il 4,9–5,3 % con Python 3.4; a 10 aggiornamenti al secondo il 5,5–6,8 % (3.12) e
fino al 9,7 % (3.4), quasi tutto nel disegno del Canvas di Tk. Il calcolo da solo resta allo
0,1–0,3 %. Su una CPU limitata a 0,2 core (E6) 10 minuti di registrazione non perdono nulla
e il grafico resta entro 0,16–0,31 s. Il selettore **Aggiornamento (Hz)** del pannello "Grafico"
(2, 5, 10) cambia il valore dal vivo: sul PC del laboratorio guardare la CPU nel Task Manager
e, se serve, scendere a 2.

### 6.7 numpy e ripiego senza numpy

All'avvio numpy viene provato **in un processo separato** (`dlive/verifica_numpy.py`): su una
CPU vecchia una libreria di calcolo può far chiudere Python di colpo, cosa che un
`try/except` non intercetta. Se la prova fallisce si usa il percorso in Python puro (lettura
e scrittura dei `.wcp` con `array`/`struct`, filtro, grafico, buffer della scheda); l'esito è
nel log, nel JSON, nella barra di stato e nel report della diagnostica. Ho controllato gli
import dei binari della wheel numpy 1.15.4 win32: solo funzioni presenti in XP (nessuna API
Vista+); la OpenBLAS inclusa sceglie le routine in base alla CPU (serve almeno SSE2,
presente dal Pentium 4).

### 6.8 Compatibilità Python 3.4

Niente f-string, annotazioni, `async`, `subprocess.run`, `math.inf`, ecc.; nessuna API numpy
rimossa. `vermin --target=3.4- --violations` su tutto il codice di runtime: **nessuna
violazione, minimo richiesto 3.3**. Tutta la suite di test gira in Docker su
**Python 3.4.10 + numpy 1.15.4 + scipy 1.2.3 + pytest 4.6**, compresa la GUI su Xvfb.

---

## 7. Cosa resta da verificare sull'hardware vero

1. **Rumore del setup attuale.** I file di prova (2007–2008) hanno rumore forte a 25–50 Hz che
   con l'LPF-8 a 15 Hz (8 poli Bessel: −14 dB a 30 Hz, −23 dB a 37,4 Hz, −40 dB a 50 Hz
   secondo il manuale e il modello) non dovrebbe arrivare al Digidata: o erano registrati con
   l'LPF-8 in *Bypass*/impostato diversamente, o il rumore entra **dopo** il filtro (cavo
   LPF-8→Digidata, masse). Il passo 11 della diagnostica misura le bande; con il CSV/WCP di
   10 s (e meglio una registrazione di qualche minuto) si rifà `strumenti/valuta_filtri.py`
   e si decide se serve il notch a 8,7 Hz.
2. **Driver**: tutti i punti della tabella in § 6.4; in particolare che arrivino 10 000 campioni
   in 10 s con `uChunksPerSecond = 0` (il valore di WinWCP) e che i campioni dispari e uguali a
   32767 siano 0.
3. **Overrun** in una registrazione lunga (il contatore "Persi" deve restare 0).
4. **Apertura in WinWCP 5.1.6** dei file `_raw`/`_filt`. Dai sorgenti (2013 e 2024) WinWCP
   rilegge virgola e punto e usa `RTIMESECS` solo se > 0 (`docs/analisi_sorgenti.md` § D).
5. **Calibrazione e ingresso**: all'avvio il programma propone canale e calibrazione di WinWCP
   (`lab interface settings.xml`); con il guadagno dell'LPF-8 diverso da 1 il segnale in mV va
   corretto (`yg = 0,001 × guadagno`: il programma avvisa); i valori in mV del grezzo e quelli di
   WinWCP sullo stesso segnale devono coincidere. Nei file di prova il segnale è su Ch.0 o Ch.4,
   non sempre sullo stesso canale: l'ingresso di oggi lo confermano il passo 1b e il passo 9.
6. **Prestazioni reali** su quel PC (barra di stato, Task Manager) e leggibilità sullo
   schermo vero (la finestra si adatta da 1024×768 in su; se i testi sono troppo piccoli o
   grandi: **Dimensione interfaccia**, § 1).
7. **Prova di crash** (§ 4 passo 6) sul disco/chiavetta che si userà.
8. **Stimolazione**: i file di prova non ne mostrano traccia (`docs/analisi_sorgenti.md` § C);
   la prova certa sono i log di WinWCP raccolti dal comando (§ 9).
9. **Impulsi oltre 500 mV**: chiedere al laboratorio se le escursioni di ~5 V lunghe decine di
   ms (come in `071211_001.1.wcp` a 1183 s) sono artefatti (predefinito: vengono trattenute
   50 ms, § 6.1) o eventi veri. Se il laboratorio dice che gli impulsi veri sono segnale, si
   abbassa questo valore: `[filtro] durata_max_picco_ms` in `config.ini` (0–500 ms).

## 8. Test eseguiti (riepilogo)

* **Validazione oggettiva** (§ 11): 42 voci con soglie fisse, verdetto *PRONTO PER LA PROVA IN LABORATORIO*.
* **375 test pytest** su Linux (tutti superati tranne 4 saltati senza display virtuale; 32 in `tests/test_bat_espansione.py` con l'emulatore delle regole di cmd su ogni `.bat` (§ 3); 56 in `tests/test_pacchetto.py` sulla cartella d'installazione e sulle guide, con gli script `.bat` eseguiti con Wine e **la guida rapida seguita alla lettera** sotto Wine a 32 bit: `prepara.bat`, `installa.bat` con il vero Python 3.4.4, Diagnostica con la DLL simulata e la domanda sull'ingresso, il programma in modalità Digidata con la DLL simulata (`main.py --finto --prova-gui`), `raccogli_risultati.bat`, § 3; 21 in `tests/test_ingresso_segnale.py` sul passo 9 della diagnostica (ingresso del segnale, domanda S/N, `config.ini` cambiato solo in quella riga e salvato dal Blocco note) e sulle diagnostiche brevi (`--secondi` sotto 2 s); 6 in `tests/test_rapporto_verdetto.py` sul verdetto del rapporto riproducibile; 12 in `tests/test_nomi_file.py` sulla numerazione dei file; 71 della fase 5 in `tests/test_fase5.py`: protocollo come WinWCP, `RTIMESECS`, LPF-8, impostazioni di WinWCP, rilevamento sul posto con un ambiente finto, comando di raccolta, `leggi_info_lab.py`) (Python 3.12, numpy 2.5, scipy 1.18, neo 0.14): filtri contro
  scipy (risposta, notch, poli di Bessel tabulati, sosfilt), attenuazioni, blocchi = colpo
  unico, ritardo/sovraelongazione, cambi dal vivo senza salti, saturazione e picchi,
  decimazione; lettura dei 7 file di prova (con e senza numpy) contro il lettore di
  riferimento e contro `neo`; andata e ritorno (anche con `neo`); intestazione chiave per
  chiave; file troncato; crash simulato; errore di scrittura simulato; limiti dei record;
  end-to-end simulazione→filtro→salvataggio→rilettura con filtrato **identico** al filtraggio
  offline causale; campioni persi, marker, cambi del filtro e dell'LPF-8 nel JSON; **3 ore
  continue** a 1000 Hz con memoria stabile; driver Digidata contro la DLL finta (protocollo,
  anello dei buffer, lettura senza buchi, overrun, contatore incoerente, scheda assente/occupata,
  ricerca della DLL); configurazione; **GUI** avviata, in registrazione, con marker e cambio
  del filtro, chiusa senza errori (con e senza numpy); **dimensione dell'interfaccia**
  (scala automatica, chiave di configurazione, nessun controllo fuori dalla finestra a
  1024×768 e 1280×1024, passaggio a 200 % e ritorno dal vivo); `vermin`.
* **233 test** (fase 5) sugli stessi file in Docker con **Python 3.4.10 + numpy 1.15.4** e Xvfb
  (esclusi solo quelli che richiedono `neo`/`vermin`, non installabili su 3.4, e quello di
  3 ore). Per ripeterli:

  ```bash
  cd /tmp && mkdir -p d34 && cat > d34/Dockerfile <<'EOF'
  FROM python:3.4
  RUN echo "deb http://archive.debian.org/debian stretch main" > /etc/apt/sources.list \
   && apt-get -o Acquire::Check-Valid-Until=false update -qq \
   && apt-get install -y -qq --allow-unauthenticated xvfb xauth
  RUN pip install "numpy==1.15.4" "pytest==4.6.11" "scipy==1.2.3"
  EOF
  docker build -t dlive-py34 d34
  cd denoising-live
  docker run --rm --init -v "$PWD":/src:ro dlive-py34 bash -c \
    "cp -r /src /w && cd /w && DLIVE_TEST_VELOCI=1 DLIVE_DISPLAY_VIRTUALE=1 xvfb-run -a python -m pytest tests -q -p no:cacheprovider"
  ```
* **Script di Windows eseguiti con Wine** (`tests/test_pacchetto.py`, § 3): si saltano se
  mancano le immagini Docker. Per crearle (serve la rete una volta):

  ```bash
  mkdir -p /tmp/wine && cd /tmp/wine
  printf 'FROM debian:bookworm-slim\nRUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wine64 wine && rm -rf /var/lib/apt/lists/*\nENV WINEDEBUG=-all\n' > Dockerfile
  docker build -t dlive-wine . && docker run --name wi dlive-wine bash -c '/usr/lib/wine/wine64 wineboot --init; /usr/lib/wine/wineserver -w'
  docker commit wi dlive-wine:pronto && docker rm wi
  # Wine a 32 bit, per installare davvero Python 3.4.4 (prova completa di installa.bat):
  printf 'FROM debian:bookworm-slim\nRUN dpkg --add-architecture i386 && apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wine wine32 wine64 xvfb xauth && rm -rf /var/lib/apt/lists/*\nENV WINEDEBUG=-all WINEARCH=win32 WINEPREFIX=/root/.wine32\nRUN wine wineboot --init; wineserver -w; true\n' > Dockerfile32
  docker build -f Dockerfile32 -t dlive-wine32 .
  ```
* Diagnostica eseguita con la DLL finta (`python diagnostica_digidata.py --finto`; con
  `--finto-ingresso N` il segnale c'è solo sull'ingresso N, per provare la domanda del passo 9).
  Il programma in modalità Digidata con la DLL finta: `python main.py --digidata --finto`
  (solo per le prove: nessuna scheda vera; con `--prova-gui 15` registra da solo ed esce).
* **Non testabile senza la scheda**: la DLL vera, WinASPI, il bus SCSI, la temporizzazione
  reale e gli overrun veri, l'apertura dei file in WinWCP 5.1.6 (non ho un Windows con
  WinWCP), il comportamento su XP (Python 3.4 a 32 bit, tkinter su XP, numpy su quella CPU).

## 9. Quando torna la cartella `info_pc_lab`

**Prima della visita** il collega incolla `docs/comandi_da_incollare.txt` nel Prompt dei
comandi del PC del laboratorio (clic destro sulla barra del titolo → Modifica → Incolla). Non fa
domande, non modifica nulla, dura pochi minuti e crea sul Desktop la cartella `info_pc_lab` con
`info_pc_lab.txt` e `wcp_recenti\`. Cosa raccoglie e perché, riga per riga:
[`docs/comando_laboratorio.md`](docs/comando_laboratorio.md). Non è stato provato su Windows (qui
non ci sono Windows né Wine): è stato rivisto riga per riga e controllato da `test_comando_*`.

Quando la cartella torna:

1. copiarla in `info_pc_lab/` accanto alla cartella del progetto (fuori dal progetto: contiene
   dati del laboratorio);
2. lanciare

   ```bash
   cd denoising-live
   python strumenti/leggi_info_lab.py
   # oppure con un'altra cartella, o senza l'analisi dei .wcp (più veloce):
   python strumenti/leggi_info_lab.py PERCORSO --senza-wcp
   ```

   Lo script non modifica nulla e stampa:

   | parte | da dove | cosa cambia |
   |---|---|---|
   | installazione | `ver`, Service Pack, 32/64 bit, amministratore, spazio su C: | sotto XP SP2 portare SP3; senza diritti portare la password di un amministratore |
   | impostazioni di WinWCP | `winwcp.ini`, `lab interface settings.xml` | `canale_ingresso` (ingresso fisico del canale di WinWCP), `yg` (V/unità × guadagno), `unita`, `nome_canale`, `yz`, `frequenza_salvataggio_hz` (1/DT) |
   | stimolazione | `RECMODE`, `FILEVPR`, righe "Stimulus Protocol" dei log | se il laboratorio stimola da WinWCP lo scrive **in evidenza**: cambia il progetto |
   | file `.wcp` sul disco | elenco con data e dimensione | quali file chiedere se quelli copiati non bastano; segnala l'orologio del PC indietro |
   | rumore dei `.wcp` recenti | `wcp_recenti\` | per ogni file: canale col segnale, rumore per banda, righe spettrali, rumore residuo con i preset 1/2/5/10 Hz; **taglio suggerito** (resta 5 Hz se il rumore residuo al 90° percentile è sotto 2 mV, il criterio di § 6.1, altrimenti il più alto che ci sta) e **notch** suggeriti per righe tra 2 e 20 Hz (come 8,7 Hz) |

   e in fondo l'elenco delle righe di `config.ini` da cambiare rispetto ai valori predefiniti;
3. mettere quei valori in `C:\denoising_live\config.ini` sul PC del laboratorio (o in
   `config.ini` della repository prima di scaricarla; oppure lasciarli proporre dal programma
   all'avvio, § 10) e, se il taglio o i notch cambiano, rifare `./valida.sh`.

DLL Axon, WinASPI, schermo, separatore decimale, Python e diritti non servono prima: li rileva
`installa.bat` e la diagnostica (passo 1b) sul posto.

---

## 10. Configurazione (`config.ini`)

Il file viene creato commentato al primo avvio; i numeri si scrivono con virgola o punto.
Le voci principali: `[digidata] canale_ingresso = 2`, `frequenza_acquisizione_hz = 1000`,
`percorso_dll`, `uscite_analogiche`, `impostazioni_winwcp = chiedi` (chiedi / usa / ignora: valori
iniziali da WinWCP, § 4 passo 1b), `chunks_per_second = 0` (come WinWCP); `[filtro] tipo = bessel`, `ordine = 4`,
`taglio_hz = 5`, `notch_hz = 50`, `soglia_picchi_mv = 500`, `durata_max_picco_ms = 50`
(0–500, § 6.1); `[salvataggio]
frequenza_salvataggio_hz = 125`, `durata_record_s = 60`, `intervallo_scrittura_s = 1`,
`separatore_decimale = auto` (quello di Windows; o virgola/punto); `[grafico] aggiornamento_hz = 5` (2, 5 o 10, anche dalla
finestra); `[calibrazione] yg = 0,001`, `yz = 0`, `unita = mV`;
`[lpf8] taglio_hz = 15` (valori dell'LPF-8: 0,1-199,9 Hz a passi di 0,1, 200-19 990 Hz a
passi di 10; 0 = Bypass; avviso di aliasing sopra ~150 Hz), `guadagno = 1`; `[interfaccia] dimensione = auto` (o una percentuale, § 1). La
finestra salva da sola filtro, taglio LPF-8, cartella dati e dimensione dell'interfaccia.

---

## 11. Come validare il programma

Per sapere **con certezza se il programma funziona** senza essere esperti di
elettrofisiologia c'è un solo comando:

```bash
cd denoising-live
./valida.sh            # tutto, ~11 minuti
./valida.sh --lungo    # aggiunge la prova di 3 ore accelerata (B8), ~13 minuti
```

Alla fine stampa il **verdetto** e scrive il rapporto in
`docs/validazione/rapporto_validazione.md`.

> **Rapporto ufficiale e parte riproducibile.** Il rapporto di validazione ufficiale è
> `docs/validazione/rapporto_validazione.md`, ottenuto con i **dati reali del laboratorio**
> (`riferimenti/dati/`, i file `.wcp`, e l'header Axon in `riferimenti/sdk_axon/`). Quei dati
> non sono pubblicati: dove mancano, `./valida.sh` esegue **solo la parte riproducibile** (i
> test che li usano risultano saltati, "non eseguibile senza i dati del laboratorio", mai
> FAIL), scrive il suo rapporto in `validazione_uscita/rapporto_riproducibile/` e non tocca
> quello ufficiale. Se non fallisce nulla, il verdetto di quel rapporto è
> **«PARZIALE: 0 FAIL, N test non eseguibili senza i dati del laboratorio»** (oggi N = 8: B6,
> C1–C5, D1), non «NON PRONTO», e rimanda al rapporto ufficiale. Lo stesso vale per `pytest`. La **prima pagina** è per chi non è
esperto: il verdetto in grande, cinque domande con risposta Sì/No e il numero che la motiva
(«Il filtro toglie il rumore?», «Deforma il segnale utile?», «Perde o altera dati?», «I file
si aprono in altri programmi?», «Regge registrazioni lunghe e crash?», «Funziona con la scheda
(finta) e su un PC lento?») e l'elenco di ciò che
**non** è stato verificato. Seguono l'analisi dei FAIL, la tabella completa (ID, cosa
controlla, valore misurato, soglia, esito, critico sì/no) e le figure.

**Verdetto**:

| verdetto | quando |
|---|---|
| **PRONTO PER LA PROVA IN LABORATORIO** | tutti i test CRITICI sono PASS e i guasti finti M1–M4 vengono rilevati |
| **PRONTO CON RISERVE** | come sopra, ma almeno un test "importante" è FAIL (le riserve sono spiegate) |
| **NON PRONTO** | almeno un test CRITICO è FAIL o non verificabile, oppure un guasto finto passa inosservato |
| **PARZIALE: 0 FAIL, N test non eseguibili senza i dati del laboratorio** | solo nel rapporto riproducibile (repository senza `riferimenti/dati/`): nessun FAIL, guasti finti rilevati, e i test critici non verificati lo sono solo per i dati mancanti; il verdetto completo è nel rapporto ufficiale |

Il verdetto riguarda **solo il software in simulazione**. Il funzionamento con il Digidata
vero si vede solo con la diagnostica in laboratorio (§ 4), e quale frequenza di taglio sia
scientificamente giusta lo decide il laboratorio, non i test.

**Cosa fa** (`tests/validazione/`; le soglie sono in `catalogo.py` e non vanno cambiate per
far passare un test):

* **A — filtro** su un segnale sintetico di 10 minuti a verità nota (livelli e gradini,
  deflessioni di 1 s, rumore a 50 / 8,7 / 37,4 Hz e 25–50 Hz, picchi a fondo scala): guadagno,
  livello dopo i gradini, sovraelongazione, ritardo, attenuazioni, notch, rumore residuo, picchi,
  filtraggio a blocchi, confronto con scipy su 24 filtri, stabilità, cambi dal vivo, percorso
  senza numpy. I valori attesi vengono dalla verità, da formule o da scipy, mai dal codice del
  programma.
* **B — catena completa**: il sintetico scritto come `.wcp` (scrittore indipendente) →
  `SimulatedDevice` → `Sessione` costruita come nella GUI → `_raw.wcp`, `_filt.wcp`, `.json`;
  grezzo identico, filtrato uguale a scipy, nessun campione perso, niente aliasing, marker,
  apertura con neo e confronto con un file WinWCP 5.1.6, `kill -9`, 3 ore, disco pieno.
* **C — i 7 file reali** (`riferimenti/dati/`, con il record nascosto di `081024_001.wcp`)
  confrontati con un filtro di riferimento a fase zero; figure per ogni file.
* **D — driver Digidata**: strutture `ctypes` contro l'header Axon compilato con `g++ -m32`,
  sequenza delle chiamate e messaggi d'errore con la DLL finta, overrun; elenco di ciò che
  solo la scheda può dire.
* **E — compatibilità**: tutti i test A e B con **Python 3.4 + numpy 1.15** (Docker),
  `vermin`, la finestra sotto Xvfb a 1280×1024 (avvio, anteprima, cambio filtro, marker,
  registrazione, chiusura: 0 eccezioni), CPU, ritardo del grafico; **E6** 10 minuti di
  registrazione con la CPU limitata a 0,2 core (`docker --cpus=0.2`); **E7** la finestra vera
  in **modalità Digidata** con la DLL finta: registrazione conforme, errori (DLL mancante,
  scheda assente, WinASPI, overrun) mostrati in chiaro e riavvio dopo ogni errore.
* **M — prova dei test**: quattro guasti finti (taglio raddoppiato, stato del filtro azzerato
  a ogni blocco, notch a 60 Hz, un campione saltato ogni 1000) introdotti uno alla volta in una
  copia temporanea del codice; ognuno deve far fallire almeno un test critico.

**Requisiti** (nessuna rete): l'ambiente conda `denoising_live` (numpy, scipy, neo,
matplotlib, pytest, vermin), `g++` e l'immagine Docker `dlive-py34` di § 8 (Python 3.4 +
numpy 1.15 + scipy 1.2 + Xvfb). Senza Docker i test E1, E3, E5 e la parte nella finestra di B9
risultano NON VERIFICABILI e il verdetto non può essere "pronto". I risultati grezzi restano
in `validazione_uscita/` (fuori da git); quelli del rapporto in `docs/validazione/risultati/`.

**Stato attuale** (`docs/validazione/rapporto_validazione.md`, dopo la correzione della
numerazione dei file, `./valida.sh`): **PRONTO PER LA PROVA IN LABORATORIO** (41 voci PASS, la
prova di 3 ore B8 si esegue solo con `--lungo`: nella fase 5 `./valida.sh --lungo` ha dato 42 su
42; nel primo giro della fase 5 E6 era FAIL di poco, 1017 ms di ritardo massimo del grafico
contro 1 s, sotto la CPU di Docker a 0,2 core: vedi l'analisi della fase 5 nel rapporto).
Storia dei rapporti in `docs/validazione/`: `rapporto_iniziale` (codice non modificato)
*NON PRONTO*; `rapporto_fase2` *PRONTO CON RISERVE* dopo tre correzioni (anteprima con il
Digidata che non partiva per una frequenza a 0 Hz, ultimo campione perso dal simulatore,
picchi trasformati in rampe); `rapporto_fase3` *PRONTO CON RISERVE*: decisioni D1–D3, nuovi
test C3b, E6, E7, e un altro bug corretto (dopo un avvio fallito la scheda restava aperta);
`rapporto_fase4` *PRONTO PER LA PROVA IN LABORATORIO*: decisioni D4–D8 (ritardo di 50 ms voluto,
`durata_max_picco_ms` 0–500 ms, `coda_max_s` tolto); fase 5: analisi dei sorgenti di WinWCP
(`docs/analisi_sorgenti.md`), protocollo con `uChunksPerSecond = 0` come WinWCP, `RTIMESECS`
dall'avvio di Windows, campo LPF-8 con i soli valori veri e avvisi di aliasing, lettura delle
impostazioni di WinWCP, rilevamento sul posto, comando di raccolta minimo; poi i file di una
registrazione si creano solo se non esistono (nessuna sovrascrittura, § 6.2). La logica del filtro e
del rilevatore non è cambiata.
