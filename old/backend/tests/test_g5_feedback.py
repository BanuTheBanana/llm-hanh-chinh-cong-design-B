"""G5 feedback API: two axes, ownership, edit and delete."""

from uuid import UUID, uuid4

from sqlalchemy import update

from app.models import Message

P = "/api/v1"


async def login(client, name="Minh"):
    response = await client.post(P + "/auth/login", json={"display_name": name})
    assert response.status_code == 200, response.text


async def completed_pair(client, ai_mock):
    await login(client)
    conversation = await client.post(P + "/conversations", json={})
    conversation_id = conversation.json()["id"]
    response = await client.post(
        P + f"/conversations/{conversation_id}/messages",
        json={"client_message_id": str(uuid4()), "content": "Câu hỏi để đánh giá"},
    )
    assert response.status_code == 200, response.text
    return conversation_id, response.json()


async def test_feedback_create_edit_list_and_delete(client, database, ai_mock):
    conversation_id, pair = await completed_pair(client, ai_mock)
    message_id = pair["assistant_message"]["id"]
    path = P + f"/messages/{message_id}/feedback"
    async with database() as db:
        await db.execute(
            update(Message)
            .where(Message.id == UUID(message_id))
            .values(
                grounding={
                    "provider": "local",
                    "model": "Qwen3-1.7B",
                    "corpus_version": "demo10-v1",
                    "prompt_version": "grounded-v2",
                }
            )
        )
        await db.commit()

    created = await client.put(
        path,
        json={
            "relevance": "relevant",
            "satisfaction": "not_satisfied",
            "reason": "  Còn khó hiểu.  ",
        },
    )
    assert created.status_code == 200, created.text
    first = created.json()
    assert first["message_id"] == message_id
    assert first["relevance"] == "relevant"
    assert first["satisfaction"] == "not_satisfied"
    assert first["reason"] == "Còn khó hiểu."
    assert first["provider"] == "local"
    assert first["model"] == "Qwen3-1.7B"
    assert first["corpus_version"] == "demo10-v1"
    assert first["prompt_version"] == "grounded-v2"

    listed = await client.get(P + f"/conversations/{conversation_id}/feedback")
    assert listed.status_code == 200
    assert listed.json() == [first]

    updated = await client.put(
        path,
        json={
            "relevance": "not_relevant",
            "satisfaction": "satisfied",
            "reason": "",
        },
    )
    assert updated.status_code == 200, updated.text
    second = updated.json()
    assert second["id"] == first["id"]
    assert second["created_at"] == first["created_at"]
    assert second["relevance"] == "not_relevant"
    assert second["satisfaction"] == "satisfied"
    assert "reason" not in second

    assert (await client.delete(path)).status_code == 204
    assert (await client.get(P + f"/conversations/{conversation_id}/feedback")).json() == []
    assert (await client.delete(path)).status_code == 204


async def test_feedback_requires_owned_completed_assistant_message(client, ai_mock):
    conversation_id, pair = await completed_pair(client, ai_mock)
    assistant_id = pair["assistant_message"]["id"]
    user_message_id = pair["user_message"]["id"]
    payload = {"relevance": "relevant", "satisfaction": "satisfied"}

    user_response = await client.put(P + f"/messages/{user_message_id}/feedback", json=payload)
    assert user_response.status_code == 422
    assert user_response.json()["error"]["code"] == "ASSISTANT_MESSAGE_REQUIRED"

    await login(client, "Hoan")
    hidden_message = await client.put(P + f"/messages/{assistant_id}/feedback", json=payload)
    assert hidden_message.status_code == 404
    assert hidden_message.json()["error"]["code"] == "NOT_FOUND"
    hidden_list = await client.get(P + f"/conversations/{conversation_id}/feedback")
    assert hidden_list.status_code == 404


async def test_feedback_contract_rejects_partial_invalid_or_extra_input(client, ai_mock):
    _, pair = await completed_pair(client, ai_mock)
    path = P + f"/messages/{pair['assistant_message']['id']}/feedback"
    invalid = (
        {"relevance": "relevant"},
        {"relevance": "maybe", "satisfaction": "satisfied"},
        {"relevance": "relevant", "satisfaction": "satisfied", "reason": "x" * 1001},
        {"relevance": "relevant", "satisfaction": "satisfied", "auto_train": True},
    )
    for payload in invalid:
        response = await client.put(path, json=payload)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
