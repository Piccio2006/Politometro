# Politometro Data Calibration Plan

## Obiettivo

Portare il Politometro da modello manuale a modello calibrato su:

- fonti politologiche per partiti e famiglie ideologiche;
- audit interno delle domande;
- risposte consensuali degli utenti;
- dati demografici facoltativi e non identificativi;
- confronto tra modello predittivo e percezione soggettiva dell'utente.

## Fonti Prioritarie

1. Chapel Hill Expert Survey (CHES)
   - Uso: partiti europei, sinistra-destra, GAL-TAN, immigrazione, UE.
   - Link: https://www.chesdata.eu/

2. Manifesto Project / MARPOR
   - Uso: programmi elettorali, categorie di policy, trend temporali.
   - Link: https://manifesto-project.wzb.eu/

3. V-Dem V-Party
   - Uso: partiti globali, illiberalismo, pluralismo, organizzazione, identita.
   - Link: https://v-dem.net/vpartyds.html

4. Party Facts
   - Uso: collegare lo stesso partito tra dataset diversi.
   - Link: https://partyfacts.herokuapp.com/

## Stato Attuale

- Domande: manuali, ora auditate automaticamente.
- Pesi: manuali, ora penalizzati se una domanda misura troppi assi insieme.
- Partiti: manual_v1; da calibrare contro dataset esterni.
- Ideologie: manual_v1; da validare con letteratura e confronto esperto.
- Personaggi storici: interpretive_v1; da separare per periodo e contesto storico.
- Dati utenti: raccolta locale solo con consenso esplicito.
- Demografia: facoltativa, raccolta per fasce e non usata nel risultato individuale.

## Regole Di Calibrazione

1. Non sostituire un prototipo solo con una fonte singola.
2. Usare medie pesate tra dataset quando disponibili.
3. Segnalare in UI il livello di evidenza: manuale, dataset, misto, validato utenti.
4. Non trattare le figure storiche come equivalenti ai partiti contemporanei.
5. Mantenere sempre una spiegazione leggibile del perche un risultato e uscito.
6. Non usare eta, istruzione o provenienza per cambiare il risultato individuale.
7. Usare i dati demografici solo per audit di bias, chiarezza e stabilita delle domande.

## Privacy

Le opinioni politiche sono dati sensibili. In locale il consenso salva solo:

- timestamp;
- versione consenso;
- versione modello;
- risposte;
- profilo vettoriale;
- match generati;
- numero di contraddizioni.

Per una versione online servono:

- informativa privacy completa;
- consenso esplicito separato dal test;
- possibilita di rifiutare senza perdere funzionalita;
- cancellazione/esportazione dei dati;
- minimizzazione e retention limitata;
- valutazione DPIA se scala o rischio aumentano.
