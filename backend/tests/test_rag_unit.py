import copy
import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest

from app.errors import APIError
from app.rag import grounding
from app.rag.corpus import CorpusError, validate_corpus
from app.rag.evaluation import evaluate
from app.rag.grounding import generate_grounded, validate_answer
from app.rag.retrieval import normalize, retrieve
from app.rag.schemas import Filters, GroundedAnswer, RetrievalInput

ROOT = Path(__file__).resolve().parents[2]
DATA = Path("backend/tests/fixtures/rag")


@pytest.fixture
def corpus():
    return validate_corpus(ROOT, ROOT / DATA, "fixture-v1", {"fixture.invalid"}, True)


@pytest.fixture
def dataset_copy(tmp_path):
    shutil.copytree(ROOT / DATA, tmp_path / DATA)
    return tmp_path


def load(root, allow=True):
    return validate_corpus(root, root / DATA, "fixture-v1", {"fixture.invalid"}, allow)


def edit(root, path, transform):
    file = root / DATA / path
    rows = [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines()]
    transform(rows)
    file.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def test_fixture_requires_optin():
    with pytest.raises(CorpusError, match="FIXTURE_REQUIRES"):
        load(ROOT, False)


def test_stable_hash_and_unicode(corpus):
    assert load(ROOT).fingerprint == corpus.fingerprint
    assert normalize("ĐĂNG KÝ") == normalize("dang ky")
    before = corpus.fragments["frag_documents"].text
    retrieve(corpus, RetrievalInput(query="HO SO"), uuid4())
    assert corpus.fragments["frag_documents"].text == before


@pytest.mark.parametrize(
    "path,change,error",
    [
        ("source_manifest.jsonl", lambda rows: rows.append(rows[0]), "DUPLICATE_ID"),
        ("source_manifest.jsonl", lambda r: r[0].update(content_sha256="0" * 64), "RAW_HASH"),
        ("source_manifest.jsonl", lambda r: r[0].update(raw_path="../../escape"), "RAW_PATH"),
        ("source_manifest.jsonl", lambda r: r[0].update(review_status="PENDING"), "NOT_REVIEWED"),
        (
            "source_manifest.jsonl",
            lambda r: r[0].update(source_url="https://evil.invalid/x"),
            "URL_NOT",
        ),
        ("source_manifest.jsonl", lambda r: r[0].update(usage="D1_PUBLIC_DEMO"), "CANNOT_BE_D1"),
        ("normalized/fragments.jsonl", lambda r: r[0].update(source_id="missing"), "BROKEN"),
        (
            "normalized/fragments.jsonl",
            lambda r: r[0].update(content_sha256="0" * 64),
            "FRAGMENT_HASH",
        ),
        ("normalized/procedures.jsonl", lambda r: r[0].update(field_evidence={}), "PROVENANCE"),
        (
            "normalized/procedures.jsonl",
            lambda r: r[0].update(jurisdiction="OTHER"),
            "JURISDICTION",
        ),
    ],
)
def test_invalid_corpus(dataset_copy, path, change, error):
    edit(dataset_copy, path, change)
    with pytest.raises(CorpusError, match=error):
        load(dataset_copy)


@pytest.mark.parametrize(
    "query,expected",
    [("DEMO001", 3), ("làm phiếu sao xanh", 3), ("lam phieu sao xanh", 3), ("quantumxyz", 0)],
)
def test_exact_alias_and_nohit(corpus, query, expected):
    found = retrieve(corpus, RetrievalInput(query=query), UUID(int=1))
    assert len(found.bundle.evidence) == expected
    assert found == retrieve(corpus, RetrievalInput(query=query), UUID(int=1))


