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
    assert POLICY_VERSION == "g6-intent-context-policy-v11"


def test_long_official_title_accepts_distinctive_noun_phrase_without_wrong_variant():
    item = payload("Hồ sơ trợ cấp hưu trí xã hội nộp ở đâu?")
    item["procedure_candidates"] = [
        {
            "id": "p_social_pension",
            "name": "Thực hiện, điều chỉnh, thôi hưởng trợ cấp hưu trí xã hội",
        },
        {
            "id": "p_social_pension_funeral",
            "name": (
                "Hỗ trợ chi phí mai táng đối với đối tượng hưởng trợ cấp "
                "hưu trí xã hội"
            ),
        },
    ]

    resolved = resolve_high_confidence_without_model(item)

    assert resolved is not None
    normalized, actions = resolved
    assert normalized["topic_action"] == "SWITCH"
    assert normalized["patch"]["procedure_id"]["value"] == "p_social_pension"
    assert normalized["patch"]["field_intents"]["value"] == [
        "receiving_authority"
    ]
    assert actions == ["DETERMINISTIC_HIGH_CONFIDENCE_ROUTE"]


def test_explicit_funeral_words_select_the_longer_social_pension_variant():
    item = payload(
        "Người hưởng trợ cấp hưu trí xã hội vừa mất, hồ sơ mai táng cần giấy tờ nào?"
    )
    item["procedure_candidates"] = [
        {
            "id": "p_social_pension",
            "name": "Thực hiện, điều chỉnh, thôi hưởng trợ cấp hưu trí xã hội",
        },
        {
            "id": "p_social_pension_funeral",
            "name": (
                "Hỗ trợ chi phí mai táng đối với đối tượng hưởng trợ cấp "
                "hưu trí xã hội"
            ),
        },
    ]

    resolved = resolve_high_confidence_without_model(item)

    assert resolved is not None
    normalized, _ = resolved
    assert normalized["patch"]["procedure_id"]["value"] == (
        "p_social_pension_funeral"
    )
    assert normalized["patch"]["field_intents"]["value"] == [
        "required_documents"
    ]


def test_short_generic_social_benefit_phrase_stays_ambiguous():
    item = payload("Hồ sơ trợ cấp xã hội nộp ở đâu?")
    item["procedure_candidates"] = [
        {
            "id": "p_social_pension",
            "name": "Thực hiện, điều chỉnh, thôi hưởng trợ cấp hưu trí xã hội",
        },
        {
            "id": "p_social_pension_funeral",
            "name": (
                "Hỗ trợ chi phí mai táng đối với đối tượng hưởng trợ cấp "
                "hưu trí xã hội"
            ),
        },
    ]

    assert resolve_high_confidence_without_model(item) is None


def test_field_only_clarification_keeps_the_active_procedure_across_domains():
    for procedure_id in ("p_birth", "p_marriage", "p_residence"):
        item = payload(
            "hồ sơ",
            procedure_id=procedure_id,
            pending_clarification="field_intents",
        )
        item["procedure_candidates"].append(
            {"id": "p_house_number", "name": "HỒ SƠ CẤP SỐ NHÀ"}
        )
        resolved = resolve_high_confidence_without_model(item)
        assert resolved is not None
        fast_output, _ = resolved
        assert fast_output["dialogue_act"] == "PROVIDE_CLARIFICATION"
        assert fast_output["topic_action"] == "KEEP"
        assert fast_output["patch"]["procedure_id"]["op"] == "KEEP"
        assert fast_output["patch"]["field_intents"]["value"] == ["required_documents"]

        wrong_model_output = output(act="PROVIDE_CLARIFICATION", topic="SWITCH")
        wrong_model_output["patch"]["procedure_id"] = {
            "op": "SET",
            "value": "p_house_number",
            "evidence": [{"message_id": "current-user", "quote": "hồ sơ"}],
        }
        repaired, actions = apply_intent_context_policy(wrong_model_output, item)
        assert repaired == fast_output
        assert actions == ["FIELD_ONLY_REPLY_KEEPS_PROCEDURE"]


def test_field_only_reply_without_a_procedure_does_not_choose_house_number():
    item = payload("hồ sơ")
    item["procedure_candidates"].append(
        {"id": "p_house_number", "name": "HỒ SƠ CẤP SỐ NHÀ"}
    )
    resolved = resolve_high_confidence_without_model(item)
    assert resolved is not None
    fast_output, _ = resolved
    assert fast_output["topic_action"] == "UNRESOLVED"
    assert fast_output["patch"]["procedure_id"]["op"] == "KEEP"
    assert fast_output["patch"]["field_intents"]["op"] == "KEEP"


