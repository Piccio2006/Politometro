# Calibrazione entità: partiti, ideologie, personaggi storici

Il file modificabile è:

```text
data/entity_registry_v1.json
```

Serve per aggiungere o sostituire partiti, ideologie e figure storiche senza toccare il codice principale.

## Scala degli assi

Ogni entità ha 8 valori da `-1` a `+1`.

- Economia: `-1` welfare/redistribuzione, `+1` mercato/privatizzazioni.
- Autorità: `-1` libertà individuale, `+1` ordine/controllo.
- Cultura: `-1` pluralismo/diritti, `+1` tradizione/religione.
- Geopolitica: `-1` cooperazione sovranazionale, `+1` sovranità nazionale.
- Ambiente: `-1` transizione verde, `+1` crescita industriale.
- Tecnologia: `-1` regolazione prudente, `+1` innovazione rapida.
- Uguaglianza: `-1` pari condizioni, `+1` gerarchie/competizione.
- Giustizia: `-1` recupero sociale, `+1` deterrenza/punizione.

## Regola per rendere il modello serio

Non assegnare un numero perché "sembra giusto". Per ogni entità servono:

- fonte ufficiale o programma;
- benchmark esterno quando disponibile;
- nota sul perché il valore è negativo, centrale o positivo;
- revisione dopo dati utenti reali.

## Fonti consigliate

- Partiti europei: CHES per posizionamenti esperti, Manifesto Project/MARPOR per programmi elettorali, V-Dem V-Party per struttura/posizioni dei partiti, programmi ufficiali.
- Partiti italiani: programmi ufficiali, documenti parlamentari, famiglie europee, comunicazione ufficiale.
- Ideologie: letteratura politica e manuali, non meme o definizioni social.
- Figure storiche: fonti storiche primarie/secondarie; evitare confronti moralistici.

## Procedura pratica

1. Aggiungi l'entità in `data/entity_registry_v1.json`.
2. Inserisci `category`: `partito`, `ideologia` o `storico`.
3. Compila gli 8 assi.
4. Aggiungi `brief`, `url`, `source_label`, `evidence` e `basis`.
5. Rigenera il sito con `build_public_site.py`.
6. Testa che il risultato non diventi sensazionalistico.

## Cautela sui personaggi storici

Le figure storiche devono essere comparabili, non equivalenze morali. Le figure estreme possono comparire nel match principale solo se marcate come `high_risk`, con avviso esplicito e testo sobrio: distanza geometrica sugli assi, non somiglianza morale, biografica o politica completa.

## Regola anti-sensazionalismo

Se una figura estrema appare come vicina o come nemesi:

- mostrare sempre l'avviso di rischio interpretativo;
- spiegare almeno due assi di somiglianza e due assi di differenza;
- non usare immagini, copy o animazioni celebrative;
- conservare nel database la versione del modello che ha prodotto il risultato;
- rivedere la posizione dopo ogni batch di dati reali e dopo revisione esperta.
