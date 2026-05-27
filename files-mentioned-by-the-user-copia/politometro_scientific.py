from __future__ import annotations

import base64
import copy
import io
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import numpy as np
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

import politometro_legacy as legacy


AXES = legacy.AXES
AXIS_SHORT = legacy.AXIS_SHORT
AXIS_EXPLANATIONS = legacy.AXIS_EXPLANATIONS
ENTITY_REGISTRY_PATH = Path(__file__).resolve().parent / "data" / "entity_registry_v1.json"


def entity_vector_from_item(item: dict[str, Any]) -> np.ndarray:
    if "vector" in item:
        vector = np.array(item["vector"], dtype=float)
    else:
        axes = item.get("axes", {})
        vector = np.array([float(axes.get(axis, 0.0)) for axis in AXIS_SHORT], dtype=float)
    if vector.shape != (len(AXIS_SHORT),):
        raise ValueError(f"Entità {item.get('name', '<senza nome>')} con vettore non valido: servono {len(AXIS_SHORT)} valori.")
    return np.clip(vector, -1.0, 1.0)


def load_entity_registry() -> tuple[dict[str, np.ndarray], list[str], list[str], list[str], dict[str, dict[str, Any]], set[str], dict[str, Any]]:
    prototypes = {name: np.array(value, dtype=float) for name, value in legacy.PROTOTYPES.items()}
    categories = {
        "ideologia": list(legacy.CAT_IDEOLOGIE),
        "partito": list(legacy.CAT_PARTITI),
        "storico": list(legacy.CAT_STORICI),
    }
    metadata: dict[str, dict[str, Any]] = {}
    high_risk: set[str] = set()
    info: dict[str, Any] = {
        "path": str(ENTITY_REGISTRY_PATH),
        "loaded": False,
        "custom_entities": 0,
        "disabled_entities": [],
    }
    if not ENTITY_REGISTRY_PATH.exists():
        return prototypes, categories["ideologia"], categories["partito"], categories["storico"], metadata, high_risk, info

    data = json.loads(ENTITY_REGISTRY_PATH.read_text(encoding="utf-8"))
    disabled = [str(name).strip() for name in data.get("disabled_entities", []) if str(name).strip()]
    for name in disabled:
        prototypes.pop(name, None)
        for items in categories.values():
            while name in items:
                items.remove(name)

    for item in data.get("entities", []):
        name = str(item.get("name", "")).strip()
        category = str(item.get("category", "")).strip().lower()
        if not name or category not in categories:
            continue

        prototypes[name] = entity_vector_from_item(item)
        for items in categories.values():
            while name in items:
                items.remove(name)
        categories[category].append(name)

        item_metadata = dict(item.get("metadata", {}))
        for key in ["brief", "url", "source_label", "evidence", "note", "basis"]:
            if item.get(key):
                item_metadata[key] = item[key]
        if item_metadata:
            metadata[name] = item_metadata
        if bool(item.get("high_risk")):
            high_risk.add(name)

    info.update(
        {
            "loaded": True,
            "custom_entities": len(data.get("entities", [])),
            "disabled_entities": disabled,
            "version": data.get("version", "custom"),
            "status": data.get("status", "manual_registry"),
        }
    )
    return prototypes, categories["ideologia"], categories["partito"], categories["storico"], metadata, high_risk, info


PROTOTYPES, CAT_IDEOLOGIE, CAT_PARTITI, CAT_STORICI, CUSTOM_ENTITY_METADATA, CUSTOM_HIGH_RISK, ENTITY_REGISTRY_INFO = load_entity_registry()

MODEL_VERSION = "politometro-scientific-v5.1-coherence-audit"

QUICK_QUESTION_IDS = [
    "taxation",
    "corporate_power",
    "police_power",
    "surveillance",
    "free_speech",
    "religion_state",
    "gender_policy",
    "abortion",
    "immigration_policy",
    "european_union",
    "national_identity",
    "war_peace",
    "climate_policy",
    "public_transport",
    "ai_governance",
    "data_privacy",
    "education_merit",
    "meritocracy",
    "crime_sentencing",
    "prison_model",
]

SOCIAL_QUESTION_IDS = [
    "taxation",
    "corporate_power",
    "surveillance",
    "free_speech",
    "religion_state",
    "gender_policy",
    "immigration_policy",
    "european_union",
    "climate_policy",
    "ai_governance",
    "meritocracy",
    "crime_sentencing",
]

CALIBRATION_NOTES = {
    "version": MODEL_VERSION,
    "status": "content_validity_v5_prevalidation",
    "summary": "Modello multidimensionale trasparente, in fase di validazione empirica: V5 rafforza audit, dominanza degli assi primari, prudenza interpretativa e confronto spiegabile.",
    "principles": [
        "Una domanda deve avere un asse primario chiaro e pochi assi secondari.",
        "Ogni domanda deve restare entro quattro assi attivi; se ne servono di più, va divisa in item separati.",
        "L'asse principale deve restare dominante rispetto ai secondari, soprattutto nelle domande usate in modalità social e rapida.",
        "I pesi secondari descrivono effetti teorici plausibili, non impressioni narrative o giudizi morali.",
        "La modalità rapida copre tutti gli 8 assi con almeno due item informativi.",
        "La modalità social usa 12 item: è pensata per condivisione, non per massima precisione.",
        "Coerenza interna e affidabilità del risultato sono indicatori separati dal contenuto politico.",
        "La validazione statistica richiede dati utenti, test-retest e benchmark esterni.",
    ],
    "benchmarks": ["CHES", "Manifesto Project / MARPOR", "V-Dem V-Party", "ESS-style survey design"],
    "limitations": [
        "La calibrazione V5 è teorica e di contenuto: non sostituisce analisi fattoriale, test-retest o campioni normativi.",
        "Partiti, ideologie e figure storiche sono prototipi interpretativi: il confronto è geometrico sugli assi, non identitario o morale.",
        "Le correlazioni future vanno lette come segnali diagnostici aggregati, non come causalità o targeting individuale.",
    ],
}

