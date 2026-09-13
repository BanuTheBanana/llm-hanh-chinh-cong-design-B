from app.intent_context_policy import (
    POLICY_VERSION,
    apply_intent_context_policy,
    resolve_high_confidence_without_model,
)


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
        "message_id": "current-user",
        "current_user_message": message,
        "state_before": {
            "procedure_id": None,
            "field_intents": [],
            "jurisdiction": None,
            "as_of": None,
            "pending_clarification": None,
            **state,
        },
        "procedure_candidates": [
            {"id": "p_birth", "name": "Đăng ký khai sinh"},
            {"id": "p_marriage", "name": "Đăng ký kết hôn"},
            {"id": "p_death", "name": "Đăng ký khai tử"},
            {"id": "p_residence", "name": "Xác nhận thông tin về cư trú"},
        ],
    }


def test_policy_version_is_explicit():
    assert POLICY_VERSION == "g6-intent-context-policy-v4"


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
    assert actions == ["EXPLICIT_RESET_WINS"]


def test_explicit_switch_wins_over_incorrect_greeting_label():
    candidate = output(act="GREET", topic="SWITCH")
    candidate["patch"]["procedure_id"] = {
        "op": "SET",
        "value": "p_birth",
        "evidence": [{"message_id": "current-user", "quote": "chuyển sang khai sinh"}],
    }
    normalized, actions = apply_intent_context_policy(
        candidate,
        payload("Không hỏi kết hôn nữa, chuyển sang khai sinh nhé.", procedure_id="p_marriage"),
    )
    assert normalized["dialogue_act"] == "CORRECT_CONTEXT"
    assert normalized["topic_action"] == "SWITCH"
    assert normalized["patch"]["procedure_id"]["value"] == "p_birth"
    assert actions == ["SEMANTIC_SIGNAL_OVERRIDES_POLICY_INTENT"]


def test_repeated_procedure_is_not_a_topic_switch():
    candidate = output(topic="SWITCH")
    candidate["patch"]["procedure_id"] = {
        "op": "SET",
        "value": "p_birth",
        "evidence": [{"message_id": "current-user", "quote": "thủ tục khai sinh đó"}],
    }
    candidate["patch"]["field_intents"] = {
        "op": "SET",
        "value": ["fees"],
        "evidence": [{"message_id": "current-user", "quote": "lệ phí"}],
    }
    normalized, actions = apply_intent_context_policy(
        candidate, payload("Thủ tục khai sinh đó có lệ phí không?", procedure_id="p_birth")
    )
    assert normalized["topic_action"] == "KEEP"
    assert normalized["patch"]["procedure_id"]["op"] == "KEEP"
    assert normalized["patch"]["field_intents"]["value"] == ["fees"]
    assert actions == ["REPEATED_PROCEDURE_KEEPS_TOPIC"]


def test_explicit_field_correction_is_not_plain_information_request():
    candidate = output()
    candidate["patch"]["field_intents"] = {
        "op": "SET",
        "value": ["receiving_authority"],
        "evidence": [{"message_id": "current-user", "quote": "nơi tiếp nhận"}],
    }
    normalized, actions = apply_intent_context_policy(
        candidate,
        payload("Tôi nói nơi tiếp nhận, không hỏi cách nộp.", procedure_id="p_birth"),
    )
    assert normalized["dialogue_act"] == "CORRECT_CONTEXT"
    assert actions == ["EXPLICIT_TOPIC_CORRECTION"]


def test_first_scope_value_is_information_not_correction():
    candidate = output(act="CORRECT_CONTEXT")
    candidate["patch"]["jurisdiction"] = {
        "op": "SET",
        "value": "Đà Nẵng",
        "evidence": [{"message_id": "current-user", "quote": "Đà Nẵng"}],
    }
    normalized, actions = apply_intent_context_policy(
        candidate, payload("Nếu làm tại Đà Nẵng thì sao?", procedure_id="p_birth")
    )
    assert normalized["dialogue_act"] == "ASK_INFORMATION"
    assert actions == ["NEW_VALUE_IS_NOT_A_CORRECTION"]


