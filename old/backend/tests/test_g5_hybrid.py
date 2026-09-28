from types import SimpleNamespace

import httpx
import pytest

from app.rag.g5.hybrid import HybridProcedureRouter


def _data():
    return SimpleNamespace(
        fingerprint="a" * 64,
        sources={
            "source-alpha": {"procedure_code": "ALPHA"},
            "source-beta": {"procedure_code": "BETA"},
        },
        procedures={
            "procedure-alpha": {
                "title": "Thủ tục alpha unique service",
                "aliases": ["alpha service"],
                "source_ids": ["source-alpha"],
                "category_label": "Nhóm alpha",
            },
            "procedure-beta": {
                "title": "Thủ tục beta different service",
                "aliases": ["beta service"],
                "source_ids": ["source-beta"],
                "category_label": "Nhóm beta",
            },
        },
    )


def _vector(text):
    # Procedure A wins on its unique title token; vectors are intentionally tiny.
    if "alpha" in text or "concept a" in text:
        return [1.0, 0.0]
    if "beta" in text:
        return [0.0, 1.0]
    return [0.7, 0.7]


@pytest.mark.asyncio
async def test_hybrid_router_uses_dense_and_lexical_scores():
    data = _data()

    async def handler(request):
        payload = request.read().decode("utf-8")
        import json

        values = json.loads(payload)["input"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": index, "embedding": _vector(value)}
                    for index, value in enumerate(values)
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    router = HybridProcedureRouter(
        base_url="http://localhost:8090/v1",
        model_name="fixture",
        min_score=0.1,
        min_margin=0.0,
        client=client,
    )
    result = await router.route(data, "concept a cần giấy tờ gì")
    assert result is not None
    assert result.procedure_id == "procedure-alpha"
    await client.aclose()


@pytest.mark.asyncio
async def test_hybrid_router_skips_embedding_for_explicit_procedure_name():
    async def handler(_request):
        raise AssertionError("embedding service must not be called for exact routing")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    router = HybridProcedureRouter(
        base_url="http://localhost:8090/v1", model_name="fixture", client=client
    )
    assert await router.route(_data(), "alpha service cần giấy tờ gì") is None
    await client.aclose()


@pytest.mark.asyncio
async def test_hybrid_router_fails_open_when_embedding_service_is_down():
    data = _data()

    async def handler(_request):
        raise httpx.ConnectError("offline")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    router = HybridProcedureRouter(
        base_url="http://localhost:8090/v1", model_name="fixture", client=client
    )
    assert await router.route(data, "thủ tục không khớp từ khóa nhưng đủ dài") is None
    await client.aclose()


def test_hybrid_router_rejects_external_or_credentialed_urls():
    with pytest.raises(ValueError, match="G5_EMBEDDING_URL_NOT_ALLOWED"):
        HybridProcedureRouter(base_url="https://example.com/v1", model_name="fixture")
    with pytest.raises(ValueError, match="G5_EMBEDDING_URL_NOT_ALLOWED"):
        HybridProcedureRouter(base_url="http://user:pass@localhost/v1", model_name="fixture")