def test_explicit_house_number_request_is_not_treated_as_field_only():
    item = payload("Hồ sơ cấp số nhà cần giấy tờ gì?", procedure_id="p_birth")
    item["procedure_candidates"].append(
        {"id": "p_house_number", "name": "HỒ SƠ CẤP SỐ NHÀ"}
    )
    assert resolve_high_confidence_without_model(item) is not None
    resolved, _ = resolve_high_confidence_without_model(item)
    assert resolved["topic_action"] == "SWITCH"
    assert resolved["patch"]["procedure_id"]["value"] == "p_house_number"


def test_correction_uses_catalog_qualifier_to_switch_procedure_variant():
    item = payload(
        "À không, tôi kết hôn với người nước ngoài chứ không phải người trong nước.",
        procedure_id="p_marriage",
        field_intents=["required_documents"],
    )
    item["procedure_candidates"].append(
        {
            "id": "p_foreign_marriage",
            "name": "Đăng ký kết hôn có yếu tố nước ngoài",
        }
    )

    resolved = resolve_high_confidence_without_model(item)

    assert resolved is not None
    normalized, actions = resolved
    assert normalized["dialogue_act"] == "CORRECT_CONTEXT"
    assert normalized["topic_action"] == "SWITCH"
    assert normalized["patch"]["procedure_id"]["value"] == "p_foreign_marriage"
    assert normalized["patch"]["field_intents"]["op"] == "KEEP"
    assert actions == ["DETERMINISTIC_EXPLICIT_TOPIC_SWITCH"]


def test_confirmation_and_remaining_followups_keep_verified_context_without_model():
    for message in (
        "Vậy là 8 nghìn một bản đúng không?",
        "Tôi có CCCD rồi thì còn bổ sung gì nữa?",
    ):
        result = resolve_high_confidence_without_model(
            payload(message, procedure_id="p_birth", field_intents=["fees"])
        )
        assert result is not None
        normalized, actions = result
        assert normalized["dialogue_act"] == "ASK_INFORMATION"
        assert normalized["topic_action"] == "KEEP"
        assert normalized["patch"]["procedure_id"]["op"] == "KEEP"
        assert actions == [
            "DETERMINISTIC_CONTEXTUAL_FOLLOWUP",
            "DOCUMENT_MENTION_CANNOT_SWITCH_ACTIVE_PROCEDURE",
        ]


def test_document_inventory_followup_cannot_switch_to_similar_procedure_title():
    item = payload(
        "Tôi đã có giấy chứng sinh và CCCD của hai vợ chồng rồi, còn cần bổ sung gì nữa?",
        procedure_id="p_birth",
        field_intents=["required_documents"],
    )
    item["procedure_candidates"].append(
        {
            "id": "p_meritorious_relative",
            "name": "Cấp giấy xác nhận thân nhân của người có công",
        }
    )

    resolved = resolve_high_confidence_without_model(item)

    assert resolved is not None
    normalized, actions = resolved
    assert normalized["topic_action"] == "KEEP"
    assert normalized["patch"]["procedure_id"]["op"] == "KEEP"
    assert normalized["patch"]["field_intents"]["value"] == [
        "required_documents"
    ]
    assert "DOCUMENT_MENTION_CANNOT_SWITCH_ACTIVE_PROCEDURE" in actions


def test_model_cannot_switch_active_procedure_from_document_words():
    item = payload(
        "Tôi đã có giấy chứng sinh và CCCD rồi, còn cần bổ sung gì nữa?",
        procedure_id="p_birth",
        field_intents=["required_documents"],
    )
    item["procedure_candidates"].append(
        {
            "id": "p_meritorious_relative",
            "name": "Cấp giấy xác nhận thân nhân của người có công",
        }
    )
    candidate = output(topic="SWITCH")
    candidate["patch"]["procedure_id"] = {
        "op": "SET",
        "value": "p_meritorious_relative",
        "evidence": [{"message_id": "current-user", "quote": "giấy chứng sinh"}],
    }

    normalized, actions = apply_intent_context_policy(candidate, item)

    assert normalized["topic_action"] == "KEEP"
    assert normalized["patch"]["procedure_id"]["op"] == "KEEP"
    assert "DOCUMENT_MENTION_CANNOT_SWITCH_ACTIVE_PROCEDURE" in actions


