# Guida completa: installare e provare denoising_live

**La versione in una pagina è [GUIDA_RAPIDA.md](GUIDA_RAPIDA.md)** (`GUIDA_RAPIDA.txt`):
di solito basta quella. Questa guida spiega, passo per passo, come portare denoising_live sul PC del laboratorio
(Windows XP, senza rete) e fare la prima prova con il Digidata 1322A.

**Importante: il programma non è mai stato provato con il Digidata vero.** Questa è la
prima prova. Non serve che tutto funzioni: serve che tu segua i passi e riporti quello che
succede (parte D). Se un passo non va, fermati, segna il messaggio, fai una foto e passa
alla parte D.

Cosa serve:

* un PC con internet (Windows 10 o 11 va benissimo);
* una chiavetta USB con almeno 100 MB liberi;
* il PC del laboratorio, con l'ok del professore;
* circa 15 minuti a casa e 30-40 minuti in laboratorio.

Cosa cambia sul PC del laboratorio: Python 3.4 in `C:\Python34`, il programma in
`C:\denoising_live` e tre icone sul desktop. **WinWCP, le sue impostazioni e i suoi file
non vengono toccati.**

**Le finestre nere non si chiudono da sole**: alla fine di ogni script (anche dopo un
errore) la finestra resta aperta; leggi la scritta, fai una foto se serve, poi chiudila.
La prima riga dice la versione, per esempio `denoising_live versione 2026-11-25`: deve
leggersi nelle foto.

---

## A. Sul PC con internet

**A1. Scaricare il progetto.** Apri <https://github.com/colasantoemanuele-cloud/denoising-live>,
premi il pulsante verde **Code** e poi **Download ZIP**. Si scarica il file
`denoising-live-main.zip` (di solito nella cartella *Download*).

**A2. Estrarlo.** Clic destro su `denoising-live-main.zip` → **Estrai tutto...** → **Estrai**.
Si apre una cartella `denoising-live-main`; a volte dentro ce n'è un'altra con lo stesso
nome. La cartella giusta è **quella in cui si vedono `prepara.bat`, `installa.bat`,
`GUIDA_RAPIDA.txt` e la cartella `dlive`**. Da qui in poi la chiamiamo "la cartella del
progetto".

**A3. Scaricare i due file che mancano: doppio clic su `prepara.bat`.** Lo script scarica
da solo, nella cartella del progetto, Python 3.4.4 e numpy (circa 33 MB), poi controlla
tutta la cartella (nomi, dimensioni e SHA-256 dei file).

* Windows 10/11 può mostrare "Windows ha protetto il PC": clic su **Ulteriori
  informazioni** → **Esegui comunque**. Se chiede "Aprire il file?", premi **Esegui**.
* **Se va bene**, la finestra nera finisce con
  `TUTTO A POSTO: copia questa cartella sulla chiavetta`. Premi un tasto per chiuderla.
* **Se dice `Download non riuscito`**: scarica a mano i due file (A3b) e rilancia
  `prepara.bat`.
* **Se dice `C'e' un problema nella cartella`**: le righe sopra (`MANCA ...`,
  `DIMENSIONE ERRATA ...`, `SHA-256 ERRATO ...`) dicono quale file e come rimediare; di
  solito basta scaricare di nuovo il ZIP (A1-A2) e rilanciare `prepara.bat`.
* Su Windows XP `prepara.bat` non scarica nulla e dice di usarlo sul PC con internet.

**A3b. Solo se `prepara.bat` non riesce a scaricare: scaricarli a mano** e metterli
**nella cartella del progetto** (non in una sottocartella), con questi nomi esatti:

| file | dove scaricarlo | dimensione |
|---|---|---|
| `python-3.4.4.msi` | <https://www.python.org/ftp/python/3.4.4/python-3.4.4.msi> (è il "Windows x86 MSI installer" della pagina <https://www.python.org/downloads/release/python-344/>) | 24.932.352 byte (23,7 MB) |
| `numpy-1.15.4-cp34-none-win32.whl` | <https://files.pythonhosted.org/packages/e6/10/798bd58c97068aad4cb24e9ba60dcc7ce2e8aac7a871ea493708039a8100/numpy-1.15.4-cp34-none-win32.whl> (dalla pagina <https://pypi.org/project/numpy/1.15.4/#files>) | 9.932.905 byte (9,5 MB) |