CALIBRATED_QUESTION_OVERRIDES: dict[str, dict[str, Any]] = {
    "immigration_policy": {
        "options": [
            "1 – Frontiere molto aperte, cittadinanza rapida e canali umanitari ampi",
            "2 – Accoglienza ampia ma organizzata con controlli amministrativi",
            "3 – Ingressi regolati per lavoro, studio, famiglia e asilo",
            "4 – Sistema bilanciato: accoglienza e controllo in pari misura",
            "5 – Ingressi limitati e selettivi in base alle esigenze nazionali",
            "6 – Blocco quasi totale dei nuovi ingressi irregolari",
            "7 – Rimpatri sistematici degli irregolari e confini fortemente militarizzati",
        ],
        "weights": [0, 0.25, 0.20, 1.00, 0, 0, 0.10, 0],
    },
    "police_power": {"weights": [0, 1.00, 0, 0, 0, 0, 0.12, 0.38]},
    "surveillance": {"weights": [0, 1.00, 0, 0, 0, 0.35, 0, 0.25]},
    "protest": {"weights": [0, 1.00, 0.12, 0, 0, 0, 0.08, 0.30]},
    "military_service": {"weights": [0, 0.95, 0.16, 0.42, 0, 0, 0, 0]},
    "drug_policy": {
        "options": [
            "1 – Legalizzazione ampia e regolata",
            "2 – Legalizzazione con vincoli",
            "3 – Depenalizzazione",
            "4 – Sistema attuale ma meno repressivo",
            "5 – Divieto con sanzioni moderate",
            "6 – Repressione dura dello spaccio",
            "7 – Sanzioni severe anche per il consumo",
        ],
        "weights": [0, 0.90, 0.18, 0, 0, 0, 0, 0.40],
    },
    "free_speech": {"weights": [0, 0.85, -0.25, 0, 0, -0.15, 0, 0.15]},
    "property": {
        "options": [
            "1 – Settori strategici collettivi o pubblici",
            "2 – Forte controllo pubblico sulle grandi imprese",
            "3 – Mercato con regolazione intensa",
            "4 – Economia mista",
            "5 – Proprietà privata come regola",
            "6 – Poche restrizioni alla proprietà privata",
            "7 – Proprietà privata tutelata al massimo e limitata solo in casi eccezionali",
        ],
        "weights": [1, 0, 0, 0, 0, 0, 0.45, 0],
    },
    "religion_state": {"weights": [0, 0.25, 1.00, 0.15, 0, 0, 0.15, 0]},
    "family_policy": {"weights": [0, 0.15, 1.00, 0, 0, 0, 0.25, 0]},
    "school_values": {"weights": [0, 0.25, 0.95, 0, 0, 0, 0.28, 0]},
    "nato_defense": {"weights": [0, 0.35, 0, 0.85, 0, 0, 0, 0.25]},
    "nuclear_energy": {"weights": [0, 0, 0.08, 0.18, 0.88, 0.32, 0, 0]},
    "animal_rights": {"weights": [0.08, 0, -0.18, 0, 0.90, 0, 0.18, 0]},
    "ai_governance": {
        "options": [
            "1 – Sospendere modelli molto potenti finché non sono sicuri",
            "2 – Regolazione molto severa",
            "3 – Regolazione forte ma favorevole all'innovazione",
            "4 – Equilibrio",
            "5 – Innovazione libera con controlli ex post",
            "6 – Pochi limiti per non perdere competitività",
            "7 – Accelerare molto: l'innovazione tecnologica va favorita il più possibile",
        ],
        "weights": [0, 0.15, -0.10, 0, 0, 1.00, 0.05, 0],
    },
    "crypto": {"weights": [0.12, -0.18, 0, 0, 0, 0.92, 0, 0]},
    "public_transport": {"weights": [0.18, 0, -0.10, 0, 0.86, 0, 0.12, 0]},
    "platform_censorship": {"weights": [0, -0.85, -0.12, 0, 0, 0.25, 0, -0.08]},
    "elite_governance": {
        "options": [
            "1 – La democrazia popolare viene prima delle competenze tecniche",
            "2 – Più partecipazione diretta dei cittadini",
            "3 – Tecnici utili ma subordinati alla politica",
            "4 – Equilibrio tra competenza e consenso",
            "5 – Più competenze tecniche nelle decisioni complesse",
            "6 – Decisioni più tecniche con minore peso dell'opinione pubblica immediata",
            "7 – Governance affidata soprattutto a competenze selezionate, con partecipazione popolare ridotta",
        ],
        "weights": [0, 0.28, 0, 0, 0, 0.12, 1.00, 0],
    },
    "democracy": {
        "options": [
            "1 – Va ampliata con partecipazione diretta",
            "2 – Va difesa e resa più inclusiva",
            "3 – Funziona con buone riforme",
            "4 – Ha pregi e limiti",
            "5 – È lenta e inefficiente",
            "6 – Meglio leader forti con meno vincoli",
            "7 – Andrebbe sostituita da forme più concentrate di decisione politica",
        ],
        "weights": [0, 1.00, 0, 0.08, 0, 0, 0.36, 0.08],
    },
    "referendum": {
        "options": [
            "1 – Usarli spesso per dare potere al popolo",
            "2 – Più consultazioni popolari",
            "3 – Utili su temi chiari",
            "4 – Uso moderato",
            "5 – Rischiano semplificazioni eccessive",
            "6 – Meglio affidarsi soprattutto a Parlamento e competenze tecniche",
            "7 – Le questioni complesse dovrebbero restare quasi sempre a Parlamento e organi tecnici",
        ],
        "weights": [0, 0.28, 0, 0, 0, 0.08, 0.82, 0],
    },
    "national_identity": {"weights": [0, 0.18, 0.48, 1.00, 0, 0, 0.12, 0]},
    "minorities": {
        "options": [
            "1 – Riconoscimento ampio di differenze e diritti specifici",
            "2 – Tutela attiva contro discriminazioni",
            "3 – Integrazione con pari diritti",
            "4 – Equilibrio tra pari diritti e regole comuni",
            "5 – Prevalenza delle regole comuni nazionali",
            "6 – Poche eccezioni culturali o religiose",
            "7 – Adattamento pieno alle regole comuni, senza riconoscimenti specifici",
        ],
        "weights": [0, 0, 0.95, 0.35, 0, 0, 0.30, 0],
    },
    "vaccines_public_health": {"weights": [0, 0.76, -0.05, 0, 0, -0.12, -0.08, 0.12]},
    "pandemic_restrictions": {"weights": [0, 0.88, -0.05, 0, 0, -0.10, -0.08, 0.15]},
    "localism": {"weights": [0, 0.85, 0.12, 0.32, 0, 0, 0.08, 0]},
    "urban_rural": {"weights": [0, 0, 0.86, 0.32, 0.12, 0, 0, 0]},
    "art_culture": {
        "options": [
            "1 – Sperimentazione, provocazione e rottura delle forme",
            "2 – Avanguardia e pluralismo culturale",
            "3 – Innovazione con accessibilità",
            "4 – Equilibrio",
            "5 – Valorizzare patrimonio e bellezza tradizionale",
            "6 – Più arte classica e identitaria",
            "7 – Preferenza netta per forme artistiche tradizionali rispetto all'arte contemporanea più sperimentale",
        ],
        "weights": [0, 0.05, 0.78, 0.20, 0, 0, 0.12, 0],
    },
    "food_identity": {"weights": [0, 0, 0.78, 0.32, 0.15, 0, 0.08, 0]},
    "science_tradition": {"weights": [0, 0.15, 0.85, 0, 0, -0.25, 0.12, 0]},
    "meritocracy": {
        "options": [
            "1 – Il merito è spesso maschera delle disuguaglianze",
            "2 – Prima correggere le condizioni di partenza",
            "3 – Merito sì, ma con sostegni sociali",
            "4 – Equilibrio",
            "5 – Premiare fortemente chi si impegna",
            "6 – Le differenze di risultato possono essere giuste se le regole sono eque",
            "7 – La selezione dei migliori dovrebbe contare molto più della redistribuzione",
        ],
        "weights": [0.35, 0, 0.05, 0, 0, 0, 1, 0],
    },
    "inheritance": {"weights": [1.00, 0, 0.08, 0, 0, 0, 0.62, 0]},
    "international_aid": {"weights": [0.16, 0, -0.12, 0.98, 0, 0, 0.26, 0]},
    "war_peace": {"weights": [0, 0.36, 0, 0.88, 0, 0, 0, 0.22]},
    "law_and_order": {
        "options": [
            "1 – Politiche sociali prima della repressione",
            "2 – Prevenzione e inclusione",
            "3 – Polizia e servizi sociali insieme",
            "4 – Equilibrio",
            "5 – Più pattuglie e controlli",
            "6 – Tolleranza molto bassa per degrado e microcriminalità",
            "7 – Ordine urbano con misure più incisive e continuità dei controlli",
        ],
        "weights": [0, 0.46, 0, 0, 0, 0, 0.18, 1.00],
    },
    "corporate_power": {"weights": [0.95, 0, -0.08, 0, 0, 0.28, 0.32, 0]},
    "public_order_vs_rights": {"weights": [0, 1.00, 0.08, 0, 0, 0, 0.14, 0.42]},
    "cultural_preservation": {
        "options": [
            "1 – Massima apertura: le culture cambiano e si contaminano naturalmente",
            "2 – Accogliere influenze globali proteggendo il patrimonio",
            "3 – Bilanciare tradizione e innovazione culturale",
            "4 – Equilibrio neutrale",
            "5 – Priorità alla preservazione delle radici culturali",
            "6 – Difendere attivamente la cultura tradizionale da influenze percepite come dannose",
            "7 – Ridurre fortemente l'apertura culturale per proteggere identità e confini simbolici",
        ],
        "weights": [0, 0, 0.90, 0.55, 0, 0, 0.15, 0],
    },
}


def build_calibrated_questions() -> list[dict[str, Any]]:
    questions = copy.deepcopy(legacy.QUESTIONS)
    for question in questions:
        override = CALIBRATED_QUESTION_OVERRIDES.get(question["id"])
        if override:
            question.update(copy.deepcopy(override))
        question["calibration_version"] = MODEL_VERSION
        question["quick"] = question["id"] in QUICK_QUESTION_IDS
    return questions


QUESTIONS = build_calibrated_questions()

SOURCE_REFERENCES = [
    {
        "name": "Chapel Hill Expert Survey (CHES)",
        "url": "https://www.chesdata.eu/",
        "use": "Benchmark per partiti europei su sinistra-destra, GAL-TAN, UE, immigrazione e temi policy.",
    },
    {
        "name": "Manifesto Project / MARPOR",
        "url": "https://manifesto-project.wzb.eu/",
        "use": "Benchmark testuale sui programmi elettorali e sulle categorie di policy dei partiti.",
    },
    {
        "name": "V-Dem V-Party",
        "url": "https://v-dem.net/vpartyds.html",
        "use": "Benchmark esperto globale su identità, posizioni e organizzazione dei partiti.",
    },
    {
        "name": "Party Facts",
        "url": "https://partyfacts.herokuapp.com/",
        "use": "Ponte tra dataset diversi per identificare partiti e famiglie politiche.",
    },
    {
        "name": "European Social Survey (ESS)",
        "url": "https://www.europeansocialsurvey.org/",
        "use": "Riferimento per formulazione prudente di domande su atteggiamenti politici, immigrazione, fiducia e valori.",
    },
]

