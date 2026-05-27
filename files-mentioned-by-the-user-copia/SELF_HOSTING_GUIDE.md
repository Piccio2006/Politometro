# Hosting senza Netlify

Obiettivo: pubblicare Politometro senza dipendere da Netlify Drop.

Non esiste un hosting pubblico davvero "senza limiti" e gratis per sempre: o usi un servizio gratuito con limiti, oppure controlli tu un server e paghi dominio/server/elettricità. La scelta più solida dipende da quanto vuoi controllo.

## Scelta consigliata per controllo vero

Usa un tuo dominio e un server tuo.

Opzioni:

- VPS economico: costa poco al mese, controllo alto, affidabile.
- Oracle Cloud Always Free: può funzionare gratis, ma resta un servizio cloud con limiti e disponibilità non garantita.
- Mini server o Raspberry a casa: massimo controllo, nessun canone server, ma servono rete stabile, DNS dinamico o tunnel, backup e attenzione alla sicurezza.

## Avvio con Docker/Caddy

La cartella `hosting/` contiene una configurazione pronta.

Prima rigenera il sito:

```bash
POLITOMETRO_SITE_URL="https://tuodominio.it/" .venv-politometro/bin/python build_public_site.py
```

Con mail reale di supporto/privacy:

```bash
POLITOMETRO_SITE_URL="https://tuodominio.it/" POLITOMETRO_CONTACT_EMAIL="supporto@tuodominio.it" .venv-politometro/bin/python build_public_site.py
```

Poi, da questa cartella:

```bash
cd hosting
docker compose up -d
```

Il sito sarà su:

```text
http://127.0.0.1:8080/
```

Su un server pubblico, colleghi il dominio alla macchina e metti Caddy/Nginx davanti al sito. Per HTTPS automatico con dominio vero conviene usare Caddy installato sul server.

## Alternative gratuite

- GitHub Pages: ottimo per statico, niente backend, limiti di banda e uso accettabile.
- Cloudflare Pages: molto generoso per statico, ma resta una piattaforma esterna.
- Vercel: comodo, ma ha piani e limiti chiari; per uso commerciale intenso va valutato.

## Quando servirà una dashboard online

La versione attuale è statica e privacy-first. Se vuoi vedere risultati di tutti gli utenti:

- database separato;
- login admin;
- eventuale login utente opzionale, non obbligatorio per fare il quiz;
- consenso esplicito;
- informativa privacy completa;
- export aggregato;
- cancellazione dati;
- niente vendita di dati individuali.

Per dati politici in UE serve trattarla come una fase legale seria, non come una feature grafica.