def test_false_reset_on_explicit_switch_is_recovered_from_catalog():
    candidate = output(act="RESET_CONTEXT", topic="RESET")
    normalized, actions = apply_intent_context_policy(
        candidate,
        payload(
            "Chuyển hẳn sang xác nhận thông tin cư trú và cho biết cơ quan nhận yêu cầu.",
            procedure_id="p_birth",
            field_intents=["processing_times"],
        ),
    )
    assert normalized["dialogue_act"] == "CORRECT_CONTEXT"
    assert normalized["topic_action"] == "SWITCH"
    assert normalized["patch"]["procedure_id"]["value"] == "p_residence"
    assert normalized["patch"]["field_intents"]["value"] == ["receiving_authority"]
    assert "UNSUPPORTED_RESET_DOWNGRADED" in actions
    assert "CATALOG_PROCEDURE_RECOVERED" in actions


def test_pending_value_wins_over_model_correction_label():
    candidate = output(act="CORRECT_CONTEXT")
    candidate["patch"]["jurisdiction"] = {
        "op": "SET",
        "value": "Thủ Dầu Một",
        "evidence": [{"message_id": "current-user", "quote": "Thủ Dầu Một"}],
    }
    normalized, actions = apply_intent_context_policy(
        candidate,
        payload(
            "Tôi thực hiện tại Thủ Dầu Một.",
            procedure_id="p_marriage",
            pending_clarification="jurisdiction",
        ),
    )
    assert normalized["dialogue_act"] == "PROVIDE_CLARIFICATION"
    assert "PENDING_SLOT_WAS_PROVIDED" in actions


def test_unresolved_request_cannot_hallucinate_procedure_or_all_fields():
    candidate = output(topic="UNRESOLVED")
    candidate["patch"]["procedure_id"] = {
        "op": "SET",
        "value": "p_birth",
        "evidence": [{"message_id": "current-user", "quote": "việc hộ tịch"}],
    }
    candidate["patch"]["field_intents"] = {
        "op": "SET",
        "value": ["fees", "steps", "required_documents"],
        "evidence": [{"message_id": "current-user", "quote": "việc hộ tịch"}],
    }
    normalized, actions = apply_intent_context_policy(
        candidate, payload("Tôi chưa biết tên thủ tục cần giải quyết.")
    )
    assert normalized["dialogue_act"] == "ASK_INFORMATION"
    assert normalized["topic_action"] == "UNRESOLVED"
    assert all(item["op"] == "KEEP" for item in normalized["patch"].values())
    assert actions == ["EXPLICIT_UNRESOLVED_REQUEST"]


def test_high_confidence_field_cues_remove_spurious_extra_field():
    candidate = output(topic="SWITCH")
    candidate["patch"]["procedure_id"] = {
        "op": "SET",
        "value": "p_residence",
        "evidence": [{"message_id": "current-user", "quote": "xác nhận thông tin cư trú"}],
    }
    candidate["patch"]["field_intents"] = {
        "op": "SET",
        "value": ["receiving_authority", "submission_methods"],
        "evidence": [{"message_id": "current-user", "quote": "phương án nộp"}],
    }
    normalized, actions = apply_intent_context_policy(
        candidate,
        payload("Xác nhận thông tin cư trú có các phương án nộp yêu cầu nào?"),
    )
    assert normalized["patch"]["field_intents"]["value"] == ["submission_methods"]
    assert "HIGH_CONFIDENCE_FIELDS_NORMALIZED" in actions


def test_field_cues_ignore_discourse_and_incidental_words():
    cases = [
        (
            "Sau khi nộp đủ thì cơ quan có bao nhiêu ngày để trả kết quả?",
            ["processing_times"],
        ),
        (
            "Ngoài căn cứ pháp lý, bộ hồ sơ yêu cầu những giấy tờ nào?",
            ["required_documents"],
        ),
        (
            "Trình tự đăng ký kết hôn từ lúc nộp đến khi nhận kết quả ra sao?",
            ["steps"],
        ),
        (
            "Hồ sơ có thể gửi đến cơ quan bằng những cách nào?",
            ["submission_methods"],
        ),
        (
            "Đăng ký kết hôn cần mang gì đến đâu nộp?",
            ["receiving_authority", "required_documents"],
        ),
        (
            "Sau khi đủ giấy tờ thì trình tự thực hiện lần lượt ra sao?",
            ["steps"],
        ),
    ]
    for message, fields in cases:
        candidate = output()
        candidate["patch"]["field_intents"] = {
            "op": "SET",
            "value": ["receiving_authority", "legal_bases", *fields],
            "evidence": [{"message_id": "current-user", "quote": message}],
        }
        normalized, _ = apply_intent_context_policy(candidate, payload(message))
        assert normalized["patch"]["field_intents"]["value"] == fields