def test_keyword_and_filters(corpus):
    found = retrieve(corpus, RetrievalInput(query="le phi", top_k=1), uuid4())
    assert found.bundle.evidence[0].fragment_id == "frag_fees"
    for filters in [
        Filters(jurisdiction="OTHER"),
        Filters(procedure_id="missing"),
        Filters(as_of="2027-01-01"),
    ]:
        assert not retrieve(
            corpus, RetrievalInput(query="DEMO001", filters=filters), uuid4()
        ).bundle.evidence
    source = corpus.sources["src_synthetic"]
    source.effective_to = None
    open_ended = retrieve(
        corpus, RetrievalInput(query="DEMO001", filters=Filters(as_of="2026-06-01")), uuid4()
    ).bundle.evidence
    assert open_ended and all(item.validity_status == "CURRENT" for item in open_ended)
    source.effective_from = None
    assert not retrieve(
        corpus, RetrievalInput(query="DEMO001", filters=Filters(as_of="2026-06-01")), uuid4()
    ).bundle.evidence


def test_ambiguous_scope(corpus):
    corpus = copy.deepcopy(corpus)
    corpus.sources["src_other"] = corpus.sources["src_synthetic"].model_copy(
        update={"source_id": "src_other", "jurisdiction": "OTHER"}
    )
    corpus.procedures["proc_other"] = corpus.procedures["proc_demo"].model_copy(
        update={"procedure_id": "proc_other", "source_ids": ["src_other"], "jurisdiction": "OTHER"}
    )
    corpus.fragments["frag_other"] = corpus.fragments["frag_documents"].model_copy(
        update={"fragment_id": "frag_other", "source_id": "src_other", "procedure_id": "proc_other"}
    )
    result = retrieve(corpus, RetrievalInput(query="làm phiếu sao xanh"), uuid4())
    assert result.needs_clarification and not result.bundle.evidence


@pytest.mark.parametrize("jurisdiction", ["DEMO_SCOPE", "OTHER"])
def test_ambiguity_is_detected_before_top_k_and_across_procedures(corpus, jurisdiction):
    corpus = copy.deepcopy(corpus)
    corpus.sources["src_other"] = corpus.sources["src_synthetic"].model_copy(
        update={"source_id": "src_other", "jurisdiction": jurisdiction}
    )
    corpus.procedures["proc_other"] = corpus.procedures["proc_demo"].model_copy(
        update={
            "procedure_id": "proc_other",
            "title": "Thủ tục khác",
            "aliases": ["thủ tục khác"],
            "source_ids": ["src_other"],
            "jurisdiction": jurisdiction,
        }
    )
    corpus.fragments["frag_other"] = corpus.fragments["frag_documents"].model_copy(
        update={"fragment_id": "frag_other", "source_id": "src_other", "procedure_id": "proc_other"}
    )
    result = retrieve(corpus, RetrievalInput(query="hồ sơ", top_k=1), uuid4())
    assert result.needs_clarification and not result.bundle.evidence


def response(bundle, **changes):
    result = GroundedAnswer.model_validate(
        {
            "request_id": str(bundle.request_id),
            "evidence_bundle_id": str(bundle.evidence_bundle_id),
            "corpus_version": bundle.corpus_version,
            "data_classification": bundle.data_classification,
            "prompt_version": "g2-grounded-v2",
            "answer": "Fixture answer",
            "status": "ANSWER",
            "cited_fragment_ids": [bundle.evidence[0].fragment_id],
            "missing_information": [],
            "provider": "mock",
            "model": "grounded-mock",
            "usage": {"input_tokens": 0, "output_tokens": 0},
            "latency_ms": 1,
        }
    )
    return result.model_copy(update=changes)


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"request_id": uuid4()}, "AI_RESPONSE_BINDING_INVALID"),
        ({"evidence_bundle_id": uuid4()}, "AI_RESPONSE_BINDING_INVALID"),
        ({"corpus_version": "other-v1"}, "AI_RESPONSE_BINDING_INVALID"),
        ({"data_classification": "D1_PUBLIC_DEMO"}, "AI_RESPONSE_BINDING_INVALID"),
        ({"prompt_version": "g2-grounded-v1"}, "AI_RESPONSE_BINDING_INVALID"),
        ({"cited_fragment_ids": ["fabricated"]}, "AI_CITATION_INVALID"),
        ({"cited_fragment_ids": []}, "AI_RESPONSE_INVALID"),
        ({"cited_fragment_ids": ["frag_fees", "frag_fees"]}, "AI_CITATION_INVALID"),
        ({"missing_information": ["extra"]}, "AI_RESPONSE_INVALID"),
        (
            {"status": "INSUFFICIENT_DATA", "cited_fragment_ids": ["frag_fees"]},
            "AI_RESPONSE_INVALID",
        ),
    ],
)
def test_invalid_citations(corpus, changes, code):
    bundle = retrieve(corpus, RetrievalInput(query="le phi"), uuid4()).bundle
    with pytest.raises(APIError) as err:
        validate_answer(response(bundle, **changes), bundle)
    assert err.value.code == code


