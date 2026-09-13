from app.intent_context_policy import POLICY_VERSION, apply_intent_context_policy


def output(*, act="ASK_INFORMATION", topic="KEEP"):
    keep = {"op": "KEEP", "value": None, "evidence": []}
    return {
        "schema_version": "g5-intent-context-v2",
        "dialogue_act": act,
        "topic_action": topic,
        "patch": {
            "procedure_id": dict(keep),
            "field_intents": dict(keep),
            "jurisdiction": dict(keep),
            "as_of": dict(keep),
        },
    }


def payload(message, **state):
    return {
        "current_user_message": message,
        "state_before": {
            "procedure_id": None,
            "field_intents": [],
            "jurisdiction": None,
            "as_of": None,
            "pending_clarification": None,
            **state,
        },
    }


def test_policy_version_is_explicit():
    assert POLICY_VERSION == "g5-intent-context-policy-v1"


def test_explicit_switch_is_a_correction():
    candidate = output(topic="SWITCH")
    candidate["patch"]["procedure_id"] = {
        "op": "SET",
        "value": "p_birth",
        "evidence": [{"message_id": "current-user", "quote": "chuyển sang khai sinh"}],
    }
    normalized, actions = apply_intent_context_policy(
        candidate,
        payload("Không hỏi kết hôn nữa, chuyển sang khai sinh.", procedure_id="p_marriage"),
    )
    assert normalized["dialogue_act"] == "CORRECT_CONTEXT"
    assert actions == ["EXPLICIT_TOPIC_CORRECTION"]


def test_pending_slot_answer_is_a_clarification():
    candidate = output()
    candidate["patch"]["as_of"] = {
        "op": "SET",
        "value": "2026-09-12",
        "evidence": [{"message_id": "current-user", "quote": "12/09/2026"}],
    }
    normalized, actions = apply_intent_context_policy(
        candidate,
        payload("Theo ngày 12/09/2026.", pending_clarification="as_of"),
    )
    assert normalized["dialogue_act"] == "PROVIDE_CLARIFICATION"
    assert actions == ["PENDING_SLOT_WAS_PROVIDED"]


def test_out_of_scope_and_acknowledgement_keep_context():
    out_of_scope, out_actions = apply_intent_context_policy(
        output(act="OUT_OF_SCOPE", topic="UNRESOLVED"),
        payload("Viết một bài thơ.", procedure_id="p_birth"),
    )
    acknowledgement, ack_actions = apply_intent_context_policy(
        output(act="OUT_OF_SCOPE", topic="UNRESOLVED"),
        payload("Đúng rồi.", procedure_id="p_birth"),
    )
    assert out_of_scope["topic_action"] == "KEEP"
    assert out_actions == ["POLICY_INTENT_KEEPS_CONTEXT"]
    assert acknowledgement["dialogue_act"] == "ASK_INFORMATION"
    assert acknowledgement["topic_action"] == "KEEP"
    assert ack_actions == ["ACKNOWLEDGEMENT_KEEPS_CONTEXT"]


def test_reset_cannot_repopulate_state():
    candidate = output(act="RESET_CONTEXT", topic="SWITCH")
    candidate["patch"]["procedure_id"] = {
        "op": "SET",
        "value": "p_birth",
        "evidence": [{"message_id": "current-user", "quote": "Bắt đầu lại"}],
    }
    normalized, actions = apply_intent_context_policy(
        candidate, payload("Bắt đầu lại", procedure_id="p_marriage")
    )
    assert normalized["topic_action"] == "RESET"
    assert all(item["op"] == "KEEP" for item in normalized["patch"].values())
    assert actions == ["RESET_ACT_CLEARS_STATE_MACHINE"]