* Se il browser dice che il file "non viene scaricato comunemente" o simili, scegli
  **Mantieni** / **Conserva**; poi spostalo dalla cartella *Download* alla cartella del
  progetto.
* Se un file è stato scaricato due volte potrebbe chiamarsi `python-3.4.4 (1).msi`:
  rinominalo togliendo "(1)" e lo spazio prima.
* Poi rilancia `prepara.bat`: trova i file già presenti, non li riscarica e li controlla.

**A4. Copiare sulla chiavetta** l'intera cartella del progetto (con dentro i due file
scaricati). Poi togli la chiavetta con "Rimozione sicura dell'hardware".

---

## B. In laboratorio

**B0. Prima di tutto: WinWCP c'è e registra con il Digidata?** denoising_live usa la DLL
Axon di WinWCP: senza WinWCP installato quella DLL non c'è e il programma non può parlare
con il Digidata.

* Cerca l'icona di **WinWCP** sul desktop o nel menu **Start → Programmi**.
* Chiedi a chi usa il PC se con WinWCP si registra normalmente dal Digidata. Se vuoi
  vederlo tu (dopo il passo B2, con il Digidata acceso): apri WinWCP, menu **Setup →
  Laboratory Interface**, deve essere scelto *Axon Instruments (Digidata 132X)*; non
  cambiare nulla, chiudi con **Cancel** e chiudi WinWCP.
* **Se WinWCP non c'è** (o non registra con il Digidata): **fermati qui, prima di
  installare**. Si può andare avanti solo con l'ok del professore a installare, dagli
  installatori del laboratorio, prima AxoScope (porta WinASPI e il driver SCSI) e poi
  WinWCP (guida di WinWCP, p. 21). Altrimenti passa alla parte D con una foto del menu
  Start.

**B1. Ok del professore.** Prima di toccare il PC chiedi l'ok e assicurati che non ci
sia un esperimento o una registrazione in corso. denoising_live legge soltanto dal
Digidata: non manda stimoli.

