# Rapporto di validazione — denoising_live

Generato il 24/11/2026 13:38 da `./valida.sh` · Python di sviluppo 3.12.16, numpy 2.5.5, scipy 1.18.1 · commit del programma: 8410967 Chiavetta rigenerata dal commit 0a3b46d (hash verificati) (+ modifiche non ancora registrate in dlive/)


> # VERDETTO: PRONTO PER LA PROVA IN LABORATORIO
>
> Tutti i test critici sono superati e le mutazioni M1–M4 sono state rilevate.
> Il verdetto riguarda **solo il software in simulazione**. Il funzionamento con il Digidata vero si vede solo con la diagnostica in laboratorio (`diagnostica.bat`), e quale frequenza di taglio sia scientificamente giusta lo decide il laboratorio, non i test.


## Cinque domande

| Domanda | Risposta | Il numero che la motiva |
|---|---|---|
| Il filtro toglie il rumore? | Sì | **A7** PASS: rumore residuo 1,10 mV RMS (soglia 2), partendo da 45,9 mV · **C2** PASS: rumore 25–60 Hz ridotto di almeno 50,3 dB sui file reali (soglia 30) |
| Deforma il segnale utile? | No | **A2** PASS: dopo un gradino errore massimo 0,14 mV (soglia 0,5) · **A3** PASS: sovraelongazione massima 0,85 % (soglia 5) · **A4** PASS: ritardo 65 ms a 5 Hz (soglia 300) · **C3** PASS: uguale al riferimento ideale su tutti i 8 casi, RMS al massimo 1,27 mV (soglia 5); tempo escluso al massimo 1,15 % (limite 2 %) · **C3b** PASS: attorno ai salti il programma fa esattamente quello che dice il README: al massimo 0,09 mV RMS su 16 finestre (soglia 2), 100 % del tempo escluso controllato |
| Perde o altera dati? | No | **B1** PASS: 0 campioni diversi su 600064 · **B2** PASS: differenza massima 0 conteggi ADC (soglia 1) · **B3** PASS: 0 campioni persi |
| I file si aprono in altri programmi? | Sì | **B6** PASS: neo e lettore di riferimento differiscono di 0,0003 mV; intestazione come WinWCP 5.1.6 |
| Regge registrazioni lunghe e crash? | Sì, con una riserva (B8) | **B7** PASS: dopo un kill -9 persi 0,60 s (soglia 2); file leggibili · **B8** NON VERIFICABILE: non eseguito: richiede ./valida.sh --lungo (3 ore di segnale) |
| Funziona con la scheda (finta) e su un PC lento? | Sì | **E7** PASS: Python di sviluppo: registrazione conforme, errori mostrati in chiaro 4 su 4, riavvio dopo gli errori sì; Python 3.4: registrazione conforme, errori mostrati in chiaro 4 su 4, riavvio dopo gli errori sì · **E6** PASS: Python 3.4.10, CPU limitata a 0,2 (--cpus=0.2), grafico a 5 Hz: registrazione 600.0 s; persi 0; arretrato massimo dell'elaborazione 0.05 s, coda massima 0.05 s (limite 600 s); ritardo del grafico massimo 65 ms (mediana 33 ms) |


## Cosa NON è stato verificato

* **la scheda Digidata 1322A vera** (driver AxDD132x.dll, WinASPI, SCSI, temporizzazione e overrun reali): si vede solo con `diagnostica.bat` in laboratorio;
* **Windows XP** e il PC del laboratorio (Python 3.4 a 32 bit, tkinter, numpy su quella CPU, schermo, disco): qui si è usato Python 3.4 a 64 bit su Linux in Docker;
* **WinWCP 5.1.6**: l'apertura dei file nel programma vero (qui: stesse chiavi di un file scritto da WinWCP 5.1.6, lettura con neo e con il lettore di riferimento);
* **la velocità reale del PC del laboratorio**: E6 la simula limitando la CPU a 0,2 core in Docker, che non riproduce una CPU di 15 anni fa (cache, disco, Windows XP);
* **se gli impulsi oltre 500 mV (~5 V, decine di ms) sono artefatti**: il programma li tratta come tali e ritarda di 50 ms quelli lunghi (scelta voluta, README § 6.1); se il laboratorio dice che sono eventi veri si abbassa `durata_max_picco_ms`;
* **il giudizio scientifico sul taglio**: quale frequenza di taglio (1, 2, 5, 10 Hz) sia giusta per i segnali del laboratorio lo decide il laboratorio, non questi test.
* la prova di 3 ore (B8): eseguire `./valida.sh --lungo`

In tutto 42 voci: 41 PASS, 0 FAIL, 1 NON VERIFICABILE.


---


## Cosa è stato ricavato dai sorgenti (fase 5)

Riassunto di `docs/analisi_sorgenti.md`: sorgenti di WinWCP (5.8.1 e 2013), unità `dd1320.pas` e `SESLabIO.pas`, header Axon, guida di WinWCP V5.2.4, manuale dell'LPF-8, installatore di WinWCP 5.2.7 (il più vicino alla 5.1.6 del laboratorio) e i 7 file di prova. La logica del filtro non è cambiata e le soglie dei test sono le stesse.


### Quale WinWCP e quale PC

* WinWCP 5.1.6 è del 16/03/2016. I file di prova li ha scritti la 5.1.6 (`VERPROG=V5.1.6`, chiave che esiste dal 2015) ma portano date del 2007-2008: **l'orologio del PC del laboratorio è indietro di 8-9 anni**. Il comando non cerca più i file recenti per nome (`25*.wcp`) e la diagnostica avvisa se la data è anteriore al 2016.
* Nella 5.1.6 l'unità che pilota la 1322A è quella del 2013 (unica modifica successiva: 2020), confermato dall'eseguibile della 5.2.7, che carica la stessa `AxDD132x.dll` 1.0.0.38 dalla propria cartella.


### Digidata 1322A: differenze rispetto a WinWCP

