"""Requires TEST_DATABASE_URL; actual PostgreSQL migration and HTTP conversation flow."""

import json
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from test_g3 import VERSION, write_dataset
from test_g4 import expanded_groups

from app.ai import AIClient, get_ai
from app.config import get_settings
from app.main import app
from app.models import Conversation
from app.rag.g3.runtime import load_active_dataset
from app.rag.g3.validator import load_serving


async def test_g4_persistence_retry_switch_and_user_isolation(
    client, database, monkeypatch, tmp_path
):
    root = write_dataset(tmp_path, expanded_groups())
    (root / "gold/questions.jsonl").unlink()
    data = load_serving(root, VERSION, 2)
    for key, value in dict(
        rag_enabled=True,
        g3_d2_enabled=True,
        rag_corpus_version=VERSION,
        g3_private_dataset_path=root,
        g3_expected_rows=2,
        g3_corpus_sha256=data.fingerprint,
    ).items():
        monkeypatch.setattr(get_settings(), key, value)
    calls = []

    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload)
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
                "provider": "mock",
                "model": "mock-g4",
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "latency_ms": 1,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        app.dependency_overrides[get_ai] = lambda: AIClient(http)
        await client.post("/api/v1/auth/login", json={"display_name": "Fictional G4 User"})
        conv = await client.post("/api/v1/conversations", json={})
        cid = conv.json()["id"]
        path = f"/api/v1/conversations/{cid}/messages"
        first_id = None
        for question in ["Mẫu Alpha cần giấy tờ gì?", "Nộp hồ sơ ở đâu?", "Còn lệ phí?"]:
            body = {"content": question, "client_message_id": str(uuid4())}
            response = await client.post(path, json=body)
            assert response.status_code == 200, response.text
            if first_id is None:
                first_id = response.json()["user_message"]["id"]
            assert all(e["procedure_id"] == "fictional-alpha" for e in calls[-1]["evidence"])
            # Clear process cache and reload history between requests.
            load_active_dataset.cache_clear()
            assert (await client.get(path)).status_code == 200
        count = len(calls)
        assert (await client.post(path, json=body)).json() == response.json()
        assert len(calls) == count
        async with database() as db:
            stored = await db.scalar(select(Conversation).where(Conversation.id == UUID(cid)))
            assert stored.rag_context["active_procedure_id"] == "fictional-alpha"
            assert stored.rag_context["source_message_ids"]["active_procedure_id"] == first_id
        response = await client.post(
            path, json={"content": "Mẫu Beta lệ phí?", "client_message_id": str(uuid4())}
        )
        assert response.status_code == 200
        assert all(e["procedure_id"] == "fictional-beta" for e in calls[-1]["evidence"])
        second = await client.post("/api/v1/conversations", json={})
        other_path = f"/api/v1/conversations/{second.json()['id']}/messages"
        response = await client.post(
            other_path, json={"content": "Còn lệ phí?", "client_message_id": str(uuid4())}
        )
        assert response.json()["assistant_message"]["grounding"]["status"] == "NEED_CLARIFICATION"
        await client.post("/api/v1/auth/login", json={"display_name": "Other Fictional G4 User"})
        assert (await client.get(path)).status_code == 404
        assert (
            await client.post(
                path, json={"content": "Còn lệ phí?", "client_message_id": str(uuid4())}
            )
        ).status_code == 404