ENTITY_WORLD_METADATA: dict[str, dict[str, str]] = {
    "PD": {
        "brief": "Area progressista e riformista: welfare, diritti civili, europeismo e compromesso istituzionale.",
        "url": "https://www.partitodemocratico.it/",
        "source_label": "Sito ufficiale",
    },
    "Alleanza Verdi e Sinistra": {
        "brief": "Area eco-sociale: ambiente, redistribuzione, diritti civili, lavoro e critica delle disuguaglianze.",
        "url": "https://alleanzaverdiesinistra.it/",
        "source_label": "Sito ufficiale",
    },
    "Movimento 5 Stelle": {
        "brief": "Area populista-progressista e civica: welfare, transizione ecologica, democrazia diretta e critica delle élite.",
        "url": "https://www.movimento5stelle.eu/",
        "source_label": "Sito ufficiale",
    },
    "Azione / Italia Viva": {
        "brief": "Area liberal-riformista: europeismo, competenza amministrativa, mercato regolato e innovazione.",
        "url": "https://www.azione.it/",
        "source_label": "Sito ufficiale Azione",
    },
    "Forza Italia": {
        "brief": "Area liberal-conservatrice: mercato, moderazione istituzionale, atlantismo e centrodestra europeo.",
        "url": "https://forzaitalia.it/",
        "source_label": "Sito ufficiale",
    },
    "Lega": {
        "brief": "Area sovranista e securitaria: autonomia, identità nazionale, controllo migratorio e riduzione fiscale.",
        "url": "https://legapersalvinipremier.it/",
        "source_label": "Sito ufficiale",
    },
    "Fratelli d'Italia": {
        "brief": "Area conservatrice nazionale: sovranità, tradizione, sicurezza, atlantismo e identità culturale.",
        "url": "https://www.fratelli-italia.it/",
        "source_label": "Sito ufficiale",
    },
    "Karl Marx": {
        "brief": "Critica del capitalismo, conflitto di classe, proprietà dei mezzi produttivi e trasformazione sociale.",
        "url": "https://it.wikipedia.org/wiki/Karl_Marx",
        "source_label": "Wikipedia",
    },
    "Franklin D. Roosevelt": {
        "brief": "Riformismo democratico, intervento pubblico, welfare, regolazione finanziaria e leadership in crisi.",
        "url": "https://it.wikipedia.org/wiki/Franklin_Delano_Roosevelt",
        "source_label": "Wikipedia",
    },
    "John F. Kennedy": {
        "brief": "Liberalismo democratico, modernizzazione, diritti civili graduali, atlantismo e fiducia nel progresso.",
        "url": "https://it.wikipedia.org/wiki/John_Fitzgerald_Kennedy",
        "source_label": "Wikipedia",
    },
    "Abraham Lincoln": {
        "brief": "Unità nazionale, istituzioni repubblicane, abolizione della schiavitù e autorità federale in emergenza.",
        "url": "https://it.wikipedia.org/wiki/Abraham_Lincoln",
        "source_label": "Wikipedia",
    },
    "Winston Churchill": {
        "brief": "Conservatorismo liberale, fermezza geopolitica, parlamentarismo e difesa dell'ordine occidentale.",
        "url": "https://it.wikipedia.org/wiki/Winston_Churchill",
        "source_label": "Wikipedia",
    },
    "Margaret Thatcher": {
        "brief": "Mercato, privatizzazioni, riduzione del ruolo economico dello Stato e conservatorismo d'ordine.",
        "url": "https://it.wikipedia.org/wiki/Margaret_Thatcher",
        "source_label": "Wikipedia",
    },
    "Ronald Reagan": {
        "brief": "Conservatorismo liberista, tasse basse, anticomunismo, patriottismo e fiducia nel mercato.",
        "url": "https://it.wikipedia.org/wiki/Ronald_Reagan",
        "source_label": "Wikipedia",
    },
    "Mahatma Gandhi": {
        "brief": "Nonviolenza, autonomia comunitaria, critica del dominio imperiale e politica come disciplina morale.",
        "url": "https://it.wikipedia.org/wiki/Mahatma_Gandhi",
        "source_label": "Wikipedia",
    },
    "Nelson Mandela": {
        "brief": "Antiapartheid, riconciliazione democratica, diritti civili e costruzione istituzionale dopo il conflitto.",
        "url": "https://it.wikipedia.org/wiki/Nelson_Mandela",
        "source_label": "Wikipedia",
    },
    "Martin Luther King Jr.": {
        "brief": "Diritti civili, nonviolenza, uguaglianza sostanziale e critica morale delle ingiustizie sociali.",
        "url": "https://it.wikipedia.org/wiki/Martin_Luther_King",
        "source_label": "Wikipedia",
    },
    "Niccolò Machiavelli": {
        "brief": "Realismo politico, potere, conflitto, stabilità dello Stato e autonomia della politica dalla morale privata.",
        "url": "https://it.wikipedia.org/wiki/Niccol%C3%B2_Machiavelli",
        "source_label": "Wikipedia",
    },
    "John Locke": {
        "brief": "Liberalismo classico, diritti naturali, governo limitato, proprietà e consenso dei governati.",
        "url": "https://it.wikipedia.org/wiki/John_Locke",
        "source_label": "Wikipedia",
    },
    "Thomas Hobbes": {
        "brief": "Ordine, sovranità forte, paura del conflitto civile e necessità di un'autorità politica stabile.",
        "url": "https://it.wikipedia.org/wiki/Thomas_Hobbes",
        "source_label": "Wikipedia",
    },
    "Giuseppe Garibaldi": {
        "brief": "Patriottismo democratico, azione popolare, unità nazionale e sensibilità repubblicana.",
        "url": "https://it.wikipedia.org/wiki/Giuseppe_Garibaldi",
        "source_label": "Wikipedia",
    },
    "Giuseppe Mazzini": {
        "brief": "Repubblicanesimo, dovere civico, nazione democratica, popolo e missione morale della politica.",
        "url": "https://it.wikipedia.org/wiki/Giuseppe_Mazzini",
        "source_label": "Wikipedia",
    },
    "Adolf Hitler": {
        "brief": "Figura totalitaria e genocidaria: ultranazionalismo, razzismo di Stato, guerra espansionista e distruzione dello Stato di diritto.",
        "url": "https://it.wikipedia.org/wiki/Adolf_Hitler",
        "source_label": "Wikipedia",
    },
    "Benito Mussolini": {
        "brief": "Figura dittatoriale fascista: autoritarismo, nazionalismo, corporativismo, repressione del pluralismo e culto dello Stato.",
        "url": "https://it.wikipedia.org/wiki/Benito_Mussolini",
        "source_label": "Wikipedia",
    },
    "Josif Stalin": {
        "brief": "Figura dittatoriale sovietica: statalismo estremo, repressione politica, pianificazione forzata e concentrazione del potere.",
        "url": "https://it.wikipedia.org/wiki/Iosif_Stalin",
        "source_label": "Wikipedia",
    },
    "Mao Zedong": {
        "brief": "Figura rivoluzionaria e dittatoriale cinese: partito-Stato, mobilitazione di massa, pianificazione e forte controllo politico.",
        "url": "https://it.wikipedia.org/wiki/Mao_Zedong",
        "source_label": "Wikipedia",
    },
    "Augusto Pinochet": {
        "brief": "Figura dittatoriale cilena: autoritarismo militare, repressione politica e svolta economica di mercato in regime non democratico.",
        "url": "https://it.wikipedia.org/wiki/Augusto_Pinochet",
        "source_label": "Wikipedia",
    },
    "Francisco Franco": {
        "brief": "Figura dittatoriale spagnola: autoritarismo nazional-cattolico, centralismo, repressione politica e tradizionalismo.",
        "url": "https://it.wikipedia.org/wiki/Francisco_Franco",
        "source_label": "Wikipedia",
    },
}
ENTITY_WORLD_METADATA.update(CUSTOM_ENTITY_METADATA)

HISTORICAL_HIGH_RISK = {
    "Adolf Hitler",
    "Benito Mussolini",
    "Josif Stalin",
    "Mao Zedong",
    "Augusto Pinochet",
    "Francisco Franco",
} | CUSTOM_HIGH_RISK

HISTORICAL_METADATA = {
    name: {
        "comparability": "standard",
        "evidence": "interpretive",
        "note": "Figura usata come riferimento storico approssimativo, non come equivalente morale o biografico.",
    }
    for name in CAT_STORICI
}
for name in HISTORICAL_HIGH_RISK:
    if name in HISTORICAL_METADATA:
        HISTORICAL_METADATA[name] = {
            "comparability": "extreme_context",
            "evidence": "caution",
            "note": "Figura storica estrema: inclusa per completezza comparativa, ma solo come distanza geometrica sugli assi. Non è un paragone morale o biografico.",
        }
for name, metadata in CUSTOM_ENTITY_METADATA.items():
    if name in HISTORICAL_METADATA:
        HISTORICAL_METADATA[name].update(metadata)

