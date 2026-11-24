# Guida per il laboratorio: installare e provare denoising_live

Questa guida spiega, passo per passo, come portare denoising_live sul PC del laboratorio
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

---

## A. Sul PC con internet

**A1. Scaricare il progetto.** Apri <https://github.com/colasantoemanuele-cloud/denoising-live>,
premi il pulsante verde **Code** e poi **Download ZIP**. Si scarica il file
`denoising-live-main.zip` (di solito nella cartella *Download*).

**A2. Estrarlo.** Clic destro su `denoising-live-main.zip` → **Estrai tutto...** → **Estrai**.
Si apre una cartella `denoising-live-main`; a volte dentro ce n'è un'altra con lo stesso
nome. La cartella giusta è **quella in cui si vedono `installa.bat`,
`verifica_pacchetto.bat`, `GUIDA_LABORATORIO.txt` e la cartella `dlive`**. Da qui in poi
la chiamiamo "la cartella del progetto".

**A3. Scaricare i due file che mancano** e metterli **nella cartella del progetto** (non
in una sottocartella). I nomi devono essere esattamente questi:

| file | dove scaricarlo | dimensione |
|---|---|---|
| `python-3.4.4.msi` | <https://www.python.org/ftp/python/3.4.4/python-3.4.4.msi> (è il "Windows x86 MSI installer" della pagina <https://www.python.org/downloads/release/python-344/>) | 24.932.352 byte (23,7 MB) |
| `numpy-1.15.4-cp34-none-win32.whl` | <https://files.pythonhosted.org/packages/e6/10/798bd58c97068aad4cb24e9ba60dcc7ce2e8aac7a871ea493708039a8100/numpy-1.15.4-cp34-none-win32.whl> (dalla pagina <https://pypi.org/project/numpy/1.15.4/#files>) | 9.932.905 byte (9,5 MB) |

* Se il browser dice che il file "non viene scaricato comunemente" o simili, scegli
  **Mantieni** / **Conserva**.
* Il browser li mette in *Download*: spostali (trascinandoli) nella cartella del progetto.
* Se Windows nasconde le estensioni vedrai `python-3.4.4` e
  `numpy-1.15.4-cp34-none-win32`: va bene così.
* Se un file è stato scaricato due volte potrebbe chiamarsi `python-3.4.4 (1).msi`:
  rinominalo togliendo "(1)" e lo spazio prima.

**A4. Controllare la cartella.** Nella cartella del progetto fai doppio clic su
**`verifica_pacchetto.bat`**.

* Windows 10/11 può mostrare "Windows ha protetto il PC": clic su **Ulteriori
  informazioni** → **Esegui comunque**. Se chiede "Aprire il file?", premi **Esegui**.
* **Se va bene**, la finestra nera finisce con
  `TUTTO A POSTO: la cartella e' completa.` e, sopra, due righe `ok` con
  `SHA-256 verificato` (una per ciascun file scaricato) e la riga
  `ok: ... file del programma, tutti con la dimensione giusta`.
  Premi un tasto per chiuderla.
* **Se no**, la finestra elenca i problemi (`MANCA ...`, `DIMENSIONE ERRATA ...`,
  `SHA-256 ERRATO ...`), ciascuno con il rimedio (di solito: riscaricare quel file).
  Correggi e rilancia `verifica_pacchetto.bat` finché dice `TUTTO A POSTO`.

**A5. Copiare sulla chiavetta** l'intera cartella del progetto (con dentro i due file
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

**B5. Controllare la cartella.** Doppio clic su **`verifica_pacchetto.bat`**.

* **Se va bene**: `TUTTO A POSTO: la cartella e' completa.` Su Windows XP le righe dei
  due file dicono solo `ok ... byte`, senza "SHA-256 verificato": è normale (lo SHA-256
  lo controlla `installa.bat`). Premi un tasto.
* **Se no**: la copia è incompleta. Ricopia la cartella dalla chiavetta e riprova.

