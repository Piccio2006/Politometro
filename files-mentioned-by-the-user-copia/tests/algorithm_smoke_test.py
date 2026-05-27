from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from politometro_scientific import AXIS_SHORT, QUICK_QUESTION_IDS, build_result


def assert_between(value: float, low: float, high: float, label: str) -> None:
    if not low <= value <= high:
        raise AssertionError(f"{label} fuori intervallo: {value}")


def main() -> None:
    neutral_answers = {question_id: 4 for question_id in QUICK_QUESTION_IDS}
    neutral_result = build_result(neutral_answers)

    assert neutral_result["answered_questions"] == len(QUICK_QUESTION_IDS)
    assert len(neutral_result["axes"]) == len(AXIS_SHORT)
    assert len(neutral_result["profile"]) == len(AXIS_SHORT)
    assert neutral_result["ideology"]["name"]
    assert len(neutral_result["parties"]) >= 3
    assert neutral_result["political_world"]["party"]["name"] == neutral_result["parties"][0]["name"]
    assert neutral_result["political_world"]["ideology"]["name"] == neutral_result["ideology"]["name"]
    assert neutral_result["political_world"]["historical"]["similar"]
    assert neutral_result["political_world"]["nemesis"]["different"]
    assert_between(neutral_result["confidence"], 0, 100, "confidence")
    assert_between(neutral_result["self_coherence"]["score"], 0, 100, "self_coherence")
    assert_between(neutral_result["reliability"]["score"], 0, 100, "reliability")

    polarized_answers = {question_id: 1 for question_id in QUICK_QUESTION_IDS}
    polarized_result = build_result(polarized_answers)
    assert len(polarized_result["axes"]) == len(AXIS_SHORT)
    assert polarized_result["ideology"]["name"]
    assert polarized_result["profile"] != neutral_result["profile"]

    try:
        build_result({question_id: 4 for question_id in QUICK_QUESTION_IDS[:5]})
    except ValueError:
        pass
    else:
        raise AssertionError("Il modello deve rifiutare profili con meno di 12 risposte.")

    print("OK: algoritmo core stabile sui casi smoke.")


if __name__ == "__main__":
    main()
