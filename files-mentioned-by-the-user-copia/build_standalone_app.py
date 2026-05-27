from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

import politometro_custom_app as webapp
from politometro_scientific import (
    AXIS_EXPLANATIONS,
    AXIS_SHORT,
    CALIBRATION_NOTES,
    CAT_IDEOLOGIE,
    CAT_PARTITI,
    CAT_STORICI,
    CONTRADICTION_GROUPS,
    CONTRADICTION_GROUP_LABELS,
    CURIOSITIES,
    EDUCATION_SECTIONS,
    ENTITY_WORLD_METADATA,
    HISTORICAL_HIGH_RISK,
    HISTORICAL_METADATA,
    MODEL_VERSION,
    PROTOTYPES,
    QUICK_QUESTION_IDS,
    SOCIAL_QUESTION_IDS,
    QUESTIONS,
    SOURCE_REFERENCES,
    build_model_audit,
    item_discrimination,
    question_loading,
)


OUT_APP = Path("politometro_standalone.html")
OUT_ADMIN = Path("politometro_admin_standalone.html")
OUT_MANIFEST = Path("manifest.webmanifest")
OUT_ICON = Path("icon.svg")
OUT_ICON_192 = Path("icon-192.png")
OUT_ICON_512 = Path("icon-512.png")
OUT_SW = Path("sw.js")


def category(name: str) -> str:
    if name in CAT_PARTITI:
        return "partito"
    if name in CAT_IDEOLOGIE:
        return "ideologia"
    if name in CAT_STORICI:
        return "storico"
    return "altro"


def write_png_icon(path: Path, size: int) -> None:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (size, size), "#10242f")
    draw = ImageDraw.Draw(img)
    margin = int(size * 0.105)
    draw.rounded_rectangle([margin, margin, size - margin, size - margin], radius=int(size * 0.18), fill="#38a3a5")
    draw.pieslice([margin, margin, size - margin, size - margin], 35, 145, fill="#f2b880")
    draw.pieslice([margin, margin, size - margin, size - margin], 145, 265, fill="#6d597a")
    draw.pieslice([margin, margin, size - margin, size - margin], 265, 395, fill="#38a3a5")
    cx = cy = size // 2
    draw.ellipse([cx - int(size * .245), cy - int(size * .245), cx + int(size * .245), cy + int(size * .245)], fill="#10242f")
    outer = int(size * 0.20)
    inner = int(size * 0.070)
    draw.polygon([(cx, cy - outer), (cx + inner, cy - inner), (cx, cy), (cx - inner, cy - inner)], fill="#f6f8f8")
    draw.polygon([(cx + outer, cy), (cx + inner, cy + inner), (cx, cy), (cx + inner, cy - inner)], fill="#f6f8f8")
    draw.polygon([(cx, cy + outer), (cx - inner, cy + inner), (cx, cy), (cx + inner, cy + inner)], fill="#f6f8f8")
    draw.polygon([(cx - outer, cy), (cx - inner, cy - inner), (cx, cy), (cx - inner, cy + inner)], fill="#f6f8f8")
    dot = int(size * 0.074)
    draw.ellipse([cx - dot, cy - dot, cx + dot, cy + dot], fill="#10242f")
    dot2 = int(size * 0.04)
    draw.ellipse([cx - dot2, cy - dot2, cx + dot2, cy + dot2], fill="#f2b880")
    img.save(path, "PNG", optimize=True)


def make_data() -> dict:
    names = list(PROTOTYPES.keys())
    matrix = np.array([PROTOTYPES[name] for name in names], dtype=float)
    scaler = StandardScaler()
    scaled = scaler.fit_transform(matrix)
    pca = PCA(n_components=2)
    coords = pca.fit_transform(scaled)

    questions = []
    for q in QUESTIONS:
        enriched = dict(q)
        enriched["loading"] = [round(float(x), 8) for x in question_loading(q)]
        enriched["discrimination"] = round(float(item_discrimination(q)), 8)
        questions.append(enriched)

    return {
        "model_version": MODEL_VERSION + "-standalone",
        "quick_question_ids": QUICK_QUESTION_IDS,
        "social_question_ids": SOCIAL_QUESTION_IDS,
        "calibration": CALIBRATION_NOTES,
        "axis_short": list(AXIS_SHORT),
        "axis_explanations": dict(AXIS_EXPLANATIONS),
        "questions": questions,
        "prototypes": {name: [float(x) for x in PROTOTYPES[name]] for name in names},
        "categories": {
            "ideologie": list(CAT_IDEOLOGIE),
            "partiti": list(CAT_PARTITI),
            "storici": list(CAT_STORICI),
            "storici_estremi": list(HISTORICAL_HIGH_RISK),
        },
        "historical_metadata": HISTORICAL_METADATA,
        "contradiction_groups": CONTRADICTION_GROUPS,
        "contradiction_group_labels": CONTRADICTION_GROUP_LABELS,
        "education": EDUCATION_SECTIONS,
        "curiosities": CURIOSITIES,
        "sources": SOURCE_REFERENCES,
        "entity_world": ENTITY_WORLD_METADATA,
        "model_audit": build_model_audit(),
        "pca_model": {
            "mean": [float(x) for x in scaler.mean_],
            "scale": [float(x) for x in scaler.scale_],
            "pca_mean": [float(x) for x in pca.mean_],
            "components": [[float(x) for x in row] for row in pca.components_],
            "explained_variance": [float(x) for x in pca.explained_variance_ratio_],
            "points": [
                {
                    "name": name,
                    "x": round(float(coords[idx, 0]), 4),
                    "y": round(float(coords[idx, 1]), 4),
                    "category": category(name),
                    "high_risk": name in HISTORICAL_HIGH_RISK,
                }
                for idx, name in enumerate(names)
            ],
        },
    }


