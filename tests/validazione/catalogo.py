# -*- coding: utf-8 -*-
"""Elenco dei test: livello, cosa controlla (in italiano semplice), soglia.

Le soglie sono quelle fissate nel documento di validazione e NON vanno
cambiate per far passare un test.
"""
from collections import OrderedDict

CRITICO = "CRITICO"
IMPORTANTE = "importante"
INFORMATIVO = "informativo"

GRUPPI = OrderedDict([
    ("A", "Filtro (segnale sintetico a verità nota)"),
    ("B", "Catena completa in simulazione (sorgente → filtro → salvataggio)"),
    ("C", "Dati reali del laboratorio"),
    ("D", "Pilota del Digidata (senza la scheda vera)"),
    ("E", "Compatibilità, interfaccia, prestazioni"),
    ("M", "Prova dei test (mutazioni)"),
])

# id: (livello, cosa controlla, soglia)
TEST = OrderedDict([
    ("A1", (CRITICO, "Un segnale lento (0,2 Hz, 100 mV) passa senza cambiare ampiezza.",
            "uscita tra 99 e 101 mV")),
    ("A2", (CRITICO, "Dopo un gradino il filtrato si assesta esattamente sul livello vero.",
            "|uscita − verità| < 0,5 mV da 2 s dopo ogni gradino")),
    ("A3", (CRITICO, "Sui gradini il filtrato non 'sfora' oltre il livello (sovraelongazione).",
            "< 5 % a 2, 5 e 10 Hz")),
    ("A4", (CRITICO, "Il filtrato segue i gradini con poco ritardo.",
            "ritardo al 50 % < 0,3 s a 2, 5 e 10 Hz")),
    ("A5", (CRITICO, "Le frequenze di rumore (25, 37,4, 50 Hz) vengono abbattute.",
            "≥ 35 dB a 25 Hz, ≥ 40 dB a 37,4 e 50 Hz")),
    ("A6", (CRITICO, "Il notch toglie i 50 Hz senza toccare il segnale a 5 Hz.",
            "50 Hz attenuato ≥ 30 dB; 5 Hz alterato < 1 %")),
    ("A7", (CRITICO, "Sul segnale sintetico con tutto il rumore, nei tratti calmi resta poco rumore.",
            "RMS < 2 mV nei tratti quieti")),
    ("A8", (CRITICO, "I picchi di saturazione non lasciano tracce ('code') nel filtrato.",
            "differenza ≤ 2 mV nei 5 s dopo ogni picco")),
    ("A9", (CRITICO, "Filtrare a pezzi dà lo stesso risultato che filtrare tutto insieme.",
            "differenza massima < 1e-6 mV")),
    ("A10", (CRITICO, "Il filtro coincide con quello di riferimento di scipy (24 combinazioni).",
             "differenza massima < 1e-4 mV")),
    ("A11", (CRITICO, "Anche il filtro più 'estremo' (Bessel 8° ordine a 1 Hz) è stabile.",
             "uscite finite; gradino entro 0,1 % in 5 s")),
    ("A12", (CRITICO, "Cambiare il filtro durante l'acquisizione non crea salti né buchi.",
             "salto < 0,5 mV, nessun NaN; livello vero entro 3 s")),
    ("A13", (IMPORTANTE, "Il percorso senza numpy (per PC vecchi) dà gli stessi numeri.",
             "differenza massima < 1e-6 mV")),
    ("B1", (CRITICO, "Il file grezzo salvato è identico, campione per campione, a quanto acquisito.",
            "0 differenze")),
    ("B2", (CRITICO, "Il file filtrato coincide con un filtro di riferimento indipendente.",
            "differenza ≤ 1 conteggio ADC (≈ 0,31 mV)")),
    ("B3", (CRITICO, "Nessun campione perso e file della durata giusta.",
            "Perse = 0; durata ± 1 campione")),
    ("B4", (CRITICO, "Un disturbo a 100 Hz non ricompare 'travestito' a bassa frequenza nel filtrato (aliasing).",
            "ampiezza < 0,5 mV")),
    ("B5", (CRITICO, "Un marker inserito durante la registrazione è salvato all'istante giusto.",
            "entro 1 s")),
    ("B6", (CRITICO, "I file si aprono con altri programmi (neo, lettore di riferimento) e hanno il formato di WinWCP 5.1.6.",
            "differenza < 0,001 mV; stesse chiavi; record multipli di 512 byte e < 2 200 000 campioni")),
    ("B7", (CRITICO, "Se il programma viene ucciso di colpo i file restano leggibili e si perde pochissimo.",
            "file leggibili con neo; persi ≤ 2 s")),
    ("B8", (IMPORTANTE, "Una registrazione di 3 ore non consuma memoria e non perde dati.",
            "memoria + < 50 MB; 0 persi; 0 errori")),
    ("B9", (IMPORTANTE, "Se il disco si riempie, l'errore viene mostrato ma l'acquisizione continua.",
            "errore in GUI e log; acquisizione continua; dati già scritti leggibili")),
    ("C1", (CRITICO, "Tutti i file reali del laboratorio si leggono.",
            "7 file senza errori")),
    ("C2", (CRITICO, "Sui dati reali il rumore 25–60 Hz viene ridotto di molto.",
            "riduzione ≥ 30 dB")),
    ("C3", (IMPORTANTE, "Sui dati reali il filtrato ha la stessa forma di un filtro di riferimento 'ideale'.",
            "correlazione ≥ 0,99 e differenza RMS < 5 mV, fuori da ±1 s attorno ai salti > 500 mV "
            "(esclusi < 2 % del tempo; era 1 % fino alla fase 3); correlazione solo se il riferimento varia "
            "di almeno 1 conteggio")),
    ("C3b", (IMPORTANTE, "Dove C3 e C4 non guardano (attorno ai salti > 500 mV) il programma fa esattamente "
                         "quello che dice il README: toglie i picchi e filtra come un filtro ideale.",
             "per finestra RMS < 2 mV dal filtro causale ideale dopo la regola dei picchi del README; "
             "copre il 100 % del tempo escluso da C3/C4")),
    ("C4", (IMPORTANTE, "Sui dati reali il filtrato non contiene valori assurdi.",
            "nessun NaN/inf; estremi entro 10 mV dal riferimento, fuori da ±1 s attorno ai salti > 500 mV "
            "(esclusi < 2 % del tempo)")),
    ("C5", (INFORMATIVO, "Grafici di grezzo, filtrato e riferimento per ogni file reale.",
            "—")),
    ("D1", (IMPORTANTE, "Le strutture dati del driver hanno dimensioni e posizioni identiche all'header Axon.",
            "dimensioni e offset uguali (gcc -m32)")),
    ("D2", (IMPORTANTE, "Contro una scheda finta il driver fa le chiamate giuste e dà messaggi chiari.",
             "sequenza corretta; messaggi chiari; overrun contato")),
    ("D3", (INFORMATIVO, "Elenco di ciò che si può verificare solo con la scheda vera.",
            "—")),
    ("E1", (CRITICO, "Tutti i test A e B passano anche con Python 3.4 + numpy 1.15 (quelli del PC del laboratorio).",
            "tutti PASS (esclusi quelli che richiedono neo)")),
    ("E2", (CRITICO, "Il codice non usa nulla che Python 3.4 non abbia.",
            "vermin --target=3.4- senza errori")),
    ("E3", (CRITICO, "La finestra funziona: avvio, anteprima, cambio filtro, marker, registrazione, chiusura.",
            "0 eccezioni nel log")),
    ("E4", (IMPORTANTE, "Il programma usa poca CPU.",
            "< 5 % del tempo reale con la finestra (impostazioni predefinite, Python di sviluppo)")),
    ("E5", (IMPORTANTE, "Il grafico mostra il segnale con poco ritardo.",
            "< 0,5 s")),
    ("E6", (IMPORTANTE, "Su un PC 5 volte più lento (come quello del laboratorio) 10 minuti di registrazione "
                        "con la finestra non perdono nulla.",
            "0 persi; coda sotto il limite; ritardo del grafico < 1 s; 0 eccezioni; file come B1, B2, B3")),
    ("E7", (CRITICO, "La finestra vera in modalità Digidata (scheda finta) registra correttamente, mostra "
                     "gli errori in modo comprensibile e riparte dopo un errore.",
            "0 eccezioni; file come B1, B2, B3; messaggi senza traceback; riavvio dopo ogni errore")),
    ("M1", (CRITICO, "Guasto finto: frequenza di taglio raddoppiata → i test se ne accorgono.",
            "almeno un test CRITICO FAIL")),
    ("M2", (CRITICO, "Guasto finto: stato del filtro azzerato a ogni blocco → i test se ne accorgono.",
            "almeno un test CRITICO FAIL")),
    ("M3", (CRITICO, "Guasto finto: notch a 60 Hz invece di 50 Hz → i test se ne accorgono.",
            "almeno un test CRITICO FAIL")),
    ("M4", (CRITICO, "Guasto finto: un campione saltato ogni 1000 nel salvataggio → i test se ne accorgono.",
            "almeno un test CRITICO FAIL")),
])


def livello(id_):
    return TEST[id_][0]


def critico(id_):
    return TEST[id_][0] == CRITICO