def test_document_field_uses_concept_structure_not_single_fixed_phrase():
    for message in (
        "Hồ sơ cần gì?",
        "Bộ hồ sơ này gồm những gì?",
        "Tôi phải chuẩn bị các tài liệu nào?",
        "Cần mang những giấy tờ nào?",
    ):
        resolved = resolve_high_confidence_without_model(
            payload(message, procedure_id="p_birth")
        )
        assert resolved is not None
        normalized, _ = resolved
        assert normalized["patch"]["field_intents"]["value"] == [
            "required_documents"
        ]


def test_confirmation_claim_values_select_their_field_instead_of_stale_carryover():
    cases = (
        (
            "Vậy bản chính không mất phí, chỉ bản sao mới 8 nghìn một bản đúng không?",
            ["fees"],
        ),
        ("Vậy thời gian xử lý là 1 ngày đúng không?", ["processing_times"]),
        (
            "Nếu tôi nộp online thì vẫn phải mang bản chính tới đối chiếu à?",
            ["required_documents", "submission_methods"],
        ),
        (
            "Nếu tôi nộp onl thì vẫn phải mang bản chính tới đối chiếu à?",
            ["required_documents", "submission_methods"],
        ),
    )
    for message, expected_fields in cases:
        resolved = resolve_high_confidence_without_model(
            payload(
                message,
                procedure_id="p_birth",
                field_intents=["required_documents"],
            )
        )
        assert resolved is not None
        normalized, _ = resolved
        assert normalized["patch"]["field_intents"]["value"] == expected_fields


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


def test_fast_route_handles_realistic_multifield_story_with_incidental_location():
    resolved = resolve_high_confidence_without_model(
        payload(
            "Tôi đang ở phường Tăng Nhơn Phú, vừa có con và muốn đăng ký khai sinh. "
            "Tôi muốn biết cần chuẩn bị giấy tờ gì, có nộp trực tuyến được không, "
            "nộp ở đâu, mất bao lâu và có phải đóng lệ phí không?"
        )
    )

    assert resolved is not None
    output, actions = resolved
    assert output["topic_action"] == "SWITCH"
    assert output["patch"]["procedure_id"]["value"] == "p_birth"
    assert output["patch"]["field_intents"]["value"] == [
        "fees",
        "processing_times",
        "receiving_authority",
        "required_documents",
        "submission_methods",
    ]
    assert output["patch"]["jurisdiction"]["op"] == "KEEP"
    assert actions == [
        "DETERMINISTIC_HIGH_CONFIDENCE_ROUTE",
        "INCIDENTAL_LOCATION_NOT_USED_AS_LEGAL_FILTER",
    ]


def test_fast_route_handles_incidental_location_after_narrative_clause():
    resolved = resolve_high_confidence_without_model(
        payload(
            "Tôi vừa có con và đang ở phường Tăng Nhơn Phú. Tôi muốn đăng ký "
            "khai sinh, cần chuẩn bị giấy tờ gì, nộp ở đâu, có nộp trực tuyến "
            "được không, mất bao lâu và lệ phí bao nhiêu?"
        )
    )

    assert resolved is not None
    output, actions = resolved
    assert output["patch"]["procedure_id"]["value"] == "p_birth"
    assert output["patch"]["jurisdiction"]["op"] == "KEEP"
    assert output["patch"]["field_intents"]["value"] == [
        "fees",
        "processing_times",
        "receiving_authority",
        "required_documents",
        "submission_methods",
    ]
    assert "INCIDENTAL_LOCATION_NOT_USED_AS_LEGAL_FILTER" in actions


def test_fast_route_still_defers_explicit_jurisdiction_applicability_question():
    assert (
        resolve_high_confidence_without_model(
            payload(
                "Tôi muốn biết thủ tục đăng ký khai sinh có áp dụng ở phường "
                "Tăng Nhơn Phú không?"
            )
        )
        is None
    )


def test_fast_route_keeps_relevant_literal_evidence_for_very_long_story():
    message = (
        "Gia đình tôi đang chuẩn bị nhiều việc sau khi có em bé. " * 8
        + "Tôi muốn đăng ký khai sinh và cần biết giấy tờ gì, nộp ở đâu, "
        "có nộp trực tuyến được không, mất bao lâu và lệ phí thế nào?"
    )
    resolved = resolve_high_confidence_without_model(payload(message))

    assert resolved is not None
    output, _ = resolved
    for slot in ("procedure_id", "field_intents"):
        quote = output["patch"][slot]["evidence"][0]["quote"]
        assert len(quote) <= 300
        assert quote in message
        assert "đăng ký khai sinh" in quote


