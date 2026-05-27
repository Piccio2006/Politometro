# Dataset e correlazioni automatiche

Politometro ora ha una base semplice per costruire un dataset utile senza trasformarlo subito in una macchina pesante.

## Dove stanno i dati

Versione server locale:

```text
data/research_samples.jsonl
data/research_feedback.jsonl
data/support_contacts.jsonl
data/politometro.sqlite3
```

Dashboard:

```text
http://127.0.0.1:7860/admin
```

## Cosa analizza da solo

- stato del dataset: setup, early, beta, validazione, scala;
- distribuzione delle ideologie principali;
- trend giorno per giorno;
- affidabilità interpretativa media;
- correlazioni tra dati facoltativi e assi;
- correlazioni tra dati facoltativi e singole domande;
- differenze forti tra gruppi;
- accuratezza percepita tramite feedback;
- segnali di cautela quando i campioni sono piccoli.

## Export

Dalla dashboard admin puoi scaricare:

- `analytics.json`: sintesi completa;
- `samples.csv`: risposte, risultato, assi e dati facoltativi;
- campi V5: coerenza, affidabilità, nemesi, personaggio storico e risultato più vicino;
- `feedback.csv`: feedback finale;
- `contacts.csv`: richieste supporto/partnership.

## Soglie consigliate

- 0-29 risposte: test tecnico e UX.
- 30-99 risposte: primi segnali, non vendibili come conclusioni.
- 100-299 risposte: pitch e report prudenti.
- 300-999 risposte: analisi più seria su item e assi.
- 1.000+ risposte: percentili, segmenti, ricalibrazione e report più difendibili.

## Cosa puoi vendere

Puoi vendere report aggregati e dashboard, non dati individuali.

Esempi:

- “quali temi dividono di più il campione”;
- “quali assi sono più forti per cluster demografici consensuali”;
- “quali domande funzionano male o sono troppo ambigue”;
- “come cambia il profilo medio nel tempo”.

## Cosa evitare

- vendere liste di persone con opinioni politiche;
- microtargeting politico opaco;
- dichiarare causalità da semplici correlazioni;
- mostrare gruppi con meno di 30 risposte come se fossero affidabili;
- promettere validazione scientifica prima dei campioni reali.
