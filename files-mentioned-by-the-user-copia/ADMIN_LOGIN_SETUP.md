# Login admin e dataset

Versione semplice.

## Come entrare

1. Apri `Avvia_Politometro_Server.command`.
2. Scrivi la mail admin, oppure premi invio per usare `piccioligiovanni@outlook.it`.
3. Scegli una password temporanea.
4. Il sito si apre su `http://127.0.0.1:7860/`.
5. Vai su `http://127.0.0.1:7860/admin`.
6. Entra con la mail e la password appena scelta.

La password non viene scritta nel codice.

## Come nasce il dataset

È come una scatola:

- una persona fa il test;
- se dice sì al consenso ricerca, le risposte entrano nella scatola;
- la dashboard apre la scatola e conta cosa succede;
- quando ci sono abbastanza risposte, mostra correlazioni e segnali.

## Dove sono i dati

```text
data/research_samples.jsonl
data/research_feedback.jsonl
data/support_contacts.jsonl
data/politometro.sqlite3
```

## Cosa mostra la dashboard

- quante risposte ci sono;
- quali risultati sono più frequenti;
- feedback degli utenti;
- correlazioni tra dati facoltativi e risposte;
- differenze tra gruppi;
- export CSV/JSON.

Sotto 100 risposte i dati sono solo indizi. Da 300 risposte diventano più utili. Da 1.000 risposte diventano molto più interessanti.
