"""Requires TEST_DATABASE_URL; exercises model intent through the real chat transaction."""

import json
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from test_g3 import VERSION, fixture_groups, write_dataset

from app.ai import AIClient, get_ai
from app.config import get_settings
from app.main import app
from app.models import Conversation
from app.rag.g3.validator import load_serving


async def test_model_intent_context_persists_followup_switch_and_reset(
    client, database, monkeypatch, tmp_path
):
    root = write_dataset(tmp_path, fixture_groups())
    (root / "gold/questions.jsonl").unlink()
    data = load_serving(root, VERSION, 2)
    for key, value in {
        "rag_enabled": True,
        "g3_d2_enabled": True,
        "rag_corpus_version": VERSION,
        "g3_private_dataset_path": root,
        "g3_expected_rows": 2,
        "g3_corpus_sha256": data.fingerprint,
        "g4_answer_plan_enabled": True,
        "g5_intent_context_enabled": True,
        "g5_intent_context_fallback_enabled": False,
    }.items():
        monkeypatch.setattr(get_settings(), key, value)

    intent_calls = []
    grounded_calls = []

    def handler(request):
        payload = json.loads(request.content)
        if request.url.path == "/internal/v3/intent-context":
            intent_calls.append(payload)
            message = payload["current_user_message"]
            evidence = [{"message_id": payload["current_message_id"], "quote": message}]
            keep = {"op": "KEEP", "value": None, "evidence": []}
            if message == "Bắt đầu lại":
                dialogue_act, topic = "RESET_CONTEXT", "RESET"
                procedure = field = keep
            elif "Beta" in message:
                dialogue_act, topic = "CORRECT_CONTEXT", "SWITCH"
                procedure = {"op": "SET", "value": "fictional-beta", "evidence": evidence}
                field = {"op": "SET", "value": ["fees"], "evidence": evidence}
            elif message == "Còn lệ phí?":
                assert payload["state_before"]["procedure_id"] == "fictional-alpha"
                dialogue_act, topic = "ASK_INFORMATION", "KEEP"
                procedure = keep
                field = {"op": "SET", "value": ["fees"], "evidence": evidence}
            else:
                dialogue_act, topic = "ASK_INFORMATION", "SWITCH"
                procedure = {"op": "SET", "value": "fictional-alpha", "evidence": evidence}
                field = {"op": "SET", "value": ["fees"], "evidence": evidence}
            output = {
                "schema_version": "g5-intent-context-v2",
                "dialogue_act": dialogue_act,
                "topic_action": topic,
                "patch": {
                    "procedure_id": procedure,
                    "field_intents": field,
                    "jurisdiction": keep,
                    "as_of": keep,
                },
            }
            return httpx.Response(
                200,
                json={
                    "request_id": payload["request_id"],
                    "output": output,
                    "provider": "fixture-intent",
                    "model": "fixture-intent-v1",
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                    "latency_ms": 1,
                },
            )
        assert request.url.path == "/internal/v2/generate"
        grounded_calls.append(payload)
        return httpx.Response(
            200,
            json={
                "request_id": payload["request_id"],
                "evidence_bundle_id": payload["evidence_bundle_id"],
                "corpus_version": payload["corpus_version"],
                "data_classification": payload["data_classification"],
                "prompt_version": "g2-grounded-v2",
                "answer": "Dữ kiện hư cấu.",
                "status": "ANSWER",
                "cited_fragment_ids": [payload["evidence"][0]["fragment_id"]],
                "missing_information": [],
                "provider": "fixture-grounded",
                "model": "fixture-grounded-v1",
                "usage": {"input_tokens": 1, "output_tokens": 1},
                "latency_ms": 1,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        app.dependency_overrides[get_ai] = lambda: AIClient(http)
        await client.post("/api/v1/auth/login", json={"display_name": "Fictional G5 Intent"})
        conversation = await client.post("/api/v1/conversations", json={})
        conversation_id = conversation.json()["id"]
        path = f"/api/v1/conversations/{conversation_id}/messages"
        for message in (
            "Mẫu Alpha có lệ phí không?",
            "Còn lệ phí?",
            "Không, đổi sang Mẫu Beta và hỏi lệ phí",
            "Bắt đầu lại",
        ):
            response = await client.post(
                path,
                json={"content": message, "client_message_id": str(uuid4())},
            )
            assert response.status_code == 200, response.text

        assert len(intent_calls) == 4
        assert len(grounded_calls) == 3
        assert all(
            fragment["procedure_id"] == "fictional-alpha"
            for fragment in grounded_calls[1]["evidence"]
        )
        assert all(
            fragment["procedure_id"] == "fictional-beta"
            for fragment in grounded_calls[2]["evidence"]
        )
        assert response.json()["assistant_message"]["content"].startswith("Đã xóa")
        async with database() as session:
            stored = await session.scalar(
                select(Conversation).where(Conversation.id == UUID(conversation_id))
            )
            assert stored.rag_context["schema_version"] == "g5-context-state-v1"
            assert stored.rag_context["procedure_id"] is None
            assert stored.rag_context["field_intents"] == []
            assert stored.rag_context["revision"] == 4
