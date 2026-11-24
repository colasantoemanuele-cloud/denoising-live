# Analisi dei sorgenti e dei documenti (fase 5)

Cosa si ricava dai materiali disponibili sul funzionamento reale di WinWCP, del Digidata 1322A,
del filtro LPF-8 e dei file di prova, e cosa ne consegue per il programma. Per ogni conclusione
ci sono la fonte (file e riga del sorgente oppure pagina del documento) e la conseguenza:
**corretto** (il programma è stato cambiato, con un test), **già giusto** oppure **da verificare
in laboratorio**.

Le righe si riferiscono a questi file:

| sigla | file |
|---|---|
| `dd1320` | `riferimenti/winwcp_chiave/dd1320.pas` (SESComponentsXE, ultima modifica 03.01.20) |
| `dd1320_old` | `riferimenti/winwcp_chiave/dd1320_SESComponents_old.pas` (stessa unità, versione 2013) |
| `SESLabIO` | `riferimenti/winwcp_chiave/SESLabIO.pas` |
| `WCPFile` | `riferimenti/winwcp_sorgenti/XE-5.8.1/WCPFIleUnit.pas` (WinWCP 5.8.1) |
| `REC` / `MDIForm` / `StimModule` | i file omonimi di `riferimenti/winwcp_sorgenti/XE-5.8.1/` |
| `AxDD132x.h` | `riferimenti/sdk_axon/AxDD132x.h` (header ufficiale Axon) |
| guida | `riferimenti/doc/WinWCP_User_Guide.pdf`: **guida della V5.2.4** (1/3/2017); le pagine sono quelle stampate |
| LPF-8 | `riferimenti/doc/LPF-8 manual.pdf` ("LPF-8 Manual 4-8-98"), pagine stampate |
| 5.2.7 | installatore di WinWCP 5.2.7 dalla cartella delle versioni, estratto: `riferimenti/winwcp5_2_7/LEGGIMI.txt` |

## 0. Quale WinWCP c'è in laboratorio, e quanto valgono i sorgenti per la 5.1.6

* **WinWCP 5.1.6 è del 16/03/2016** (`MDIForm`:672, storia delle versioni). I sorgenti sono
  della 5.8.1 (2024) e del ramo `master` (V4.5.8, 2013): la 5.1.6 sta in mezzo.
