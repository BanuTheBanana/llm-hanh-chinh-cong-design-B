"""Unit checks for the locked G5 intent/context final evaluator."""

import importlib.util
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/evaluate-g5-intent-context-models.py"
SPEC = importlib.util.spec_from_file_location("g5_final_evaluator", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_field_scores_count_false_negative_when_prediction_is_empty():
    counts = {label: Counter() for label in MODULE.FIELD_INTENTS}
    expected = {"field_intents": ["fees"]}
    predicted = {"field_intents": []}

    assert MODULE.update_field_scores(counts, expected, predicted) is False
    assert counts["fees"]["fn"] == 1
    assert MODULE.macro_f1(counts) < 1


def test_final_conversations_require_twenty_ordered_three_turn_chains():
    keep_patch = {
        slot: {"op": "KEEP", "value": None} for slot in MODULE.CONTEXT_SLOTS
    }
    expected = {
        "dialogue_act": "ASK_INFORMATION",
        "topic_action": "KEEP",
        "patch": keep_patch,
    }
    cases = []
    for conversation_number in range(1, 21):
        for turn in range(1, 4):
            cases.append(
                {
                    "case_id": f"case-{conversation_number}-{turn}",
                    "conversation_id": f"conversation-{conversation_number}",
                    "turn_index": turn,
                    "assistant_message_before": None if turn == 1 else "Câu chuyển lượt.",
                    "state_before": {
                        "procedure_id": None,
                        "field_intents": [],
                        "jurisdiction": None,
                        "as_of": None,
                    },
                    "expected": expected,
                }
            )

    assert MODULE.validate_final_conversations(cases) is True
    cases[-1]["turn_index"] = 2
    assert MODULE.validate_final_conversations(cases) is False