**B2. Digidata acceso prima del PC.** Il Digidata va acceso **prima** di accendere il PC
(il PC vede la scheda solo all'accensione). Se il PC è già acceso e il Digidata è spento:
spegni il PC (Start → Spegni computer), accendi il Digidata e il filtro LPF-8, aspetta
qualche secondo, riaccendi il PC. Entra in Windows con il solito utente (amministratore).

**B3. WinWCP chiuso.** Se WinWCP (o AxoScope, o Clampex) è aperto, chiudilo: la scheda
si usa da un solo programma alla volta.

**B4. Copiare la cartella sul PC.** Inserisci la chiavetta, apri *Risorse del computer*,
apri la chiavetta e copia la cartella del progetto direttamente nel disco **C:** (per
esempio diventa `C:\denoising-live-main`). Apri quella cartella sul disco C:.

**B5. Niente da controllare a mano.** `installa.bat` controlla da solo che nella cartella
ci sia tutto (lo fa con `verifica_pacchetto.bat`, che non serve lanciare); se manca
qualcosa si ferma e dice cosa fare (di solito: ricopiare la cartella dalla chiavetta).

**B6. Installare.** Doppio clic su **`installa.bat`**. Dura 2-5 minuti: scorre i passi da
`0/8` a `8/8`; durante il passo `2/8` compare una finestrella di installazione di
Python con una barra verde: aspetta, non premere Annulla.

* **Se va bene**, la finestra finisce con `INSTALLAZIONE COMPLETATA.` e sul desktop
  compaiono tre icone: **denoising_live (Digidata)**, **Diagnostica Digidata** e
  **Raccogli risultati**. (L'icona della simulazione non c'è più: nella repository non ci
  sono i file di prova; se è rimasta da una prova vecchia, `disinstalla.bat` la toglie.) Nel passo `7/8` devi
  leggere `WinWCP: ...`, `AxDD132x.dll: presente`, `Axoutils32.dll: presente`,
  `WinASPI: presente`. Nel passo `8/8` ogni riga inizia con `[OK    ]`, `[AVVISO]` o
  `[ERRORE]`: gli AVVISO non bloccano.
* **Se finisce con `INSTALLAZIONE COMPLETATA, MA CI SONO ... ATTENZIONI`**: leggi le righe
  `ATTENZIONE` (WinWCP, DLL Axon, WinASPI) e guarda la parte C. Fai una foto.
* **Se finisce con `INSTALLAZIONE INTERROTTA`**: il motivo e il rimedio sono scritti
  subito sopra. Se non riesci a risolvere, fai una foto e fai doppio clic su
  `raccogli_risultati.bat` nella cartella del progetto (parte D).

**B7. Diagnostica.** Con WinWCP ancora chiuso, doppio clic sull'icona **Diagnostica
Digidata** del desktop. Dura circa 30 secondi, poi si apre il Blocco note con il file
`report_diagnostica.txt`.

* **Se va bene**, la finestra nera dice
  `ESITO: nessun errore. Si puo' passare all'anteprima (avvia.bat).` e in fondo al
  report, sotto `RIEPILOGO`, le righe sono `[OK    ]` o `[AVVISO]` e l'ultima riga è
  `Nessun errore: si puo' passare all'anteprima (avvia.bat).` In particolare devi
  vedere: passo 3 `WinASPI funziona`, passo 7 `Digidata trovato con ...`,
  passo 10 `ricevuti ... campioni su ... attesi`.
* **Se no** (`ESITO: ci sono errori`): guarda le righe `[ERRORE]` del riepilogo e la
  parte C. Non andare avanti con un errore ai passi 3, 5, 7 o 10: passa alla parte D.

Chiudi il Blocco note.

**B7b. Su quale ingresso arriva il segnale.** La finestra del programma non permette di
scegliere l'ingresso: lo decide la riga `canale_ingresso` di `C:\denoising_live\config.ini`
(di solito 2). Al passo 9 la diagnostica guarda tutti i 16 ingressi (`AI0` ... `AI15`).

* **Se il segnale arriva su un altro ingresso**, la diagnostica si ferma e chiede, per
  esempio, `Il segnale arriva sull'ingresso AI4. Vuoi usarlo? (S/N)`. Scrivi `S` e premi
  Invio: aggiorna da sola config.ini (ne tiene una copia in `config.ini.bak`), scrive
  `config.ini aggiornato: ora il programma usa l'ingresso AI4` e continua. Con `N` non
  cambia nulla.
* Nel report, sotto `PASSO 9`, e nel `RIEPILOGO` c'è sempre una riga che dice com'è
  andata, per esempio `segnale trovato sull'ingresso AI2; config.ini usa AI2` (va bene).
* **Se dice `nessun ingresso con segnale`**: controlla che il cavo dall'LPF-8 al
  Digidata sia collegato e che in quel momento ci sia un segnale; fai una foto dei
  collegamenti e rifai la diagnostica.
* **Se dice `segnale su piu' ingressi`** e config.ini usa uno di quelli: lascia tutto
  com'è e annotalo.
* **Ripiego a mano** (solo se hai risposto `N` per sbaglio, o se te lo chiedono): chiudi
  denoising_live; apri la cartella `C:\denoising_live` e fai doppio clic su `config.ini`
  (si apre con il Blocco note); cerca la riga `canale_ingresso = 2` (menu
  **Modifica → Trova**) e cambia solo il numero, per esempio `canale_ingresso = 4`;
  menu **File → Salva** (non "Salva con nome", non cambiare la codifica); rifai la
  diagnostica: la riga deve dire `config.ini usa AI4`.

**B8. Avviare il programma.** Doppio clic sull'icona **denoising_live (Digidata)**.

* All'avvio può chiedere "Impostazioni di WinWCP": rispondi **Sì** (usa canale e
  calibrazione di WinWCP). Altri avvisi: vedi la parte C.
* Si apre la finestra **denoising_live - DIGIDATA 1322A**.

**B9. Anteprima.** Premi **Avvia anteprima**.