* **I 7 file di prova li ha scritti proprio la 5.1.6**: hanno `VERPROG=V5.1.6`, una chiave che
  esiste solo dalla V4.9.0 del 20/03/2015 (`MDIForm`:604, `WCPFile`:87) e che WinWCP scrive alla
  creazione del file (`WCPFile`:790); hanno anche `RTIMESECS` e `RTIME`, aggiunte il 27/08/2013
  (`WCPFile`:84). **Però le date dentro i file (CTIME, RTIME), i nomi `AAMMGG` e le date dei file
  sono del 2007-2008.** Conclusione (certa): quando sono stati registrati, **l'orologio del PC
  del laboratorio era indietro di circa 8-9 anni** (batteria della scheda madre scarica o data
  impostata a mano). Conseguenze: (a) il comando di raccolta non può cercare i file recenti per
  nome (`25*.wcp`, `26*.wcp` come faceva): ora li prende dalle impostazioni di WinWCP
  (§ 2); (b) la diagnostica avvisa se la data del PC è anteriore al 2016 (§ G); (c) il
  programma, come WinWCP, dà ai file il nome con la data del PC: non la cambiamo (**decide il
  laboratorio** se correggere l'orologio).
* **La versione dell'unità che pilota la 1322A nella 5.1.6 è quella del 2013**: nella storia di
  `dd1320` dopo il 05.12.13 c'è una sola modifica, del 03.01.20 (V5.5.3, `MDIForm`:742);
  `dd1320_old` è identico a `dd1320` tranne quella modifica, la dimensione del buffer dei
  messaggi d'errore e il tipo dei caratteri. L'eseguibile della 5.2.7 (2017) conferma: contiene
  "Unable to open Digidata 132x!" ma non "Unable to find Digidata 132x!", il messaggio aggiunto
  nel 2020.

Livelli di certezza usati sotto per la 5.1.6: **certa** = confermata dai file di prova o
dall'eseguibile della 5.2.7; **alta** = codice uguale nel 2013 e nel 2024 senza modifiche
annotate nel mezzo (o modifiche annotate prima del 2016); **media** = solo il codice 2024 e
nessuna annotazione contraria.

## A. Come WinWCP usa il Digidata 1322A, confrontato con `Digidata1322Device`

### A.1 Sequenza delle chiamate

| passo | WinWCP (5.1.6) | denoising_live | esito |
|---|---|---|---|
| DLL | carica `Axoutils32.DLL` e poi `AxDD132x.DLL` **dalla cartella di `winwcp.exe`** (`dd1320`:495-505, dal 18.9.03); risolve con `GetProcAddress` 25 funzioni, segnalando quelle mancanti (`dd1320`:508-561). Certezza **certa**: la 5.2.7 contiene le stringhe `AxDD132x.DLL`, `Axoutils32.DLL`, "AXDD132X.DLL library not found" e il pacchetto installa `AxDD132x.dll` **1.0.0.38** (md5 `00a26060…bab9`, identica a quella della 5.8.1) accanto a `winwcp.exe` | ordine: `percorso_dll` → cartella del programma → cartelle di WinWCP → pCLAMP/AxoScope → system32 → copie della chiavetta; `AxoUtils32.dll` precaricata dalla stessa cartella; `LoadLibraryEx` con `LOAD_WITH_ALTERED_SEARCH_PATH` | **già giusto**; **corretto** un dettaglio: si cercano anche `C:\WinWCP*` (per esempio `C:\WinWCPXE`), non solo `C:\WinWCP` (`digidata.py`, `test_cartelle_winwcp_cercate`) |
| ricerca | `DeviceInfo.Length := SizeOf`, `DD132X_FindDevices(DeviceInfo, 1, Err)`, errore se `Err<>0` (`dd1320`:600-608) | uguale, in più controlla che il numero trovato sia ≥ 1 | già giusto |
| apertura | `DD132X_OpenDevice(Adaptor, Target)` ripetuta una seconda volta, subito, se fallisce ("dopo l'accensione la prima volta non va", `dd1320`:612-622) | due tentativi con 0,5 s di pausa | già giusto (la pausa non toglie nulla) |
| calibrazione | `DD132X_GetCalibrationData` (non `Calibrate`, dal 01.09.07; `dd1320`:628-631) | uguale | già giusto |
| uscite | `NumOutChannels = NumberOfDACs + 1`; valore di riposo dei DAC = `-anDACOffset[ch]`, digitali 0 (`dd1320`:634-637) | uguale con `uscite_analogiche = come_winwcp` (predefinito) | già giusto |
| avvio | se `IsAcquiring` → `StopAcquisition` (`dd1320`:682-685); `Protocol.Length := SizeOf`; `SetProtocol`; `StartAcquisition` (`dd1320`:797-803) | uguale | già giusto |
| lettura | `DD132X_GetADCSamples` a ogni tick del timer della finestra (`SESLabIO`:2941) | thread di acquisizione ogni 50 ms | già giusto (vedi A.3) |
| arresto | `IsAcquiring` → `StopAcquisition` (`dd1320`:821-842) | uguale | già giusto |
| chiusura | `StopAcquisition`, `CloseDevice`, poi `FreeLibrary` delle due DLL (`dd1320`:1173-1210) | `StopAcquisition` e `CloseDevice`; la DLL resta caricata fino all'uscita | già giusto: riaprire usa la stessa DLL già caricata; il sistema la libera alla chiusura del processo |

### A.2 Campi del protocollo

| campo | WinWCP | denoising_live | esito |
|---|---|---|---|
| `dSampleInterval` | `Round(dt·10⁶ / NumADCChannels)` µs (`dd1320`:693), con `dt` già arrotondato al µs (`dd1320`:915-930); limiti 4 µs - 100 s (`dd1320`:475-476) | `round(10⁶/1000)` = 1000 µs, 1 canale | già giusto |
| `eTriggering` | `StartImmediately` salvo trigger esterno (`dd1320`:696-697) | `StartImmediately` | già giusto |
| `eAIDataBits` | `DD132X_Bit0Tag` "così il valore vuoto non può comparire nei dati" (`dd1320`:699-702) | uguale | già giusto |
| canali | `uAIChannels = n`, `anAIChannels[ch] = ADCChannelInputMap[ch]`: il canale WinWCP *ch* può venire da un **ingresso fisico qualunque** (`dd1320`:705-706, mappatura dal 06.11.13, quindi nella 5.1.6: certezza alta; la 5.2.7 contiene `INPUTNUMBER`) | un canale, `canale_ingresso` | già giusto; ora l'ingresso si **propone dalle impostazioni di WinWCP** (B) |
| range ADC | solo ±10 V (`dd1320`:458-459; guida p. 21 "fixed input and output voltage range of 10V"); `ADCMinValue = -32678`, `ADCMaxValue = 32677` (`dd1320`:463-464): da qui `ADCMAX=32677` nei file | `range_v = 10`, `ADCMAX=32677` | già giusto (certa: file di prova) |
| buffer | sotto-buffer di `600 × canali in × canali out` campioni (`dd1320`:711); buffer di `(1 000 000 div sotto-buffer) × sotto-buffer` (`dd1320`:46, 714; da 65 536 a 1 048 576 il 18.11.11, V4.4.1, `MDIForm`:491); `uAIBuffers = min(…, 1667)` (`dd1320`:724); anello `pPrev/pNext` (`dd1320`:737-744); buffer dei flag della stessa dimensione | 1 × 3 × 600 = 1800, 555 sotto-buffer, 999 000 campioni, flag, anello | già giusto |
| uscite | stessi numeri di sotto-buffer; `anAOChannels = 0 … n-2` + `DD132X_PROTOCOL_DIGITALOUTPUT` (`dd1320`:774-776); riempite con i valori di riposo (`dd1320`:1273-1300) | uguale | già giusto |
| `uTerminalCount`, `dwFlags` | 0 (`dd1320`:778, 780) | 0 | già giusto |
| **`uChunksPerSecond`** | **0**: nel record Delphi il campo non esiste, dopo `uTerminalCount` c'è `Unused: array[1..264]` (`dd1320`:227, `dd1320_old`:225) e il record è una variabile globale, quindi a zero. L'header Axon lo dichiara e suggerisce 20 (`AxDD132x.h`:117, 124: valore del costruttore C++, che il Delphi non chiama) | era **20** | **corretto**: ora 0 come WinWCP, configurabile (`[digidata] chunks_per_second`). Test `test_chunks_per_second_come_winwcp` (fallisce sul codice della fase 4: 20 ≠ 0). Certezza per la 5.1.6: alta (record uguale nel 2013). Che il driver acquisisca con 0 lo dimostra WinWCP tutti i giorni: resta comunque nel passo 10 della diagnostica |
| impulso di uscita (`eOutputPulseType`…) | zero (stesso `Unused`) | `NoOutputPulse` = 0, resto 0 | già giusto |

La DLL finta (`dlive/devices/dd132x_finto.py`) ora registra `uChunksPerSecond` ricevuto e accetta
0 come il driver vero.

### A.3 Lettura dei dati

* **Campioni nuovi**: WinWCP parte da `AIPointer + canali - 1` e avanza finché il campione è
  diverso da `EmptyFlag` (`dd1320`:856-866); copia e rimette `EmptyFlag` (`dd1320`:868-876).
  `EmptyFlag = 32767` (`dd1320`:1319; `SESLabIO`:986). **Già giusto**: stesso metodo.
* **Posizione di acquisizione e overrun**: WinWCP carica `DD132X_GetAcquisitionPosition` ma non
  la usa e **non si accorge degli overrun**: se il PC non legge per più di ~16 minuti il buffer
  circolare viene riscritto in silenzio. Il programma usa la posizione per contare e segnalare i
  campioni persi (e la ignora se incoerente). **Già giusto** (in più rispetto a WinWCP).
* **Bit TAG e valore 32767**: con `Bit0Tag` il bit 0 vale 0 se l'ingresso TAG non è collegato,
  quindi 32767 (dispari) non è un dato possibile. **Già giusto**; il passo 10 della diagnostica
  conta comunque i campioni dispari e quelli uguali a 32767 (**da verificare in laboratorio**:
  devono essere 0).
* **Più canali e intervallo > 10 ms**: la guida (p. 22) segnala che con più canali e intervallo
  > 10 ms i campioni si mescolano tra i canali (anche in AxoScope). Il programma usa 1 canale a
  1 ms: **già giusto**.

### A.4 Calibrazione

* WinWCP legge `ADCGainRatio` e `ADCOffset` (`dd1320`:239-240) ma **non li usa**: l'unica
  correzione applicata è l'offset dei DAC sulle uscite. Il programma fa lo stesso (li scrive nel
  JSON). **Già giusto**.
