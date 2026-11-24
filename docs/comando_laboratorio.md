# Comando minimo per il PC del laboratorio

File: `docs/comandi_da_incollare.txt` (37 righe, ASCII, a capo CR LF). Il collega lo
incolla nel Prompt dei comandi di Windows XP; non fa domande, non modifica nulla sul PC, scrive
solo `info_pc_lab\info_pc_lab.txt` e `info_pc_lab\wcp_recenti\` sul Desktop, dura pochi minuti
(una sola scansione del disco C:) e alla fine dice di copiare sulla chiavetta tutta la cartella.

**Regola**: si tiene solo ciò che soddisfa almeno un criterio:
1. non si ricava dai materiali e non si rileva sul posto (`dlive/rilevamento.py`, punto G di
   `docs/analisi_sorgenti.md`);
2. senza saperlo prima, la prima visita può fallire;
3. serve a scegliere prima della visita i valori predefiniti (file recenti, impostazioni di
   WinWCP).

**Non è stato eseguito**: su questo PC non ci sono Windows né Wine. È stato rivisto riga per
riga (sotto) e controllato da `tests/test_fase5.py` (`test_comando_*`: solo ASCII, CR LF, niente
`set /p`, PowerShell, `pause`, `%%`, nessun comando che modifica il sistema, ogni scrittura va in
`%F%` o in `%D%\wcp_recenti\`, nessuna delle raccolte tolte).

## Righe tenute

| righe | cosa | criterio | motivazione |
|---|---|---|---|
| 1 | `echo off` | — | non mostra i comandi durante l'esecuzione (si rimette `echo on` alla fine) |
| 2-9 | commenti | — | istruzioni per il collega |
| 10-13 | cartella `info_pc_lab`, `wcp_recenti`, file `info_pc_lab.txt` | — | le sole scritture permesse |
| 14 | intestazione con data, ora e nome del PC | 1 | la data del PC confrontata con il giorno vero dice subito se l'orologio è indietro (§ 0 dell'analisi) |
| 15-16 | titoli | — | avanzamento a video e sezione nel file |
| 17 | `ver` | 2 | versione di Windows: Python 3.4 richiede almeno XP |
| 18 | `CSDVersion` | 2 | **Service Pack**: sotto XP SP2 Python 3.4 non parte (`msvcr100.dll`), andrebbe portato SP3 |
| 19 | `PROCESSOR_ARCHITECTURE`/`…W6432` | 2 | 32 o 64 bit: su XP x64 non ci sono WinASPI e il driver SCSI a 32 bit |
| 20 | `fsutil fsinfo drives` → `AMMINISTRATORE=SI/NO` | 2 | senza diritti di amministratore `installa.bat` non installa Python: va portata la password giusta. `fsutil` richiede l'amministratore e qui legge solo l'elenco dei dischi |
| 21 | `dir C:\` (riga dei byte liberi) | 2 | servono ~150 MB per installare |
| 22-24 | elenco di **tutti i `.wcp` di C:** con data e dimensione | 3 | dice dove sono e quali sono i file recenti anche se mancano le impostazioni di WinWCP; serve a chiedere i file giusti se quelli copiati non bastano. È l'unica scansione completa del disco |
| 25-27 | contenuto di `winwcp.ini`, `lab interface settings.xml`, `amplifier settings.xml` (cercati in `%ALLUSERSPROFILE%`, `%ProgramFiles%`, `C:\WinWCP`, `C:\WinWCPXE`) | 3 | canale ↔ ingresso fisico, V/unità, guadagno, campionamento, modo di registrazione, cartella dati e file recenti: da qui `strumenti/leggi_info_lab.py` ricava i valori di `config.ini` (sul posto li legge anche il programma, ma prima della visita servono per preparare la configurazione e decidere il filtro) |
| 28-29 | righe dei log di WinWCP: "Stimulus Protocol", "Recording Started", "Stopped (", "New data file" | 2, 3 | **unica prova certa sulla stimolazione** (§ C dell'analisi): se il laboratorio la usa, il programma non può sostituire WinWCP e la visita va ripensata |
| 30-31 | copia dei file `FILE=`, `RF0`-`RF3` di `winwcp.ini` (sotto 400 MB) | 3 | i file usati per ultimi in WinWCP, registrati con il setup di oggi: servono a rifare l'analisi del rumore e a scegliere taglio e notch. Non si cercano per nome (`25*.wcp`) perché l'orologio del PC è indietro |
| 32 | copia dei 3 `.wcp` più recenti della cartella dati `DDIR=` | 3 | come sopra, se i recenti di WinWCP sono pochi; l'ordine per data funziona anche con l'orologio sbagliato, purché avanzi |
| 33-35 | elenco dei file copiati, riga di fine | — | per controllare che la copia sia completa |
| 36-37 | `echo on` e messaggio finale | — | dice al collega di copiare tutta la cartella sulla chiavetta |

## Tolto rispetto alla versione precedente (`comandi_da_incollare.txt` nella cartella del progetto)

| raccolta tolta | perché |
|---|---|
| `systeminfo`, `wmic os/cpu`, RAM, CPU | Windows/SP/bit restano con comandi da un secondo; CPU (SSE2) e RAM le gestisce il programma da solo (numpy provato in un processo separato, ripiego in Python puro) |
| `net user` | sostituito da una prova diretta dei diritti (`fsutil`) |
| risoluzione, DPI (`FontDPI`) | rilevati sul posto dal programma, che adatta i caratteri (`dlive/scala.py`, rilevamento "Schermo") |
| impostazioni internazionali | separatore decimale rilevato sul posto e usato per i `.wcp` (`separatore_decimale = auto`); WinWCP rilegge virgola e punto |
| `wmic logicaldisk` (tutti i dischi) | lo spazio per le registrazioni lo controlla il programma (avviso sotto 3 ore); resta solo C: per l'installazione |
| `python --version`, `C:\Python*`, `msvcr100.dll`, `python34.dll` | `installa.bat` li rileva e usa un Python 3.4 già installato; `msvcr100.dll` la installa l'MSI se manca |
| programmi installati (`Uninstall`) | non serve prima: la versione di WinWCP è nota (5.1.6, confermata dai file) e le DLL le trova la diagnostica |
| registro Axon, periferiche SCSI, `driverquery`, `ASPI32` | rilevati dalla diagnostica (passi 3-4); WinWCP funziona già con la scheda, quindi SCSI e ASPI ci sono |
| ricerca di `axdd*.dll`, `wnaspi*.dll`, `aspi32.*` su tutto il disco e `wmic datafile` | la diagnostica prova tutte le DLL candidate (passo 5) e `rilevamento` le confronta con gli md5 noti; la chiavetta ha comunque tutte le versioni |
| eseguibili `winwcp*.exe`, `winedr*.exe` | la cartella di WinWCP la trova il programma; la versione è nota |
| tutti gli `.ini`/`.xml` delle cartelle WinWCP/SESLAB | restano solo i tre file di impostazioni che WinWCP 5.1.6 usa davvero |
| elenco dei `.vpr` | i protocolli della 5.1.6 sono `.xml` (dal 2011); `RECMODE`, `FILEVPR` e i log dicono se si usano |
| elenco delle cartelle con `.wcp` (formato `dir /s`) | sostituito dall'elenco con data e dimensione (righe 22-24) |
| copia di `C:\25*.wcp` e `C:\26*.wcp` | **sbagliata**: i nomi seguono l'orologio del PC, che segna il 2007-2008 |
| apertura del Blocco note | non serve: il messaggio finale basta |

## Quando la cartella torna dal laboratorio

Metterla in `info_pc_lab/` accanto alla cartella del progetto (fuori da git: contiene dati del
laboratorio) e lanciare
`python strumenti/leggi_info_lab.py` (README § 9).