def test_natural_school_transfer_does_not_match_house_number_or_fake_correction():
    realistic = payload(
        "Con tôi đang học cấp 2 và muốn chuyển sang một trường THCS khác. "
        "Gia đình cần chuẩn bị hồ sơ gì, gửi ở đâu, có nộp qua mạng được không, "
        "bao lâu có kết quả và tốn khoản nào?"
    )
    realistic["procedure_candidates"].extend(
        [
            {"id": "p_school", "name": "Chuyển trường đối với học sinh THCS"},
            {"id": "p_house", "name": "Hồ sơ cấp số nhà"},
        ]
    )

    resolved = resolve_high_confidence_without_model(realistic)

    assert resolved is not None
    output, _ = resolved
    assert output["dialogue_act"] == "ASK_INFORMATION"
    assert output["patch"]["procedure_id"]["value"] == "p_school"
    assert output["patch"]["field_intents"]["value"] == [
        "fees",
        "processing_times",
        "receiving_authority",
        "required_documents",
        "submission_methods",
    ]


def test_explicitly_unknown_procedure_family_stays_unresolved():
    realistic = payload(
        "Gia đình tôi muốn xin hỗ trợ mai táng nhưng chưa rõ thuộc thủ tục nào, "
        "cần chuẩn bị giấy tờ và nộp ở đâu?"
    )

    resolved = resolve_high_confidence_without_model(realistic)

    assert resolved is not None
    output, actions = resolved
    assert output["topic_action"] == "UNRESOLVED"
    assert output["patch"]["procedure_id"]["op"] == "KEEP"
    assert actions == ["DETERMINISTIC_EXPLICIT_UNRESOLVED"]


def test_followup_extracts_all_fields_when_document_phrase_is_reversed():
    resolved = resolve_high_confidence_without_model(
        payload(
            "Còn lệ phí và hồ sơ cần chuẩn bị thì sao?",
            procedure_id="p_marriage",
            field_intents=["submission_methods"],
        )
    )

    assert resolved is not None
    output, _ = resolved
    assert output["topic_action"] == "KEEP"
    assert output["patch"]["field_intents"]["value"] == [
        "fees",
        "required_documents",
    ]


def test_cccd_document_followup_does_not_trigger_legal_bases():
    resolved = resolve_high_confidence_without_model(
        payload(
            "Tôi có căn cước công dân rồi, cần bổ sung gì nữa?",
            procedure_id="p_birth",
            field_intents=["required_documents"],
        )
    )

    assert resolved is not None
    output, _ = resolved
    assert output["topic_action"] == "KEEP"
    assert output["patch"]["field_intents"]["value"] == ["required_documents"]


def test_can_cuoc_alone_is_not_a_legal_basis_phrase():
    candidate = output()
    candidate["patch"]["field_intents"] = {
        "op": "SET",
        "value": ["legal_bases"],
        "evidence": [
            {
                "message_id": "current-user",
                "quote": "Tôi đã có căn cước công dân.",
            }
        ],
    }

    normalized, actions = apply_intent_context_policy(
        candidate,
        payload("Tôi đã có căn cước công dân.", procedure_id="p_birth"),
    )

    assert normalized["patch"]["field_intents"]["op"] == "KEEP"
    assert normalized["patch"]["field_intents"]["value"] is None
    assert "UNSUPPORTED_LEGAL_BASIS_GUESS_REMOVED" in actions


def test_colloquial_return_to_birth_switches_topic_without_guessing_a_field():
    resolved = resolve_high_confidence_without_model(
        payload(
            "Không, quay lại cái sinh con cơ.",
            procedure_id="p_marriage",
            field_intents=["required_documents"],
        )
    )

    assert resolved is not None
    output, actions = resolved
    assert output["dialogue_act"] == "CORRECT_CONTEXT"
    assert output["topic_action"] == "SWITCH"
    assert output["patch"]["procedure_id"]["value"] == "p_birth"
    assert output["patch"]["field_intents"]["op"] == "KEEP"
    assert actions == ["DETERMINISTIC_EXPLICIT_TOPIC_SWITCH"]