def test_reference_to_previous_switch_is_not_a_new_correction():
    candidate = output()
    candidate["patch"]["field_intents"] = {
        "op": "SET",
        "value": ["required_documents"],
        "evidence": [{"message_id": "current-user", "quote": "kèm theo"}],
    }
    normalized, actions = apply_intent_context_policy(
        candidate,
        payload(
            "Trong hồ sơ kết hôn vừa chuyển sang cần kèm theo những gì?",
            procedure_id="p_marriage",
        ),
    )
    assert normalized["dialogue_act"] == "ASK_INFORMATION"
    assert "EXPLICIT_TOPIC_CORRECTION" not in actions


def test_negated_old_procedure_does_not_beat_new_catalog_topic():
    candidate = output(act="CORRECT_CONTEXT", topic="SWITCH")
    candidate["patch"]["procedure_id"] = {
        "op": "SET",
        "value": "p_residence",
        "evidence": [{"message_id": "current-user", "quote": "xác nhận thông tin cư trú"}],
    }
    normalized, _ = apply_intent_context_policy(
        candidate,
        payload(
            "Không hỏi khai tử nữa, chuyển sang xác nhận thông tin cư trú.",
            procedure_id="p_death",
        ),
    )
    assert normalized["topic_action"] == "SWITCH"
    assert normalized["patch"]["procedure_id"]["value"] == "p_residence"


def test_natural_reset_phrases_win_over_model_label():
    for message in (
        "Hãy xóa toàn bộ chủ đề hiện tại để tôi hỏi lại từ đầu.",
        "Bỏ hết thông tin đang trao đổi và bắt đầu một yêu cầu khác.",
    ):
        normalized, _ = apply_intent_context_policy(
            output(), payload(message, procedure_id="p_birth")
        )
        assert normalized["dialogue_act"] == "RESET_CONTEXT"
        assert normalized["topic_action"] == "RESET"


def test_temporal_regulation_phrase_only_sets_date():
    candidate = output()
    candidate["patch"]["field_intents"] = {
        "op": "SET",
        "value": ["legal_bases"],
        "evidence": [{"message_id": "current-user", "quote": "quy định"}],
    }
    candidate["patch"]["as_of"] = {
        "op": "SET",
        "value": "2026-08-15",
        "evidence": [{"message_id": "current-user", "quote": "15 tháng 8 năm 2026"}],
    }
    normalized, _ = apply_intent_context_policy(
        candidate,
        payload(
            "Hãy tra cứu theo quy định có hiệu lực tại ngày 15 tháng 8 năm 2026.",
            procedure_id="p_birth",
        ),
    )
    assert normalized["patch"]["field_intents"]["op"] == "KEEP"


def test_unsolicited_clarification_is_plain_information():
    candidate = output(act="PROVIDE_CLARIFICATION")
    candidate["patch"]["jurisdiction"] = {
        "op": "SET",
        "value": "Ba Đình, Hà Nội",
        "evidence": [{"message_id": "current-user", "quote": "Ba Đình, Hà Nội"}],
    }
    normalized, actions = apply_intent_context_policy(
        candidate,
        payload(
            "Tôi thực hiện tại Ba Đình, Hà Nội.",
            procedure_id="p_marriage",
            field_intents=["submission_methods"],
        ),
    )
    assert normalized["dialogue_act"] == "ASK_INFORMATION"
    assert "UNSOLICITED_CLARIFICATION_DOWNGRADED" in actions


