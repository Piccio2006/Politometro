# Politometro startup: database, login e dashboard

Questo file risponde alla domanda pratica: dove leggerai le risposte degli utenti e come si passa dalla demo attuale a una piattaforma vera.

## Stato attuale

La versione pubblicabile statica in `dist/` non raccoglie risposte centralizzate. È una scelta prudente: il quiz funziona, la PWA si installa, ma i dati restano nel browser dell'utente.

Se avvii la versione server locale, le risposte con consenso finiscono qui:

```text
data/research_samples.jsonl
data/research_feedback.jsonl
data/politometro.sqlite3
```

La dashboard locale è:

```text
/admin
```

Il login admin locale è configurato con variabili ambiente e hash, non con password nel codice. Vedi `ADMIN_LOGIN_SETUP.md`.

## Versione startup online

Per leggere le risposte di tutti gli utenti ti serviranno:

1. backend API;
2. database Postgres;
3. login admin;
4. consenso esplicito;
5. privacy policy completa;
6. dashboard aggregata;
7. export e cancellazione dati.

Lo schema base è già in:

```text
database/politometro_schema.sql
database/analytics_views.sql
```

## Login utenti

Il login utente deve essere opzionale. Il quiz deve restare accessibile senza account.

Account utile per:

- salvare storico personale;
- rifare il test dopo settimane;
- vedere come cambia il profilo;
- cancellare più facilmente i propri dati;
- ricevere aggiornamenti se l'utente li accetta.

Da evitare:

- obbligare il login prima del quiz;
- salvare email in chiaro se non serve;
- collegare opinioni politiche a identità reali senza motivo forte;
- usare i dati per microtargeting politico opaco.

## Login admin

La dashboard online deve stare dietro login.

Ruoli consigliati:

- owner: tu;
- admin: collaboratori fidati;
- analyst: vede aggregati, non dati individuali inutili;
- viewer: sola lettura.

Ogni accesso o export importante dovrebbe finire in `admin_audit_log`.

## Contatti e supporto

La pagina `supporto.html` è il luogo pubblico per:

- supporto utenti;
- privacy;
- assistenza;
- offerte commerciali;
- partnership.

Prima del lancio imposta una mail vera:

```bash
POLITOMETRO_CONTACT_EMAIL="supporto@tuodominio.it" .venv-politometro/bin/python build_public_site.py
```

## Roadmap dei due mesi

Settimana 1: dominio, email, repo pulito, hosting stabile.

Settimana 2: backend minimo con salvataggio consensuale.

Settimana 3: login admin e dashboard online.

Settimana 4: login utente opzionale o lista d'attesa.

Settimana 5: prime 100 risposte, controlli qualità e bugfix mobile.

Settimana 6: analytics aggregate e report interno.

Settimana 7: pagina commerciale, pitch per media/organizzazioni.

Settimana 8: beta pubblica controllata, privacy review e piano Elezioni 2027.