**B6. Installare.** Doppio clic su **`installa.bat`**. Dura 2-5 minuti: scorre i passi da
`0/8` a `8/8`; durante il passo `2/8` compare una finestrella di installazione di
Python con una barra verde: aspetta, non premere Annulla.

* **Se va bene**, la finestra finisce con `INSTALLAZIONE COMPLETATA.` e sul desktop
  compaiono tre icone: **denoising_live (Digidata)**, **Diagnostica Digidata** e
  **denoising_live (simulazione)** (quest'ultima non serve). Nel passo `7/8` devi
  leggere `WinWCP: ...`, `AxDD132x.dll: presente`, `Axoutils32.dll: presente`,
  `WinASPI: presente`. Nel passo `8/8` ogni riga inizia con `[OK    ]`, `[AVVISO]` o
  `[ERRORE]`: gli AVVISO non bloccano.
* **Se finisce con `INSTALLAZIONE COMPLETATA, MA CI SONO ... ATTENZIONI`**: leggi le righe
  `ATTENZIONE` (WinWCP, DLL Axon, WinASPI) e guarda la parte C. Fai una foto.
* **Se finisce con `INSTALLAZIONE INTERROTTA`**: il motivo e il rimedio sono scritti
  subito sopra. Se non riesci a risolvere, fai una foto e porta indietro il file
  `installa_log.txt` (e, se c'è, `python_msi_log.txt`) dalla cartella del progetto.

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
(di solito 2). Nel report, sotto `PASSO 9`, ci sono i valori dei 16 ingressi (`AI0` ...
`AI15`) e poi una riga che inizia con `>>> OK:` o `>>> AVVISO:`, per esempio
`segnale trovato sull'ingresso AI4; config.ini usa AI2`. La stessa frase compare nel
`RIEPILOGO` come `passo 9`.

* **Se i due numeri sono uguali** (per esempio `sull'ingresso AI2; config.ini usa AI2`):
  va bene, vai a B8.
* **Se sono diversi**, metti in config.ini il numero dell'ingresso trovato:
  1. chiudi denoising_live, se è aperto;
  2. apri la cartella `C:\denoising_live` e fai doppio clic su `config.ini` (si apre
     con il Blocco note; se chiede con cosa aprirlo, scegli **Blocco note**);
  3. cerca la riga `canale_ingresso = 2` (menu **Modifica → Trova**, scrivi
     `canale_ingresso`) e cambia solo il numero, per esempio `canale_ingresso = 4`;
  4. menu **File → Salva** (non "Salva con nome", non cambiare la codifica) e chiudi il
     Blocco note;
  5. rifai la diagnostica (B7): ora la riga deve dire `config.ini usa AI4`.
* **Se dice `nessun ingresso con segnale`**: controlla che il cavo dall'LPF-8 al
  Digidata sia collegato e che in quel momento ci sia un segnale; fai una foto dei
  collegamenti e rifai la diagnostica.
* **Se dice `segnale su piu' ingressi`** e config.ini usa uno di quelli: lascia
  config.ini com'è e annotalo.

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
  foto, premi **Ferma**, chiudi il programma, guarda la riga del passo 9 del report
  (B7b) e, se l'ingresso è diverso da quello di config.ini, cambialo come spiegato in
  B7b, rifai la diagnostica e riapri il programma.
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
| `MANCA python-3.4.4.msi` (o il file numpy), `DIMENSIONE ERRATA`, `SHA-256 ERRATO` | `verifica_pacchetto.bat`, `installa.bat` | riscaricare quel file (parte A3) e ricopiare la cartella |
| `NON TROVO I FILE DEL PROGRAMMA` | `verifica_pacchetto.bat` | il ZIP non è stato estratto: parte A2 |
| `ATTENZIONE: WinWCP non trovato` | `installa.bat`, passo 7/8 | WinWCP è in una cartella insolita: clic destro sull'icona di WinWCP → Proprietà, fotografa il percorso; la diagnostica lo cerca comunque anche altrove |
| `manca AxDD132x.dll` o `manca Axoutils32.dll` nella cartella di WinWCP; nella diagnostica passo 5 `nessuna AxDD132x.dll trovata` o `nessuna copia caricabile`; all'avvio la finestra "Driver Digidata" | `installa.bat`, diagnostica, programma | la DLL Axon si prende da WinWCP: senza, il programma non parla con il Digidata. Fotografa il contenuto della cartella di WinWCP e passa alla parte D. Non scaricare DLL da internet |
| `WinASPI non installato` (installazione) o passo 3 `WinASPI non funziona` (diagnostica) | `installa.bat`, diagnostica | WinASPI e il driver SCSI si installano con **AxoScope** (guida di WinWCP, p. 21): solo con l'ok del professore e se l'installatore di AxoScope è disponibile in laboratorio; poi riavviare il PC. Altrimenti fermarsi e passare alla parte D |
| passo 7 `Digidata non trovato` (diagnostica) oppure "Nessun Digidata trovato" all'anteprima | diagnostica, programma | spegnere il PC, controllare che il Digidata sia acceso e il cavo collegato, riaccendere il PC (Digidata sempre acceso **prima**), rifare la diagnostica |
| `segnale trovato sull'ingresso AI4; config.ini usa AI2` (numeri diversi), oppure traccia piatta o solo rumore nell'anteprima | diagnostica (passo 9), programma | cambiare `canale_ingresso` in `C:\denoising_live\config.ini` con il Blocco note (B7b) e rifare la diagnostica |
| WinWCP non installato (nessuna icona né voce nel menu Start) | prima di installare (B0) | fermarsi: senza WinWCP non c'è la DLL Axon. Solo con l'ok del professore: installare AxoScope e poi WinWCP dagli installatori del laboratorio |
| `WinWCP e' aperto` o la finestra "Scheda occupata" / "La scheda Digidata e' gia' in uso da: winwcp.exe" | diagnostica, programma | chiudere WinWCP (e AxoScope/Clampex) e riprovare |
| `Persi: N` in rosso o la banda rossa "Campioni persi" (overrun: il PC non ha letto in tempo i dati della scheda) | programma | non chiudere: annotare il numero, mettere **Aggiornamento (Hz)** a **2**, chiudere gli altri programmi aperti; se continua a salire, fare una foto e mandare la cartella `log` |
| grafico lento, a scatti, finestra che risponde in ritardo | programma | **Aggiornamento (Hz)** → **2** |
| `ATTENZIONE: numpy non funziona su questo PC` | `installa.bat`, passo 4/8 | niente da fare: il programma funziona lo stesso, un po' più lento (in basso si legge "Python puro") |
| `Python 3.4 non trovato` | icone del desktop | rifare `installa.bat` (B6) |
| `ERRORE DI SCRITTURA` (banda rossa) | programma | disco pieno o guasto: premere **Ferma**, fare una foto, passare alla parte D |

---

## D. Cosa riportare indietro

Copia sulla chiavetta, in una cartella nuova (per esempio `risultati_prova`):

1. `C:\denoising_live\report_diagnostica.txt`
2. la cartella `C:\denoising_live\log` (tutta)
3. i file creati dalla registrazione, in `C:\denoising_live\dati_registrati`:
   `AAMMGG_NNN_raw.wcp`, `AAMMGG_NNN_filt.wcp`, `AAMMGG_NNN.json`
4. i file creati dalla diagnostica, in `C:\denoising_live`:
   `diagnostica_AAMMGG_HHMMSS.wcp` e `diagnostica_AAMMGG_HHMMSS.csv`
5. `C:\denoising_live\rilevamento_pc.txt`, `C:\denoising_live\config.ini` (soprattutto se
   l'hai cambiato in B7b) e, dalla cartella del progetto,
   `installa_log.txt` (e `python_msi_log.txt`, se c'è)
6. le **foto**: la finestra di denoising_live durante la registrazione, i file aperti in
   WinWCP e ogni messaggio di errore

Poi riconsegna la chiavetta (o manda i file) a chi ti ha dato questa guida. Non serve
disinstallare niente; se un giorno servirà, c'è `disinstalla.bat` nella cartella del
progetto (conserva le registrazioni).