* **Corretto**: `uChunksPerSecond` era 20 (valore suggerito dall'header Axon), WinWCP lo lascia a 0 perché nel suo record il campo è "Unused". Ora 0, configurabile. Test `test_chunks_per_second_come_winwcp`, che fallisce sul codice della fase 4.
* **Corretto**: la DLL si cerca anche in `C:\WinWCP*` (per esempio `C:\WinWCPXE`). Test `test_cartelle_winwcp_cercate`.
* **Già giusto** (stesso codice di WinWCP): ricerca e doppia apertura, calibrazione, uscite a riposo con l'offset dei DAC, intervallo in µs, `Bit0Tag`, sotto-buffer da 600 × canali, buffer circolare di 999 000 campioni, valore vuoto 32767, range fisso 10 V, `ADCMAX=32677`, offset e guadagno dell'ADC non applicati (WinWCP li legge ma non li usa).
* **Motivato**: la scala in mV divide per `ADCMAX` (come la guida e neo) mentre il codice di WinWCP divide per `ADCMAX+1`: 0,003 %, nessun effetto sui file. In più rispetto a WinWCP: il rilevamento degli overrun.


### Impostazioni di WinWCP

* WinWCP non usa il registro: `winwcp.ini` in `Documenti condivisi\WinWCP`, `lab interface settings.xml` in `Documenti condivisi\SESLABIO` (canali, V/unità, guadagno, ingresso fisico), log giornalieri accanto a `winwcp.ini`.
* **Nuovo**: il programma e la diagnostica le leggono (mai scritte) e propongono canale, calibrazione e campionamento come valori iniziali (`[digidata] impostazioni_winwcp = chiedi`), con `config.ini` come ripiego. 11 test con file costruiti dal formato del sorgente e con quello vero dei sorgenti.


### Stimoli

* I 7 file di prova (13 record, tutti `TEST`, gruppo uguale al numero del record, sweep da 1 ora fermati a mano, nessun ritmo nelle escursioni): **registrati senza stimolazione, con alta probabilità; non dimostrabile al 100 % dai soli file**. La prova certa (modo di registrazione e righe "Stimulus Protocol" dei log) la raccoglie il comando; il programma avvisa all'avvio se WinWCP è in modo protocollo o trigger esterno.


### Formato .wcp

* Chiavi della 5.1.6 identiche a quelle scritte dal programma; record fino a 16 777 216 campioni e file fino a 2 GB: i nostri record da 59,4 s sono 280 volte sotto il limite.
* **Corretto**: `RTIMESECS` sono i secondi dall'avvio di Windows (guida p. 163 e file di prova), non dalla mezzanotte. Test `test_rtimesecs_*`.
* **Corretto**: separatore decimale `auto` (quello di Windows, come WinWCP, che rilegge comunque virgola e punto).
* I marker vanno già nel campo identificativo del record (16 caratteri), il modo nativo di WinWCP. Nei file di prova il segnale è su un solo canale ma non sempre lo stesso (Ch.0 o Ch.4): l'ingresso di oggi va confermato (passi 1b e 9 della diagnostica).


### Filtro LPF-8

* Bessel a 8 poli, 0,1-199,9 Hz a passi di 0,1 Hz e 10-19 990 Hz a passi di 10 Hz, attenuazione massima 60 dB, guadagno 1-200, Bypass, uscita ±10 V come l'ADC.
* **Corretto**: il campo "Taglio LPF-8 (Hz)" accetta solo questi valori o Bypass; il programma avvisa di aliasing sopra ~150 Hz (meno di 40 dB a 500 Hz) e in Bypass, e se il guadagno non è 1 ma la calibrazione è rimasta 0,001. Con 15 Hz nessun aliasing. 7 test.


### Rilevamento sul posto e comando minimo

* **Nuovo** `dlive/rilevamento.py` (in `installa.bat`, nella diagnostica e a mano): Windows, Service Pack, 32/64 bit, diritti, Python e `msvcr100.dll`, schermo, separatore, disco per 3 ore, DLL Axon e WinASPI, impostazioni e processi di WinWCP, orologio. 21 casi con un ambiente finto. `installa.bat` controlla in batch Service Pack, diritti e spazio prima di installare e usa un Python 3.4 già registrato.
* Il comando per il collega passa da 73 a 37 righe e da 11 a 4 passi: tiene solo Windows/SP/bit, diritti, spazio su C:, l'elenco dei `.wcp`, le impostazioni e i log di WinWCP e la copia dei file usati per ultimi (motivazioni in `docs/comando_laboratorio.md`). Non è stato eseguito (niente Windows né Wine): controlli statici in `test_comando_*`.


### Le validazioni

* Fase 5, primo `./valida.sh`: 41 PASS su 42, **E6 FAIL** di poco (ritardo massimo del grafico 1017 ms contro il limite di 1 s, mediana 41 ms, 0 campioni persi; fase 4: 909 ms), sotto la CPU di Docker limitata a 0,2 core in parallelo agli altri test.
* Fase 5, `./valida.sh --lungo` (con la prova di 3 ore B8): **42 PASS su 42**, E6 a 419 ms.
* Dopo la correzione della numerazione dei file (sotto), `./valida.sh` (questo rapporto, senza `--lungo`): 41 PASS, B8 non eseguita (si esegue solo con `--lungo`; la correzione non tocca la catena di acquisizione), E6 a 759 ms. Verdetto secondo le regole in vigore.


### Nessuna registrazione sovrascritta (orologio del PC indietro)

* Con l'orologio del laboratorio fermo al 2007-2008 i nomi `AAMMGG_NNN` si ripetono. `tests/test_nomi_file.py` (12 test, in simulazione) controlla sei casi, verificando contenuto e data di modifica di tutti i file già presenti: due registrazioni di seguito, riapertura del programma (processo nuovo) con la stessa data, orologio tornato indietro, un solo file rimasto da una registrazione interrotta, file di WinWCP con lo stesso prefisso, nome sbagliato di proposito.
* I casi 1-5 passavano già: il numero si ricalcola dai file su disco (`nome_base_libero`).
* **Corretto** il caso 6: i `.wcp` si aprivano con `w+b` e il JSON si scriveva con `os.replace`, quindi un nome sbagliato avrebbe sovrascritto i file. Ora i tre file si creano solo se non esistono (apertura esclusiva); se uno esiste la registrazione non parte, il messaggio lo dice e l'acquisizione continua senza perdere campioni.


## Fase 4 (storico): chiusura di C3, C3b, C4

La fase 3 (`rapporto_fase3`) dava **PRONTO CON RISERVE** con C3, C3b e C4 in FAIL. In fase 4 sono state applicate le decisioni D4–D8. **La logica del filtro e del rilevatore dei picchi non è stata cambiata.** Il codice di produzione cambia di 12 righe: il controllo dell'intervallo di un parametro già esistente e la rimozione di un parametro inutilizzato.


### 1. Decisioni applicate

* **D4 — il programma resta com'è.** Il ritardo di 50 ms sulle escursioni oltre 500 mV accettate come segnale è una scelta voluta. Far "recuperare" al filtro i 50 ms trattenuti peggiorerebbe la reiezione degli artefatti: il filtro integrerebbe l'intera escursione (104 ms) invece dei 54 ms accettati. Nei file di prova queste escursioni valgono circa 5 V, 50 volte il segnale utile, quindi sono artefatti. Il laboratorio deve confermarlo (README § 6.1 e § 7, punto 8).
* **D5 — C3b si confronta con il filtro ideale più la regola del README.** La regola del README § 6.1 è riscritta nel test a partire dal testo, senza importare il codice del rilevatore. Saturazioni: ultimo valore valido. Escursioni oltre 500 mV lunghe al massimo 50 ms: ultimo valore valido. Escursioni più lunghe: i primi 50 ms sostituiti, il resto passa. Poi si applica il filtro causale ideale di scipy (notch 50 Hz + Bessel 4° ordine 5 Hz). Risultato: **tutte le 16 finestre stanno tra 0,08 e 0,09 mV RMS**, con scarto massimo 0,15 mV (mezzo conteggio ADC, cioè l'arrotondamento del file); soglia 2 mV per finestra. Nessuna escursione cade nella fascia ambigua di 50 ms ± 2 campioni del file. Le escursioni trovate durano 8–17 ms (picchi tolti) oppure 88–104 ms (impulsi accettati, con i ritorni al livello di base).
* La finestra di **071210_001.wcp a 452,5 s**, segnalata come possibile problema (picco di 27 mV in fase 3), ora dà **0,08 mV RMS**. Quei 4,4 mV RMS e 27 mV di picco erano una differenza di modello nel test, non nel programma. Il riferimento di fase 3 toglieva il picco (17 ms a 1000 Hz) con la mediana mobile di 0,1 s, mentre il programma, come dice il README, tiene l'ultimo valore valido. Con la stessa regola nel riferimento la differenza scompare. Su 071211 a 1183,2 s si passa da 932 mV RMS a 0,09 mV: la differenza di fase 3 era tutta nei 50 ms di attesa, che ora fanno parte del riferimento.
* **Copertura.** C3b controlla il 100 % del tempo escluso da C3 e C4. Il test lo verifica campione per campione: le finestre valutate da C3b coincidono esattamente con i campioni esclusi.
* **D6 — il limite del tempo escluso in C3 e C4 passa da 1 % a 2 %.** È l'unica soglia cambiata, per decisione del proprietario del progetto. Motivo: il limite dell'1 % serviva a impedire che l'esclusione nascondesse difetti; ora le finestre escluse sono controllate da C3b con un confronto più severo del riferimento a fase zero. Su 071211_001.1 l'esclusione è 1,15 % (17 salti), quindi C3 e C4 passano. Le altre soglie (correlazione ≥ 0,99, RMS < 5 mV, estremi entro 10 mV) sono invariate. Con quelle, fuori dalle finestre, su 071211 si ha r = 1,0000, RMS 0,44 mV ed estremi entro 0,3 mV.
* **D7 — l'attesa era già un parametro di `config.ini`.** Si chiama `[filtro] durata_max_picco_ms` (predefinito 50) e arriva al rilevatore così: `config.ini` → `gui._crea_sessione` → `Sessione(durata_max_picco_s)` → `Elaboratore(max_campioni_picco)`. Non è stato creato un nuovo `attesa_picchi_ms`. Il nome resta questo, così un `config.ini` già esistente continua a valere. Aggiunto solo il controllo dell'intervallo 0–500 ms: un valore fuori intervallo blocca l'avvio con "[filtro] durata_max_picco_ms = 600 fuori dall'intervallo 0-500 ms". Comportamento predefinito invariato: su tutti gli 8 casi reali il filtrato salvato coincide campione per campione con l'Elaboratore costruito con 50 campioni scritti a mano (0 campioni diversi); A8 e B2 danno gli stessi numeri della fase 3 (vedi la tabella "Prima e dopo"). Nuovo test (`tests/test_simulatore.py`): un impulso di 5 V lungo 104 ms, registrato attraverso la Sessione, entra nel filtrato con 0, 20 o 50 ms di ritardo a seconda del valore, e con 200 ms viene tolto del tutto.
* **D8 — `coda_max_s` tolto dalla Sessione.** Era un argomento mai usato. Il limite di 600 s è ora una costante del test E6 (`LIMITE_CODA_S`). Nessun controllo della coda è stato aggiunto al codice di produzione.


### 2. Cosa resta da vedere in laboratorio

* Se le escursioni di ~5 V lunghe decine di ms sono artefatti (predefinito) o eventi veri: nel secondo caso si abbassa `durata_max_picco_ms`.
* Tutto l'elenco "Cosa NON è stato verificato" in prima pagina: Digidata vero, Windows XP e la velocità reale del PC, WinWCP 5.1.6, giudizio scientifico sul taglio.


## Fase 3 (storico): decisioni, nuovi test E6/E7/C3b, correzioni

La fase 2 (`rapporto_fase2`) dava **PRONTO CON RISERVE** con C3, C4 ed E4 in FAIL. In fase 3 sono state applicate le decisioni del proprietario del progetto (D1–D3) e sono stati aggiunti i test C3b, E6 ed E7 (E7 è CRITICO). Il verdetto resta **PRONTO CON RISERVE**: tutti i critici sono superati, E7 compreso. Restano FAIL tre test importanti (C3, C3b, C4), per i motivi spiegati al punto 3. Le soglie non sono state cambiate.


### 1. Decisioni applicate

* **D1 — C2.** La riduzione del rumore si misura sull'uscita del programma prima dell'arrotondamento a 16 bit; la soglia resta 30 dB. B2 verifica ancora che `_filt.wcp` coincida con quell'uscita (0 conteggi di differenza) e il test C2 lo ricontrolla su ogni file reale. Il rapporto riporta entrambe le misure (programma / file). Riduzione minima 50,3 dB.
* **D2 — C3 e C4.** Il confronto si fa fuori da ±1 s attorno ai salti > 500 mV del grezzo; la frazione esclusa deve restare sotto l'1 %. La correlazione si valuta solo se il riferimento varia di almeno 1 conteggio ADC: su 071224_003 il riferimento varia di 0,021 mV contro 1 conteggio = 0,306 mV, quindi "correlazione non applicabile" e conta solo la differenza RMS (0,03 mV). Motivo del cambio: il riferimento a fase zero applica il filtro due volte e risponde in modo diverso da qualunque filtro in tempo reale a impulsi brevi e grandi. Nuovo **C3b**: nelle finestre escluse il programma deve coincidere con un filtro causale ideale (scipy, stessi parametri, senza gestione dei picchi) entro 2 mV RMS.
* **D3 — E4.** Il grafico si aggiorna 5 volte al secondo di default: nel codice (`dlive/config.py`), nel `config.ini` di esempio del repository, nella chiavetta e nel README. Nel pannello "Grafico" c'è il selettore **Aggiornamento (Hz)** con 2, 5 e 10: effetto immediato, valore salvato in `config.ini`. E7 lo verifica dal vivo e misura 2,0 / 9,8 / 5,0 disegni al secondo. E4, con la finestra, sul Python di sviluppo e con le impostazioni predefinite: **3,27 %** (soglia 5 %, PASS; 3,62 % in una seconda esecuzione). Valori informativi: 4,94 % con Python 3.4; 5,92 % a 10 Hz.


### 2. Nuovi test e bug trovati

* **E7 [CRITICO] — finestra vera in modalità Digidata con la DLL finta.** La DLL finta usata è "rigorosa": come un driver vero, rifiuta di aprire una scheda già aperta. Sul codice della fase 2 E7 **falliva**. Se l'avvio si interrompeva *dopo* l'apertura della scheda, la scheda restava aperta, e ogni nuovo tentativo dava "Digidata trovato ma impossibile aprirlo (errore 9999)": 4 tentativi su 4, 8 doppie aperture rifiutate. In laboratorio sarebbe servito chiudere il programma, forse spegnere il Digidata. È lo stesso tipo di bug della frequenza a 0 Hz della fase 2, cioè stato lasciato a metà. Correzioni: `Sessione.avvia_anteprima` richiude il dispositivo se qualcosa fallisce dopo `apri()`; `Digidata1322Device.apri()` chiude un'eventuale apertura rimasta; `avvia()` azzera il contatore degli overrun e l'affidabilità del contatore di posizione a ogni acquisizione (prima restavano dalla sessione precedente). Tre test di regressione in `tests/test_digidata_finto.py` falliscono sul codice vecchio e passano sul nuovo.
* Dopo le correzioni E7 passa con Python 3.4 e con il Python di sviluppo. DLL mancante, scheda assente e WinASPI assente compaiono come messaggi in italiano senza traceback e il programma resta aperto. L'overrun compare nella banda "Campioni persi: 8002 (il PC non ha letto in tempo il buffer della scheda)". Dopo gli errori la sessione riparte e alla fine nessuna scheda resta aperta. La registrazione (anteprima 30 s, 60 s con un marker e un cambio di taglio) è conforme a B1, B2 e B3 rispetto al segnale generato dalla DLL finta: 0 campioni diversi, 0 conteggi di differenza (esclusi i 3 s dopo il cambio di taglio), 0 persi.
* **E6 [importante] — PC lento.** Docker con `--cpus=0.2`, Python 3.4, finestra sotto Xvfb, sorgente simulata in tempo reale, anteprima 30 s e poi registrazione di 10 minuti con le impostazioni predefinite. Risultati: 0 persi; arretrato massimo dell'elaborazione 0,08 s (limite della coda 600 s); ritardo massimo del grafico 0,16 s (0,31 s in una seconda esecuzione) (soglia 1 s); 0 eccezioni; file conformi a B1, B2 e B3. Il processo usa il 5,2 % di un core, cioè circa un quarto della quota di 0,2. Limite della prova: la quota di Docker rallenta "a scatti" e non riproduce una CPU di 15 anni fa (cache, disco, Windows XP).
* **Osservazione.** Il "limite configurato" della coda (`coda_max_s = 600` nella Sessione) è un parametro che il programma non usa: non c'è nessun controllo che lo faccia rispettare. Nelle prove la coda resta sotto 0,1 s, quindi non ha conseguenze.


### 3. FAIL rimasti (importanti): servono decisioni

* **C3 e C4 su 071211_001.1 — tempo escluso 1,15 % (limite 1 %).** Fuori dalle finestre il programma è perfetto: r = 1,0000, RMS 0,44 mV, estremi entro 0,3 mV dal riferimento. Ma i salti oltre 500 mV nel grezzo sono 17: due saturazioni (744,4 s e 756,3 s), quattro picchi brevi da 8–16 ms e l'escursione vera di 104 ms a 1183,2 s. Contando come salti solo le escursioni che il programma accetta come segnale (oltre 50 ms), l'esclusione sarebbe circa 0,2 %. Le saturazioni e i picchi brevi li tolgono sia il programma sia il riferimento, e A8 li verifica a parte.
* **C3b — 071211_001.1: 374,6 mV RMS; 071210_001: 3,17 mV RMS (soglia 2 mV).** Su 071211 quasi tutto viene da una sola finestra, l'escursione vera di 104 ms a 1183,2 s: RMS 932 mV, massimo 3110 mV. Il programma ritarda di 50 ms tutte le escursioni oltre 500 mV, sia all'inizio sia alla fine. È la regola documentata del rilevatore dei picchi (README § 6.1: "se dura di più è segnale vero e passa, con 50 ms di ritardo"). Il confronto di fase 2 (7,46 contro 7,38 mV RMS sull'intero file) non lo mostrava, perché quelle differenze erano misurate contro il riferimento a fase zero. **C3b ha fatto il suo lavoro: l'esclusione nascondeva questo comportamento.** Le altre finestre, cioè picchi brevi e saturazioni che il programma toglie tenendo l'ultimo valore valido mentre il riferimento li sostituisce con la mediana, stanno tra 0,1 e 4,4 mV RMS. Il caso peggiore è 071210_001 a 452,5 s: un'escursione di 23 ms, 4,4 mV RMS, picco di 27 mV.
* Possibili strade, da decidere, nessuna applicata:
* (a) correggere il programma perché, quando accetta un'escursione lunga, "recuperi" i 50 ms trattenuti (ripassandoli al filtro), così da lì in poi coincide con il filtro ideale; i 50 ms già mostrati e salvati restano come sono;
* (b) accettare il ritardo di 50 ms sulle escursioni > 500 mV (in questi file sono artefatti da 5 V, non segnale fisiologico) e valutare C3b solo sulle escursioni accettate come segnale, o con una soglia che tenga conto dei 50 ms;
* (c) per C3/C4, contare come "salti" solo le escursioni oltre 50 ms.


### 4. Pulizia e controlli per il laboratorio

* **Nessuna finestra sullo schermo.** I test della GUI (`tests/test_gui.py`, `tests/test_scala.py`) partono solo sotto un display virtuale dichiarato (`DLIVE_DISPLAY_VIRTUALE=1` con `xvfb-run`), altrimenti si saltano anche se `DISPLAY` è impostato. Lo scenario della validazione rifiuta di partire fuori da Xvfb.
* **`installa.bat`: revisione riga per riga, non eseguito** (né Windows né Wine su questo PC). Le tabelle dell'MSI di Python sono state lette con 7z. Con `ADDLOCAL=ALL` l'installatore aggiungeva Python al **PATH di sistema** (funzione `PrependPath`) e registrava le **associazioni dei file .py** (`Extensions`). Ora installa solo `DefaultFeature, SharedCRT, PrivateCRT, TclTk, pip_feature`. Restano, perché fanno parte di ogni installazione di Python "per tutti gli utenti", `python34.dll` in system32, `msvcr100.dll` in system32 se manca, la chiave `HKLM\Software\Python\PythonCore\3.4` e la voce di disinstallazione. pip ora gira con `--no-cache-dir --disable-pip-version-check`, così non scrive nel profilo utente. WinWCP, le DLL Axon e WinASPI non vengono toccati. Aggiunto **`disinstalla.bat`**: conserva dati, log e configurazione, e rimuove Python solo se l'aveva installato `installa.bat` (file segnale) e dopo conferma.
* **Chiavetta** rigenerata dall'ultimo commit: hash dei file del programma confrontati con quelli del repository, `config.ini` con `aggiornamento_hz = 5`. Il controllo è descritto nel README, § 3.


## Fase 2 (storico): FAIL della fase 1 e correzioni

La fase 1 (codice non modificato, `rapporto_iniziale`) aveva dato **NON PRONTO**: 4 test critici FAIL (B1, C2, E1, E2) e 4 importanti FAIL (C3, C4, D2, E4). Per ogni FAIL è stata cercata la causa. Ne sono usciti 3 bug del programma (corretti), 5 errori nei test (corretti e dimostrati con i numeri) e 3 punti su cui decide il laboratorio (lasciati FAIL).


### 1. Bug del programma (corretti)

* **B1, B3, E1 — il simulatore perdeva l'ultimo campione della sorgente.** Prima: 1 campione diverso su 600 064 (l'ultimo, n. 600 063); grezzo di 600 063 campioni invece di 600 064. Causa: `lunghezza_utile()` (`dlive/devices/simulated.py`) toglie la "coda costante" dei record fermati prima della fine, ma eliminava anche l'ultimo valore acquisito davvero. Correzione: si toglie solo la ripetizione. Dopo: 0 campioni diversi, 600 064 su 600 064, anche con Python 3.4. Riguardava solo la simulazione, mai il Digidata.
* **D2 — con il Digidata l'anteprima non partiva.** Prima: `ValueError: frequenza di taglio 5 Hz non valida per fs=0 Hz` avviando la sessione con la scheda finta. Causa: `Digidata1322Device` calcolava la frequenza solo in `avvia()`, mentre la `Sessione` la legge subito dopo `apri()` per progettare il filtro. In laboratorio **"Avvia anteprima" sarebbe fallito sempre con la scheda vera**. I test esistenti provavano il driver da solo, mai dentro la sessione. Correzione: la frequenza è calcolata già in `apri()`, con la stessa formula. Dopo: overrun simulato attraverso la sessione completa, 1 evento, 9984 campioni persi contati anche nel JSON, base dei tempi conservata.
* **C4 (071210_001.wcp) — un picco del file non veniva tolto.** Prima: nel filtrato un avvallamento fino a −151 mV dove il riferimento arriva a −31 mV (120 mV oltre la soglia di 10 mV). Causa: il sovracampionamento a 1000 Hz del simulatore interpolava linearmente un picco di 1 campione (−1115 mV a 113,7 Hz) trasformandolo in una rampa di ~17 ms a gradini di ~125 mV. Il rilevatore dei picchi riconosce solo salti oltre 500 mV e non lo vedeva. Correzione: il sovracampionamento non interpola i salti oltre 500 unità, come già non interpolava le saturazioni. Dopo: estremi entro il riferimento (−5,2 mV / −0,7 mV).
* Rischio residuo, da vedere in laboratorio: se a 1000 Hz i picchi veri **non** sono bruschi (ad esempio se nascono prima dell'LPF-8) il rilevatore non li riconosce e nel filtrato restano come brevi avvallamenti. È nell'elenco D3.
* Per ciascuno dei tre bug c'è un test di regressione nella suite del progetto (`tests/test_simulatore.py`, `tests/test_digidata_finto.py`). Sul codice vecchio fallisce, sul nuovo passa.


### 2. Test sbagliati (corretti, con la dimostrazione)

* **E2 — vermin.** vermin stampa sempre 4 righe di riepilogo, che il test contava come violazioni. Numeri: codice di uscita 0, "Minimum required versions: 3.3". Con una f-string messa apposta per prova: codice 1, file e riga indicati, "Target versions not met". Ora il test guarda il codice di uscita e le righe che citano un file.
* **C3/C4 — saturazioni nel riferimento.** Il filtro mediano di 0,1 s del riferimento non toglie saturazioni più lunghe di 50 ms. In 071211 a 756,2 s l'ADC resta a −32768 conteggi per 64 campioni e il riferimento scendeva a −6140 mV, mentre il programma (correttamente) tiene l'ultimo valore valido. Ora nel riferimento i campioni sulle rotaie dell'ADC (−32768 / +32767) si interpolano, qualunque sia la loro durata.
* **C3/C4 — calibrazione del record nascosto di 081024.** Il canale 0 di 081024 è in **nA** (YG = 0,01, YZ = −16250); lo scrittore del test ricopiava il record con YG = 0,001 e YZ = 0. Così −16 248 conteggi (≈ 0 nA) diventavano "−4973 mV" e la soglia dei picchi cambiava di 10 volte. Con la calibrazione giusta: r = 0,9999, RMS 1,27 nA, ritardo 67 ms, C4 superato.
* **C2 — misura sotto la risoluzione del file.** Il filtrato si salva a 16 bit, come il grezzo: l'arrotondamento lascia ~0,04–0,09 mV RMS nella banda 25–60 Hz, e sotto questo livello il file non può scendere. Sui file poco rumorosi la riduzione misurata nel file è limitata dall'arrotondamento, non dal filtro. 071210_001.1: rumore 1,55 mV → 0,061 mV nel file (28,1 dB) ma 0,0030 mV all'uscita del programma (54,4 dB). 071222_002.1: 0,239 → 0,0385 mV (15,9 dB) contro 0,00067 mV (51,1 dB). Su 071224_003 e 081024_001 (record 1) il rumore 25–60 Hz è 0,0000 mV: la riduzione è 0/0 (il test dava −inf e −287 dB). Ora la riduzione si misura sull'uscita del programma prima dell'arrotondamento, che B2 e il test stesso verificano coincidere col file a meno dell'arrotondamento (0 conteggi di differenza). I casi con meno di 0,1 mV RMS di rumore (1/3 di conteggio) risultano "non applicabili". **La soglia di 30 dB non è cambiata.** Riduzione minima ora: 50,3 dB. Entrambi i valori sono nella tabella.
* **B8 — prova di 3 ore.** Nella prima versione la sorgente non era in tempo reale e produceva dati più in fretta di quanto la catena li elaborasse: la coda cresceva senza limite (con la scheda vera non può succedere) e la sessione non si chiudeva in tempo. Ora la sorgente è in tempo reale accelerato 100× e la coda resta a 0 blocchi.
* **E4 — misura disturbata.** Lo scenario della finestra girava in parallelo ad altri test: la CPU misurata variava da 2,3 % a 6,1 % tra un'esecuzione e l'altra. Ora gli scenari della finestra girano per ultimi, a macchina scarica.
* **M3.** Nella fase 1 M3 risultava "rilevato" anche da B1, ma solo perché B1 falliva per il bug del punto 1. Il vero test che lo rileva è A6 (50 Hz attenuato di 0,0 dB invece di oltre 30). Nella fase 1 A6 era registrato come NON VERIFICABILE per un errore del raccoglitore dei risultati (valore `numpy.bool_`), corretto prima del rapporto iniziale.


### 3. Lasciati FAIL: decide il laboratorio

* **C3 e C4 su 071211_001.1 (importanti).** Il canale 0 contiene due impulsi veri a −4981 mV lunghi ~100 ms (a 1183,03 s e 1183,28 s; non sono saturazioni). Il riferimento richiesto è a fase zero (`filtfilt` applica il Butterworth due volte: −6 dB a 5 Hz) e su impulsi così brevi e grandi risponde in modo diverso da qualunque filtro in tempo reale. **Un Bessel causale ideale calcolato da scipy, indipendente dal programma, ottiene gli stessi numeri del programma**: RMS 7,38 mV contro 7,46 e minimo 218,6 mV sotto il riferimento contro 222,9. Fuori da ±1 s attorno a questi 4 salti (0,2 % del tempo) il programma ha RMS 0,47 mV e r = 1,0000. La differenza 7,46 − 7,38 mV è l'effetto dei 50 ms di attesa del rilevatore dei picchi sui salti oltre 500 mV (scelta documentata nel README, § 6.1).
* **C3 su 071224_003 (importante).** Dopo il taglio della coda il segnale utile dura 16 s ed è quasi piatto: la deviazione standard del riferimento è 0,031 mV, un decimo di conteggio ADC. La correlazione (0,81) misura solo il rumore di arrotondamento; la differenza RMS è 0,03 mV (soglia 5 mV).
* **E4 (importante).** Il calcolo vero e proprio (lettura, filtro, salvataggio con fsync) usa lo 0,16 % del tempo reale con Python 3.12 e lo 0,28 % con Python 3.4. Il programma intero con la finestra, misurato a macchina scarica, arriva al 6,8 % (3.12) e al 9,7 % (3.4). Il profilo mostra che quasi tutto va nel disegno del grafico di Tk a 10 aggiornamenti al secondo (circa 2500 segmenti per disegno); il codice del disegno non fa lavoro inutile (due sole linee aggiornate, assi ridisegnati solo quando cambiano). Con `aggiornamento_hz = 5` in `config.ini` la CPU scende al 4,2 % (3.12) e al 5,3 % (3.4) e il ritardo massimo del grafico sale a 0,12 s. Il valore predefinito non è stato cambiato perché riguarda l'esperienza d'uso. Sul PC del laboratorio (di ~15 anni fa) la quota sarà più alta: va guardata nel Task Manager durante la prova (README § 7, punto 6).


### 4. Osservazione (nessun test la copre)

* **Scala in mV.** I file WinWCP 5.1.6 dichiarano ADCMAX = 32677 e WinWCP li legge con ADCMAX + 1 = 32678 (`WCPFIleUnit.pas`, `CalibFactorToADCScale`). Il programma, neo e il lettore di riferimento usano 32677: tra loro la differenza è dello 0,003 %. Rispetto alla conversione ideale del Digidata (±10 V su 65 536 livelli, 32768) i valori mostrati da WinWCP **e** dal programma sono più alti dello 0,28 % (100 mV veri → 100,28 mV). Il programma è quindi coerente con WinWCP. La taratura assoluta va controllata in laboratorio con un segnale noto (README § 7, punto 5).


## Tabella completa

**Critico** = decide il verdetto. Valori misurati sul PC di sviluppo salvo dove indicato (E1: Python 3.4 in Docker; E3/E5: finestra sotto Xvfb).


### A. Filtro (segnale sintetico a verità nota)

| ID | Cosa controlla | Valore misurato | Soglia | Esito | Critico |
|---|---|---|---|---|---|
| A1 | Un segnale lento (0,2 Hz, 100 mV) passa senza cambiare ampiezza. | 99.952 mV (ingresso 100.003 mV) | uscita tra 99 e 101 mV | PASS | sì |
| A2 | Dopo un gradino il filtrato si assesta esattamente sul livello vero. | errore massimo 0.142 mV (su 572 s di segnale, 7 gradini) | \|uscita − verità\| < 0,5 mV da 2 s dopo ogni gradino | PASS | sì |
| A3 | Sui gradini il filtrato non 'sfora' oltre il livello (sovraelongazione). | 2 Hz: 0.84 %; 5 Hz: 0.84 %; 10 Hz: 0.85 % | < 5 % a 2, 5 e 10 Hz | PASS | sì |
| A4 | Il filtrato segue i gradini con poco ritardo. | 2 Hz: 164 ms; 5 Hz: 65 ms; 10 Hz: 33 ms | ritardo al 50 % < 0,3 s a 2, 5 e 10 Hz | PASS | sì |
| A5 | Le frequenze di rumore (25, 37,4, 50 Hz) vengono abbattute. | 25 Hz: 42.0 dB; 37.4 Hz: 55.8 dB; 50 Hz: 280.0 dB | ≥ 35 dB a 25 Hz, ≥ 40 dB a 37,4 e 50 Hz | PASS | sì |
| A6 | Il notch toglie i 50 Hz senza toccare il segnale a 5 Hz. | 50 Hz: 272.0 dB; 5 Hz: ampiezza -0.001 %, forma d'onda max 0.34 % | 50 Hz attenuato ≥ 30 dB; 5 Hz alterato < 1 % | PASS | sì |
| A7 | Sul segnale sintetico con tutto il rumore, nei tratti calmi resta poco rumore. | 1.10 mV RMS (rumore in ingresso 45.9 mV RMS; 451 s di tratti quieti) | RMS < 2 mV nei tratti quieti | PASS | sì |
| A8 | I picchi di saturazione non lasciano tracce ('code') nel filtrato. | differenza massima 1.226 mV (30 picchi: 15 a fondo scala, 15 a +5,6 V) | differenza ≤ 2 mV nei 5 s dopo ogni picco | PASS | sì |
| A9 | Filtrare a pezzi dà lo stesso risultato che filtrare tutto insieme. | differenza massima 0 mV | differenza massima < 1e-6 mV | PASS | sì |
| A10 | Il filtro coincide con quello di riferimento di scipy (24 combinazioni). | differenza massima 2.7e-09 mV (butterworth 8 1 Hz), 24 combinazioni | differenza massima < 1e-4 mV | PASS | sì |
| A11 | Anche il filtro più 'estremo' (Bessel 8° ordine a 1 Hz) è stabile. | uscite finite: sì; errore dopo 5 s 0.0000 % (sotto lo 0,1 % da 1.14 s) | uscite finite; gradino entro 0,1 % in 5 s | PASS | sì |
| A12 | Cambiare il filtro durante l'acquisizione non crea salti né buchi. | salto massimo su 100 mV costanti 0.000 mV; NaN: 0; scarto dal livello vero 3 s dopo un cambio 0.142 mV (16 cambi) | salto < 0,5 mV, nessun NaN; livello vero entro 3 s | PASS | sì |
| A13 | Il percorso senza numpy (per PC vecchi) dà gli stessi numeri. | differenza massima 0 mV | differenza massima < 1e-6 mV | PASS | no (importante) |


### B. Catena completa in simulazione (sorgente → filtro → salvataggio)

| ID | Cosa controlla | Valore misurato | Soglia | Esito | Critico |
|---|---|---|---|---|---|
| B1 | Il file grezzo salvato è identico, campione per campione, a quanto acquisito. | 0 campioni diversi su 600064 | 0 differenze | PASS | sì |
| B2 | Il file filtrato coincide con un filtro di riferimento indipendente. | differenza massima 0 conteggi (0.00 mV) su 75008 campioni a 125 Hz; 0 campioni differiscono di 1 | differenza ≤ 1 conteggio ADC (≈ 0,31 mV) | PASS | sì |
| B3 | Nessun campione perso e file della durata giusta. | Perse = 0; grezzo 600064 campioni (attesi 600064), filtrato 75008 (attesi 75008); durata nel JSON 600.064 s; 11 record per file (attesi 11) | Perse = 0; durata ± 1 campione | PASS | sì |
| B4 | Un disturbo a 100 Hz non ricompare 'travestito' a bassa frequenza nel filtrato (aliasing). | ampiezza a 25 Hz (alias di 100 Hz) 0.0000 mV; scostamento massimo 0.000 mV | ampiezza < 0,5 mV | PASS | sì |
| B5 | Un marker inserito durante la registrazione è salvato all'istante giusto. | marker a 6.312 s nel JSON, istante reale 6.300 s (scarto +0.012 s) | entro 1 s | PASS | sì |
| B6 | I file si aprono con altri programmi (neo, lettore di riferimento) e hanno il formato di WinWCP 5.1.6. | neo vs riferimento: 0.0003 mV; chiavi uguali a 071210_001.wcp (VERPROG=V5.1.6): sì; 261124_001_raw.wcp: 11 record da 59392 campioni (118784 byte di dati = 232 settori da 512); 261124_001_filt.wcp: 11 record da 7424 campioni (14848 byte di dati = 29 settori da 512) | differenza < 0,001 mV; stesse chiavi; record multipli di 512 byte e < 2 200 000 campioni | PASS | sì |
| B7 | Se il programma viene ucciso di colpo i file restano leggibili e si perde pochissimo. | ucciso dopo 64.0 s di acquisizione; nel file 63.4 s validi; persi 0.60 s; leggibile con neo: sì; JSON leggibile (chiusura_regolare=False) | file leggibili con neo; persi ≤ 2 s | PASS | sì |
| B8 | Una registrazione di 3 ore non consuma memoria e non perde dati. | non eseguito: richiede ./valida.sh --lungo (3 ore di segnale) | memoria + < 50 MB; 0 persi; 0 errori | NON VERIFICABILE | no (importante) |
| B9 | Se il disco si riempie, l'errore viene mostrato ma l'acquisizione continua. | guasto a 6.1 s; acquisizione continuata fino a 14.1 s: sì; errore nel log: sì; messaggio alla finestra: sì; file leggibili con 6.1 s di dati corretti: sì; finestra (Python 3.12.16): banda rossa sì, nel log sì, continua sì, file leggibili sì; finestra (Python 3.4.10): banda rossa sì, nel log sì, continua sì, file leggibili sì | errore in GUI e log; acquisizione continua; dati già scritti leggibili | PASS | no (importante) |


### C. Dati reali del laboratorio

| ID | Cosa controlla | Valore misurato | Soglia | Esito | Critico |
|---|---|---|---|---|---|
| C1 | Tutti i file reali del laboratorio si leggono. | 7 file letti su 7 | 7 file senza errori | PASS | sì |
| C2 | Sui dati reali il rumore 25–60 Hz viene ridotto di molto. | riduzione minima 50.3 dB (071211_001.1 (1).wcp); per file (uscita del programma / file a 16 bit): 071210_001.1.wcp 54.4 / 28.1 dB (rumore 1.55 → 0.0030 mV RMS); 071210_001.wcp 57.4 / 46.9 dB (rumore 14.54 → 0.0196 mV RMS); 071211_001.1 (1).wcp 50.3 / 47.3 dB (rumore 21.08 → 0.0644 mV RMS); 071211_001.1.wcp 50.3 / 47.3 dB (rumore 21.08 → 0.0644 mV RMS); 071222_002.1.wcp 51.1 / 15.9 dB (rumore 0.24 → 0.0007 mV RMS); 081024_001.wcp record 2 (non dichiarato) 50.4 / 49.1 dB (rumore 2.18 → 0.0066 mV RMS); non applicabile (nessun rumore 25–60 Hz nel grezzo, < 0.1 mV RMS): 071224_003.wcp (0.0000 mV),… | riduzione ≥ 30 dB | PASS | sì |
| C3 | Sui dati reali il filtrato ha la stessa forma di un filtro di riferimento 'ideale'. | 071210_001.1.wcp: r = 0.9999, RMS 0.36 mV, ritardo 67 ms, esclusi 0.00 % (0 salti); 071210_001.wcp: r = 0.9988, RMS 0.61 mV, ritardo 67 ms, esclusi 0.07 % (4 salti); 071211_001.1 (1).wcp: r = 1.0000, RMS 0.44 mV, ritardo 67 ms, esclusi 1.15 % (17 salti); 071211_001.1.wcp: r = 1.0000, RMS 0.44 mV, ritardo 67 ms, esclusi 1.15 % (17 salti); 071222_002.1.wcp: r = 1.0000, RMS 0.10 mV, ritardo 67 ms, esclusi 0.00 % (0 salti); 071224_003.wcp: correlazione non applicabile (il riferimento varia di 0.021, meno di 1 conteggio = 0.306 mV), RMS 0.03 mV, ritardo 75 ms, esclusi 0.00 % (0 salti); 081024_001.… | correlazione ≥ 0,99 e differenza RMS < 5 mV, fuori da ±1 s attorno ai salti > 500 mV (esclusi < 2 % del tempo; era 1 % fino alla fase 3); correlazione solo se il riferimento varia di almeno 1 conteggio | PASS | no (importante) |
| C3b | Dove C3 e C4 non guardano (attorno ai salti > 500 mV) il programma fa esattamente quello che dice il README: toglie i picchi e filtra come un filtro ideale. | 071210_001.wcp: 2 finestre, RMS massimo 0.09 mV; copertura del tempo escluso 100 %; 071211_001.1 (1).wcp: 7 finestre, RMS massimo 0.09 mV; copertura del tempo escluso 100 %; 071211_001.1.wcp: 7 finestre, RMS massimo 0.09 mV; copertura del tempo escluso 100 % | per finestra RMS < 2 mV dal filtro causale ideale dopo la regola dei picchi del README; copre il 100 % del tempo escluso da C3/C4 | PASS | no (importante) |
| C4 | Sui dati reali il filtrato non contiene valori assurdi. | 071210_001.1.wcp: finiti sì, massimo -0.14, minimo -0.40 mV rispetto al riferimento; 071210_001.wcp: finiti sì, massimo +2.46, minimo +0.67 mV rispetto al riferimento; 071211_001.1 (1).wcp: finiti sì, massimo -0.13, minimo -0.27 mV rispetto al riferimento; 071211_001.1.wcp: finiti sì, massimo -0.13, minimo -0.27 mV rispetto al riferimento; 071222_002.1.wcp: finiti sì, massimo +0.04, minimo -0.07 mV rispetto al riferimento; 071224_003.wcp: finiti sì, massimo -0.06, minimo -0.82 mV rispetto al riferimento; 081024_001.wcp: finiti sì, massimo -32.86, minimo +44.17 nA rispetto al riferimento; 0810… | nessun NaN/inf; estremi entro 10 mV dal riferimento, fuori da ±1 s attorno ai salti > 500 mV (esclusi < 2 % del tempo) | PASS | no (importante) |
| C5 | Grafici di grezzo, filtrato e riferimento per ogni file reale. | dati per 8 figure salvati (le figure sono disegnate dal rapporto) | — | PASS | no (informativo) |


### D. Pilota del Digidata (senza la scheda vera)

| ID | Cosa controlla | Valore misurato | Soglia | Esito | Critico |
|---|---|---|---|---|---|
| D1 | Le strutture dati del driver hanno dimensioni e posizioni identiche all'header Axon. | DD132X_Info 384 byte (16 campi); DD132X_Protocol 832 byte (21 campi); DD132X_CalibrationData 256 byte (10 campi); DATABUFFER 24 byte (6 campi); tutti gli offset coincidono (anche a 64 bit) | dimensioni e offset uguali (gcc -m32) | PASS | no (importante) |
| D2 | Contro una scheda finta il driver fa le chiamate giuste e dà messaggi chiari. | sequenza OK; dll_mancante OK; scheda_assente OK; winaspi OK; overrun OK | sequenza corretta; messaggi chiari; overrun contato | PASS | no (importante) |
| D3 | Elenco di ciò che si può verificare solo con la scheda vera. | 11 punti verificabili solo in laboratorio (passi della diagnostica) | — | PASS | no (informativo) |


### E. Compatibilità, interfaccia, prestazioni

| ID | Cosa controlla | Valore misurato | Soglia | Esito | Critico |
|---|---|---|---|---|---|
| E1 | Tutti i test A e B passano anche con Python 3.4 + numpy 1.15 (quelli del PC del laboratorio). | Python 3.4.10 + numpy 1.15.4 + scipy 1.2.3: 19 PASS, 0 FAIL; esclusi: B6 (neo non installato: confronto non eseguito; chiavi uguali a 071210_001.wcp (VERPROG=V5.1.6): sì; 261); B7 (ucciso dopo 64.0 s di acquisizione; nel file 63.3 s validi; persi 0.71 s; leggibile con neo: non pro); B8 (non eseguito: solo con --lungo) | tutti PASS (esclusi quelli che richiedono neo) | PASS | sì |
| E2 | Il codice non usa nulla che Python 3.4 non abbia. | codice di uscita 0, 0 violazioni; Minimum required versions: 3.3 | vermin --target=3.4- senza errori | PASS | sì |
| E3 | La finestra funziona: avvio, anteprima, cambio filtro, marker, registrazione, chiusura. | Python 3.12.16, grafico a 5 Hz: codice 0, eccezioni nel log 0, nei callback 0, dialoghi d'errore 0, finestra 1272x960 su schermo 1280x1024, controlli fuori 0, registrazione 30.0 s, marker e cambio filtro nel JSON: sì; Python 3.4.10, grafico a 5 Hz: codice 0, eccezioni nel log 0, nei callback 0, dialoghi d'errore 0, finestra 1272x960 su schermo 1280x1024, controlli fuori 0, registrazione 30.1 s, marker e cambio filtro nel JSON: sì; Python 3.12.16, grafico a 10 Hz: codice 0, eccezioni nel log 0, nei callback 0, dialoghi d'errore 0, finestra 1272x960 su schermo 1280x1024, controlli fuori 0, regi… | 0 eccezioni nel log | PASS | sì |
| E4 | Il programma usa poca CPU. | **con la finestra, grafico a 5 Hz (predefinito), Python 3.12.16: 2.23 %**; informativo: con la finestra, grafico a 5 Hz, Python 3.4.10: 3.27 %; informativo: con la finestra, grafico a 10 Hz, Python 3.12.16: 3.87 %; informativo: calcolo senza finestra, Python 3.12.16: 0.16 %; informativo: calcolo senza finestra, Python 3.4.10: 0.30 % | < 5 % del tempo reale con la finestra (impostazioni predefinite, Python di sviluppo) | PASS | no (importante) |
| E5 | Il grafico mostra il segnale con poco ritardo. | Python 3.12.16: mediana 35 ms, 95° percentile 53 ms, massimo 127 ms (296 disegni); Python 3.4.10: mediana 33 ms, 95° percentile 56 ms, massimo 61 ms (296 disegni) (grafico a 5 Hz, predefinito) | < 0,5 s | PASS | no (importante) |
| E6 | Su un PC 5 volte più lento (come quello del laboratorio) 10 minuti di registrazione con la finestra non perdono nulla. | Python 3.4.10, CPU limitata a 0,2 (--cpus=0.2), grafico a 5 Hz: registrazione 600.0 s; persi 0; arretrato massimo dell'elaborazione 0.05 s, coda massima 0.05 s (limite 600 s); ritardo del grafico massimo 65 ms (mediana 33 ms); eccezioni 0; B1 0 campioni diversi; B2 differenza massima 0 conteggi; B3 persi 0; CPU del processo 3.4 % di un core | 0 persi; coda sotto il limite; ritardo del grafico < 1 s; 0 eccezioni; file come B1, B2, B3 | PASS | no (importante) |
| E7 | La finestra vera in modalità Digidata (scheda finta) registra correttamente, mostra gli errori in modo comprensibile e riparte dopo un errore. | Python 3.12.16: PASS; errori → DLL mancante: OK; scheda assente: OK; WinASPI assente: OK; errore interno dopo l'apertura: OK; riprova dopo gli errori: OK; overrun mostrato sì; registrazione B1 0 diversi, B2 0 conteggi, B3 persi 0; aggiornamento del grafico cambiato dal vivo 2 Hz → 2.0 disegni/s, 10 Hz → 9.8 disegni/s, 5 Hz → 5.0 disegni/s; schede rimaste aperte 0; traceback inattesi 0 \| Python 3.4.10: PASS; errori → DLL mancante: OK; scheda assente: OK; WinASPI assente: OK; errore interno dopo l'apertura: OK; riprova dopo gli errori: OK; overrun mostrato sì; registrazione B1 0 diversi, B2 0 c… | 0 eccezioni; file come B1, B2, B3; messaggi senza traceback; riavvio dopo ogni errore | PASS | sì |


### M. Prova dei test (mutazioni)

| ID | Cosa controlla | Valore misurato | Soglia | Esito | Critico |
|---|---|---|---|---|---|
| M1 | Guasto finto: frequenza di taglio raddoppiata → i test se ne accorgono. | rilevato da: A10 (differenza massima 1.5e+02 mV (butterworth 8 2 Hz), 24 combinazioni); A5 (25 Hz: 19.6 dB; 37.4 Hz: 32.4 dB; 50 Hz: 280.0 dB); A7 (3.22 mV RMS (rumore in ingresso 45.9 mV RMS; 451 s di tratti quieti)); A8 (differenza massima 2.455 mV (30 picchi: 15 a fondo scala, 15 a +5,6 V)); B2 (differenza massima 289 conteggi (88.20 mV) su 75008 campioni a 125 Hz; 3700 campioni differiscono di 1) | almeno un test CRITICO FAIL | PASS | sì |
| M2 | Guasto finto: stato del filtro azzerato a ogni blocco → i test se ne accorgono. | rilevato da: A10 (differenza massima 45 mV (butterworth 8 1 Hz), 24 combinazioni); A12 (salto massimo su 100 mV costanti 100.098 mV; NaN: 0; scarto dal livello vero 3 s dopo un cambio 120.000 mV (16 cambi)); A9 (differenza massima 1.3e+02 mV); B2 (differenza massima 430 conteggi (131.23 mV) su 75008 campioni a 125 Hz; 6 campioni differiscono di 1); B4 (ampiezza a 25 Hz (alias di 100 Hz) 1.0574 mV; scostamento massimo 12.512 mV) | almeno un test CRITICO FAIL | PASS | sì |
| M3 | Guasto finto: notch a 60 Hz invece di 50 Hz → i test se ne accorgono. | rilevato da: A6 (50 Hz: 0.0 dB; 5 Hz: ampiezza -0.000 %, forma d'onda max 0.28 %) | almeno un test CRITICO FAIL | PASS | sì |
| M4 | Guasto finto: un campione saltato ogni 1000 nel salvataggio → i test se ne accorgono. | rilevato da: B1 (597899 campioni diversi su 600064) | almeno un test CRITICO FAIL | PASS | sì |


### Note ai test

* **A3** — atteso da scipy: 2 Hz 0.84 %; 5 Hz 0.84 %; 10 Hz 0.85 %
* **A4** — atteso da scipy: 2 Hz 164 ms; 5 Hz 65 ms; 10 Hz 33 ms
* **A5** — atteso da scipy: 25 Hz 42 dB; 37.4 Hz 56 dB; 50 Hz 335 dB
* **C1** — 071210_001.1.wcp: 5 canali, 1 record, 3600 s, 113.70 Hz; 071210_001.wcp: 1 canali, 4 record, 14401 s, 113.70 Hz; 071211_001.1 (1).wcp: 5 canali, 1 record, 3584 s, 125.00 Hz; 071211_001.1.wcp: 5 canali, 1 record, 3584 s, 125.00 Hz; 071222_002.1.wcp: 1 canali, 1 record, 3584 s, 125.00 Hz; 071224_003.wcp: 1 canali, 1 record, 3584 s, 125.00 Hz; 081024_001.wcp: 5 canali, 2 record, 7168 s, 125.00 Hz
* **C2** — metodo corretto in fase 2: misura prima dell'arrotondamento a 16 bit del file; casi senza rumore nella banda esclusi (vedi analisi). Controllo D7 (fase 4): su ogni file il filtrato salvato coincide campione per campione con l'Elaboratore costruito con l'attesa di 50 campioni scritta a mano: campioni diversi = 0, 0, 0, 0, 0, 0, 0, 0
* **C3** — fase 3 (D2): fuori da ±1 s attorno ai salti > 500 mV del grezzo; il riferimento a fase zero applica il filtro due volte e risponde in modo diverso da qualunque filtro in tempo reale a impulsi brevi e grandi. Lì vale C3b.
* **C3b** — fase 4 (D5): filtro causale ideale (scipy, notch 50 Hz + Bessel 4° ordine 5 Hz, partenza a regime) applicato al grezzo a 1000 Hz dopo la regola dei picchi del README § 6.1, scritta nel test senza usare il codice del programma: saturazioni e escursioni > 500 mV fino a 50 ms sostituite dall'ultimo valore valido, delle escursioni più lunghe solo i primi 50 ms
* **C4** — fuori da ±1 s attorno ai salti > 500 mV (come C3); valori positivi del massimo o negativi del minimo = il filtrato va oltre il riferimento
* **D1** — DATABUFFER non e' nell'header Axon: confrontata con TDATABUFFER di dd1320.pas
* **D2** — sequenza: FindDevices → OpenDevice → GetCalibrationData → IsAcquiring → SetProtocol → StartAcquisition → GetAcquisitionPosition → IsAcquiring → StopAcquisition → CloseDevice (1015 campioni in 1 s) | DLL mancante: «AxDD132x.dll non trovata o non caricabile. Cercata in: cartella del programma, cartelle di WinWCP, pCLAMP/AxoScope, C:\Axon\..., system32.  denoising_live usa l» | scheda assente: «Nessun Digidata trovato (FindDevices=0, errore finto 1000).  Controllare che il Digidata sia acceso PRIMA di accendere il PC, che il cavo SCSI e il terminatore » | WinASPI mancante: «Nessun Digidata trovato (FindDevices=0, errore finto 1000).  WinASPI non funziona (wnaspi32.dll non caricabile: [WinError 126]): installare AxoScope (dall'insta» | overrun: 1 evento, 10028 campioni persi contati (JSON: 10028), base dei tempi conservata: sì
* **E4** — fase 3 (D3): grafico a 5 Hz predefinito; esito sul programma intero con la finestra, Python di sviluppo; gli altri valori sono informativi
* **E5** — punto di misura esterno: istante del disegno meno istante in cui la sorgente simulata ha prodotto l'ultimo campione disegnato
* **E6** — la quota di CPU di Docker rallenta a scatti (periodi di 100 ms) e non riproduce una CPU vecchia (cache, disco, Windows XP); il limite della coda (600 s) è una costante del test: il programma non ne ha uno (D8)


## Prima e dopo: fase 4 → fase 5

Fase 4 = `rapporto_fase4` (archiviato); fase 5 = questo rapporto. Sono riportate le voci con esito cambiato e, per mostrare che la logica del filtro non è cambiata, A8, B2, C3, C3b, C4. Le correzioni della fase 5 (protocollo, RTIMESECS, LPF-8, impostazioni di WinWCP, rilevamento) sono provate dai test di `tests/test_fase5.py`, elencati nella sezione «Cosa è stato ricavato dai sorgenti».

| ID | Prima | Valore prima | Dopo | Valore dopo |
|---|---|---|---|---|
| A8 | PASS | differenza massima 1.226 mV (30 picchi: 15 a fondo scala, 15 a +5,6 V) | PASS | differenza massima 1.226 mV (30 picchi: 15 a fondo scala, 15 a +5,6 V) |
| B2 | PASS | differenza massima 0 conteggi (0.00 mV) su 75008 campioni a 125 Hz; 0 campioni differiscono di 1 | PASS | differenza massima 0 conteggi (0.00 mV) su 75008 campioni a 125 Hz; 0 campioni differiscono di 1 |
| B8 | PASS | 3.01 ore di segnale in 108 s (100x); memoria del processo: 224 MB all'avvio, 225 MB dopo 10 min di segnale, massimo 225 MB (crescita 0.9 MB; 0.3 MB dopo i primi 10 min); persi 0; errori di scrittura 0; errori nel log 0; 183 record; coda massima 0 blocchi | NON VERIFICABILE | non eseguito: richiede ./valida.sh --lungo (3 ore di segnale) |
| C3 | PASS | 071210_001.1.wcp: r = 0.9999, RMS 0.36 mV, ritardo 67 ms, esclusi 0.00 % (0 salti); 071210_001.wcp: r = 0.9988, RMS 0.61 mV, ritardo 67 ms, esclusi 0.07 % (4 salti); 071211_001.1 (1).wcp: r = 1.0000, RMS 0.44 mV, ritardo 67 ms, esclusi 1.15 % (17 salti); 071211_001.1.wcp: r = 1.0000, RMS 0.44 mV, r… | PASS | 071210_001.1.wcp: r = 0.9999, RMS 0.36 mV, ritardo 67 ms, esclusi 0.00 % (0 salti); 071210_001.wcp: r = 0.9988, RMS 0.61 mV, ritardo 67 ms, esclusi 0.07 % (4 salti); 071211_001.1 (1).wcp: r = 1.0000, RMS 0.44 mV, ritardo 67 ms, esclusi 1.15 % (17 salti); 071211_001.1.wcp: r = 1.0000, RMS 0.44 mV, r… |
| C3b | PASS | 071210_001.wcp: 2 finestre, RMS massimo 0.09 mV; copertura del tempo escluso 100 %; 071211_001.1 (1).wcp: 7 finestre, RMS massimo 0.09 mV; copertura del tempo escluso 100 %; 071211_001.1.wcp: 7 finestre, RMS massimo 0.09 mV; copertura del tempo escluso 100 % | PASS | 071210_001.wcp: 2 finestre, RMS massimo 0.09 mV; copertura del tempo escluso 100 %; 071211_001.1 (1).wcp: 7 finestre, RMS massimo 0.09 mV; copertura del tempo escluso 100 %; 071211_001.1.wcp: 7 finestre, RMS massimo 0.09 mV; copertura del tempo escluso 100 % |
| C4 | PASS | 071210_001.1.wcp: finiti sì, massimo -0.14, minimo -0.40 mV rispetto al riferimento; 071210_001.wcp: finiti sì, massimo +2.46, minimo +0.67 mV rispetto al riferimento; 071211_001.1 (1).wcp: finiti sì, massimo -0.13, minimo -0.27 mV rispetto al riferimento; 071211_001.1.wcp: finiti sì, massimo -0.13… | PASS | 071210_001.1.wcp: finiti sì, massimo -0.14, minimo -0.40 mV rispetto al riferimento; 071210_001.wcp: finiti sì, massimo +2.46, minimo +0.67 mV rispetto al riferimento; 071211_001.1 (1).wcp: finiti sì, massimo -0.13, minimo -0.27 mV rispetto al riferimento; 071211_001.1.wcp: finiti sì, massimo -0.13… |


## Figure

*(figura non pubblicata: «Verità, segnale con rumore e filtrato (sintetico), con zoom su un gradino.»)*

*Verità, segnale con rumore e filtrato (sintetico), con zoom su un gradino.*

*(figura non pubblicata: «Risposta in frequenza misurata sul programma e attesa da scipy, con le frequenze di rumore evidenziate (valori sotto −160 dB disegnati a −160).»)*

*Risposta in frequenza misurata sul programma e attesa da scipy, con le frequenze di rumore evidenziate (valori sotto −160 dB disegnati a −160).*

*(figura non pubblicata: «C5 — 071210_001.1.wcp: grezzo, filtrato e riferimento; spettro prima e dopo.»)*

*C5 — 071210_001.1.wcp: grezzo, filtrato e riferimento; spettro prima e dopo.*

*(figura non pubblicata: «C5 — 071210_001.wcp: grezzo, filtrato e riferimento; spettro prima e dopo.»)*

*C5 — 071210_001.wcp: grezzo, filtrato e riferimento; spettro prima e dopo.*

*(figura non pubblicata: «C5 — 071211_001.1 (1).wcp: grezzo, filtrato e riferimento; spettro prima e dopo.»)*

*C5 — 071211_001.1 (1).wcp: grezzo, filtrato e riferimento; spettro prima e dopo.*

*(figura non pubblicata: «C5 — 071222_002.1.wcp: grezzo, filtrato e riferimento; spettro prima e dopo.»)*

*C5 — 071222_002.1.wcp: grezzo, filtrato e riferimento; spettro prima e dopo.*

*(figura non pubblicata: «C5 — 071224_003.wcp: grezzo, filtrato e riferimento; spettro prima e dopo.»)*

*C5 — 071224_003.wcp: grezzo, filtrato e riferimento; spettro prima e dopo.*

*(figura non pubblicata: «C5 — 081024_001.wcp: grezzo, filtrato e riferimento; spettro prima e dopo.»)*

*C5 — 081024_001.wcp: grezzo, filtrato e riferimento; spettro prima e dopo.*

*(figura non pubblicata: «C5 — 081024_001.wcp record 2 (non dichiarato): grezzo, filtrato e riferimento; spettro prima e dopo.»)*

*C5 — 081024_001.wcp record 2 (non dichiarato): grezzo, filtrato e riferimento; spettro prima e dopo.*


## Dettagli


### C1 — I file reali

| File | Canali | Record | Durata | Campionamento | Avvisi del lettore | MD5 |
|---|---|---|---|---|---|---|
| 071210_001.1.wcp | 5 | 1 (intestazione: 1) | 3600 s | 113.70 Hz | — | 172d36d4 |
| 071210_001.wcp | 1 | 4 (intestazione: 4) | 14401 s | 113.70 Hz | — | 707db2b4 |
| 071211_001.1 (1).wcp | 5 | 1 (intestazione: 1) | 3584 s | 125.00 Hz | — | 320f38c5 |
| 071211_001.1.wcp | 5 | 1 (intestazione: 1) | 3584 s | 125.00 Hz | — | 320f38c5 |
| 071222_002.1.wcp | 1 | 1 (intestazione: 1) | 3584 s | 125.00 Hz | — | e6b3aaf9 |
| 071224_003.wcp | 1 | 1 (intestazione: 0) | 3584 s | 125.00 Hz | NR=0 nell'intestazione, ricalcolato dalla dimensione: 1 | 95b3ec5a |
| 081024_001.wcp | 5 | 2 (intestazione: 1) | 7168 s | 125.00 Hz | il file contiene 1 record completi oltre NR=1 (non visibili in WinWCP); letti | e6b2c5f3 |

| Caso | Canale | Durata utile | Rumore 25–60 Hz grezzo (RMS) | … uscita del programma (RMS) | C2 riduzione programma / file | C3 correlazione | C3 RMS | Ritardo | Salti > 500 / tempo escluso | C3b RMS | C4 estremi oltre il rif. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 071210_001.1.wcp | 4 | 387 s | 1.55 | 0.0030 | 54.4 / 28.1 dB | 0.9999 | 0.36 | 67 ms | 0 / 0.00 % | — | +-0.1 / −0.4 |
| 071210_001.wcp | 0 | 5587 s | 14.54 | 0.0196 | 57.4 / 46.9 dB | 0.9988 | 0.61 | 67 ms | 4 / 0.07 % | 0.09 | +2.5 / −-0.7 |
| 071211_001.1 (1).wcp | 0 | 1258 s | 21.08 | 0.0644 | 50.3 / 47.3 dB | 1.0000 | 0.44 | 67 ms | 17 / 1.15 % | 0.09 | +-0.1 / −0.3 |
| 071211_001.1.wcp | 0 | 1258 s | 21.08 | 0.0644 | 50.3 / 47.3 dB | 1.0000 | 0.44 | 67 ms | 17 / 1.15 % | 0.09 | +-0.1 / −0.3 |
| 071222_002.1.wcp | 0 | 447 s | 0.24 | 0.0007 | 51.1 / 15.9 dB | 1.0000 | 0.10 | 67 ms | 0 / 0.00 % | — | +0.0 / −0.1 |
| 071224_003.wcp | 0 | 16 s | 0.00 | 0.0000 | -inf / -inf dB | n. a. (piatto) | 0.03 | 75 ms | 0 / 0.00 % | — | +-0.1 / −0.8 |
| 081024_001.wcp | 0 | 218 s | 0.00 | 0.0000 | -287.4 / -287.4 dB | 0.9954 | 0.86 | 67 ms | 0 / 0.00 % | — | +-32.9 / −-44.2 |
| 081024_001.wcp record 2 (non dichiarato) | 0 | 534 s | 2.18 | 0.0066 | 50.4 / 49.1 dB | 0.9999 | 1.27 | 67 ms | 0 / 0.00 % | — | +-30.3 / −-29.8 |


### Mutazioni (copia temporanea del codice)

| ID | Guasto | File | Test falliti | Rilevato da un test critico |
|---|---|---|---|---|
| M1 | frequenza di taglio raddoppiata | dlive/filters.py | A10, A5, A7, A8, B2 | sì |
| M2 | stato del filtro azzerato a ogni blocco | dlive/filters.py | A10, A12, A9, B2, B4 | sì |
| M3 | notch a 60 Hz invece di 50 Hz | dlive/filters.py | A6 | sì |
| M4 | un campione saltato ogni 1000 nel salvataggio | dlive/recorder.py | B1 | sì |


### D3 — Da verificare solo con la scheda

* la DLL vera AxDD132x.dll (quale versione funziona, firme reali, convenzione di chiamata a runtime)
* WinASPI (wnaspi32.dll / aspi32.sys) e il controller SCSI su Windows XP
* che la scheda accetti il protocollo (uChunksPerSecond = 20, uscite DAC nel protocollo)
* la temporizzazione reale: 1000 campioni al secondo esatti, deriva del clock della scheda
* il significato reale di DD132X_GetAcquisitionPosition e gli overrun veri
* il valore 32767 come 'vuoto' con il bit TAG: comportamento del firmware reale
* la calibrazione (offset/guadagno ADC, offset DAC: 8 o 16 DAC nella struttura)
* la forma reale dei picchi a 1000 Hz (nei file di prova sono campionati a 114-125 Hz)
* il guadagno reale della catena (LPF-8, scala mV) rispetto a quanto mostra WinWCP
* l'apertura dei file in WinWCP 5.1.6 su Windows XP
* tkinter, numpy 1.15 e le prestazioni sul PC del laboratorio (CPU, schermo, disco)


### E1 — Esiti in Python 3.4 (Docker)

| ID | Esito | Valore misurato su Python 3.4 |
|---|---|---|
| A1 | PASS | 99.952 mV (ingresso 100.003 mV) |
| A2 | PASS | errore massimo 0.142 mV (su 572 s di segnale, 7 gradini) |
| A3 | PASS | 2 Hz: 0.84 %; 5 Hz: 0.84 %; 10 Hz: 0.85 % |
| A4 | PASS | 2 Hz: 164 ms; 5 Hz: 65 ms; 10 Hz: 33 ms |
| A5 | PASS | 25 Hz: 42.0 dB; 37.4 Hz: 55.8 dB; 50 Hz: 280.0 dB |
| A6 | PASS | 50 Hz: 272.0 dB; 5 Hz: ampiezza -0.001 %, forma d'onda max 0.34 % |
| A7 | PASS | 1.10 mV RMS (rumore in ingresso 45.9 mV RMS; 451 s di tratti quieti) |
| A8 | PASS | differenza massima 1.226 mV (30 picchi: 15 a fondo scala, 15 a +5,6 V) |
| A9 | PASS | differenza massima 0 mV |
| A10 | PASS | differenza massima 2.6e-09 mV (butterworth 8 1 Hz), 24 combinazioni |
| A11 | PASS | uscite finite: sì; errore dopo 5 s 0.0000 % (sotto lo 0,1 % da 1.14 s) |
| A12 | PASS | salto massimo su 100 mV costanti 0.000 mV; NaN: 0; scarto dal livello vero 3 s dopo un cambio 0.142 mV (16 cambi) |
| A13 | PASS | differenza massima 0 mV |
| B1 | PASS | 0 campioni diversi su 600064 |
| B2 | PASS | differenza massima 0 conteggi (0.00 mV) su 75008 campioni a 125 Hz; 0 campioni differiscono di 1 |
| B3 | PASS | Perse = 0; grezzo 600064 campioni (attesi 600064), filtrato 75008 (attesi 75008); durata nel JSON 600.064 s; 11 record per file (attesi 11) |
| B4 | PASS | ampiezza a 25 Hz (alias di 100 Hz) 0.0000 mV; scostamento massimo 0.000 mV |
| B5 | PASS | marker a 6.378 s nel JSON, istante reale 6.331 s (scarto +0.047 s) |
| B6 | NON VERIFICABILE | neo non installato: confronto non eseguito; chiavi uguali a 071210_001.wcp (VERPROG=V5.1.6): sì; 261124_001_raw.wcp: 11 record da 59392 campioni (118784 byte di dati = 232 settori da 512); 261124_001_filt.wcp: 11 record… |
| B7 | NON VERIFICABILE | ucciso dopo 64.0 s di acquisizione; nel file 63.3 s validi; persi 0.71 s; leggibile con neo: non provato; JSON leggibile (chiusura_regolare=False); neo non installato: lettura con neo non verificata |
| B9 | PASS | guasto a 6.1 s; acquisizione continuata fino a 14.2 s: sì; errore nel log: sì; messaggio alla finestra: sì; file leggibili con 6.0 s di dati corretti: sì |
| D1 | PASS | DD132X_Info 384 byte (16 campi); DD132X_Protocol 832 byte (21 campi); DD132X_CalibrationData 256 byte (10 campi); DATABUFFER 24 byte (6 campi); tutti gli offset coincidono (anche a 64 bit) |
| D2 | PASS | dll_mancante OK; scheda_assente OK; sequenza OK; overrun OK; winaspi OK |
| D3 | PASS | 11 punti verificabili solo in laboratorio (passi della diagnostica) |
| E4 | PASS | 0.30 % (1.78 s di CPU per 600 s di segnale; Python 3.4.10) — senza il disegno della finestra, misurato a parte con la finestra in E3 |


### Come rifare tutto

```
./valida.sh            # tutto tranne la prova di 3 ore (~10 minuti)
./valida.sh --lungo    # aggiunge la prova di 3 ore accelerata (B8)
```