def standalone_script(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"""
    const STANDALONE_DATA = {payload};
    const STANDALONE_KEYS = {{
      samples: "politometro.samples.v3",
      feedback: "politometro.feedback.v3",
      support: "politometro.support.v1"
    }};
    const nativeFetch = window.fetch.bind(window);
    const STANDALONE_MEMORY_STORE = {{}};

    function standaloneJson(data, status = 200) {{
      return new Response(JSON.stringify(data), {{ status, headers: {{ "Content-Type": "application/json" }} }});
    }}

    function standaloneStorage() {{
      try {{
        const storage = window.localStorage;
        const probe = "__politometro_probe__";
        storage.setItem(probe, "1");
        storage.removeItem(probe);
        return storage;
      }} catch (_) {{
        return null;
      }}
    }}

    const STANDALONE_STORAGE = standaloneStorage();

    function standaloneStorageLabel() {{
      return STANDALONE_STORAGE ? "localStorage" : "memoria temporanea del browser (localStorage bloccato)";
    }}

    function standaloneRead(key) {{
      try {{
        const raw = STANDALONE_STORAGE ? STANDALONE_STORAGE.getItem(key) : STANDALONE_MEMORY_STORE[key];
        return JSON.parse(raw || "[]");
      }}
      catch (_) {{ return []; }}
    }}

    function standaloneWrite(key, rows) {{
      const value = JSON.stringify(rows);
      try {{
        if (STANDALONE_STORAGE) STANDALONE_STORAGE.setItem(key, value);
        else STANDALONE_MEMORY_STORE[key] = value;
      }} catch (_) {{
        STANDALONE_MEMORY_STORE[key] = value;
      }}
    }}

    function standaloneNormalize(value) {{
      return (Number(value) - 4) / 3;
    }}

    function standaloneNorm(values) {{
      return Math.sqrt(values.reduce((sum, value) => sum + value * value, 0));
    }}

    function standaloneClip(value, low, high) {{
      return Math.max(low, Math.min(high, value));
    }}

    function standaloneRound(value, digits = 4) {{
      const scale = Math.pow(10, digits);
      return Math.round(value * scale) / scale;
    }}

    function standaloneMean(values) {{
      const clean = values.filter((x) => Number.isFinite(x));
      if (!clean.length) return null;
      return clean.reduce((a, b) => a + b, 0) / clean.length;
    }}

    function standaloneQuestionMap() {{
      return Object.fromEntries(STANDALONE_DATA.questions.map((q) => [q.id, q]));
    }}

    function standaloneComputeProfile(answers) {{
      const axisCount = STANDALONE_DATA.axis_short.length;
      const scores = Array(axisCount).fill(0);
      const totals = Array(axisCount).fill(0);
      const absAnswers = Array.from({{ length: axisCount }}, () => []);
      const qmap = standaloneQuestionMap();
      for (const q of STANDALONE_DATA.questions) {{
        if (!(q.id in answers)) continue;
        const response = standaloneNormalize(answers[q.id]);
        const loading = q.loading;
        const discrimination = Number(q.discrimination || 1);
        for (let i = 0; i < axisCount; i++) {{
          const weight = Number(loading[i] || 0);
          if (Math.abs(weight) <= 1e-9) continue;
          scores[i] += response * weight * discrimination;
          totals[i] += Math.abs(weight) * discrimination;
          absAnswers[i].push(Math.abs(response));
        }}
      }}
      const profile = scores.map((score, i) => totals[i] > 0 ? standaloneClip(score / totals[i], -1, 1) : 0);
      const maxTotal = Math.max(1, ...totals);
      const axes = STANDALONE_DATA.axis_short.map((name, i) => {{
        const coverage = standaloneClip(totals[i] / maxTotal, 0, 1);
        const clarity = standaloneMean(absAnswers[i]) || 0;
        const confidence = standaloneClip(0.55 * coverage + 0.45 * clarity, 0, 1);
        return {{
          name,
          value: standaloneRound(profile[i], 4),
          confidence: standaloneRound(confidence, 4),
          coverage: standaloneRound(coverage, 4),
          clarity: standaloneRound(clarity, 4),
          explanation: STANDALONE_DATA.axis_explanations[name] || ""
        }};
      }});
      const contradictions = standaloneDetectContradictions(answers, qmap);
      let globalConfidence = axes.reduce((sum, axis) => sum + axis.confidence, 0) / axes.length;
      globalConfidence = standaloneClip(globalConfidence - Math.min(0.25, 0.04 * contradictions.length), 0, 1);
      return {{ profile, axes, contradictions, globalConfidence }};
    }}

    function standaloneDetectContradictions(answers, qmap) {{
      const issues = [];
      for (const [group, ids] of STANDALONE_DATA.contradiction_groups) {{
        const values = [];
        const labels = [];
        for (const id of ids) {{
          if (!(id in answers) || !qmap[id]) continue;
          values.push(standaloneNormalize(answers[id]));
          labels.push(qmap[id].question);
        }}
        if (values.length < 3) continue;
        const spread = Math.max(...values) - Math.min(...values);
        if (spread >= 1.55) {{
          issues.push({{
            group,
            spread: standaloneRound(spread, 4),
            questions: labels,
            message: "Risposte molto polarizzate nello stesso blocco tematico: risultato meno stabile su questo tema."
          }});
        }}
      }}
      return issues;
    }}

    function standaloneBuildSelfCoherence(answers, contradictions) {{
      const axisRows = [];
      const axisValues = STANDALONE_DATA.axis_short.map(() => []);
      const axisWeights = STANDALONE_DATA.axis_short.map(() => []);
      for (const q of STANDALONE_DATA.questions) {{
        if (!(q.id in answers)) continue;
        const response = standaloneNormalize(answers[q.id]);
        const loading = q.loading || [];
        const discrimination = Number(q.discrimination || 1);
        for (let i = 0; i < STANDALONE_DATA.axis_short.length; i++) {{
          const weight = Number(loading[i] || 0);
          if (Math.abs(weight) <= 0.08) continue;
          axisValues[i].push(response * (weight >= 0 ? 1 : -1));
          axisWeights[i].push(Math.abs(weight) * discrimination);
        }}
      }}
      for (let i = 0; i < axisValues.length; i++) {{
        const values = axisValues[i];
        if (values.length < 2) continue;
        const rawWeights = axisWeights[i].map((w) => Number(w || 0));
        const fallbackWeight = 1 / values.length;
        const weights = rawWeights.map((w) => w || fallbackWeight);
        const weightSum = weights.reduce((sum, w) => sum + w, 0) || 1;
        const mean = values.reduce((sum, value, idx) => sum + value * weights[idx], 0) / weightSum;
        const variance = values.reduce((sum, value, idx) => sum + ((value - mean) ** 2) * weights[idx], 0) / weightSum;
        const std = Math.sqrt(Math.max(0, variance));
        let posWeight = 0;
        let negWeight = 0;
        for (let idx = 0; idx < values.length; idx++) {{
          if (Math.abs(values[idx]) <= 0.22) continue;
          if (values[idx] > 0) posWeight += weights[idx];
          if (values[idx] < 0) negWeight += weights[idx];
        }}
        const activeWeight = posWeight + negWeight;
        const flipShare = activeWeight ? Math.min(posWeight, negWeight) / activeWeight : 0;
        const dispersionScore = standaloneClip(1 - std / 0.82, 0, 1);
        const directionScore = standaloneClip(1 - flipShare * 1.65, 0, 1);
        const axisScore = standaloneClip(0.70 * dispersionScore + 0.30 * directionScore, 0, 1);
        axisRows.push({{
          group: `axis_${{STANDALONE_DATA.axis_short[i].toLowerCase()}}`,
          type: "axis",
          label: STANDALONE_DATA.axis_short[i],
          score: standaloneRound(axisScore * 100, 1),
          spread: standaloneRound(Math.max(...values) - Math.min(...values), 3),
          mean: standaloneRound(mean, 3),
          items: values.length
        }});
      }}
      const rows = [];
      for (const [group, ids] of STANDALONE_DATA.contradiction_groups) {{
        const values = ids
          .filter((id) => id in answers)
          .map((id) => standaloneNormalize(answers[id]));
        if (values.length < 3) continue;
        const spread = Math.max(...values) - Math.min(...values);
        const groupScore = standaloneClip(1 - Math.max(0, spread - 0.75) / 1.25, 0, 1);
        rows.push({{
          group,
          type: "theme",
          label: STANDALONE_DATA.contradiction_group_labels[group] || group.replaceAll("_", " "),
          score: standaloneRound(groupScore * 100, 1),
          spread: standaloneRound(spread, 3),
          items: values.length
        }});
      }}
      const axisScore = axisRows.length ? standaloneMean(axisRows.map((row) => row.score)) / 100 : 0.72;
      const themeScore = rows.length ? standaloneMean(rows.map((row) => row.score)) / 100 : axisScore;
      const completionScore = Math.min(1, Object.keys(answers).length / 20);
      const severePenalty = Math.min(0.36, contradictions.length * 0.12);
      const score = standaloneRound(standaloneClip((0.62 * axisScore + 0.24 * themeScore + 0.09 * completionScore + 0.05) - severePenalty, 0, 1) * 100, 1);
      const neutralAnswers = Object.values(answers).filter((value) => Number(value) === 4).length;
      const comparableRows = [...axisRows, ...rows].sort((a, b) => a.score - b.score);
      const strongestTension = comparableRows.length ? comparableRows[0] : null;
      let label = "Instabile";
      let explanation = "Le risposte tirano spesso in direzioni diverse dentro gli stessi temi.";
      if (score >= 85) {{
        label = "Molto alta";
        explanation = "Le risposte restano molto compatibili tra loro sugli assi e nei principali blocchi tematici.";
      }} else if (score >= 70) {{
        label = "Buona";
        explanation = "Il profilo è abbastanza stabile: ci sono sfumature, ma poche tensioni interne forti.";
      }} else if (score >= 55) {{
        label = "Media";
        explanation = "Il profilo contiene alcune tensioni interne: il risultato va letto con più prudenza.";
      }}
      const signals = [
        `Tensioni forti rilevate: ${{contradictions.length}}.`,
        `Risposte centrali: ${{neutralAnswers}} su ${{Object.keys(answers).length}}; il centro non è penalizzato, viene letto come prudenza o equilibrio.`,
        `Blocchi tematici confrontabili: ${{rows.length}}.`,
        `Assi confrontabili: ${{axisRows.length}}.`
      ];
      if (strongestTension) signals.push(`Area più tesa: ${{strongestTension.label}} (spread ${{strongestTension.spread}}).`);
      return {{
        score,
        label,
        explanation,
        signals,
        neutral_answers: neutralAnswers,
        contradiction_count: contradictions.length,
        groups: comparableRows,
        axis_groups: axisRows.sort((a, b) => a.score - b.score),
        theme_groups: rows.sort((a, b) => a.score - b.score)
      }};
    }}

    function standaloneAffinityGap(matches) {{
      if (!matches || matches.length < 2) return 100;
      return Math.max(0, Number(matches[0].affinity || 0) - Number(matches[1].affinity || 0));
    }}

    function standaloneBuildReliability(answers, confidence, selfCoherence, ideologies, parties, contradictions) {{
      const answered = Object.keys(answers).length;
      const neutralAnswers = Object.values(answers).filter((value) => Number(value) === 4).length;
      const neutralShare = answered ? neutralAnswers / answered : 1;
      const completionScore = Math.min(100, answered / STANDALONE_DATA.questions.length * 100);
      const coherenceScore = Number(selfCoherence?.score || 0);
      const ideologyGap = standaloneAffinityGap(ideologies);
      const partyGap = standaloneAffinityGap(parties);
      const matchSeparationScore = Math.min(100, Math.max(ideologyGap, partyGap) * 8);
      const neutralPenalty = Math.max(0, neutralShare - 0.34) * 42;
      const contradictionPenalty = Math.min(22, (contradictions || []).length * 5);
      const score = standaloneRound(standaloneClip(
        0.42 * Number(confidence || 0)
        + 0.22 * coherenceScore
        + 0.16 * completionScore
        + 0.20 * matchSeparationScore
        - neutralPenalty
        - contradictionPenalty,
        0,
        100
      ), 1);
      let label = "Bassa";
      let explanation = "Il risultato è esplorativo: troppe risposte centrali, tensioni interne o match molto ravvicinati riducono la stabilità.";
      if (score >= 76) {{
        label = "Alta";
        explanation = "Il risultato è abbastanza stabile: assi coperti, poche tensioni forti e riferimenti principali sufficientemente separati.";
      }} else if (score >= 58) {{
        label = "Media";
        explanation = "Il risultato è leggibile ma va interpretato con prudenza: alcune risposte o confronti sono vicini tra loro.";
      }}
      return {{
        type: "heuristic_v5",
        score,
        label,
        explanation,
        neutral_share: standaloneRound(neutralShare, 3),
        ideology_gap: standaloneRound(ideologyGap, 1),
        party_gap: standaloneRound(partyGap, 1),
        signals: [
          `Confidenza tecnica: ${{Number(confidence || 0).toFixed(1)}}%.`,
          `Coerenza interna: ${{coherenceScore.toFixed(1)}}%.`,
          `Risposte centrali: ${{neutralAnswers}} su ${{answered}}.`,
          `Differenza tra le ideologie più vicine: ${{ideologyGap.toFixed(1)}} punti di affinità.`,
          `Differenza tra i partiti più vicini: ${{partyGap.toFixed(1)}} punti di affinità.`,
          `Tensioni forti rilevate: ${{(contradictions || []).length}}.`
        ],
        note: "Affidabilità euristica: non è ancora un intervallo statistico validato. Diventerà più solida con test-retest, campioni normativi e benchmark esterni."
      }};
    }}

    function standaloneBuildUncertainty(axes, answeredCount) {{
      const modePenalty = answeredCount < STANDALONE_DATA.questions.length ? 0.06 : 0;
      return {{
        type: "heuristic",
        note: "Intervalli euristici: indicano prudenza interpretativa in base a copertura, chiarezza e numero di risposte. Diventeranno intervalli statistici veri solo con dati test-retest e campioni normativi.",
        axes: axes.map((axis) => {{
          const margin = standaloneClip(0.10 + (1 - axis.confidence) * 0.34 + modePenalty, 0.10, 0.55);
          return {{
            axis: axis.name,
            value: standaloneRound(axis.value, 3),
            low: standaloneRound(standaloneClip(axis.value - margin, -1, 1), 3),
            high: standaloneRound(standaloneClip(axis.value + margin, -1, 1), 3),
            margin: standaloneRound(margin, 3)
          }};
        }})
      }};
    }}

    function standaloneWeightedDistance(profile, prototype, axes) {{
      let sum = 0;
      for (let i = 0; i < profile.length; i++) {{
        const confidence = Math.max(0.25, Number(axes[i]?.confidence || 0));
        const delta = (profile[i] - prototype[i]) * confidence;
        sum += delta * delta;
      }}
      return Math.sqrt(sum);
    }}

    function standaloneClosest(profile, axes, subset, topN = 3, reverse = false) {{
      const allowed = subset ? new Set(subset) : null;
      const maxDistance = Math.sqrt(STANDALONE_DATA.axis_short.length) * 2;
      const matches = Object.entries(STANDALONE_DATA.prototypes)
        .filter(([name]) => !allowed || allowed.has(name))
        .map(([name, proto]) => {{
          const distance = standaloneWeightedDistance(profile, proto, axes);
          const affinity = standaloneClip(100 * (1 - distance / maxDistance), 0, 100);
          return {{ name, distance: standaloneRound(distance, 4), affinity: standaloneRound(affinity, 1) }};
        }})
        .sort((a, b) => reverse ? b.distance - a.distance : a.distance - b.distance);
      return matches.slice(0, topN);
    }}

    function standaloneInterpret(profile) {{
      const [econ, auth, culture, geopolitics] = profile;
      let family = "profilo ibrido";
      if (econ < -0.35 && auth < -0.25) family = "progressista libertario";
      else if (econ < -0.35 && auth > 0.25) family = "statalista autoritario";
      else if (econ > 0.35 && auth < -0.25) family = "liberale libertario";
      else if (econ > 0.35 && auth > 0.25) family = "conservatore d'ordine";
      else if (Math.abs(econ) <= 0.25 && Math.abs(auth) <= 0.25) family = "centrista pragmatico";
      const cultureText = culture < -0.30 ? "culturalmente aperto" : culture > 0.30 ? "culturalmente tradizionale" : "culturalmente bilanciato";
      const geopoliticsText = geopolitics < -0.30 ? "internazionalista" : geopolitics > 0.30 ? "sovranista" : "pragmatico sui rapporti internazionali";
      return {{ family, culture: cultureText, geopolitics: geopoliticsText }};
    }}

    function standaloneProject(profile) {{
      const m = STANDALONE_DATA.pca_model;
      const scaled = profile.map((value, i) => (value - m.mean[i]) / (m.scale[i] || 1));
      const centered = scaled.map((value, i) => value - m.pca_mean[i]);
      return {{
        x: standaloneRound(centered.reduce((sum, value, i) => sum + value * m.components[0][i], 0), 4),
        y: standaloneRound(centered.reduce((sum, value, i) => sum + value * m.components[1][i], 0), 4)
      }};
    }}

    function standaloneDirection(axisIdx, value) {{
      if (Math.abs(value) < 0.02) return "neutro";
      const neg = ["welfare / redistribuzione", "libertà individuale", "apertura sociale", "cooperazione internazionale", "transizione verde", "regolazione cauta", "pari condizioni", "recupero sociale"];
      const pos = ["mercato / privatizzazioni", "ordine e controllo", "tradizione", "sovranità nazionale", "crescita industriale", "innovazione rapida", "gerarchie / competizione", "deterrenza / punizione"];
      return value > 0 ? pos[axisIdx] : neg[axisIdx];
    }}

    function standaloneEntityMetadata(name) {{
      const known = STANDALONE_DATA.entity_world?.[name];
      if (known) return known;
      return {{
        brief: "Riferimento usato come prototipo nel modello: la somiglianza è geometrica sugli 8 assi, non un'identificazione totale.",
        url: `https://it.wikipedia.org/wiki/${{encodeURIComponent(String(name).replaceAll(" ", "_"))}}`,
        source_label: "Wikipedia / approfondimento",
        evidence: "manual_prevalidation",
        basis: "Coordinate teoriche assegnate manualmente: da validare con fonti esterne, revisione esperta e dati utenti consensuali.",
        note: "Confronto interpretativo sugli 8 assi: non è un consiglio di voto né un'identificazione personale.",
        sources: [{{ label: "Wikipedia / approfondimento", url: `https://it.wikipedia.org/wiki/${{encodeURIComponent(String(name).replaceAll(" ", "_"))}}` }}]
      }};
    }}

    function standaloneAxisWorldText(axisIdx, userValue, entityValue) {{
      const userPole = Math.abs(userValue) < 0.15 ? "zona bilanciata" : standaloneDirection(axisIdx, userValue);
      const entityPole = Math.abs(entityValue) < 0.15 ? "zona bilanciata" : standaloneDirection(axisIdx, entityValue);
      if (Math.abs(userValue - entityValue) <= 0.22) return `Entrambi tendete verso ${{userPole}}.`;
      return `Tu sei più vicino a ${{userPole}}; il riferimento tende di più verso ${{entityPole}}.`;
    }}

    function standaloneCompareEntity(profile, name, limit = 3) {{
      const proto = STANDALONE_DATA.prototypes[name] || new Array(STANDALONE_DATA.axis_short.length).fill(0);
      const rows = STANDALONE_DATA.axis_short.map((axis, idx) => {{
        const userValue = Number(profile[idx] || 0);
        const entityValue = Number(proto[idx] || 0);
        const delta = Math.abs(userValue - entityValue);
        return {{
          axis,
          user: standaloneRound(userValue, 3),
          entity: standaloneRound(entityValue, 3),
          delta: standaloneRound(delta, 3),
          text: standaloneAxisWorldText(idx, userValue, entityValue)
        }};
      }});
      return {{
        similar: [...rows].sort((a, b) => a.delta - b.delta || Math.abs(b.user) - Math.abs(a.user)).slice(0, limit),
        different: [...rows].sort((a, b) => b.delta - a.delta).slice(0, limit)
      }};
    }}

    function standaloneWorldCard(profile, match, kind) {{
      const meta = standaloneEntityMetadata(match.name);
      const comparison = standaloneCompareEntity(profile, match.name);
      return {{
        kind,
        name: match.name,
        distance: standaloneRound(match.distance || 0, 4),
        affinity: standaloneRound(match.affinity || 0, 1),
        brief: meta.brief,
        what_they_think: meta.brief,
        url: meta.url,
        source_label: meta.source_label,
        sources: meta.sources || [{{ label: meta.source_label || "Fonte", url: meta.url || "" }}],
        evidence: meta.evidence || "manual_prevalidation",
        basis: meta.basis || "",
        method_note: meta.note || "",
        high_risk: STANDALONE_DATA.categories.storici_estremi.includes(match.name),
        risk_note: (STANDALONE_DATA.historical_metadata[match.name] || {{}}).note || "",
        similar: comparison.similar,
        different: comparison.different
      }};
    }}

    function standaloneBuildPoliticalWorld(profile, ideology, parties, historical, nemesis) {{
      return {{
        title: "Il tuo mondo politico",
        summary: "Una lettura narrativa e spiegabile dei riferimenti più vicini e più lontani nel modello.",
        ideology: ideology ? standaloneWorldCard(profile, ideology, "ideologia") : null,
        party: parties[0] ? standaloneWorldCard(profile, parties[0], "partito") : null,
        historical: historical[0] ? standaloneWorldCard(profile, historical[0], "storico") : null,
        nemesis: nemesis[0] ? standaloneWorldCard(profile, nemesis[0], "nemesi") : null,
        note: "Questi confronti non sono consigli di voto né equivalenze morali: mostrano somiglianze e divergenze tra punti nello spazio a 8 assi. Le figure storiche estreme sono incluse ma segnalate come alto rischio interpretativo."
      }};
    }}

    function standaloneContributions(answers) {{
      const rows = [];
      for (const q of STANDALONE_DATA.questions) {{
        if (!(q.id in answers)) continue;
        const response = standaloneNormalize(answers[q.id]);
        const contributions = q.loading.map((w) => response * w * q.discrimination);
        let strongest = 0;
        for (let i = 1; i < contributions.length; i++) {{
          if (Math.abs(contributions[i]) > Math.abs(contributions[strongest])) strongest = i;
        }}
        rows.push({{
          id: q.id,
          question: q.question,
          answer: answers[q.id],
          primary_axis: STANDALONE_DATA.axis_short[strongest],
          contribution: standaloneRound(contributions[strongest], 4),
          magnitude: standaloneRound(Math.abs(contributions[strongest]), 4),
          direction: standaloneDirection(strongest, contributions[strongest])
        }});
      }}
      return rows.sort((a, b) => b.magnitude - a.magnitude);
    }}

    function standaloneBuildReport(profile, axes, ideology, parties, historical, nemesis, opponents, interpretation, confidence, selfCoherence, reliability) {{
      const strongest = axes.reduce((a, b) => Math.abs(a.value) > Math.abs(b.value) ? a : b);
      const weakest = axes.reduce((a, b) => Math.abs(a.value) < Math.abs(b.value) ? a : b);
      return [
        {{ title: "Lettura sintetica", body: `Il profilo cade nell'area ${{interpretation.family}}, con orientamento ${{interpretation.culture}} e postura ${{interpretation.geopolitics}}. Il modello lo associa soprattutto a ${{ideology.name}}.` }},
        {{ title: "Asse più forte", body: `${{strongest.name}}: ${{strongest.value >= 0 ? "+" : ""}}${{strongest.value.toFixed(2)}}. Questo è il tema dove le risposte hanno prodotto il segnale più netto.` }},
        {{ title: "Asse più equilibrato", body: `${{weakest.name}}: ${{weakest.value >= 0 ? "+" : ""}}${{weakest.value.toFixed(2)}}. Qui il risultato è più vicino al centro o più misto.` }},
        {{ title: "Confidenza del risultato", body: `Confidenza globale ${{confidence.toFixed(1)}}%. Tiene conto di copertura degli assi, chiarezza delle risposte e possibili contraddizioni tematiche.` }},
        {{ title: "Coerenza interna", body: `${{selfCoherence.label}} (${{selfCoherence.score.toFixed(1)}}%). ${{selfCoherence.explanation}}` }},
        {{ title: "Affidabilità interpretativa", body: `${{reliability.label}} (${{reliability.score.toFixed(1)}}%). ${{reliability.explanation}}` }},
        {{ title: "Partiti più vicini", body: parties.slice(0, 3).map((x) => `${{x.name}} (${{x.affinity.toFixed(0)}}%)`).join(", ") }},
        {{ title: "Confronto storico", body: historical.slice(0, 3).map((x) => `${{x.name}} (${{x.affinity.toFixed(0)}}%)`).join(", ") }},
        {{ title: "Nemesi storica metodologica", body: nemesis.slice(0, 3).map((x) => `${{x.name}} (distanza ${{x.distance.toFixed(2)}})`).join(", ") + ". Le figure estreme sono incluse ma marcate come alto rischio interpretativo: non sono equivalenze morali." }},
        {{ title: "Distanze maggiori", body: opponents.slice(0, 3).map((x) => `${{x.name}} (${{x.affinity.toFixed(0)}}%)`).join(", ") }}
      ];
    }}

    function standaloneBuildResult(answers, mode = "deep") {{
      if (Object.keys(answers).length < 12) {{
        throw new Error("Servono almeno 12 risposte per calcolare un profilo minimamente stabile.");
      }}
      const computed = standaloneComputeProfile(answers);
      const completion = Math.min(1, Object.keys(answers).length / STANDALONE_DATA.questions.length);
      const globalConfidence = standaloneClip(computed.globalConfidence * (0.55 + 0.45 * completion), 0, 1);
      const ideologies = standaloneClosest(computed.profile, computed.axes, STANDALONE_DATA.categories.ideologie, 3);
      const ideology = ideologies[0];
      const parties = standaloneClosest(computed.profile, computed.axes, STANDALONE_DATA.categories.partiti, 5);
      const historical = standaloneClosest(computed.profile, computed.axes, STANDALONE_DATA.categories.storici, 5);
      const historicalNemesis = standaloneClosest(computed.profile, computed.axes, STANDALONE_DATA.categories.storici, 3, true).map((x) => ({{ ...x, metadata: STANDALONE_DATA.historical_metadata[x.name] || {{}} }}));
      const historicalExtreme = standaloneClosest(computed.profile, computed.axes, STANDALONE_DATA.categories.storici_estremi, 3).map((x) => ({{ ...x, metadata: STANDALONE_DATA.historical_metadata[x.name] || {{}} }}));
      const opponents = standaloneClosest(computed.profile, computed.axes, STANDALONE_DATA.categories.partiti, 3, true);
      const interpretation = standaloneInterpret(computed.profile);
      const confidence = standaloneRound(globalConfidence * 100, 1);
      const selfCoherence = standaloneBuildSelfCoherence(answers, computed.contradictions);
      const reliability = standaloneBuildReliability(answers, confidence, selfCoherence, ideologies, parties, computed.contradictions);
      const uncertainty = standaloneBuildUncertainty(computed.axes, Object.keys(answers).length);
      const politicalWorld = standaloneBuildPoliticalWorld(computed.profile, ideology, parties, historical, historicalNemesis);
      return {{
        model_version: STANDALONE_DATA.model_version,
        mode,
        profile: computed.profile.map((x) => standaloneRound(x, 4)),
        axes: computed.axes,
        confidence,
        self_coherence: selfCoherence,
        reliability,
        uncertainty,
        completion: standaloneRound(completion * 100, 1),
        answered_questions: Object.keys(answers).length,
        total_questions: STANDALONE_DATA.questions.length,
        contradictions: computed.contradictions,
        interpretation,
        ideology,
        ideologies,
        parties,
        historical,
        historical_nemesis: historicalNemesis,
        historical_extreme_context: historicalExtreme,
        opponents,
        political_world: politicalWorld,
        visuals: {{
          axis_poles: [
            {{ axis: "Economia", negative: "welfare / redistribuzione", positive: "mercato / privatizzazioni" }},
            {{ axis: "Autorità", negative: "libertà individuale", positive: "ordine / controllo" }},
            {{ axis: "Cultura", negative: "pluralismo / diritti", positive: "tradizione / religione" }},
            {{ axis: "Geopolitica", negative: "cooperazione", positive: "sovranità nazionale" }},
            {{ axis: "Ambiente", negative: "transizione verde", positive: "crescita industriale" }},
            {{ axis: "Tecnologia", negative: "regolazione prudente", positive: "innovazione rapida" }},
            {{ axis: "Uguaglianza", negative: "pari condizioni", positive: "gerarchie / competizione" }},
            {{ axis: "Giustizia", negative: "recupero", positive: "punizione / deterrenza" }}
          ],
          pca: {{
            explained_variance: STANDALONE_DATA.pca_model.explained_variance,
            user: standaloneProject(computed.profile),
            points: STANDALONE_DATA.pca_model.points
          }}
        }},
        report: standaloneBuildReport(computed.profile, computed.axes, ideology, parties, historical, historicalNemesis, opponents, interpretation, confidence, selfCoherence, reliability),
        education: STANDALONE_DATA.education,
        curiosities: STANDALONE_DATA.curiosities,
        top_contributions: standaloneContributions(answers).slice(0, 12),
        model_audit: STANDALONE_DATA.model_audit,
        sources: STANDALONE_DATA.sources,
        calibration: STANDALONE_DATA.calibration,
        method: "Versione autonoma: modello multi-asse eseguito nel browser con pesi normalizzati, copertura per asse, chiarezza delle risposte e penalizzazione delle incoerenze tematiche."
      }};
    }}

    function standaloneSaveSample(body, result) {{
      if (!body.research_consent) return;
      const rows = standaloneRead(STANDALONE_KEYS.samples);
      rows.push({{
        timestamp_utc: new Date().toISOString(),
        consent_version: "2026-05-25-local-browser-v1",
        model_version: result.model_version,
        session_id: String(body.session_id || "").slice(0, 100),
        mode: body.mode || "deep",
        answers: body.answers,
        demographics: body.demographics || {{}},
        profile: result.profile,
        confidence: result.confidence,
        self_coherence: result.self_coherence,
        reliability: result.reliability,
        uncertainty: result.uncertainty,
        ideology: result.ideology,
        ideologies: result.ideologies,
        parties: result.parties,
        historical: result.historical,
        historical_nemesis: result.historical_nemesis,
        contradictions_count: result.contradictions.length
      }});
      standaloneWrite(STANDALONE_KEYS.samples, rows);
    }}

    function standaloneAnalytics() {{
      const samples = standaloneRead(STANDALONE_KEYS.samples);
      const feedback = standaloneRead(STANDALONE_KEYS.feedback);
      const support = standaloneRead(STANDALONE_KEYS.support);
      const ideologyCounts = {{}};
      for (const row of samples) {{
        const name = row.ideology?.name || "Sconosciuta";
        ideologyCounts[name] = (ideologyCounts[name] || 0) + 1;
      }}
      const demographicCounts = {{}};
      for (const row of samples) {{
        for (const [key, value] of Object.entries(row.demographics || {{}})) {{
          if (!value) continue;
          demographicCounts[key] ||= {{}};
          demographicCounts[key][value] = (demographicCounts[key][value] || 0) + 1;
        }}
      }}
      const trendMap = {{}};
      for (const row of samples) {{
        const day = String(row.timestamp_utc || "").slice(0, 10) || "senza-data";
        trendMap[day] ||= {{ date: day, samples: 0, feedback: 0, confidences: [], reliabilities: [], ratings: [], ideologies: {{}} }};
        trendMap[day].samples += 1;
        if (Number.isFinite(row.confidence)) trendMap[day].confidences.push(row.confidence);
        if (Number.isFinite(Number(row.reliability?.score))) trendMap[day].reliabilities.push(Number(row.reliability.score));
        if (row.ideology?.name) trendMap[day].ideologies[row.ideology.name] = (trendMap[day].ideologies[row.ideology.name] || 0) + 1;
      }}
      for (const row of feedback) {{
        const day = String(row.timestamp_utc || "").slice(0, 10) || "senza-data";
        trendMap[day] ||= {{ date: day, samples: 0, feedback: 0, confidences: [], reliabilities: [], ratings: [], ideologies: {{}} }};
        trendMap[day].feedback += 1;
        if (Number.isFinite(row.accuracy_rating)) trendMap[day].ratings.push(row.accuracy_rating);
      }}
      const timeTrends = Object.values(trendMap).sort((a, b) => a.date.localeCompare(b.date)).map((x) => {{
        const top = Object.entries(x.ideologies).sort((a, b) => b[1] - a[1])[0];
        return {{
          date: x.date,
          samples: x.samples,
          feedback: x.feedback,
          average_confidence: standaloneMean(x.confidences),
          average_reliability: standaloneMean(x.reliabilities),
          average_accuracy_rating: standaloneMean(x.ratings),
          top_ideology: top ? top[0] : "n/d"
        }};
      }});
      const byPredicted = {{}};
      for (const row of feedback) {{
        const ideology = row.predicted_ideology || "Sconosciuta";
        if (Number.isFinite(Number(row.accuracy_rating))) {{
          byPredicted[ideology] ||= [];
          byPredicted[ideology].push(Number(row.accuracy_rating));
        }}
      }}
      const byPredictedIdeology = Object.entries(byPredicted)
        .map(([ideology, values]) => ({{ ideology, n: values.length, average_rating: standaloneMean(values) }}))
        .sort((a, b) => b.n - a.n);
      const summary = {{
        samples: samples.length,
        feedback_samples: feedback.length,
        support_contacts: support.length,
        average_confidence: standaloneMean(samples.map((x) => x.confidence)),
        average_reliability: standaloneMean(samples.map((x) => Number(x.reliability?.score))),
        average_accuracy_rating: standaloneMean(feedback.map((x) => x.accuracy_rating)),
        ideology_counts: ideologyCounts,
        demographic_counts: demographicCounts,
        storage: standaloneStorageLabel(),
        feedback_storage: standaloneStorageLabel()
      }};
      const demographicBreakdowns = standaloneBuildBreakdowns(samples);
      const strongestGaps = standaloneStrongestGaps(samples);
      const ordinalCorrelations = standaloneOrdinalCorrelations(samples, feedback);
      const datasetHealth = standaloneDatasetHealth(samples, feedback, support, summary);
      return {{
        model_version: STANDALONE_DATA.model_version,
        privacy: `Dashboard locale nel browser. Archivio attivo: ${{standaloneStorageLabel()}}.`,
        minimum_sample_note: "Le correlazioni sono esplorative: sotto 30 campioni totali e 20 per gruppo vanno lette solo come indizi.",
        dataset_health: datasetHealth,
        auto_insights: standaloneAutoInsights(samples, feedback, ordinalCorrelations, strongestGaps, demographicBreakdowns, datasetHealth),
        summary,
        time_trends: timeTrends,
        demographic_breakdowns: demographicBreakdowns,
        strongest_response_gaps: strongestGaps,
        ordinal_correlations: ordinalCorrelations,
        feedback: {{
          average_rating: standaloneMean(feedback.map((x) => x.accuracy_rating)),
          ratings_count: feedback.length,
          party_alignment_rate: null,
          party_alignment_n: 0,
          by_predicted_ideology: byPredictedIdeology,
          joined_feedback_samples: 0
        }}
      }};
    }}

    function standalonePdfBlob(result) {{
      const lines = [
        "Politometro - Report personale",
        `Modello: ${{result.model_version}}`,
        `Profilo: ${{result.ideology.name}}`,
        `Confidenza: ${{result.confidence}}% - Completezza: ${{result.completion}}%`,
        `${{result.interpretation.family}}; ${{result.interpretation.culture}}; ${{result.interpretation.geopolitics}}.`,
        "",
        "Assi:",
        ...result.axes.map((a) => `${{a.name}} ${{a.value >= 0 ? "+" : ""}}${{a.value.toFixed(2)}} confidenza ${{Math.round(a.confidence * 100)}}%`),
        "",
        "Partiti vicini: " + result.parties.map((x) => `${{x.name}} ${{x.affinity}}%`).join(", "),
        "Confronti storici: " + result.historical.map((x) => `${{x.name}} ${{x.affinity}}%`).join(", ")
      ];
      const esc = (s) => String(s).replace(/[()\\\\]/g, "\\\\$&").slice(0, 110);
      let y = 790;
      const text = ["BT /F1 18 Tf 50 820 Td (Politometro) Tj ET"].concat(lines.map((line, i) => {{
        y -= i === 0 ? 44 : 18;
        return `BT /F1 ${{i === 0 ? 16 : 10}} Tf 50 ${{y}} Td (${{esc(line)}}) Tj ET`;
      }})).join("\\n");
      const objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        `<< /Length ${{text.length}} >>\\nstream\\n${{text}}\\nendstream`
      ];
      let pdf = "%PDF-1.4\\n";
      const offsets = [0];
      objects.forEach((obj, i) => {{
        offsets.push(pdf.length);
        pdf += `${{i + 1}} 0 obj\\n${{obj}}\\nendobj\\n`;
      }});
      const xref = pdf.length;
      pdf += `xref\\n0 ${{objects.length + 1}}\\n0000000000 65535 f \\n`;
      offsets.slice(1).forEach((off) => {{ pdf += `${{String(off).padStart(10, "0")}} 00000 n \\n`; }});
      pdf += `trailer << /Size ${{objects.length + 1}} /Root 1 0 R >>\\nstartxref\\n${{xref}}\\n%%EOF`;
      return new Blob([pdf], {{ type: "application/pdf" }});
    }}

    const STANDALONE_ORDINAL = {{
      age_range: {{ "meno di 18": 1, "18-24": 2, "25-34": 3, "35-44": 4, "45-54": 5, "55-64": 6, "65+": 7 }},
      education: {{
        "Scuola media o inferiore": 1,
        "Diploma superiore": 2,
        "Laurea triennale": 3,
        "Laurea magistrale o ciclo unico": 4,
        "Dottorato / master avanzato": 5,
        "Altro percorso": 2
      }},
      political_interest: {{ "Molto basso": 1, "Basso": 2, "Medio": 3, "Alto": 4, "Molto alto": 5 }},
      political_knowledge: {{ "Principiante": 1, "Base": 2, "Intermedia": 3, "Avanzata": 4, "Studio/lavoro nel settore": 5 }},
      news_frequency: {{ "Quasi mai": 1, "Qualche volta al mese": 2, "Settimanalmente": 3, "Quasi ogni giorno": 4, "Ogni giorno da più fonti": 5 }}
    }};

    function standalonePearson(xs, ys) {{
      if (xs.length < 3 || xs.length !== ys.length) return null;
      const mx = standaloneMean(xs), my = standaloneMean(ys);
      const num = xs.reduce((sum, x, i) => sum + (x - mx) * (ys[i] - my), 0);
      const denX = Math.sqrt(xs.reduce((sum, x) => sum + Math.pow(x - mx, 2), 0));
      const denY = Math.sqrt(ys.reduce((sum, y) => sum + Math.pow(y - my, 2), 0));
      if (!denX || !denY) return null;
      return standaloneRound(num / (denX * denY), 4);
    }}

    function standaloneBuildBreakdowns(samples) {{
      const fields = ["age_range", "education", "origin_area", "political_interest", "political_knowledge", "news_frequency", "student_worker"];
      const out = {{}};
      for (const field of fields) {{
        const groups = {{}};
        for (const row of samples) {{
          const value = row.demographics?.[field];
          if (!value) continue;
          groups[value] ||= [];
          groups[value].push(row);
        }}
        out[field] = Object.entries(groups).map(([value, rows]) => {{
          const ideologies = {{}};
          for (const row of rows) {{
            const name = row.ideology?.name || "Sconosciuta";
            ideologies[name] = (ideologies[name] || 0) + 1;
          }}
          const axisMeans = {{}};
          STANDALONE_DATA.axis_short.forEach((axis, i) => {{
            axisMeans[axis] = standaloneMean(rows.map((row) => Number(row.profile?.[i])));
          }});
          return {{
            value,
            n: rows.length,
            average_confidence: standaloneMean(rows.map((row) => Number(row.confidence))),
            average_reliability: standaloneMean(rows.map((row) => Number(row.reliability?.score))),
            axis_means: axisMeans,
            top_ideologies: Object.entries(ideologies).sort((a, b) => b[1] - a[1]).slice(0, 5)
          }};
        }}).sort((a, b) => b.n - a.n);
      }}
      return out;
    }}

    function standaloneStrongestGaps(samples) {{
      const fields = ["education", "political_knowledge", "news_frequency", "age_range", "origin_area"];
      const rows = [];
      for (const field of fields) {{
        const values = [...new Set(samples.map((sample) => sample.demographics?.[field]).filter(Boolean))].sort();
        if (values.length < 2) continue;
        for (const q of STANDALONE_DATA.questions) {{
          const means = {{}};
          const counts = {{}};
          for (const value of values) {{
            const answers = samples
              .filter((sample) => sample.demographics?.[field] === value && Number.isFinite(Number(sample.answers?.[q.id])))
              .map((sample) => Number(sample.answers[q.id]));
            if (!answers.length) continue;
            means[value] = standaloneMean(answers);
            counts[value] = answers.length;
          }}
          const keys = Object.keys(means);
          if (keys.length < 2) continue;
          const low = keys.reduce((a, b) => means[a] < means[b] ? a : b);
          const high = keys.reduce((a, b) => means[a] > means[b] ? a : b);
          rows.push({{
            field,
            question_id: q.id,
            question: q.question,
            low_group: low,
            high_group: high,
            low_mean: standaloneRound(means[low], 3),
            high_mean: standaloneRound(means[high], 3),
            gap: standaloneRound(means[high] - means[low], 3),
            min_group_n: Math.min(...Object.values(counts)),
            caution: Math.min(...Object.values(counts)) < 20
          }});
        }}
      }}
      return rows.sort((a, b) => Math.abs(b.gap) - Math.abs(a.gap)).slice(0, 20);
    }}

    function standaloneReadableField(field) {{
      return {{
        age_range: "età",
        education: "titolo di studio",
        origin_area: "area di provenienza",
        political_interest: "interesse politico",
        political_knowledge: "conoscenza politica dichiarata",
        news_frequency: "frequenza informativa",
        student_worker: "condizione studio/lavoro"
      }}[field] || field;
    }}

    function standaloneDatasetHealth(samples, feedback, support, summary) {{
      const n = samples.length;
      let stage = "setup", label = "Dataset ancora iniziale", nextGoal = "Testare il flusso e raccogliere i primi campioni con consenso.";
      if (n >= 1000) {{ stage = "scala"; label = "Pronto per analisi robuste"; nextGoal = "Ricalibrare pesi, percentili e stabilità del modello."; }}
      else if (n >= 300) {{ stage = "validazione"; label = "Pronto per analisi fattoriale esplorativa"; nextGoal = "Controllare assi ridondanti, item deboli e bias demografici."; }}
      else if (n >= 100) {{ stage = "beta"; label = "Pronto per primi report interni"; nextGoal = "Usare i trend per correggere domande, non per vendere conclusioni forti."; }}
      else if (n >= 30) {{ stage = "early"; label = "Prime indicazioni"; nextGoal = "Raccogliere almeno 100 risposte consensuali."; }}
      const demographicCompletion = {{}};
      for (const key of ["age_range", "education", "origin_area", "political_interest", "political_knowledge", "news_frequency"]) {{
        const filled = samples.filter((row) => row.demographics?.[key]).length;
        demographicCompletion[key] = n ? standaloneRound(filled / n * 100, 1) : 0;
      }}
      const warnings = [];
      if (n < 100) warnings.push("Non vendere ancora correlazioni come insight forti: il campione è troppo piccolo.");
      if (feedback.length && feedback.length < Math.max(10, n * 0.15)) warnings.push("Pochi feedback rispetto ai test completati: semplifica la domanda finale sull'accuratezza percepita.");
      if (n && demographicCompletion.education < 35) warnings.push("Pochi dati facoltativi sul titolo di studio: le correlazioni istruzione-risposte saranno fragili.");
      if (!support.length) warnings.push("Nessun contatto commerciale/supporto salvato: aumenta la visibilità delle call-to-action in beta.");
      return {{
        stage,
        label,
        next_goal: nextGoal,
        samples: n,
        feedback_samples: feedback.length,
        support_contacts: support.length,
        average_confidence: summary.average_confidence,
        average_reliability: summary.average_reliability,
        average_accuracy_rating: summary.average_accuracy_rating,
        demographic_completion: demographicCompletion,
        warnings,
        sellable_public_claim: n >= 100,
        research_claim_ready: n >= 300
      }};
    }}

    function standaloneInsight(kind, title, body, n = 0, strength = null, caution = true) {{
      return {{ kind, title, body, n, strength, caution }};
    }}

    function standaloneAutoInsights(samples, feedback, ordinal, gaps, breakdowns, health) {{
      const insights = [
        standaloneInsight("dataset", health.label, `${{health.samples}} campioni, ${{health.feedback_samples}} feedback e ${{health.support_contacts}} contatti. Prossimo obiettivo: ${{health.next_goal}}`, health.samples, null, health.samples < 100)
      ];
      const axisCorr = (ordinal.axes || []).filter((row) => row.n >= 10);
      if (axisCorr.length) {{
        const top = axisCorr[0];
        const direction = top.correlation > 0 ? "cresce" : "diminuisce";
        insights.push(standaloneInsight("correlation", `Segnale tra ${{standaloneReadableField(top.field)}} e asse ${{top.target}}`, `Nel campione attuale, all'aumentare di ${{standaloneReadableField(top.field)}} il punteggio su ${{top.target}} tende a ${{direction}}. È un segnale esplorativo, non una causa.`, top.n, Math.abs(top.correlation), top.n < 30));
      }}
      const qCorr = (ordinal.questions || []).filter((row) => row.n >= 10);
      if (qCorr.length) {{
        const top = qCorr[0];
        insights.push(standaloneInsight("question", `Domanda sensibile a ${{standaloneReadableField(top.field)}}`, `Questa domanda varia parecchio per ${{standaloneReadableField(top.field)}}: “${{top.question}}”. Controllala per capire se misura ideologia o anche linguaggio/competenza.`, top.n, Math.abs(top.correlation), top.n < 30));
      }}
      if (gaps.length) {{
        const gap = gaps[0];
        insights.push(standaloneInsight("gap", `Differenza forte tra gruppi su ${{standaloneReadableField(gap.field)}}`, `La domanda “${{gap.question}}” separa ${{gap.low_group}} e ${{gap.high_group}} con gap medio ${{gap.gap}}. Utile per revisione item e segmenti editoriali.`, gap.min_group_n || 0, Math.abs(gap.gap || 0), Boolean(gap.caution)));
      }}
      const ratings = feedback.map((row) => Number(row.accuracy_rating)).filter(Number.isFinite);
      if (ratings.length) {{
        const avg = standaloneMean(ratings);
        insights.push(standaloneInsight("feedback", "Accuratezza percepita dagli utenti", `Il voto medio di accuratezza percepita è ${{avg}}/5. Se scende sotto 3.5, rivedi domande, nomi degli archetipi e spiegazioni finali.`, ratings.length, avg, ratings.length < 30));
      }}
      for (const [field, groups] of Object.entries(breakdowns || {{}})) {{
        const large = groups.filter((group) => group.n >= 10 && Number.isFinite(Number(group.average_confidence)));
        if (large.length < 2) continue;
        const top = large.reduce((a, b) => a.average_confidence > b.average_confidence ? a : b);
        const low = large.reduce((a, b) => a.average_confidence < b.average_confidence ? a : b);
        const delta = standaloneRound(top.average_confidence - low.average_confidence, 2);
        if (Math.abs(delta) >= 4) {{
          insights.push(standaloneInsight("confidence", `Confidenza diversa per ${{standaloneReadableField(field)}}`, `La confidenza media è più alta in “${{top.value}}” rispetto a “${{low.value}}” di ${{delta}} punti. Può segnalare domande più chiare per alcuni gruppi.`, Math.min(top.n, low.n), Math.abs(delta), Math.min(top.n, low.n) < 30));
          break;
        }}
      }}
      return insights.slice(0, 8);
    }}

    function standaloneCsvCell(value) {{
      const text = typeof value === "object" && value !== null ? JSON.stringify(value) : String(value ?? "");
      return `"${{text.replace(/"/g, '""')}}"`;
    }}

    function standaloneCsv(rows) {{
      const keys = [...new Set(rows.flatMap((row) => Object.keys(row)))].sort();
      if (!keys.length) keys.push("empty");
      return [keys.map(standaloneCsvCell).join(","), ...rows.map((row) => keys.map((key) => standaloneCsvCell(row[key])).join(","))].join("\\n");
    }}

    function standaloneFlattenSample(row) {{
      const out = {{
        timestamp_utc: row.timestamp_utc || "",
        session_id: row.session_id || "",
        mode: row.mode || "",
        model_version: row.model_version || "",
        confidence: row.confidence ?? "",
        self_coherence: row.self_coherence?.score ?? "",
        reliability: row.reliability?.score ?? "",
        reliability_label: row.reliability?.label || "",
        ideology: row.ideology?.name || "",
        top_party: row.parties?.[0]?.name || "",
        top_party_affinity: row.parties?.[0]?.affinity ?? "",
        top_historical: row.historical?.[0]?.name || "",
        nemesis: row.historical_nemesis?.[0]?.name || "",
        contradictions_count: row.contradictions_count ?? "",
        answers_json: row.answers || {{}}
      }};
      for (const key of ["age_range", "education", "origin_area", "country_region", "political_interest", "political_knowledge", "news_frequency", "student_worker"]) out[key] = row.demographics?.[key] || "";
      STANDALONE_DATA.axis_short.forEach((axis, i) => {{ out[`axis_${{axis.toLowerCase().replace(/[^a-z0-9]+/g, "")}}`] = row.profile?.[i] ?? ""; }});
      return out;
    }}

    function standaloneFlattenFeedback(row) {{
      return {{
        timestamp_utc: row.timestamp_utc || "",
        session_id: row.session_id || "",
        accuracy_rating: row.accuracy_rating ?? "",
        self_label: row.self_label || "",
        closest_party_self: row.closest_party_self || "",
        predicted_ideology: row.predicted_ideology || "",
        predicted_parties: row.predicted_parties || [],
        notes: row.notes || ""
      }};
    }}

    function standaloneFlattenSupport(row) {{
      return {{
        timestamp_utc: row.timestamp_utc || "",
        contact_type: row.contact_type || "",
        email: row.email || "",
        name: row.name || "",
        organization: row.organization || "",
        message: row.message || "",
        consent_contact: row.consent_contact ?? ""
      }};
    }}

    function standaloneOrdinalCorrelations(samples, feedback) {{
      const feedbackBySession = Object.fromEntries(feedback.filter((row) => row.session_id).map((row) => [row.session_id, row]));
      const joined = samples.filter((row) => feedbackBySession[row.session_id]).map((row) => ({{ ...row, feedback: feedbackBySession[row.session_id] }}));
      const axisRows = [], questionRows = [], feedbackRows = [];
      for (const [field, mapping] of Object.entries(STANDALONE_ORDINAL)) {{
        const paired = samples.map((row) => [mapping[row.demographics?.[field]], row]).filter(([x]) => Number.isFinite(x));
        if (paired.length >= 3) {{
          const xs = paired.map(([x]) => Number(x));
          STANDALONE_DATA.axis_short.forEach((axis, i) => {{
            const ys = paired.map(([, row]) => Number(row.profile?.[i]));
            const corr = standalonePearson(xs, ys);
            if (corr !== null) axisRows.push({{ field, target: axis, correlation: corr, n: xs.length }});
          }});
          for (const q of STANDALONE_DATA.questions) {{
            const qPairs = paired.filter(([, row]) => Number.isFinite(Number(row.answers?.[q.id])));
            const corr = standalonePearson(qPairs.map(([x]) => Number(x)), qPairs.map(([, row]) => Number(row.answers[q.id])));
            if (corr !== null) questionRows.push({{ field, question: q.question, question_id: q.id, correlation: corr, n: qPairs.length }});
          }}
        }}
        const joinedPairs = joined.map((row) => [mapping[row.demographics?.[field]], row]).filter(([x, row]) => Number.isFinite(x) && Number.isFinite(Number(row.feedback?.accuracy_rating)));
        const corr = standalonePearson(joinedPairs.map(([x]) => Number(x)), joinedPairs.map(([, row]) => Number(row.feedback.accuracy_rating)));
        if (corr !== null) feedbackRows.push({{ field, target: "accuracy_rating", correlation: corr, n: joinedPairs.length }});
      }}
      axisRows.sort((a, b) => Math.abs(b.correlation) - Math.abs(a.correlation));
      questionRows.sort((a, b) => Math.abs(b.correlation) - Math.abs(a.correlation));
      feedbackRows.sort((a, b) => Math.abs(b.correlation) - Math.abs(a.correlation));
      return {{ axes: axisRows.slice(0, 20), questions: questionRows.slice(0, 20), feedback: feedbackRows.slice(0, 10) }};
    }}

    window.fetch = async function standaloneFetch(input, init = {{}}) {{
      const url = typeof input === "string" ? input : input.url;
      if (url.endsWith("/api/questions") || url === "/api/questions") {{
        return standaloneJson({{ model_version: STANDALONE_DATA.model_version, quick_question_ids: STANDALONE_DATA.quick_question_ids, social_question_ids: STANDALONE_DATA.social_question_ids, calibration: STANDALONE_DATA.calibration, questions: STANDALONE_DATA.questions }});
      }}
      if (url.endsWith("/api/audit") || url === "/api/audit") {{
        return standaloneJson({{ model_version: STANDALONE_DATA.model_version, audit: STANDALONE_DATA.model_audit, sources: STANDALONE_DATA.sources }});
      }}
      if (url.endsWith("/api/private-analytics") || url === "/api/private-analytics") {{
        return standaloneJson(standaloneAnalytics());
      }}
      if (url.endsWith("/api/admin/export/analytics.json")) {{
        return standaloneJson(standaloneAnalytics());
      }}
      if (url.endsWith("/api/admin/export/samples.csv")) {{
        const csv = standaloneCsv(standaloneRead(STANDALONE_KEYS.samples).map(standaloneFlattenSample));
        return new Response(csv, {{ status: 200, headers: {{ "Content-Type": "text/csv; charset=utf-8" }} }});
      }}
      if (url.endsWith("/api/admin/export/feedback.csv")) {{
        const csv = standaloneCsv(standaloneRead(STANDALONE_KEYS.feedback).map(standaloneFlattenFeedback));
        return new Response(csv, {{ status: 200, headers: {{ "Content-Type": "text/csv; charset=utf-8" }} }});
      }}
      if (url.endsWith("/api/admin/export/contacts.csv")) {{
        const csv = standaloneCsv(standaloneRead(STANDALONE_KEYS.support).map(standaloneFlattenSupport));
        return new Response(csv, {{ status: 200, headers: {{ "Content-Type": "text/csv; charset=utf-8" }} }});
      }}
      if (url.endsWith("/api/admin/logout") || url === "/api/admin/logout") {{
        return standaloneJson({{ ok: true }});
      }}
      if (url.endsWith("/api/result") || url === "/api/result") {{
        try {{
          const body = JSON.parse(init.body || "{{}}");
          const result = standaloneBuildResult(body.answers || {{}}, body.mode || "deep");
          standaloneSaveSample(body, result);
          return standaloneJson(result);
        }} catch (error) {{
          return standaloneJson({{ detail: String(error.message || error) }}, 400);
        }}
      }}
      if (url.endsWith("/api/feedback") || url === "/api/feedback") {{
        const body = JSON.parse(init.body || "{{}}");
        if (!body.research_consent) return standaloneJson({{ saved: false, message: "Feedback non salvato per assenza di consenso ricerca." }});
        const rows = standaloneRead(STANDALONE_KEYS.feedback);
        rows.push({{ ...body, timestamp_utc: new Date().toISOString(), model_version: STANDALONE_DATA.model_version }});
        standaloneWrite(STANDALONE_KEYS.feedback, rows);
        return standaloneJson({{ saved: true }});
      }}
      if (url.endsWith("/api/support-contact") || url === "/api/support-contact") {{
        const body = JSON.parse(init.body || "{{}}");
        if (!body.consent_contact) return standaloneJson({{ detail: "Serve consenso per salvare la richiesta di contatto." }}, 400);
        const rows = standaloneRead(STANDALONE_KEYS.support);
        rows.push({{ ...body, timestamp_utc: new Date().toISOString(), model_version: STANDALONE_DATA.model_version }});
        standaloneWrite(STANDALONE_KEYS.support, rows);
        return standaloneJson({{ saved: true }});
      }}
      if (url.endsWith("/api/report-pdf") || url === "/api/report-pdf") {{
        const body = JSON.parse(init.body || "{{}}");
        const result = standaloneBuildResult(body.answers || {{}}, body.mode || "deep");
        return new Response(standalonePdfBlob(result), {{ status: 200, headers: {{ "Content-Type": "application/pdf" }} }});
      }}
      return nativeFetch(input, init);
    }};
    """


def build() -> None:
    data = make_data()
    script = standalone_script(data)
    app_html = webapp.HTML.replace("<script>", "<script>\n" + script, 1)
    app_html = app_html.replace('href="/manifest.webmanifest"', 'href="manifest.webmanifest"')
    app_html = app_html.replace('navigator.serviceWorker.register("/sw.js")', 'navigator.serviceWorker.register("sw.js")')
    app_html = app_html.replace("La versione locale non manda le risposte a un server esterno: il calcolo gira nel tuo ambiente Codex.", "Questa versione autonoma non usa server: calcolo, grafici e salvataggi restano nel browser.")
    OUT_APP.write_text(app_html, encoding="utf-8")
    admin_html = webapp.ADMIN_HTML.replace("<script>", "<script>\n" + script, 1)
    OUT_ADMIN.write_text(admin_html, encoding="utf-8")
    OUT_MANIFEST.write_text(
        json.dumps(
            {
                "name": "Politometro",
                "short_name": "Politometro",
                "description": "Test politico multi-asse con report, mappe, card e dashboard locale.",
                "start_url": "politometro_standalone.html",
                "scope": "./",
                "display": "standalone",
                "display_override": ["standalone", "minimal-ui"],
                "id": "politometro_standalone.html",
                "orientation": "portrait-primary",
                "background_color": "#f6f8f8",
                "theme_color": "#10242f",
                "categories": ["education", "utilities", "social"],
                "shortcuts": [
                    {"name": "Inizia test", "url": "politometro_standalone.html", "description": "Apri Politometro"},
                    {"name": "Dashboard privata", "url": "politometro_admin_standalone.html", "description": "Leggi trend e feedback locali"},
                ],
                "icons": [
                    {"src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                    {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
                    {"src": "icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"},
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    OUT_ICON.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
<defs>
<linearGradient id="g" x1="64" y1="42" x2="450" y2="474" gradientUnits="userSpaceOnUse">
<stop stop-color="#38a3a5"/><stop offset=".46" stop-color="#f2b880"/><stop offset="1" stop-color="#6d597a"/>
</linearGradient>
<radialGradient id="r" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(142 116) rotate(48) scale(410)">
<stop stop-color="#ffffff" stop-opacity=".62"/><stop offset=".46" stop-color="#ffffff" stop-opacity=".08"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
</radialGradient>
</defs>
<rect width="512" height="512" rx="92" fill="#10242f"/>
<rect x="54" y="54" width="404" height="404" rx="76" fill="url(#g)"/>
<rect x="54" y="54" width="404" height="404" rx="76" fill="url(#r)"/>
<circle cx="256" cy="256" r="126" fill="#10242f" fill-opacity=".92"/>
<path d="M256 154 292 228 256 256 220 228Z M358 256 284 292 256 256 284 220Z M256 358 220 284 256 256 292 284Z M154 256 228 220 256 256 228 292Z" fill="#f6f8f8"/>
<circle cx="256" cy="256" r="44" fill="#10242f"/>
<circle cx="256" cy="256" r="20" fill="#f2b880"/>
</svg>""",
        encoding="utf-8",
    )
    write_png_icon(OUT_ICON_192, 192)
    write_png_icon(OUT_ICON_512, 512)
    OUT_SW.write_text(
        """
const CACHE = "politometro-standalone-v8";
const CORE = ["./politometro_standalone.html", "./manifest.webmanifest", "./icon.svg", "./icon-192.png", "./icon-512.png"];
self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(CORE)));
  self.skipWaiting();
});
self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.pathname.startsWith("/api/") || url.pathname === "/admin" || url.pathname.startsWith("/admin/") || url.pathname === "/login" || url.pathname.startsWith("/login/")) return;
  event.respondWith(fetch(request).then(response => {
    if (!response || !response.ok || response.type === "opaque") return response;
    const copy = response.clone();
    caches.open(CACHE).then(cache => cache.put(request, copy));
    return response;
  }).catch(() => caches.match(request).then(cached => cached || caches.match("./politometro_standalone.html"))));
});
""".strip()
        + "\n",
        encoding="utf-8",
    )
    print(OUT_APP.resolve())
    print(OUT_ADMIN.resolve())
    print(OUT_MANIFEST.resolve())


if __name__ == "__main__":
    build()