IDEOLOGY_METADATA = {
    name: {
        "evidence": "manual_v1",
        "note": "Prototipo teorico costruito manualmente; va validato con letteratura e dati utenti.",
    }
    for name in CAT_IDEOLOGIE
}
for name, metadata in CUSTOM_ENTITY_METADATA.items():
    if name in IDEOLOGY_METADATA:
        IDEOLOGY_METADATA[name].update(metadata)


@dataclass
class AxisResult:
    name: str
    value: float
    confidence: float
    coverage: float
    clarity: float
    explanation: str


CONTRADICTION_GROUPS = [
    ("economia_pubblica", ["taxation", "healthcare", "housing", "inheritance", "corporate_power"]),
    ("sicurezza_giustizia", ["crime_sentencing", "prison_model", "death_penalty", "law_and_order"]),
    ("liberta_autorita", ["surveillance", "public_order_vs_rights", "pandemic_restrictions", "vaccines_public_health"]),
    ("cultura_diritti", ["religion_state", "family_policy", "gender_policy", "abortion", "euthanasia"]),
    ("apertura_identita", ["immigration_policy", "national_identity", "minorities", "cultural_preservation"]),
    ("tecnologia", ["ai_governance", "data_privacy", "crypto", "platform_censorship"]),
]

CONTRADICTION_GROUP_LABELS = {
    "economia_pubblica": "Economia pubblica",
    "sicurezza_giustizia": "Sicurezza e giustizia",
    "liberta_autorita": "Libertà e autorità",
    "cultura_diritti": "Cultura e diritti",
    "apertura_identita": "Apertura e identità",
    "tecnologia": "Tecnologia e piattaforme",
}


def normalize_answer(value: int) -> float:
    return (int(value) - 4) / 3.0


def question_loading(question: dict[str, Any]) -> np.ndarray:
    weights = np.array(question["weights"], dtype=float)
    norm = np.linalg.norm(weights)
    if norm == 0:
        return weights
    return weights / norm


def item_discrimination(question: dict[str, Any]) -> float:
    weights = np.abs(np.array(question["weights"], dtype=float))
    strongest = float(np.max(weights))
    spread = float(np.count_nonzero(weights > 0.05))
    focus_bonus = 1.0 if spread <= 2 else 0.9 if spread <= 4 else 0.8
    return float(np.clip(0.55 + strongest * 0.45, 0.55, 1.0) * focus_bonus * question_quality(question))


def question_quality(question: dict[str, Any]) -> float:
    audit = audit_question(question)
    if audit["status"] == "ok":
        return 1.0
    if audit["status"] == "review":
        return 0.9
    return 0.78


LOADED_LANGUAGE_MARKERS = [
    "deportazioni",
    "sacra",
    "sacro",
    "corruzione",
    "caotica",
    "caotico",
    "masse capiscono poco",
    "andarsene",
    "senza freni",
    "tolleranza zero",
]


def option_word_count(option: str) -> int:
    text = option.split("–", 1)[-1] if "–" in option else option
    return len(text.replace("/", " ").split())


def content_risk_audit(question: dict[str, Any]) -> dict[str, Any]:
    question_text = question.get("question", "")
    options = question.get("options", [])
    combined = " ".join([question_text, *options]).lower()
    loaded_terms = [term for term in LOADED_LANGUAGE_MARKERS if term in combined]
    max_option_words = max((option_word_count(option) for option in options), default=0)
    avg_option_words = float(np.mean([option_word_count(option) for option in options])) if options else 0.0
    double_barrel_markers = [
        marker
        for marker in [" / ", " e ", " o "]
        if marker in question_text.lower() and len(question_text.split()) <= 8
    ]
    complexity = "bassa"
    if max_option_words >= 15 or avg_option_words >= 11:
        complexity = "media"
    if max_option_words >= 21 or avg_option_words >= 15:
        complexity = "alta"
    return {
        "emotional_bias_risk": "medio" if loaded_terms else "basso",
        "loaded_terms": loaded_terms,
        "double_barrel_risk": "medio" if double_barrel_markers else "basso",
        "double_barrel_markers": double_barrel_markers,
        "linguistic_complexity": complexity,
        "max_option_words": max_option_words,
        "avg_option_words": round(avg_option_words, 1),
    }


def audit_question(question: dict[str, Any]) -> dict[str, Any]:
    weights = np.abs(np.array(question["weights"], dtype=float))
    active = [AXIS_SHORT[i] for i, value in enumerate(weights) if value > 0.05]
    strongest_idx = int(np.argmax(weights))
    strongest = float(weights[strongest_idx])
    secondary = float(np.partition(weights, -2)[-2]) if len(weights) > 1 else 0.0
    total = float(np.sum(weights))
    focus_ratio = strongest / total if total else 0.0
    dominance_ratio = strongest / secondary if secondary > 0 else float("inf")
    issues: list[str] = []

    if strongest < 0.45:
        issues.append("primary_axis_weak")
    if len(active) > 4:
        issues.append("too_many_axes")
    if focus_ratio < 0.45 and len(active) > 2:
        issues.append("low_focus")
    if dominance_ratio < 1.35 and len(active) > 2:
        issues.append("primary_not_dominant")
    if len(question.get("options", [])) != 7:
        issues.append("not_7_point_scale")
    if "?" not in question.get("question", "") and ":" not in question.get("question", ""):
        issues.append("question_label_too_short")

    if not issues:
        status = "ok"
    elif len(issues) <= 2:
        status = "review"
    else:
        status = "critical"

    content_risk = content_risk_audit(question)
    return {
        "id": question["id"],
        "question": question["question"],
        "primary_axis": AXIS_SHORT[strongest_idx],
        "active_axes": active,
        "active_axes_count": len(active),
        "max_weight": round(strongest, 3),
        "secondary_max_weight": round(secondary, 3),
        "focus_ratio": round(focus_ratio, 3),
        "dominance_ratio": None if not np.isfinite(dominance_ratio) else round(dominance_ratio, 3),
        "status": status,
        "issues": issues,
        "content_risk": content_risk,
        "discrimination_utility": round(float(item_discrimination_without_quality(question)), 3),
        "suggestion": audit_suggestion(issues),
    }


def item_discrimination_without_quality(question: dict[str, Any]) -> float:
    weights = np.abs(np.array(question["weights"], dtype=float))
    strongest = float(np.max(weights))
    spread = float(np.count_nonzero(weights > 0.05))
    focus_bonus = 1.0 if spread <= 2 else 0.9 if spread <= 4 else 0.8
    return float(np.clip(0.55 + strongest * 0.45, 0.55, 1.0) * focus_bonus)


def audit_suggestion(issues: list[str]) -> str:
    if not issues:
        return "Domanda utilizzabile: asse primario chiaro e buona concentrazione del peso."
    suggestions = {
        "primary_axis_weak": "Rafforzare l'asse principale o dividere la domanda in due item.",
        "too_many_axes": "Ridurre gli assi attivi: la domanda misura troppi costrutti insieme.",
        "low_focus": "Aumentare la concentrazione sul costrutto principale.",
        "primary_not_dominant": "Ridurre i pesi secondari: il secondo asse è troppo vicino al principale.",
        "not_7_point_scale": "Uniformare la scala a 7 opzioni ordinate.",
        "question_label_too_short": "Scrivere una formulazione più esplicita della domanda.",
    }
    return " ".join(suggestions[item] for item in issues if item in suggestions)


def compute_profile_scientific(answers: dict[str, int]) -> tuple[np.ndarray, list[AxisResult], dict[str, Any]]:
    scores = np.zeros(len(AXES), dtype=float)
    totals = np.zeros(len(AXES), dtype=float)
    axis_abs_answers: list[list[float]] = [[] for _ in AXES]

    question_by_id = {q["id"]: q for q in QUESTIONS}
    unanswered = [q["id"] for q in QUESTIONS if q["id"] not in answers]

    for question in QUESTIONS:
        qid = question["id"]
        if qid not in answers:
            continue

        response = normalize_answer(answers[qid])
        loading = question_loading(question)
        discrimination = item_discrimination(question)

        for axis_idx, weight in enumerate(loading):
            if abs(weight) <= 1e-9:
                continue
            contribution_weight = abs(weight) * discrimination
            scores[axis_idx] += response * weight * discrimination
            totals[axis_idx] += contribution_weight
            axis_abs_answers[axis_idx].append(abs(response))

    profile = np.zeros(len(AXES), dtype=float)
    for axis_idx in range(len(AXES)):
        if totals[axis_idx] > 0:
            profile[axis_idx] = scores[axis_idx] / totals[axis_idx]

    profile = np.clip(profile, -1.0, 1.0)

    max_total = max(float(np.max(totals)), 1.0)
    axis_results: list[AxisResult] = []
    for axis_idx, short in enumerate(AXIS_SHORT):
        coverage = float(np.clip(totals[axis_idx] / max_total, 0.0, 1.0))
        clarity = float(np.mean(axis_abs_answers[axis_idx])) if axis_abs_answers[axis_idx] else 0.0
        confidence = float(np.clip(0.55 * coverage + 0.45 * clarity, 0.0, 1.0))
        axis_results.append(
            AxisResult(
                name=short,
                value=float(profile[axis_idx]),
                confidence=confidence,
                coverage=coverage,
                clarity=clarity,
                explanation=AXIS_EXPLANATIONS.get(short, ""),
            )
        )

    contradictions = detect_contradictions(answers, question_by_id)
    global_confidence = float(np.mean([a.confidence for a in axis_results]))
    contradiction_penalty = min(0.25, 0.04 * len(contradictions))
    global_confidence = float(np.clip(global_confidence - contradiction_penalty, 0.0, 1.0))

    diagnostics = {
        "unanswered": unanswered,
        "global_confidence": global_confidence,
        "contradictions": contradictions,
        "method": "Modello multi-asse con pesi normalizzati, copertura per asse, chiarezza delle risposte e penalizzazione delle incoerenze tematiche.",
    }
    return profile, axis_results, diagnostics


