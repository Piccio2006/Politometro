# Lancio online facile del Politometro

## Scelta consigliata

Per ora conviene pubblicare il Politometro come sito statico + PWA installabile.

Questo significa:

- lo puoi mettere online subito;
- gli utenti lo aprono da link;
- da telefono possono aggiungerlo alla schermata Home;
- tu puoi aggiornarlo caricando una nuova versione;
- non devi ancora gestire server, database, login, consenso avanzato e dati politici centralizzati.

## Cosa caricare online

Carica la cartella:

`dist`

Dentro ci sono:

- `index.html`: app pubblica;
- `manifest.webmanifest`: installazione PWA;
- `sw.js`: offline/cache;
- `icon.svg`, `icon-192.png`, `icon-512.png`: icone PWA anche per telefono;
- `og-image.png`: immagine anteprima per WhatsApp, Telegram, X/Twitter e Facebook;
- `privacy.html`: privacy minima per versione statica;
- `metodo.html`: spiegazione metodo;
- `supporto.html`: contatti per supporto, assistenza, privacy e offerte;
- `organizzazioni.html`: pagina per media, scuole, partiti e organizzazioni;
- `_headers` e `_redirects`: configurazione per Netlify;
- `robots.txt` e `sitemap.xml`: indicizzazione base.

## Metodo più semplice: Netlify Drop

1. Vai su `https://app.netlify.com/drop`
2. Trascina dentro la cartella `dist`
3. Aspetta il caricamento
4. Netlify ti dà un link pubblico
5. Apri il link da telefono e prova “Aggiungi alla schermata Home”

Questa è la via con meno cose da fare.

## Aggiornamenti futuri

Quando vuoi aggiornare il sito:

1. facciamo modifiche al codice;
2. rigeneriamo `dist`;
3. ricarichi la nuova cartella su Netlify.

Se usi GitHub + Netlify/Vercel, poi gli aggiornamenti diventano automatici: basta aggiornare il repository.

## Dove vedi i risultati

Nella versione statica iniziale non vedi i risultati di tutti gli utenti online.

Motivo: le risposte politiche sono dati sensibili. Per partire velocemente e con meno rischi, il calcolo resta nel browser dell'utente.

La pagina `admin.html` legge solo i dati salvati nel browser di chi la apre, quindi non è ancora una dashboard centrale.

## Quando vorrai vedere risultati online

Seconda fase:

- Supabase o database Postgres;
- consenso esplicito;
- dashboard admin protetta;
- export CSV;
- grafici trend;
- cancellazione dati;
- informativa privacy completa.

Quella è la fase giusta quando il sito inizia a girare davvero.

## Modalità elezioni 2027

La modalità elettorale si aggiunge dopo senza rifare tutto:

- nuovo set domande “Elezioni 2027”;
- posizioni partiti da programmi ufficiali;
- fonti visibili;
- confronto partiti/candidati;
- attivazione temporanea durante la campagna.

## Prima del lancio serio

Da fare prima di promuoverlo molto:

- comprare dominio;
- verificare che l'email pubblica indicata in privacy/supporto sia quella giusta;
- per sostituirla: `POLITOMETRO_CONTACT_EMAIL="supporto@tuodominio.it" .venv-politometro/bin/python build_public_site.py`;
- decidere nome finale;
- testarlo su iPhone e Android;
- non promettere “test scientificamente validato” finché non raccogli dati reali.