def test_reviewed_typo_switches_to_birth_without_reusing_old_field():
    resolved = resolve_high_confidence_without_model(
        payload(
            "Tôi muốn làm giấy kha sin cho em bé.",
            procedure_id="p_marriage",
            field_intents=["required_documents"],
        )
    )

    assert resolved is not None
    output, _ = resolved
    assert output["topic_action"] == "SWITCH"
    assert output["patch"]["procedure_id"]["value"] == "p_birth"
    assert output["patch"]["field_intents"]["op"] == "KEEP"


def test_repeated_topic_without_field_clears_stale_field_for_clarification():
    resolved = resolve_high_confidence_without_model(
        payload(
            "Tôi muốn hỏi về khai sinh.",
            procedure_id="p_birth",
            field_intents=["required_documents"],
        )
    )

    assert resolved is not None
    output, actions = resolved
    assert output["topic_action"] == "KEEP"
    assert output["patch"]["field_intents"]["op"] == "CLEAR"
    assert actions == ["DETERMINISTIC_TOPIC_ONLY_REQUEST"]


def test_all_information_followup_maps_to_complete_field_request():
    resolved = resolve_high_confidence_without_model(
        payload(
            "Tất cả mọi thứ.",
            procedure_id="p_birth",
            field_intents=[],
            pending_clarification="field_intents",
        )
    )

    assert resolved is not None
    output, _ = resolved
    assert output["patch"]["field_intents"]["value"] == [
        "applicant_scope",
        "fees",
        "legal_bases",
        "processing_times",
        "receiving_authority",
        "required_documents",
        "steps",
        "submission_methods",
    ]


def test_receiving_question_does_not_inherit_incidental_file_field():
    resolved = resolve_high_confidence_without_model(
        payload(
            "Nơi nào nhận bộ hồ sơ này?",
            procedure_id="p_birth",
            field_intents=["required_documents"],
        )
    )
    assert resolved is not None
    output, _ = resolved
    assert output["patch"]["field_intents"]["value"] == ["receiving_authority"]


def test_explicit_slot_clear_is_recovered_when_model_keeps_it():
    normalized, actions = apply_intent_context_policy(
        output(act="CORRECT_CONTEXT"),
        payload(
            "Bỏ mốc ngày đã chọn nhưng giữ thủ tục.",
            procedure_id="p_birth",
            as_of="2026-02-11",
        ),
    )
    assert normalized["patch"]["as_of"]["op"] == "CLEAR"
    assert "EXPLICIT_CLEAR_AS_OF_APPLIED" in actions


def test_unknown_service_wording_is_unresolved_not_out_of_scope():
    normalized, actions = apply_intent_context_policy(
        output(act="OUT_OF_SCOPE", topic="UNRESOLVED"),
        payload("Tôi không rõ dịch vụ mình cần gọi là gì."),
    )
    assert normalized["dialogue_act"] == "ASK_INFORMATION"
    assert normalized["topic_action"] == "UNRESOLVED"
    assert "EXPLICIT_UNRESOLVED_REQUEST" in actions


def test_switch_after_negated_old_topic_keeps_positive_field_clause():
    candidate = output(act="CORRECT_CONTEXT", topic="SWITCH")
    candidate["patch"]["procedure_id"] = {
        "op": "SET",
        "value": "p_birth",
        "evidence": [{"message_id": "current-user", "quote": "khai sinh"}],
    }
    candidate["patch"]["field_intents"] = {
        "op": "CLEAR",
        "value": None,
        "evidence": [{"message_id": "current-user", "quote": "khai sinh"}],
    }
    message = "Không tiếp tục hỏi kết hôn; chuyển sang khai sinh và cho biết nơi tiếp nhận."
    normalized, _ = apply_intent_context_policy(
        candidate,
        payload(message, procedure_id="p_marriage", field_intents=["steps"]),
    )
    assert normalized["patch"]["procedure_id"]["value"] == "p_birth"
    assert normalized["patch"]["field_intents"]["value"] == ["receiving_authority"]


def test_negated_old_field_is_not_kept_by_fast_route():
    resolved = resolve_high_confidence_without_model(
        payload(
            "Không cần hình thức nộp nữa, tôi hỏi thời gian trả kết quả.",
            procedure_id="p_copy",
            field_intents=["submission_methods"],
        )
    )
    assert resolved is not None
    output, _ = resolved
    assert output["dialogue_act"] == "CORRECT_CONTEXT"
    assert output["patch"]["field_intents"]["value"] == ["processing_times"]