def test_citations_resolved_from_pinned_bundle(corpus):
    bundle = retrieve(corpus, RetrievalInput(query="le phi"), uuid4()).bundle
    result = validate_answer(response(bundle), bundle)
    assert result.sources[0].url == "https://fixture.invalid/synthetic"
    assert result.corpus_version == corpus.version


async def test_no_evidence_never_calls_ai(corpus, monkeypatch):
    monkeypatch.setattr(grounding, "load_corpus", AsyncMock(return_value=corpus))
    monkeypatch.setattr(grounding.get_settings(), "rag_corpus_version", corpus.version)
    ai = SimpleNamespace(client=object())
    generate = AsyncMock(side_effect=AssertionError("AI should not be called"))
    monkeypatch.setattr(grounding, "generate_grounded", generate)
    _, result = await grounding.answer_with_rag(
        SimpleNamespace(commit=AsyncMock()), RetrievalInput(query="quantumxyz"), uuid4(), ai
    )
    assert result["status"] == "INSUFFICIENT_DATA"
    generate.assert_not_called()


@pytest.mark.parametrize(
    "mode,status", [("success", 200), ("http", 502), ("malformed", 502), ("timeout", 504)]
)
async def test_grounded_http_contract(corpus, mode, status):
    bundle = retrieve(corpus, RetrievalInput(query="le phi"), uuid4()).bundle

    def handler(request):
        assert request.url.path == "/internal/v2/generate"
        body = json.loads(request.content)
        assert body["request_id"] == str(bundle.request_id)
        assert body["evidence_bundle_id"] == str(bundle.evidence_bundle_id)
        assert body["corpus_version"] == bundle.corpus_version
        assert body["data_classification"] == "D0_SYSTEM_SMOKE"
        assert "history" not in body
        assert "url" not in body["evidence"][0]
        assert "score" not in body["evidence"][0]
        assert "metadata" not in body["evidence"][0]
        if mode == "timeout":
            raise httpx.ReadTimeout("test")
        if mode == "http":
            return httpx.Response(500)
        if mode == "malformed":
            return httpx.Response(200, json={})
        return httpx.Response(200, json=response(bundle).model_dump(mode="json"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        if status == 200:
            assert (await generate_grounded(client, bundle)).status == "ANSWER"
        else:
            with pytest.raises(APIError) as err:
                await generate_grounded(client, bundle)
            assert err.value.status == status


def test_evaluation_does_not_use_gold_procedure_as_filter(corpus, dataset_copy):
    report = evaluate(corpus, ROOT / DATA / "gold/questions.jsonl")
    assert report["query_count"] == 10 and report["synthetic_fixture"]
    assert report["recall_at_k"] == 1 and report["mrr"] == 1
    assert not report["failed_question_ids"]
    edit(dataset_copy, "gold/questions.jsonl", lambda r: r[0].update(gold_fragment_ids=["bad"]))
    with pytest.raises(CorpusError, match="GOLD_REFERENCE"):
        evaluate(corpus, dataset_copy / DATA / "gold/questions.jsonl")