def test_procedure_signal_overrides_false_greeting_during_clarification():
    normalized, actions = apply_intent_context_policy(
        output(act="GREET", topic="UNRESOLVED"),
        payload(
            "Việc cần làm chính xác là đăng ký kết hôn.",
            pending_clarification="procedure_id",
        ),
    )
    assert normalized["dialogue_act"] == "PROVIDE_CLARIFICATION"
    assert normalized["topic_action"] == "SWITCH"
    assert normalized["patch"]["procedure_id"]["value"] == "p_marriage"
    assert "SEMANTIC_SIGNAL_OVERRIDES_POLICY_INTENT" in actions
    assert "PENDING_SLOT_WAS_PROVIDED" in actions


def test_incidental_workflow_and_regulation_words_do_not_add_fields():
    cases = [
        (
            "Ngoài quy trình, hồ sơ phải kèm theo tài liệu nào?",
            ["required_documents"],
        ),
        (
            "Vậy trình tự xử lý hồ sơ gồm các bước ra sao?",
            ["steps"],
        ),
        (
            "Khoản lệ phí dành cho họ được quy định thế nào?",
            ["fees"],
        ),
        (
            "Tôi cần đối chiếu quy định có hiệu lực vào ngày 21 tháng 6 năm 2026.",
            [],
        ),
    ]
    for message, fields in cases:
        candidate = output()
        candidate["patch"]["field_intents"] = {
            "op": "SET",
            "value": ["legal_bases", "required_documents", "steps", *fields],
            "evidence": [{"message_id": "current-user", "quote": message}],
        }
        normalized, _ = apply_intent_context_policy(candidate, payload(message))
        if fields:
            assert normalized["patch"]["field_intents"]["value"] == fields
        else:
            assert normalized["patch"]["field_intents"]["op"] == "KEEP"


def test_unsupported_clear_cannot_delete_remembered_scope():
    candidate = output()
    candidate["patch"]["jurisdiction"] = {
        "op": "CLEAR",
        "value": None,
        "evidence": [{"message_id": "current-user", "quote": "Ở địa bàn mới"}],
    }
    normalized, actions = apply_intent_context_policy(
        candidate,
        payload(
            "Ở địa bàn mới, hồ sơ khai sinh gồm những tài liệu nào?",
            procedure_id="p_birth",
            jurisdiction="Tam Kỳ, Quảng Nam",
        ),
    )
    assert normalized["patch"]["jurisdiction"]["op"] == "KEEP"
    assert "UNSUPPORTED_CLEAR_JURISDICTION_REMOVED" in actions


def test_explicit_jurisdiction_edit_is_a_correction():
    candidate = output(act="CORRECT_CONTEXT")
    candidate["patch"]["jurisdiction"] = {
        "op": "SET",
        "value": "thành phố Huế",
        "evidence": [{"message_id": "current-user", "quote": "thành phố Huế"}],
    }
    normalized, actions = apply_intent_context_policy(
        candidate,
        payload(
            "Sửa địa bàn thực hiện thành thành phố Huế.",
            procedure_id="p_change",
        ),
    )
    assert normalized["dialogue_act"] == "CORRECT_CONTEXT"
    assert "NEW_VALUE_IS_NOT_A_CORRECTION" not in actions


def test_fast_route_handles_only_clear_procedure_and_field():
    resolved = resolve_high_confidence_without_model(
        payload("Đăng ký khai sinh cần chuẩn bị giấy tờ nào?")
    )
    assert resolved is not None
    output, actions = resolved
    assert output["topic_action"] == "SWITCH"
    assert output["patch"]["procedure_id"]["value"] == "p_birth"
    assert output["patch"]["field_intents"]["value"] == ["required_documents"]
    assert actions == ["DETERMINISTIC_HIGH_CONFIDENCE_ROUTE"]


def test_fast_route_defers_pending_scope_date_and_out_of_scope():
    cases = [
        payload(
            "Đăng ký khai sinh cần giấy tờ nào?",
            pending_clarification="jurisdiction",
        ),
        payload("Đăng ký khai sinh tại quận 1 cần giấy tờ nào?"),
        payload("Đăng ký khai sinh ngày 12/09/2026 cần giấy tờ nào?"),
        payload("Viết bài quảng cáo về lệ phí.", procedure_id="p_birth"),
    ]
    assert all(resolve_high_confidence_without_model(item) is None for item in cases)
