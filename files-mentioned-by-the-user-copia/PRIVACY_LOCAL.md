# Politometro Privacy Locale

Questa versione gira localmente nel workspace Codex.

## Cosa succede senza consenso

- Il test funziona normalmente.
- Le risposte non vengono salvate nei file di ricerca.
- Viene calcolato solo il risultato mostrato sullo schermo.

## Cosa succede con consenso

Se l'utente sceglie di contribuire al miglioramento del modello, vengono salvati localmente:

- timestamp UTC;
- versione del consenso;
- versione del modello;
- risposte numeriche;
- profilo sugli 8 assi;
- confidenza;
- match con ideologia, partiti e storici;
- numero di contraddizioni rilevate.
- dati facoltativi aggregabili: fascia d'eta, titolo di studio, area di provenienza, interesse politico, competenza politica auto-percepita, frequenza informativa e situazione prevalente.

File: `data/research_samples.jsonl`

I dati facoltativi non modificano il risultato individuale. Servono solo per verificare se alcune domande funzionano diversamente tra gruppi diversi o se il test richiede formulazioni piu chiare.

Se l'utente invia anche feedback post-risultato, vengono salvati localmente:

- valutazione di accuratezza da 1 a 5;
- auto-descrizione politica facoltativa;
- partito percepito come vicino facoltativo;
- note facoltative;
- risultato previsto dal modello.

File: `data/research_feedback.jsonl`

## Per versione pubblica online

Prima di pubblicare online servono almeno:

- informativa privacy completa;
- consenso esplicito separato per dati politici;
- possibilita di rifiutare senza perdere accesso al test;
- possibilita di revocare consenso;
- esportazione/cancellazione dei dati;
- retention definita;
- misure di sicurezza;
- valutazione legale specifica, perche le opinioni politiche sono dati sensibili.