* Conversione in unità: nel codice di WinWCP `scala = |range del record| / (YG · (ADCMAX + 1))`
  (`WCPFile`:2764, 3233), nella **guida** `y = Vmax / (ADCmax · YG) · y_adc` (p. 165) e così in
  `neo` e nel programma. Differenza: 1/32 678 = **0,003 %** (meno di un conteggio a fondo scala).
  **Motivato, non cambiato**: i file salvano i conteggi della scheda (WinWCP applica la propria
  scala quando li apre, quindi sui file non cambia nulla) e il filtrato torna in conteggi con la
  stessa scala usata in ingresso; cambia solo il valore in mV mostrato dal vivo, di 3 µV su
  100 mV. Nota: il fondo scala vero della 1322A è ±32 768 conteggi = ±10 V, quindi sia WinWCP
  sia il programma mostrano mV più alti dello 0,27 % del vero, **in modo identico**.
* Il **guadagno** del canale (campo GAIN della tabella dei canali) WinWCP lo mette nel range del
  record (`range = 10 V / GAIN`, `REC`:1500-1502), non in `YG` (`REC`:1071). Il programma usa
  `yg = V/unità × guadagno` con range 10 V: in WinWCP i valori sono identici (B).

### A.5 Errori

* WinWCP mostra il testo di `DD132X_GetLastErrorText` (`dd1320`:1212-1240) e continua. Nella
  5.1.6, se la scheda non c'è, dopo il messaggio può seguire un *access violation* (corretto solo
  nella V5.5.3, `MDIForm`:742). Il programma solleva un errore con il testo della DLL, i codici
  dell'header e i consigli, e si può riprovare (test E7). **Già giusto**.
