# Politometro

Politometro è un test politico multi-asse in italiano. Calcola un profilo su 8 dimensioni, mostra risultati, grafici, mappa, report, card social, PWA installabile, una sezione finale "Il tuo mondo politico" e una pagina per aziende, media e organizzazioni.

Questa versione pubblicabile è statica e client-side: non usa un database online e non raccoglie centralmente le risposte. I dati salvati restano nel browser dell'utente.

## File principali

- `politometro_scientific.py`: domande, assi, pesi, prototipi e algoritmo.
- `politometro_custom_app.py`: interfaccia principale e dashboard admin.
- `build_standalone_app.py`: crea la versione autonoma offline.
- `build_public_site.py`: crea la cartella `dist/` pronta per pubblicazione statica.
- `QUESTION_CALIBRATION_V5.md`: audit e calibrazione teorica più recente delle domande.
- `dist/`: cartella da caricare online.
- `dist/organizzazioni.html`: pagina pubblica per spiegare valore, limiti e possibili partnership.
- `dist/supporto.html`: pagina contatti per supporto, assistenza, privacy e offerte.
- `ADMIN_LOGIN_SETUP.md`: guida per avviare dashboard protetta senza password in chiaro.
- `DATASET_ANALYTICS_GUIDE.md`: guida pratica a dataset, export e correlazioni automatiche.
- `PITCH_COMMERCIALE.md`: proposta semplice per venderlo a media, scuole e organizzazioni.

## Creare il sito pubblico

```bash
.venv-politometro/bin/python build_public_site.py
```

Poi pubblica la cartella `dist/` sul tuo hosting statico.

Per impostare il dominio reale nei meta tag e nella sitemap:

```bash
POLITOMETRO_SITE_URL="https://tuodominio.it/" .venv-politometro/bin/python build_public_site.py
```

Per impostare la mail pubblica di supporto/privacy:

```bash
POLITOMETRO_CONTACT_EMAIL="supporto@tuodominio.it" .venv-politometro/bin/python build_public_site.py
```

Puoi combinare dominio e mail:

```bash
POLITOMETRO_SITE_URL="https://tuodominio.it/" POLITOMETRO_CONTACT_EMAIL="supporto@tuodominio.it" .venv-politometro/bin/python build_public_site.py
```

## Controlli prima del lancio

```bash
.venv-politometro/bin/python tests/algorithm_smoke_test.py
.venv-politometro/bin/python -m py_compile politometro_scientific.py politometro_custom_app.py build_standalone_app.py build_public_site.py
```

## Privacy

La versione statica non invia risposte a un server del progetto. Se in futuro verrà aggiunta una dashboard online centralizzata, serviranno consenso esplicito, informativa completa, cancellazione dati, protezione admin e attenzione speciale ai dati politici, che in UE sono dati sensibili.

Prima di una promozione pubblica seria, verifica che l'email indicata nella privacy policy sia attiva.

## Dove leggere le risposte

- Versione statica online: non ricevi risposte centralizzate.
- Versione server locale: `/admin`, `data/research_samples.jsonl`, `data/research_feedback.jsonl`, `data/politometro.sqlite3`.
- Versione startup futura: database Postgres + dashboard admin protetta, secondo `database/politometro_schema.sql`.

Per avviare la versione server con login admin basta aprire `Avvia_Politometro_Server.command`, scegliere una password temporanea e andare su `/admin`.

La dashboard admin ora genera anche stato dataset, affidabilità media, insight automatici, correlazioni esplorative e download `CSV/JSON` per analisi esterne. Vedi `DATASET_ANALYTICS_GUIDE.md`.

## Immagini

Loghi e ritratti nei risultati vengono caricati da Wikimedia Commons quando disponibili. Se un'immagine esterna non carica, l'interfaccia torna automaticamente all'icona generata con iniziali, così la PWA resta stabile anche offline.