* **Se va bene**: dopo pochi secondi il grafico scorre con una traccia grigia (segnale
  grezzo) e una rossa (filtrato); a destra, sotto "Filtrato attuale", c'è un valore in
  mV; nella barra in basso leggi `anteprima` (in verde) e `Persi: 0`.
* **Controlla che il grafico mostri il segnale**: valori in mV dello stesso ordine di
  quelli che si vedono di solito in WinWCP, che cambiano quando il segnale cambia. Se la
  traccia è piatta a 0 o è solo rumore, potrebbe essere l'ingresso sbagliato: fai una
  foto, premi **Ferma**, chiudi il programma e rifai la diagnostica (B7); se chiede di
  usare un altro ingresso rispondi `S`, poi riapri il programma. Se non lo chiede, vedi
  il ripiego a mano in B7b.
* (facoltativo) Se sai a quanto è impostato il filtro LPF-8, scrivi quel valore nella
  casella **Taglio LPF-8 (Hz)** e premi **Applica** accanto.
* Se il grafico è lento o a scatti: nel riquadro **Grafico**, **Aggiornamento (Hz)**,
  scegli **2**.

**B10. Registrazione di 4 minuti con un marker.**

1. Premi **Avvia registrazione**: in basso compare `REGISTRAZIONE` in rosso e il tempo
   (`t 0:00`) avanza.
2. Dopo circa 2 minuti, nella casella **Marker:** scrivi `prova` e premi **Invio** (oppure
   **Aggiungi marker**).
3. Dopo altri 2 minuti (tempo circa `t 4:00`) premi **Ferma** e conferma con **Sì**.
4. Fai una **foto della finestra** (con il telefono va benissimo) prima di chiuderla.
5. Chiudi denoising_live (la X in alto a destra).

I file sono in `C:\denoising_live\dati_registrati`: `AAMMGG_NNN_raw.wcp`,
`AAMMGG_NNN_filt.wcp` e `AAMMGG_NNN.json` (AAMMGG è la data del PC, NNN un numero: per
esempio `261124_001_raw.wcp`). Se la data nel nome non è quella di oggi, annotalo:
l'orologio del PC è sbagliato.

**B11. Aprire i file in WinWCP.** Apri WinWCP e, dal menu **File**, apri
`C:\denoising_live\dati_registrati\AAMMGG_NNN_raw.wcp`, poi `AAMMGG_NNN_filt.wcp`.

* **Se va bene**: si aprono senza errori; ci sono circa 4-5 record da circa 59 s; il
  segnale è in mV come nell'anteprima; il record che contiene il marker ha come
  identificativo `M:prova`; il file `_filt` ha gli stessi record, con il segnale più
  pulito. Fai una foto di ciascuno.
* **Se no**: annota il messaggio di WinWCP e fai una foto.

Chiudi WinWCP. Fine della prova.

---

## C. Se qualcosa va storto

