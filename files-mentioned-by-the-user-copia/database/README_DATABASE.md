# Database proprietario Politometro

Quando avrai dominio e pubblicazione stabile, questa è la base per tenere i dati in un tuo database.

## File

- `politometro_schema.sql`: tabelle principali.
- `analytics_views.sql`: viste per trend e correlazioni aggregate.

## Regola importante

Le opinioni politiche sono dati sensibili. Il database va attivato solo con:

- consenso esplicito;
- privacy policy completa;
- possibilità di cancellazione;
- accesso admin protetto;
- niente vendita di dati individuali;
- niente microtargeting politico opaco.

## Dove leggerai le risposte

Nella demo locale:

- dashboard admin locale;
- `data/research_samples.jsonl`;
- `data/research_feedback.jsonl`.
- `data/support_contacts.jsonl`;
- `data/politometro.sqlite3`.

Nella versione online vera:

- tabella `quiz_sessions` per sessioni e consenso;
- tabella `answers` per le risposte;
- tabella `result_profiles` per punteggi, coerenza, affidabilità e risultato;
- tabella `feedback` per accuratezza percepita e correzioni utente;
- viste in `analytics_views.sql` per leggere trend e correlazioni senza guardare singoli profili.

## Login

Lo schema separa:

- `user_accounts`: account utente opzionali, meglio con email hash o provider esterno;
- `admin_users`: login per te e collaboratori;
- `admin_audit_log`: traccia delle azioni admin;
- `support_contacts`: richieste supporto, assistenza e offerte commerciali.

Il login utente non deve essere obbligatorio per fare il test. Serve solo per funzioni extra: storico personale, confronto nel tempo, esportazione e cancellazione più semplice.

## Algoritmo correlazioni

La prima versione usa correlazioni aggregate:

- risposte domanda ↔ assi finali;
- demografia facoltativa ↔ assi finali;
- trend giorno per giorno;
- coerenza interna media;
- affidabilità interpretativa media;
- partiti/ideologie prevalenti per gruppo solo con campioni sufficienti.
- accuratezza percepita tramite feedback consensuale;
- deviazioni aggregate per gruppo, con soglia minima per evitare letture su campioni piccoli.

Le correlazioni non dimostrano causalità. Servono per trovare domande da correggere, bias da controllare e pattern da verificare.

## Soglie consigliate

- Sotto 30 risposte per gruppo: non mostrare classifiche.
- Da 100 risposte: usare le correlazioni solo come diagnostica.
- Da 300 risposte: iniziare analisi fattoriale esplorativa.
- Da 1.000 risposte: ricalibrare pesi, percentili e stabilità del modello.
