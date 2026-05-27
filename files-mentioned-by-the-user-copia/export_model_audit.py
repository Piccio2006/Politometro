from __future__ import annotations

import json
from pathlib import Path

from politometro_scientific import MODEL_VERSION, QUESTIONS, SOURCE_REFERENCES, audit_question, build_model_audit


def main() -> None:
    out_dir = Path("audit")
    out_dir.mkdir(exist_ok=True)

    audit = build_model_audit()
    question_rows = [audit_question(question) for question in QUESTIONS]

    (out_dir / "model_audit.json").write_text(
        json.dumps(
            {
                "model_version": MODEL_VERSION,
                "summary": audit,
                "questions": question_rows,
                "sources": SOURCE_REFERENCES,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        "# Politometro Model Audit",
        "",
        f"Model version: `{MODEL_VERSION}`",
        "",
        "## Sintesi",
        "",
        f"- Domande OK: {audit['question_status_counts']['ok']}",
        f"- Domande da rivedere: {audit['question_status_counts']['review']}",
        f"- Domande critiche: {audit['question_status_counts']['critical']}",
        "",
        "## Copertura Assi",
        "",
    ]
    for item in audit["axis_coverage"]:
        lines.append(f"- {item['axis']}: {item['questions']} domande")

    checks = audit.get("v5_content_checks", {})
    lines.extend(
        [
            "",
            "## Controlli V5",
            "",
            f"- Massimo assi attivi per domanda: {checks.get('max_active_axes', 'n/d')}",
            f"- Domande con asse primario non dominante: {checks.get('questions_with_primary_dominance_issue', 'n/d')}",
            f"- Domande con marker linguistici emotivi: {checks.get('questions_with_loaded_language_markers', 'n/d')}",
            f"- Domande con complessità linguistica media/alta: {checks.get('questions_with_medium_or_high_complexity', 'n/d')}",
            f"- Nota: {checks.get('note', '')}",
        ]
    )

    lines.extend(["", "## Domande Da Rivedere", ""])
    for item in question_rows:
        if item["status"] == "ok":
            continue
        lines.extend(
            [
                f"### {item['id']} ({item['status']})",
                "",
                f"Domanda: {item['question']}",
                "",
                f"- Asse primario: {item['primary_axis']}",
                f"- Assi attivi: {', '.join(item['active_axes'])}",
                f"- Peso massimo: {item['max_weight']}",
                f"- Peso secondario massimo: {item.get('secondary_max_weight')}",
                f"- Focus ratio: {item['focus_ratio']}",
                f"- Dominanza primario/secondario: {item.get('dominance_ratio')}",
                f"- Rischio bias emotivo: {item.get('content_risk', {}).get('emotional_bias_risk')}",
                f"- Complessità linguistica: {item.get('content_risk', {}).get('linguistic_complexity')}",
                f"- Problemi: {', '.join(item['issues'])}",
                f"- Azione suggerita: {item['suggestion']}",
                "",
            ]
        )

    lines.extend(["## Fonti Di Calibrazione", ""])
    for source in SOURCE_REFERENCES:
        lines.append(f"- [{source['name']}]({source['url']}): {source['use']}")

    (out_dir / "model_audit.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