| cosa vedi | dove | cosa fare |
|---|---|---|
| `Download non riuscito` | `prepara.bat` | scaricare a mano i due file (A3b) e rilanciare `prepara.bat` |
| `MANCA python-3.4.4.msi` (o il file numpy), `DIMENSIONE ERRATA`, `SHA-256 ERRATO` | `prepara.bat`, `installa.bat` | sul PC con internet rilanciare `prepara.bat` (parte A) e ricopiare la cartella |
| `NON TROVO I FILE DEL PROGRAMMA` | `prepara.bat` | il ZIP non è stato estratto: parte A2 |
| `ATTENZIONE: WinWCP non trovato` | `installa.bat`, passo 7/8 | WinWCP è in una cartella insolita: clic destro sull'icona di WinWCP → Proprietà, fotografa il percorso; la diagnostica lo cerca comunque anche altrove |
| `manca AxDD132x.dll` o `manca Axoutils32.dll` nella cartella di WinWCP; nella diagnostica passo 5 `nessuna AxDD132x.dll trovata` o `nessuna copia caricabile`; all'avvio la finestra "Driver Digidata" | `installa.bat`, diagnostica, programma | la DLL Axon si prende da WinWCP: senza, il programma non parla con il Digidata. Fotografa il contenuto della cartella di WinWCP e passa alla parte D. Non scaricare DLL da internet |
| `WinASPI non installato` (installazione) o passo 3 `WinASPI non funziona` (diagnostica) | `installa.bat`, diagnostica | WinASPI e il driver SCSI si installano con **AxoScope** (guida di WinWCP, p. 21): solo con l'ok del professore e se l'installatore di AxoScope è disponibile in laboratorio; poi riavviare il PC. Altrimenti fermarsi e passare alla parte D |
| passo 7 `Digidata non trovato` (diagnostica) oppure "Nessun Digidata trovato" all'anteprima | diagnostica, programma | spegnere il PC, controllare che il Digidata sia acceso e il cavo collegato, riaccendere il PC (Digidata sempre acceso **prima**), rifare la diagnostica |
| `Il segnale arriva sull'ingresso AI4. Vuoi usarlo? (S/N)` | diagnostica (passo 9) | rispondere `S` (B7b) |
| traccia piatta o solo rumore nell'anteprima, oppure `segnale trovato sull'ingresso AI4; config.ini usa AI2` | programma, diagnostica (passo 9) | rifare la diagnostica e rispondere `S`; altrimenti il ripiego a mano di B7b |
| WinWCP non installato (nessuna icona né voce nel menu Start) | prima di installare (B0) | fermarsi: senza WinWCP non c'è la DLL Axon. Solo con l'ok del professore: installare AxoScope e poi WinWCP dagli installatori del laboratorio |
| `WinWCP e' aperto` o la finestra "Scheda occupata" / "La scheda Digidata e' gia' in uso da: winwcp.exe" | diagnostica, programma | chiudere WinWCP (e AxoScope/Clampex) e riprovare |
| `Persi: N` in rosso o la banda rossa "Campioni persi" (overrun: il PC non ha letto in tempo i dati della scheda) | programma | non chiudere: annotare il numero, mettere **Aggiornamento (Hz)** a **2**, chiudere gli altri programmi aperti; se continua a salire, fare una foto e mandare la cartella `log` |
| grafico lento, a scatti, finestra che risponde in ritardo | programma | **Aggiornamento (Hz)** → **2** |
| `ATTENZIONE: numpy non funziona su questo PC` | `installa.bat`, passo 4/8 | niente da fare: il programma funziona lo stesso, un po' più lento (in basso si legge "Python puro") |
| `Python 3.4 non trovato` | icone del desktop | rifare `installa.bat` (B6) |
| `ERRORE DI SCRITTURA` (banda rossa) | programma | disco pieno o guasto: premere **Ferma**, fare una foto, passare alla parte D |

---

## D. Cosa riportare indietro

Doppio clic sull'icona **Raccogli risultati** del desktop (se l'icona non c'è, perché
l'installazione si è fermata prima: doppio clic su `raccogli_risultati.bat` nella cartella
del progetto). Copia quello che c'è, anche se la prova si è fermata a metà, in una cartella
nuova sul Desktop, `risultati_prova_AAMMGG_HHMM`, e finisce con
`Copia sulla chiavetta la cartella risultati_prova_... dal Desktop`.

Copia sulla chiavetta quella cartella e manda anche le **foto**: la finestra di
denoising_live durante la registrazione, i file aperti in WinWCP e ogni messaggio di
errore.

Cosa c'è nella cartella (per sapere cosa cercare se va copiato a mano):

1. `report_diagnostica.txt`, `rilevamento_pc.txt`, `config.ini` (e `config.ini.bak`, se
   la diagnostica l'ha cambiato), da `C:\denoising_live`
2. la cartella `log`
3. la cartella `dati_registrati`: `AAMMGG_NNN_raw.wcp`, `AAMMGG_NNN_filt.wcp`,
   `AAMMGG_NNN.json`
4. i file della diagnostica `diagnostica_AAMMGG_HHMMSS.wcp` e `.csv`
5. dalla cartella del progetto: `installa_log.txt` e `python_msi_log.txt`
6. `elenco.txt`: cosa è stato copiato e cosa no

Poi riconsegna la chiavetta (o manda i file) a chi ti ha dato questa guida. Non serve
disinstallare niente; se un giorno servirà, c'è `disinstalla.bat` nella cartella del
progetto (conserva le registrazioni).