* **WinASPI**: WinWCP non lo controlla; se manca, la DLL risponde con l'errore 1
  `ASPINOTFOUND` (`AxDD132x.h`). L'installatore di WinWCP (5.2.7) **non contiene WinASPI**: lo
  installano AxoScope/pCLAMP (guida p. 21, passi 3-5: "Install the AxoScope software supplied with
  the Digidata 1320"). Il programma controlla `wnaspi32.dll`, `aspi32.sys` e
  `GetASPI32SupportInfo` (diagnostica passo 3, `rilevamento.controlla_dll`) e la chiavetta porta
  `aspiinst.exe`. **Già giusto**.

## B. Impostazioni di WinWCP 5.1.6

WinWCP **non usa il registro** di Windows (nessun `TRegistry` nei sorgenti): tutto è in file di
testo. Certezza per la 5.1.6: **alta** (spostamenti annotati nel 2013; la 5.2.7 contiene le
stringhe `winwcp.ini`, `\SESLABIO\`, `lab interface settings.xml`, `INPUTNUMBER`, `VOLTSPERUNIT`,
`RECMODE=`, `FILEVPR=`).

| file | dove (XP in italiano) | fonte | formato | chiavi utili |
|---|---|---|---|---|
| `winwcp.ini` | `<Documenti condivisi>\WinWCP\` = `C:\Documents and Settings\All Users\Documenti\WinWCP\` (prima della V4.6.3, 26/08/13: cartella del programma) | `WCPFile`:1996-2002; `MDIForm`:548-553 | righe `CHIAVE=valore`, ANSI, CR LF, virgola o punto secondo il PC | `FILE` ultimo file, `RF0`-`RF3` recenti, `DDIR` cartella dati, `NC`, `NSAMP`, `RECDUR`, `DT` intervallo (s), `RECMODE` (0 protocollo, 1 free run, 2 trigger esterno, 3 eventi), `FILEVPR` protocollo, `VPDIR`, `LABINT` (`WCPFile`:1220-1410) |
| `lab interface settings.xml` | `<Documenti condivisi>\SESLABIO\` (dal 20.08.13) | `SESLabIO`:113, 1095-1101, 5385-5480 (scrittura), 5514-5600 (lettura) | XML su una riga, `LABINTERFACESETTINGS` | `INTERFACETYPE` (6 = Digidata 132X, `SESLabIO`:183), `ADCNUMCHANNELS`, `ADCVOLTAGERANGE`; per canale `ADCCHANNEL`: `NAME`, `UNITS`, `VOLTSPERUNIT` (= `YG`), `GAIN`, `ZEROLEVEL`, `CHANNELOFFSET`, `INPUTNUMBER` (ingresso fisico) |
| `amplifier settings.xml` | `<Documenti condivisi>\WinWCP\` | `AmpModule.pas`:1465-1467 | XML | amplificatori (non usati dal laboratorio) |
| log giornalieri `gg-mm-aaaa.log` | stessa cartella di `winwcp.ini` (la guida p. 78 dice ancora "program directory") | `WCPFile`:2795 | testo | "Recording Started", "Stopped (N records)", **"Stimulus Protocol: file"** (`REC`:1701, 1143, 1826) |

Cosa fa ora il programma (**corretto**, modulo nuovo `dlive/winwcp_impostazioni.py`, **solo
lettura**: i file si aprono in `rb` e un test verifica che contenuto e data restino uguali):

* trova `<Documenti condivisi>` con `SHGetFolderPathW(CSIDL_COMMON_DOCUMENTS)`, con il registro
  (`Shell Folders\Common Documents`) e con `%ALLUSERSPROFILE%\Documenti|Documents` come ripiego;
  guarda anche le cartelle di installazione di WinWCP (versioni vecchie);
* legge e mostra interfaccia, canali (nome, unità, V/unità, guadagno, ingresso), DT, modo di
  registrazione, protocollo, cartella dati e file recenti;
* **propone** come valori iniziali: `canale_ingresso` = `INPUTNUMBER` del canale registrato (se
  WinWCP registra un solo canale, è quello; se più, quello già indicato in `config.ini`, altrimenti
  avvisa e non sceglie), `yg` = V/unità × guadagno, `unita`, `nome_canale`, `yz` = zero,
  `frequenza_salvataggio_hz` = 1/DT se divide 1000 Hz; avvisa se l'interfaccia selezionata non è
  il Digidata 132X, se il range non è 10 V, se `RECMODE` è "Stimulus protocol" o trigger esterno;
* in modalità Digidata, all'avvio, secondo `[digidata] impostazioni_winwcp`: `chiedi`
  (predefinito: mostra i valori e chiede; la risposta diventa `usa` o `ignora`), `usa`, `ignora`.
  `config.ini` resta il ripiego;
* la diagnostica le mostra (passo 1b) e, se WinWCP acquisisce da un altro ingresso, usa quello;
* test con file costruiti come li scrivono `TStringList.SaveToFile` e `SaveToXMLFile1`
  (`tests/test_fase5.py`, 11 test), e con il file XML vero incluso nei sorgenti 5.8.1 (interfaccia
  NI, viene segnalata come "non Digidata").

**Da verificare in laboratorio**: la guida 5.2.4 (p. 40) dice che la mappatura canale →
ingresso "is currently only available with National Instruments interface cards", mentre il
codice la applica anche alla 1322A dal 2013 (`dd1320`:706). Se nella 5.1.6 la mappatura non
valesse, il canale *n* di WinWCP sarebbe l'ingresso *n* (guida p. 21-22, p. 61: "Channels are
always acquired in sequence from Ch.0 upwards"). Il passo 9 della diagnostica legge tutti i 16
ingressi e mostra dove c'è il segnale.

## C. Stimoli

Come li genera WinWCP:

* modo **Stimulus protocol** (`RECMODE=0`, `REC`:146): WinWCP genera sul DAC0-3 e sulle uscite
  digitali forme d'onda definite in protocolli `.xml` nella cartella `VPDIR`
  (`<Documenti condivisi>\WinWCP\Vprot\`); i vecchi `.vpr` vengono convertiti in `.xml`
  (`StimModule`:1882-1886; XML dal 15/06/11, quindi nella 5.1.6); guida p. 60-62;
* modo **Ext. triggered** (`RECMODE=2`): lo stimolo lo dà uno stimolatore esterno che fa partire
  ogni sweep (guida p. 58).

Tracce che lasciano:

| dove | traccia | fonte |
|---|---|---|
| intestazione del `.wcp` | nessuna | `WCPFile`:816-907 |
| record | tipo `TEST`/`LEAK`; in modo protocollo il **gruppo** è il numero del gruppo del protocollo invece del numero del record | `REC`:1483-1491, 1507-1508 |
| log | "Stimulus Protocol: *file*" a ogni avvio | `REC`:1826 |
| `winwcp.ini` | `RECMODE`, `FILEVPR` | `WCPFile`:1296, 1308 |

I 7 file di prova (13 record):

| file | NR | tipo | gruppo = n. record | durata del record | uso | segni di stimolazione |
|---|---|---|---|---|---|---|
| `071210_001.wcp` | 4 | TEST | sì | 3600 s (409 344 × 8,795 ms), fermati a mano a 557-3600 s | 1 canale | no |
| `071210_001.1.wcp` | 1 | TEST | sì | 3600 s, fermato a 387 s | 5 canali | no |
| `071211_001.1.wcp` (e la copia "(1)") | 1 | TEST | sì | 3584 s (448 000 × 8 ms), fermato a 1258 s | 5 canali | no |
| `071222_002.1.wcp`, `071224_003.wcp` | 1 | TEST | sì | 3584 s, fermati a 447 s e 16 s | 1 canale | no |
| `081024_001.wcp` | 1 (+1 nascosto) | TEST | sì | 3584 s | 5 canali | no |

Le escursioni grandi (> 500 mV) sono 0-8 per record, a intervalli irregolari (da 0,26 s a 396 s):
non c'è un ritmo da stimolatore. Nessun canale contiene una forma d'onda di comando.

**Conclusione: registrati SENZA stimolazione da WinWCP (con alta probabilità); non dimostrabile
al 100 % dai soli file**: un protocollo con un unico sweep lungo a 0 V lascerebbe file
identici. La prova definitiva sono `RECMODE`/`FILEVPR` in `winwcp.ini` e le righe "Stimulus
Protocol" nei log: le raccoglie il comando (§ 2) e le legge `strumenti/leggi_info_lab.py`, che
scrive in evidenza se il laboratorio usa la stimolazione. Il programma ora avvisa all'avvio se
WinWCP è impostato in modo protocollo o trigger esterno. **La stimolazione non è implementata.**

## D. Formato `.wcp` di WinWCP 5.1.6

* **Chiavi dell'intestazione**: quelle dei file di prova (certa), nell'ordine di `SaveHeader`
  (`WCPFile`:816-907): `VER VERPROG CTIME RTIMESECS RTIME NBH ADCMAX NC NBA NBD AD NR DT NZ`,
  per canale `YO YU YN YG YZ YR`, poi `TXPERC PKPAVG NSVCHAN NSVALIGN NSVTYPR NSVS2P NSVCUR0
  NSVCUR1 ID`. Le chiavi in più della 5.8.1 (`TXLEV`, `TXTOLEV`, `PKMODE`, `QUPERC` dal 2017,
  `LATPERC`, `TRISELO/HI` dal 2019, cursori dal 2022) **non ci sono** nei file della 5.1.6: il
  programma scrive esattamente quelle della 5.1.6. **Già giusto.**
* **ADCMAX** = 32677 (A.2). **Già giusto.**
* **Dimensioni**: intestazione e blocco di analisi `((NC-1) div 8 + 1) × 1024` byte
  (`WCPFile`:2771-2781; guida p. 163-164); dati in settori interi da 512 byte (`NBD`). **Già
  giusto.**
* **RTIMESECS**: "Time of start of recording in seconds (relative to last system boot)" (guida
  p. 163; `WCPFile`:254). Nei file di prova non coincide con l'ora di `RTIME` (996 s per una
  registrazione delle 2:27, 476 s per una delle 21:56): sono secondi dall'avvio. La 5.8.1 lo
  calcola invece dall'ora del giorno, con un errore (`REC`:817: ore × 60 invece di × 3600).
  WinWCP lo usa solo se > 0 (`Replay.pas`:421) e come base dell'ora del giorno nei fit. Il
  programma scriveva i secondi dalla mezzanotte: **corretto**, ora i secondi dall'avvio di
  Windows (`GetTickCount`, presente in XP), mai 0 (`test_rtimesecs_*`).
* **Separatore decimale**: WinWCP scrive i numeri con quello del PC e li rilegge accettando
  **sia la virgola sia il punto** (`ExtractFloat`, `WCPFile`:3950; uguale nel `master` 2013,
  `Shared.pas`:250: certezza alta). Ora `separatore_decimale = auto` usa quello di Windows, come
  WinWCP (**corretto**, prima era fisso a virgola; nessun rischio per l'apertura).
* **Limiti**: campioni per record (tutti i canali) ≤ `ADCBufferLimit` = `MaxADCSamples` =
  16 777 216 (`SESLabIO`:161, 1196; da 1048576×8 a ×16 il 26-6-14, quindi nella 5.1.6); la guida
  dice "256-8388608 samples per recording sweep, depending upon laboratory interface" (p. 5). I
  file di prova arrivano a 2 240 000 per record (certa: la 5.1.6 li ha scritti e li apre). Numero
  di record: "2 billion records per data file" (guida p. 5), ma gli spostamenti nel file sono
  interi a 32 bit (`FileSeek`, `WCPFile`:2390): **file ≤ 2 GB**. Lettura: un record intero alla
  volta in un buffer di `MaxADCSamples` (`GetRecord`, `WCPFile`:2429-2460). **I nostri record da
  59,392 s** (59 392 campioni grezzi, 7424 filtrati) sono 38 volte sotto i file di prova e 280
  volte sotto il limite; il grezzo occupa 120 832 byte per record, quindi il limite dei 2 GB
  arriva dopo ~17 700 record ≈ 290 ore. Il programma rifiuta record oltre 1 000 000 di
  campioni. **Già giusto.**
* **NR=0** (file interrotto prima di aggiornare l'intestazione, come `071224_003.wcp`): WinWCP
  ricalcola il numero dalla dimensione e avvisa (`WCPFile`:1066-1080). Il programma tiene `NR`
  sempre aggiornato (§ 6.3 del README). **Già giusto.**
* **Marker**: il modo nativo di WinWCP è il **campo identificativo del record, 16 caratteri**
  (`PutRecordHeaderOnly`, `WCPFile`:2408-2411, `MaxRecordIdentChars = 16`, `WCPFile`:753): dalla
  V5.1.1 il testo del riquadro Marker finisce lì (`REC`:1523); la guida lo chiama "Marker 16 x
  ASCII bytes, user entered marker" (p. 164). Il programma scrive già `M:testo` in quel campo per
  il record in cui cade il marker, e tutti i marker (ora, istante, testo intero) nel JSON. **Già
  giusto.** Non ci sono altri modi nativi: la riga `ID=` è una sola per file (la usiamo per dire
  chi ha scritto il file) e il log è di WinWCP.
* **Canali dei file di prova**:

  | file | canali (nome, unità, YG) | segnale | gli altri |
  |---|---|---|---|
  | `071210_001.wcp` | Ch.0 mV 0,001 | Ch.0 | — |
  | `071210_001.1.wcp` | Ch.0-Ch.4 mV 0,001 | **Ch.4** (σ 22 mV) | Ch.0-3: ±2 conteggi, ingressi scollegati |
  | `071211_001.1.wcp` | Ch.0-Ch.4 mV 0,001 | **Ch.0** (con saturazioni) | Ch.1-4: < 0,5 mV di rumore |
  | `071222_002.1.wcp`, `071224_003.wcp` | Vm mV 0,001 | Vm (Ch.0) | — |
  | `081024_001.wcp` | Im nA 0,01 (zero −16 250), Vm mV 0,01, Ch.2-4 mV 0,001 | **Im (Ch.0)** | Vm piatto, Ch.2-4 scollegati |

  "Vm" e "Im" con 0,01 sono i nomi e i fattori che WinWCP propone per un amplificatore patch
  clamp: nel 2008 la tabella dei canali era impostata così; il segnale è sempre su un solo
  canale, ma **non sempre lo stesso** (Ch.0 o Ch.4). Con un solo canale WinWCP acquisisce Ch.0
  = AI0 salvo mappatura (B). Quale ingresso porta oggi il segnale (il documento di progetto dice
  AI2) è **da verificare**: lo dicono `lab interface settings.xml` (raccolto dal comando) e il
  passo 9 della diagnostica.

## E. Filtro LPF-8

| caratteristica | manuale | conseguenza |
|---|---|---|
| tipo e ordine | Bessel a 8 poli, "no overshoot or ringing" (p. 1, schema p. 4) | modello del programma: poli di Bessel di ordine 8 (`dlive/lpf8.py`) |
| attenuazione | −3 dB al taglio, −14 dB a 2×, −114 dB a 10×, **massimo 60 dB** (p. 1-2) | il modello dà −13,7 dB e −114 dB, limitato a 60 dB (test) |
| campo | Low 0,1-199,9 Hz a passi di 0,1 Hz; High 10 Hz-19,99 kHz a passi di 10 Hz; 3979 valori (p. 1, 2, 5) | il campo "Taglio LPF-8 (Hz)" accettava qualunque numero > 0: **corretto**, ora accetta solo i valori impostabili e **Bypass** (scritto "Bypass" o 0), e rifiuta gli altri spiegando i passi |
| guadagno | 1, 2, 5, 10, 20, 50, 100, 200, prima del filtro (p. 3, 6) | avviso se `lpf8.guadagno` non è uno di questi o se è ≠ 1 e `yg` è ancora 0,001 |
| bypass | sul selettore del campo; guadagno e offset restano (p. 5) | ammesso; avviso di aliasing |
| uscita | ±10 V, LED esterni = saturazione (p. 2, 5); 50 Ω | uguale al range dell'ADC (±10 V): **già giusto**; la saturazione dell'ADC è già rilevata e trattata |

**Aliasing a 1000 Hz** (metà = 500 Hz), attenuazione dell'LPF-8 a 500 Hz secondo il modello:
taglio ≤ 110 Hz → 60 dB (il massimo); 150 Hz → 40 dB; 199,9 Hz → 23 dB; 500 Hz → 3 dB; Bypass
→ 0 dB. Con il taglio del laboratorio (15 Hz) non c'è aliasing. Il programma ora **avvisa** (finestra
all'avvio e quando si applica il taglio, `config.ini`, diagnostica): "possibile aliasing" tra 20 e
40 dB (taglio tra ~150 e ~210 Hz), "rischio di aliasing" sotto 20 dB, e in Bypass. Per il
filtrato (≤ 10 Hz) gli alias verrebbero da 1000 ± 10 Hz, dove l'LPF-8 attenua ≥ 40 dB fino a un
taglio di ~300 Hz. Test `test_lpf8_*` (7 test).

## F. Guida di WinWCP (V5.2.4)

| pagina | cosa dice | conseguenza |
|---|---|---|
| 21 | per la 1320/1322 si installa prima AxoScope (WinASPI, driver SCSI), poi in WinWCP *Setup > Laboratory Interface > Axon Instruments (Digidata 132X)*; range fisso 10 V; 4 uscite digitali | già giusto (diagnostica passi 3-5) |
| 21-22 | Ch. *n* ↔ Analog In *n*, AO0/AO1, Trigger In Start per trigger esterno | da verificare l'ingresso del segnale (D) |
| 22 | con più canali e intervallo > 10 ms i campioni si mescolano | già giusto (1 canale, 1 ms) |
| 40 | V/Units = volt all'ADC per unità (es. 0,01 per 10 mV/mV); mappatura canali solo NI (in contrasto col codice) | `yg` = V/unità; da verificare la mappatura (B) |
| 55-60 | quattro modi: free run, trigger esterno, eventi, protocollo (stimolazione dal PC) | C |
| 61 | nel free run i canali partono sempre da Ch.0; filtrare sotto metà del campionamento | D, E |
| 78 | marker brevi nel record; log giornaliero dd-mm-yy.log | D; il comando cerca i log accanto a `winwcp.ini` |
| 163-165 | formato del file, `RTIMESECS` dall'avvio, formula della scala | D, A.4 |

Niente nella guida parla di registrazione continua oltre lo sweep: WinWCP registra sempre per
sweep (record) di durata fissa, come fa il programma con record da ~60 s.

## G. Rilevamento sul posto

Modulo nuovo `dlive/rilevamento.py`, usato da `installa.bat` (passo 8, scrive
`C:\denoising_live\rilevamento_pc.txt` e `installa_log.txt` sulla chiavetta), dalla diagnostica
(passo 1b) e lanciabile a mano (`python -m dlive.rilevamento`). Ogni controllo dà OK / AVVISO /
ERRORE con un messaggio chiaro; un errore imprevisto in un controllo non ferma gli altri. Le
informazioni arrivano da un oggetto "ambiente": i test usano un ambiente finto
(`tests/test_fase5.py`, 21 casi).

| controllo | come | dove anche in batch | test |
|---|---|---|---|
| Windows, Service Pack, 32/64 bit | `getwindowsversion`, `ProductName`, `IsWow64Process`; ERRORE sotto XP SP2 (`msvcr100.dll` di Python 3.4 usa `EncodePointer`, da XP SP2) | `installa.bat` passo 0: `ver`, `CSDVersion`, `PROCESSOR_ARCHITEW6432` | SP1, senza SP, 64 bit, non Windows |
| diritti di amministratore | `IsUserAnAdmin` | `installa.bat`: `fsutil fsinfo drives` (richiede l'amministratore, non modifica nulla) | non amministratore |
| Python e `msvcr100.dll` | Python in uso, `HKLM/HKCU\SOFTWARE\Python\PythonCore\*\InstallPath`, `C:\Python*`, `msvcr100.dll` con versione | `installa.bat`: se `C:\Python34` non c'è ma è registrato un Python 3.4 altrove, **usa quello** invece di reinstallare | Python 3.12 a 64 bit |
| schermo e caratteri | `GetSystemMetrics`, `GetDeviceCaps(LOGPIXELSX)`: scala dell'interfaccia calcolata come `dlive/scala.py` (che adatta già i caratteri della finestra) | — | 800×600, 120 DPI |
| separatore decimale | `GetLocaleInfoW(LOCALE_SDECIMAL)`; ora usato anche per i `.wcp` (`auto`) | — | punto, non leggibile |
| spazio su disco | cartella dati: ore di registrazione possibili, AVVISO se non bastano per **3 ore** (8,1 MB/ora + minimo di `config.ini`); installazione: ERRORE sotto 150 MB | `installa.bat`: `dir C:\` | 210 MB, 100 MB |
| DLL Axon e WinASPI | tutte le `AxDD132x.dll` candidate con dimensione, versione, md5 e confronto con le copie estratte; `wnaspi32.dll`, `aspi32.sys` | — | DLL di WinWCP, sconosciuta, della chiavetta, WinASPI assente |
| impostazioni di WinWCP | B | — | proposta del canale |
| WinWCP in esecuzione | Toolhelp32 (`winwcp.exe`, `winedr.exe`, `axoscope.exe`, `clampex.exe`) | — | `winwcp.exe` aperto |
| orologio | AVVISO se l'anno è prima del 2016 (§ 0) | — | 2008 |

## Riepilogo

**Differenze rispetto a WinWCP trovate e corrette**: `uChunksPerSecond` 20 → 0; `RTIMESECS`
dalla mezzanotte → dall'avvio di Windows; separatore decimale fisso → quello di Windows; ricerca
della DLL anche in `C:\WinWCP*`; canale, calibrazione e campionamento ora proposti dalle
impostazioni di WinWCP; campo LPF-8 limitato ai valori veri, con Bypass e avvisi di aliasing.
**Motivate e lasciate**: scala ADCMAX invece di ADCMAX+1 (0,003 %, come guida e neo; nessun
effetto sui file); pausa di 0,5 s tra i due `OpenDevice`; DLL non scaricata alla chiusura;
rilevamento degli overrun (in più).

**Da verificare in laboratorio** (la diagnostica lo mostra): che con `uChunksPerSecond = 0`
arrivino 10 000 campioni in 10 s (passo 10, è il valore di WinWCP); campioni dispari e 32767
uguali a 0; quale ingresso porta il segnale e se la mappatura `INPUTNUMBER` vale per la 1322A
nella 5.1.6 (passi 1b e 9); apertura dei file in WinWCP 5.1.6 (con `RTIMESECS` ora come i suoi).

**Da decidere in laboratorio**: se si usa la stimolazione di WinWCP (lo dicono i log raccolti
dal comando: se sì cambia il progetto); se correggere l'orologio del PC; quale ingresso e quale
calibrazione sono quelli di oggi (proposti da WinWCP all'avvio); le impostazioni attuali
dell'LPF-8 (taglio, guadagno, Bypass); se le escursioni di ~5 V sono artefatti (README § 7.8).
