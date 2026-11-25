# Guida rapida: prima prova di denoising_live in laboratorio

Il programma non è mai stato provato con il Digidata vero: questa è la prima prova.
Fai i passi in ordine; dopo ogni passo controlla la scritta indicata.
Alla fine di ogni passo la finestra nera resta aperta: leggi la scritta, poi chiudila.

## A casa, sul PC con internet

1. Apri github.com/colasantoemanuele-cloud/denoising-live, premi **Code** e poi
   **Download ZIP**. Clic destro sul file scaricato, **Estrai tutto**.
2. Nella cartella estratta fai doppio clic su **prepara.bat**.
   Se Windows dice "Windows ha protetto il PC": **Ulteriori informazioni**, **Esegui comunque**.
   Alla fine deve dire `TUTTO A POSTO: copia questa cartella sulla chiavetta`.
3. Copia quella cartella sulla chiavetta.

## In laboratorio, con l'ok del professore

4. Sul PC c'è l'icona di WinWCP (desktop o menu Start)? Se no: fermati e scrivimi.
5. A PC spento accendi prima il Digidata, poi il PC. Tieni WinWCP chiuso.
6. Copia dalla chiavetta nel disco `C:\` la cartella che contiene `installa.bat`: deve
   diventare `C:\denoising-live-main`, con `installa.bat` direttamente dentro.
7. Lì fai doppio clic su **installa.bat** (2-5 minuti).
   Deve finire con `INSTALLAZIONE COMPLETATA`.
8. Doppio clic sull'icona **Diagnostica Digidata** (circa 30 secondi).
   Se chiede `Vuoi usarlo? (S/N)`, scrivi `S` e premi Invio.
   Alla fine deve dire `ESITO: nessun errore`.
9. Doppio clic sull'icona **denoising_live (Digidata)**, poi premi **Avvia anteprima**:
   nel grafico si muove il segnale.
10. Premi **Avvia registrazione**. Dopo 2 minuti scrivi `prova` nella casella
    **Marker** e premi Invio. A 4 minuti premi **Ferma** e conferma. Fai una foto
    dello schermo, poi chiudi il programma.
11. Apri WinWCP e, dal menu File, apri i due file in `C:\denoising_live\dati_registrati`
    (`..._raw.wcp` e `..._filt.wcp`). Fai una foto di ciascuno, poi chiudi WinWCP.
12. Doppio clic sull'icona **Raccogli risultati**. Deve dire
    `Copia sulla chiavetta la cartella risultati_prova_...`: copia quella cartella
    dal Desktop sulla chiavetta e mandamela con le foto.

## Se qualcosa va storto

Fai una foto dello schermo (si deve leggere la riga `denoising_live versione ...`),
doppio clic su **Raccogli risultati** (o
`raccogli_risultati.bat` nella cartella), manda la cartella e le foto.
Per i dettagli: GUIDA_COMPLETA.
