from __future__ import annotations

from itertools import product


def classify_confidence(
    top_score: float | None,
    second_score: float | None,
    *,
    score_floor: float,
    margin_floor: float,
) -> str:
    if top_score is None or top_score < score_floor:
        return "low_confidence"
    if second_score is not None and (top_score - second_score) < margin_floor:
        return "ambiguous"
    return "resolved"


def tune_thresholds(
    records: list[dict],
    *,
    score_floors: list[float],
    margin_floors: list[float],
) -> dict:
    labelled = [row for row in records if row.get("expected_confidence_status")]
    if not labelled:
        raise ValueError("no rows with expected_confidence_status")
    trials = []
    for score_floor, margin_floor in product(score_floors, margin_floors):
        correct = 0
        confusion: dict[str, dict[str, int]] = {}
        for row in labelled:
            expected = row["expected_confidence_status"]
            predicted = classify_confidence(
                row.get("top_score"),
                row.get("second_score"),
                score_floor=score_floor,
                margin_floor=margin_floor,
            )
            correct += int(predicted == expected)
            confusion.setdefault(expected, {}).setdefault(predicted, 0)
            confusion[expected][predicted] += 1
        trials.append(
            {
                "score_floor": score_floor,
                "margin_floor": margin_floor,
                "accuracy": correct / len(labelled),
                "correct": correct,
                "total": len(labelled),
                "confusion": confusion,
            }
        )
    trials.sort(key=lambda row: (-row["accuracy"], row["score_floor"], row["margin_floor"]))
    return {"best": trials[0], "trials": trials}