def compute_question_contributions(answers: dict[str, int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for question in QUESTIONS:
        qid = question["id"]
        if qid not in answers:
            continue
        response = normalize_answer(answers[qid])
        loading = question_loading(question)
        discrimination = item_discrimination(question)
        contributions = response * loading * discrimination
        strongest_axis = int(np.argmax(np.abs(contributions)))
        strongest_value = float(contributions[strongest_axis])
        rows.append(
            {
                "id": qid,
                "question": question["question"],
                "answer": answers[qid],
                "primary_axis": AXIS_SHORT[strongest_axis],
                "contribution": round(strongest_value, 4),
                "magnitude": round(abs(strongest_value), 4),
                "direction": direction_label(strongest_axis, strongest_value),
            }
        )
    return sorted(rows, key=lambda row: row["magnitude"], reverse=True)


def direction_label(axis_idx: int, value: float) -> str:
    if abs(value) < 0.02:
        return "neutro"
    negative = {
        "Economia": "welfare / redistribuzione",
        "Autorità": "libertà individuale",
        "Cultura": "apertura sociale",
        "Geopolitica": "cooperazione internazionale",
        "Ambiente": "transizione verde",
        "Tecnologia": "regolazione cauta",
        "Uguaglianza": "pari condizioni",
        "Giustizia": "recupero sociale",
    }
    positive = {
        "Economia": "mercato / privatizzazioni",
        "Autorità": "ordine e controllo",
        "Cultura": "tradizione",
        "Geopolitica": "sovranità nazionale",
        "Ambiente": "crescita industriale",
        "Tecnologia": "innovazione rapida",
        "Uguaglianza": "gerarchie / competizione",
        "Giustizia": "deterrenza / punizione",
    }
    axis = AXIS_SHORT[axis_idx]
    return positive[axis] if value > 0 else negative[axis]


def detect_contradictions(answers: dict[str, int], question_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for group_name, qids in CONTRADICTION_GROUPS:
        values = []
        labels = []
        for qid in qids:
            if qid not in answers or qid not in question_by_id:
                continue
            values.append(normalize_answer(answers[qid]))
            labels.append(question_by_id[qid]["question"])
        if len(values) < 3:
            continue
        spread = float(np.max(values) - np.min(values))
        if spread >= 1.55:
            issues.append(
                {
                    "group": group_name,
                    "spread": spread,
                    "questions": labels,
                    "message": "Risposte molto polarizzate nello stesso blocco tematico: risultato meno stabile su questo tema.",
                }
            )
    return issues


def build_self_coherence(answers: dict[str, int], diagnostics: dict[str, Any]) -> dict[str, Any]:
    question_by_id = {q["id"]: q for q in QUESTIONS}
    axis_rows: list[dict[str, Any]] = []
    axis_values: list[list[float]] = [[] for _ in AXIS_SHORT]
    axis_weights: list[list[float]] = [[] for _ in AXIS_SHORT]

    for question in QUESTIONS:
        qid = question["id"]
        if qid not in answers:
            continue
        response = normalize_answer(answers[qid])
        loading = question_loading(question)
        discrimination = item_discrimination(question)
        for axis_idx, weight in enumerate(loading):
            if abs(weight) <= 0.08:
                continue
            axis_values[axis_idx].append(response * (1.0 if weight >= 0 else -1.0))
            axis_weights[axis_idx].append(abs(float(weight)) * discrimination)

    for axis_idx, values in enumerate(axis_values):
        if len(values) < 2:
            continue
        arr = np.array(values, dtype=float)
        weights = np.array(axis_weights[axis_idx], dtype=float)
        if float(np.sum(weights)) <= 0:
            weights = np.ones_like(arr)
        mean = float(np.average(arr, weights=weights))
        variance = float(np.average((arr - mean) ** 2, weights=weights))
        std = math.sqrt(max(0.0, variance))
        active = np.abs(arr) > 0.22
        if np.count_nonzero(active) >= 2:
            active_weights = weights[active]
            active_values = arr[active]
            pos_weight = float(np.sum(active_weights[active_values > 0]))
            neg_weight = float(np.sum(active_weights[active_values < 0]))
            total_active = pos_weight + neg_weight
            flip_share = min(pos_weight, neg_weight) / total_active if total_active else 0.0
        else:
            flip_share = 0.0
        dispersion_score = float(np.clip(1.0 - std / 0.82, 0.0, 1.0))
        direction_score = float(np.clip(1.0 - flip_share * 1.65, 0.0, 1.0))
        axis_score = float(np.clip(0.70 * dispersion_score + 0.30 * direction_score, 0.0, 1.0))
        axis_rows.append(
            {
                "group": f"axis_{AXIS_SHORT[axis_idx].lower()}",
                "type": "axis",
                "label": AXIS_SHORT[axis_idx],
                "score": round(axis_score * 100, 1),
                "spread": round(float(np.max(arr) - np.min(arr)), 3),
                "mean": round(mean, 3),
                "items": len(values),
            }
        )

    group_rows: list[dict[str, Any]] = []
    for group_name, qids in CONTRADICTION_GROUPS:
        values = [normalize_answer(answers[qid]) for qid in qids if qid in answers and qid in question_by_id]
        if len(values) < 3:
            continue
        spread = float(np.max(values) - np.min(values))
        group_score = float(np.clip(1.0 - max(0.0, spread - 0.75) / 1.25, 0.0, 1.0))
        group_rows.append(
            {
                "group": group_name,
                "type": "theme",
                "label": CONTRADICTION_GROUP_LABELS.get(group_name, group_name.replace("_", " ").title()),
                "score": round(group_score * 100, 1),
                "spread": round(spread, 3),
                "items": len(values),
            }
        )

    axis_score = float(np.mean([row["score"] for row in axis_rows]) / 100) if axis_rows else 0.72
    theme_score = float(np.mean([row["score"] for row in group_rows]) / 100) if group_rows else axis_score
    completion_score = min(1.0, len(answers) / 20)
    severe_count = len(diagnostics.get("contradictions", []))
    severe_penalty = min(0.36, severe_count * 0.12)
    score = float(np.clip((0.62 * axis_score + 0.24 * theme_score + 0.09 * completion_score + 0.05) - severe_penalty, 0.0, 1.0) * 100)
    neutral_answers = sum(1 for value in answers.values() if int(value) == 4)
    comparable_rows = sorted([*axis_rows, *group_rows], key=lambda row: row["score"])
    strongest_tension = comparable_rows[0] if comparable_rows else None

    if score >= 85:
        label = "Molto alta"
        explanation = "Le risposte restano molto compatibili tra loro sugli assi e nei principali blocchi tematici."
    elif score >= 70:
        label = "Buona"
        explanation = "Il profilo è abbastanza stabile: ci sono sfumature, ma poche tensioni interne forti."
    elif score >= 55:
        label = "Media"
        explanation = "Il profilo contiene alcune tensioni interne: il risultato va letto con più prudenza."
    else:
        label = "Instabile"
        explanation = "Le risposte tirano spesso in direzioni diverse dentro gli stessi temi."

    signals = [
        f"Tensioni forti rilevate: {severe_count}.",
        f"Risposte centrali: {neutral_answers} su {len(answers)}; il centro non è penalizzato, viene letto come prudenza o equilibrio.",
        f"Blocchi tematici confrontabili: {len(group_rows)}.",
        f"Assi confrontabili: {len(axis_rows)}.",
    ]
    if strongest_tension:
        signals.append(f"Area più tesa: {strongest_tension['label']} (spread {strongest_tension['spread']}).")

    return {
        "score": round(score, 1),
        "label": label,
        "explanation": explanation,
        "signals": signals,
        "neutral_answers": neutral_answers,
        "contradiction_count": severe_count,
        "groups": comparable_rows,
        "axis_groups": sorted(axis_rows, key=lambda row: row["score"]),
        "theme_groups": sorted(group_rows, key=lambda row: row["score"]),
    }


def build_uncertainty(axis_results: list[AxisResult], answered_count: int) -> dict[str, Any]:
    mode_penalty = 0.06 if answered_count < len(QUESTIONS) else 0.0
    axis_intervals = []
    for axis in axis_results:
        margin = float(np.clip(0.10 + (1.0 - axis.confidence) * 0.34 + mode_penalty, 0.10, 0.55))
        low = float(np.clip(axis.value - margin, -1.0, 1.0))
        high = float(np.clip(axis.value + margin, -1.0, 1.0))
        axis_intervals.append(
            {
                "axis": axis.name,
                "value": round(axis.value, 3),
                "low": round(low, 3),
                "high": round(high, 3),
                "margin": round(margin, 3),
            }
        )
    note = (
        "Intervalli euristici: indicano prudenza interpretativa in base a copertura, chiarezza e numero di risposte. "
        "Diventeranno intervalli statistici veri solo con dati test-retest e campioni normativi."
    )
    return {"type": "heuristic", "note": note, "axes": axis_intervals}


def affinity_gap(matches: list[tuple[str, float, float]]) -> float:
    if len(matches) < 2:
        return 100.0
    return max(0.0, float(matches[0][2] - matches[1][2]))


def build_result_reliability(
    answers: dict[str, int],
    diagnostics: dict[str, Any],
    self_coherence: dict[str, Any],
    ideologies: list[tuple[str, float, float]],
    parties: list[tuple[str, float, float]],
) -> dict[str, Any]:
    answered_count = len(answers)
    neutral_count = sum(1 for value in answers.values() if int(value) == 4)
    neutral_share = neutral_count / answered_count if answered_count else 1.0
    contradiction_count = len(diagnostics.get("contradictions", []))
    completion_score = min(100.0, answered_count / len(QUESTIONS) * 100)
    confidence_score = float(diagnostics.get("global_confidence", 0.0)) * 100
    coherence_score = float(self_coherence.get("score", 0.0))
    ideology_gap = affinity_gap(ideologies)
    party_gap = affinity_gap(parties)
    match_separation_score = min(100.0, max(ideology_gap, party_gap) * 8.0)
    neutral_penalty = max(0.0, neutral_share - 0.34) * 42.0
    contradiction_penalty = min(22.0, contradiction_count * 5.0)
    score = float(
        np.clip(
            0.42 * confidence_score
            + 0.22 * coherence_score
            + 0.16 * completion_score
            + 0.20 * match_separation_score
            - neutral_penalty
            - contradiction_penalty,
            0.0,
            100.0,
        )
    )

    if score >= 76:
        label = "Alta"
        explanation = "Il risultato è abbastanza stabile: assi coperti, poche tensioni forti e riferimenti principali sufficientemente separati."
    elif score >= 58:
        label = "Media"
        explanation = "Il risultato è leggibile ma va interpretato con prudenza: alcune risposte o confronti sono vicini tra loro."
    else:
        label = "Bassa"
        explanation = "Il risultato è esplorativo: troppe risposte centrali, tensioni interne o match molto ravvicinati riducono la stabilità."

    signals = [
        f"Confidenza tecnica: {confidence_score:.1f}%.",
        f"Coerenza interna: {coherence_score:.1f}%.",
        f"Risposte centrali: {neutral_count} su {answered_count}.",
        f"Differenza tra le ideologie più vicine: {ideology_gap:.1f} punti di affinità.",
        f"Differenza tra i partiti più vicini: {party_gap:.1f} punti di affinità.",
        f"Tensioni forti rilevate: {contradiction_count}.",
    ]
    return {
        "type": "heuristic_v5",
        "score": round(score, 1),
        "label": label,
        "explanation": explanation,
        "signals": signals,
        "neutral_share": round(neutral_share, 3),
        "ideology_gap": round(ideology_gap, 1),
        "party_gap": round(party_gap, 1),
        "note": "Affidabilità euristica: non è ancora un intervallo statistico validato. Diventerà più solida con test-retest, campioni normativi e benchmark esterni.",
    }


def weighted_distance(profile: np.ndarray, prototype: np.ndarray, axis_results: list[AxisResult]) -> float:
    confidence = np.array([max(0.25, a.confidence) for a in axis_results], dtype=float)
    delta = (profile - prototype) * confidence
    return float(np.linalg.norm(delta))


def closest_prototypes_scientific(
    profile: np.ndarray,
    axis_results: list[AxisResult],
    subset: set[str] | None = None,
    top_n: int = 3,
    reverse: bool = False,
) -> list[tuple[str, float, float]]:
    matches = []
    max_distance = np.sqrt(len(AXES)) * 2
    for name, proto in PROTOTYPES.items():
        if subset and name not in subset:
            continue
        dist = weighted_distance(profile, proto, axis_results)
        affinity = float(np.clip(100 * (1 - dist / max_distance), 0, 100))
        matches.append((name, dist, affinity))
    return sorted(matches, key=lambda x: x[1], reverse=reverse)[:top_n]


def entity_metadata(name: str) -> dict[str, str]:
    if name in ENTITY_WORLD_METADATA:
        meta = dict(ENTITY_WORLD_METADATA[name])
    else:
        meta = {
            "brief": "Riferimento usato come prototipo nel modello: la somiglianza è geometrica sugli 8 assi, non un'identificazione totale.",
            "url": f"https://it.wikipedia.org/wiki/{quote(name.replace(' ', '_'))}",
            "source_label": "Wikipedia / approfondimento",
        }
    meta.setdefault("brief", "Riferimento usato come prototipo nel modello: la somiglianza è geometrica sugli 8 assi, non un'identificazione totale.")
    meta.setdefault("url", f"https://it.wikipedia.org/wiki/{quote(name.replace(' ', '_'))}")
    meta.setdefault("source_label", "Wikipedia / approfondimento")
    meta.setdefault("evidence", "manual_prevalidation")
    meta.setdefault("basis", "Coordinate teoriche assegnate manualmente: da validare con fonti esterne, revisione esperta e dati utenti consensuali.")
    meta.setdefault("note", "Confronto interpretativo sugli 8 assi: non è un consiglio di voto né un'identificazione personale.")
    meta.setdefault(
        "sources",
        [
            {
                "label": meta.get("source_label", "Approfondimento"),
                "url": meta.get("url", ""),
            }
        ],
    )
    return meta


def axis_comparison_text(axis_name: str, user_value: float, entity_value: float) -> str:
    axis_idx = AXIS_SHORT.index(axis_name)
    user_pole = "zona bilanciata" if abs(user_value) < 0.15 else direction_label(axis_idx, user_value)
    entity_pole = "zona bilanciata" if abs(entity_value) < 0.15 else direction_label(axis_idx, entity_value)
    if abs(user_value - entity_value) <= 0.22:
        return f"Entrambi tendete verso {user_pole}."
    return f"Tu sei più vicino a {user_pole}; il riferimento tende di più verso {entity_pole}."


def compare_with_entity(profile: np.ndarray, name: str, limit: int = 3) -> dict[str, Any]:
    proto = np.array(PROTOTYPES.get(name, np.zeros(len(AXES))), dtype=float)
    rows = []
    for idx, axis in enumerate(AXIS_SHORT):
        user_value = float(profile[idx])
        entity_value = float(proto[idx])
        delta = abs(user_value - entity_value)
        rows.append(
            {
                "axis": axis,
                "user": round(user_value, 3),
                "entity": round(entity_value, 3),
                "delta": round(delta, 3),
                "text": axis_comparison_text(axis, user_value, entity_value),
            }
        )
    similar = sorted(rows, key=lambda row: (row["delta"], -abs(row["user"])))[:limit]
    different = sorted(rows, key=lambda row: row["delta"], reverse=True)[:limit]
    return {"similar": similar, "different": different}


def world_card(profile: np.ndarray, match: tuple[str, float, float] | dict[str, Any], kind: str) -> dict[str, Any]:
    if isinstance(match, dict):
        name = match["name"]
        distance = float(match.get("distance", 0))
        affinity = float(match.get("affinity", 0))
    else:
        name, distance, affinity = match
    meta = entity_metadata(name)
    comparison = compare_with_entity(profile, name)
    return {
        "kind": kind,
        "name": name,
        "distance": round(distance, 4),
        "affinity": round(affinity, 1),
        "brief": meta["brief"],
        "what_they_think": meta["brief"],
        "url": meta["url"],
        "source_label": meta["source_label"],
        "sources": meta.get("sources", []),
        "evidence": meta.get("evidence", "manual_prevalidation"),
        "basis": meta.get("basis", ""),
        "method_note": meta.get("note", ""),
        "high_risk": name in HISTORICAL_HIGH_RISK,
        "risk_note": HISTORICAL_METADATA.get(name, {}).get("note", ""),
        "similar": comparison["similar"],
        "different": comparison["different"],
    }


def build_political_world(
    profile: np.ndarray,
    ideology: tuple[str, float, float],
    parties: list[tuple[str, float, float]],
    historical: list[tuple[str, float, float]],
    historical_nemesis: list[tuple[str, float, float]],
) -> dict[str, Any]:
    ideology_card = world_card(profile, ideology, "ideologia") if ideology else None
    party = world_card(profile, parties[0], "partito") if parties else None
    figure = world_card(profile, historical[0], "storico") if historical else None
    nemesis = world_card(profile, historical_nemesis[0], "nemesi") if historical_nemesis else None
    return {
        "title": "Il tuo mondo politico",
        "summary": "Una lettura narrativa e spiegabile dei riferimenti più vicini e più lontani nel modello.",
        "ideology": ideology_card,
        "party": party,
        "historical": figure,
        "nemesis": nemesis,
        "note": "Questi confronti non sono consigli di voto né equivalenze morali: mostrano somiglianze e divergenze tra punti nello spazio a 8 assi. Le figure storiche estreme sono incluse ma segnalate come alto rischio interpretativo.",
    }


def historical_subset(include_extreme: bool = False) -> set[str]:
    return set(CAT_STORICI)


def interpret_profile(profile: np.ndarray) -> dict[str, str]:
    econ, auth, culture, geopolitics = profile[0], profile[1], profile[2], profile[3]

    if econ < -0.35 and auth < -0.25:
        family = "progressista libertario"
    elif econ < -0.35 and auth > 0.25:
        family = "statalista autoritario"
    elif econ > 0.35 and auth < -0.25:
        family = "liberale libertario"
    elif econ > 0.35 and auth > 0.25:
        family = "conservatore d'ordine"
    elif abs(econ) <= 0.25 and abs(auth) <= 0.25:
        family = "centrista pragmatico"
    else:
        family = "profilo ibrido"

    if culture < -0.30:
        culture_text = "culturalmente aperto"
    elif culture > 0.30:
        culture_text = "culturalmente tradizionale"
    else:
        culture_text = "culturalmente bilanciato"

    if geopolitics < -0.30:
        geopolitics_text = "internazionalista"
    elif geopolitics > 0.30:
        geopolitics_text = "sovranista"
    else:
        geopolitics_text = "pragmatico sui rapporti internazionali"

    return {
        "family": family,
        "culture": culture_text,
        "geopolitics": geopolitics_text,
    }


def build_result(answers: dict[str, int]) -> dict[str, Any]:
    missing = [q["id"] for q in QUESTIONS if q["id"] not in answers]
    if len(answers) < 12:
        raise ValueError("Servono almeno 12 risposte per calcolare un profilo minimamente stabile.")

    profile, axis_results, diagnostics = compute_profile_scientific(answers)
    completion_ratio = min(1.0, len(answers) / len(QUESTIONS))
    diagnostics["global_confidence"] = float(np.clip(diagnostics["global_confidence"] * (0.55 + 0.45 * completion_ratio), 0.0, 1.0))
    diagnostics["completion_ratio"] = completion_ratio
    ideologies = closest_prototypes_scientific(profile, axis_results, CAT_IDEOLOGIE, 3)
    ideology = ideologies[0]
    parties = closest_prototypes_scientific(profile, axis_results, CAT_PARTITI, 5)
    historical = closest_prototypes_scientific(profile, axis_results, historical_subset(), 5)
    historical_nemesis = closest_prototypes_scientific(profile, axis_results, historical_subset(), 3, reverse=True)
    historical_extreme_context = closest_prototypes_scientific(profile, axis_results, HISTORICAL_HIGH_RISK, 3)
    opponents = closest_prototypes_scientific(profile, axis_results, CAT_PARTITI, 3, reverse=True)
    interpretation = interpret_profile(profile)
    visuals = build_visuals(profile)
    self_coherence = build_self_coherence(answers, diagnostics)
    reliability = build_result_reliability(answers, diagnostics, self_coherence, ideologies, parties)
    uncertainty = build_uncertainty(axis_results, len(answers))
    report = build_report(profile, axis_results, ideology, parties, historical, historical_nemesis, opponents, interpretation, diagnostics, reliability)
    political_world = build_political_world(profile, ideology, parties, historical, historical_nemesis)
    report.insert(
        4,
        {
            "title": "Coerenza interna",
            "body": f"{self_coherence['label']} ({self_coherence['score']:.1f}%). {self_coherence['explanation']}",
        },
    )
    contributions = compute_question_contributions(answers)
    audit = build_model_audit()

    return {
        "model_version": MODEL_VERSION,
        "profile": [round(float(x), 4) for x in profile],
        "axes": [axis.__dict__ for axis in axis_results],
        "confidence": round(diagnostics["global_confidence"] * 100, 1),
        "self_coherence": self_coherence,
        "reliability": reliability,
        "uncertainty": uncertainty,
        "completion": round(completion_ratio * 100, 1),
        "answered_questions": len(answers),
        "total_questions": len(QUESTIONS),
        "contradictions": diagnostics["contradictions"],
        "interpretation": interpretation,
        "ideology": {"name": ideology[0], "distance": round(ideology[1], 4), "affinity": round(ideology[2], 1)},
        "ideologies": [{"name": x[0], "distance": round(x[1], 4), "affinity": round(x[2], 1)} for x in ideologies],
        "parties": [{"name": x[0], "distance": round(x[1], 4), "affinity": round(x[2], 1)} for x in parties],
        "historical": [{"name": x[0], "distance": round(x[1], 4), "affinity": round(x[2], 1)} for x in historical],
        "historical_nemesis": [{"name": x[0], "distance": round(x[1], 4), "affinity": round(x[2], 1), "metadata": HISTORICAL_METADATA.get(x[0], {})} for x in historical_nemesis],
        "historical_extreme_context": [{"name": x[0], "distance": round(x[1], 4), "affinity": round(x[2], 1), "metadata": HISTORICAL_METADATA.get(x[0], {})} for x in historical_extreme_context],
        "opponents": [{"name": x[0], "distance": round(x[1], 4), "affinity": round(x[2], 1)} for x in opponents],
        "political_world": political_world,
        "visuals": visuals,
        "report": report,
        "education": EDUCATION_SECTIONS,
        "curiosities": CURIOSITIES,
        "top_contributions": contributions[:12],
        "model_audit": audit,
        "sources": SOURCE_REFERENCES,
        "calibration": CALIBRATION_NOTES,
        "method": diagnostics["method"],
    }


def prototype_category(name: str) -> str:
    if name in CAT_PARTITI:
        return "partito"
    if name in CAT_IDEOLOGIE:
        return "ideologia"
    if name in CAT_STORICI:
        return "storico"
    return "altro"


def build_visuals(profile: np.ndarray) -> dict[str, Any]:
    names = list(PROTOTYPES.keys())
    matrix = np.array([PROTOTYPES[name] for name in names])
    scaler = StandardScaler()
    scaled = scaler.fit_transform(matrix)
    user_scaled = scaler.transform(profile.reshape(1, -1))
    pca = PCA(n_components=2)
    coords = pca.fit_transform(scaled)
    user_xy = pca.transform(user_scaled)[0]

    points = []
    for idx, name in enumerate(names):
        points.append(
            {
                "name": name,
                "x": round(float(coords[idx, 0]), 4),
                "y": round(float(coords[idx, 1]), 4),
                "category": prototype_category(name),
                "high_risk": name in HISTORICAL_HIGH_RISK,
            }
        )

    return {
        "axis_poles": [
            {"axis": "Economia", "negative": "welfare / redistribuzione", "positive": "mercato / privatizzazioni"},
            {"axis": "Autorità", "negative": "libertà individuale", "positive": "ordine / controllo"},
            {"axis": "Cultura", "negative": "pluralismo / diritti", "positive": "tradizione / religione"},
            {"axis": "Geopolitica", "negative": "cooperazione", "positive": "sovranità nazionale"},
            {"axis": "Ambiente", "negative": "transizione verde", "positive": "crescita industriale"},
            {"axis": "Tecnologia", "negative": "regolazione prudente", "positive": "innovazione rapida"},
            {"axis": "Uguaglianza", "negative": "pari condizioni", "positive": "gerarchie / competizione"},
            {"axis": "Giustizia", "negative": "recupero", "positive": "punizione / deterrenza"},
        ],
        "pca": {
            "explained_variance": [round(float(x), 4) for x in pca.explained_variance_ratio_],
            "user": {"x": round(float(user_xy[0]), 4), "y": round(float(user_xy[1]), 4)},
            "points": points,
        },
    }


def build_model_audit() -> dict[str, Any]:
    question_audit = [audit_question(question) for question in QUESTIONS]
    status_counts = {
        "ok": sum(1 for item in question_audit if item["status"] == "ok"),
        "review": sum(1 for item in question_audit if item["status"] == "review"),
        "critical": sum(1 for item in question_audit if item["status"] == "critical"),
    }
    axis_coverage = []
    for axis_idx, axis in enumerate(AXIS_SHORT):
        covering = [
            question["id"]
            for question in QUESTIONS
            if abs(float(question["weights"][axis_idx])) > 0.05
        ]
        axis_coverage.append({"axis": axis, "questions": len(covering)})

    return {
        "question_status_counts": status_counts,
        "axis_coverage": axis_coverage,
        "v5_content_checks": {
            "max_active_axes": max(item["active_axes_count"] for item in question_audit),
            "questions_with_primary_dominance_issue": sum("primary_not_dominant" in item["issues"] for item in question_audit),
            "questions_with_loaded_language_markers": sum(bool(item["content_risk"]["loaded_terms"]) for item in question_audit),
            "questions_with_medium_or_high_complexity": sum(item["content_risk"]["linguistic_complexity"] in {"media", "alta"} for item in question_audit),
            "note": "Controlli euristici V5: servono per audit interno e non sostituiscono validazione psicometrica.",
        },
        "quick_question_ids": QUICK_QUESTION_IDS,
        "social_question_ids": SOCIAL_QUESTION_IDS,
        "calibration": CALIBRATION_NOTES,
        "entity_registry": ENTITY_REGISTRY_INFO,
        "questions_to_review": [item for item in question_audit if item["status"] != "ok"][:12],
        "prototype_status": [
            {"group": "Ideologie", "count": len(CAT_IDEOLOGIE), "status": "manual_v2_prevalidation", "next_step": "Validare con letteratura politica, revisione esperta e dati utenti."},
            {"group": "Partiti", "count": len(CAT_PARTITI), "status": "manual_v2_prevalidation", "next_step": "Calibrare con CHES, Manifesto Project, V-Party e programmi aggiornati."},
            {"group": "Storici comparabili", "count": len(historical_subset()), "status": "interpretive_v2", "next_step": "Validare per periodo, regime, asse economico e asse libertà/autorità."},
            {"group": "Storici ad alto rischio interpretativo", "count": len(HISTORICAL_HIGH_RISK), "status": "caution", "next_step": "Mostrare con avviso esplicito: distanza geometrica, non equivalenza morale o biografica."},
        ],
    }


def image_to_data_url(buffer: io.BytesIO) -> str:
    buffer.seek(0)
    data = base64.b64encode(buffer.read()).decode("ascii")
    return f"data:image/png;base64,{data}"


def build_charts(
    profile: np.ndarray,
    ideology: tuple[str, float, float],
    parties: list[tuple[str, float, float]],
    historical: list[tuple[str, float, float]],
    opponents: list[tuple[str, float, float]],
) -> dict[str, str]:
    _, bar = legacy.make_bar_chart(profile)
    _, radar = legacy.make_radar_chart(profile)
    _, pca_all = legacy.make_pca_map(profile, "Tutti")
    _, pca_parties = legacy.make_pca_map(profile, "Solo Partiti")
    _, pca_ideologies = legacy.make_pca_map(profile, "Solo Ideologie")
    _, pca_historical = legacy.make_pca_map(profile, "Solo Storici")

    social_top_id = (ideology[0], ideology[1])
    social_parties = [(name, dist) for name, dist, _ in parties[:3]]
    worst_historical = (historical[-1][0], historical[-1][1]) if historical else (opponents[0][0], opponents[0][1])
    _, social = legacy.make_social_card(profile, social_top_id, social_parties, worst_historical)

    return {
        "bar": image_to_data_url(bar),
        "radar": image_to_data_url(radar),
        "pca_all": image_to_data_url(pca_all),
        "pca_parties": image_to_data_url(pca_parties),
        "pca_ideologies": image_to_data_url(pca_ideologies),
        "pca_historical": image_to_data_url(pca_historical),
        "social": image_to_data_url(social),
    }


def build_report(
    profile: np.ndarray,
    axis_results: list[AxisResult],
    ideology: tuple[str, float, float],
    parties: list[tuple[str, float, float]],
    historical: list[tuple[str, float, float]],
    historical_nemesis: list[tuple[str, float, float]],
    opponents: list[tuple[str, float, float]],
    interpretation: dict[str, str],
    diagnostics: dict[str, Any],
    reliability: dict[str, Any],
) -> list[dict[str, Any]]:
    strongest = max(axis_results, key=lambda axis: abs(axis.value))
    weakest = min(axis_results, key=lambda axis: abs(axis.value))
    return [
        {
            "title": "Lettura sintetica",
            "body": (
                f"Il profilo cade nell'area {interpretation['family']}, con orientamento "
                f"{interpretation['culture']} e postura {interpretation['geopolitics']}. "
                f"Il modello lo associa soprattutto a {ideology[0]}."
            ),
        },
        {
            "title": "Asse più forte",
            "body": f"{strongest.name}: {strongest.value:+.2f}. Questo è il tema dove le risposte hanno prodotto il segnale più netto.",
        },
        {
            "title": "Asse più equilibrato",
            "body": f"{weakest.name}: {weakest.value:+.2f}. Qui il risultato è più vicino al centro o più misto.",
        },
        {
            "title": "Confidenza del risultato",
            "body": (
                f"Confidenza globale {diagnostics['global_confidence'] * 100:.1f}%. "
                "Tiene conto di copertura degli assi, chiarezza delle risposte e possibili contraddizioni tematiche."
            ),
        },
        {
            "title": "Affidabilità interpretativa",
            "body": f"{reliability['label']} ({reliability['score']:.1f}%). {reliability['explanation']}",
        },
        {
            "title": "Partiti più vicini",
            "body": ", ".join(f"{name} ({affinity:.0f}%)" for name, _, affinity in parties[:3]),
        },
        {
            "title": "Confronto storico",
            "body": ", ".join(f"{name} ({affinity:.0f}%)" for name, _, affinity in historical[:3]),
        },
        {
            "title": "Nemesi storica metodologica",
            "body": (
                ", ".join(f"{name} (distanza {dist:.2f})" for name, dist, _ in historical_nemesis[:3])
                + ". Se compaiono figure estreme, sono marcate come alto rischio interpretativo: non sono equivalenze morali."
            ),
        },
        {
            "title": "Distanze maggiori",
            "body": ", ".join(f"{name} ({affinity:.0f}%)" for name, _, affinity in opponents[:3]),
        },
    ]


EDUCATION_SECTIONS = [
    {
        "title": "Come funziona il Politometro",
        "body": "Il profilo viene calcolato su 8 dimensioni indipendenti: Economia, Autorità, Cultura, Geopolitica, Ambiente, Tecnologia, Uguaglianza e Giustizia.",
    },
    {
        "title": "Normalizzazione delle risposte",
        "body": "Ogni risposta da 1 a 7 viene trasformata in un valore da -1 a +1. Il valore 4 è il centro, cioè equilibrio o neutralità.",
    },
    {
        "title": "Pesi per asse",
        "body": "Ogni domanda pesa in modo diverso sugli assi. Una domanda sulla sanità pesa molto su Economia; una domanda sulla pena di morte pesa molto su Giustizia e Autorità.",
    },
    {
        "title": "Aggregazione",
        "body": "Le risposte normalizzate vengono combinate tramite media ponderata. Nella nuova versione i pesi vengono normalizzati per evitare che le domande con molti assi attivi dominino troppo.",
    },
    {
        "title": "Match con partiti e ideologie",
        "body": "Il profilo finale è un punto in uno spazio a 8 dimensioni. Lo confrontiamo con prototipi di ideologie, partiti e figure storiche misurando la distanza.",
    },
    {
        "title": "Mappa PCA",
        "body": "La mappa comprime lo spazio politico da 8 dimensioni a 2 dimensioni. È utile per orientarsi, ma perde una parte dell'informazione.",
    },
    {
        "title": "Privacy",
        "body": "La versione locale non manda le risposte a un server esterno: il calcolo gira nel tuo ambiente Codex.",
    },
]


CURIOSITIES = [
    "Due persone con la stessa ideologia dominante possono avere profili molto diversi sugli assi secondari.",
    "Un risultato vicino al centro non significa per forza moderazione: può anche indicare risposte molto polarizzate che si compensano.",
    "La mappa PCA è una fotografia semplificata: i grafici a barre e radar sono più fedeli al profilo completo.",
    "Le affinità con partiti e storici non equivalgono a un consiglio di voto: misurano somiglianza geometrica nel modello.",
    "La confidenza bassa è un'informazione utile, non un errore: segnala che servono domande migliori o risposte meno ambigue.",
]
