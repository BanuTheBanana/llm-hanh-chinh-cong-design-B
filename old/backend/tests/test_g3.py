"""Fictional content only. D2 label exercises the frozen schema, not real data."""

import copy
import json
import os
import unicodedata
from pathlib import Path
from uuid import uuid4

import pytest

from app.rag.corpus import CorpusError
from app.rag.g3.cli import main
from app.rag.g3.retrieval import evaluate, retrieve
from app.rag.g3.runtime import (
    load_active_dataset,
    retrieve_active_dataset,
    retrieve_direct_active_dataset,
)
from app.rag.g3.validator import FILES, SECTIONS, digest, load, load_serving
from app.rag.schemas import RetrievalInput

VERSION = "fictional-g3-v1"


def fixture_groups():
    base = dict(
        schema_version="g3-data-v1", dataset_version=VERSION, data_classification="D2_COMPANY_REAL"
    )
    review = dict(
        status="APPROVED_FOR_DEMO",
        reviewer_role="fictional-reviewer",
        reviewed_at="2026-09-09T00:00:00Z",
        note=None,
    )
    scope = dict(country_code="VN", province=None, district=None, ward=None)
    groups = [[] for _ in FILES]
    for ordinal, name in enumerate(["Alpha", "Beta"], 2):
        pid, sid, fid = (
            "fictional-" + name.lower(),
            "source-" + name.lower(),
            "frag-" + name.lower(),
        )
        text = "Lệ phí hư cấu: không thu phí trong mô phỏng."
        source = dict(
            base,
            record_type="SOURCE_MANIFEST",
            source_id=sid,
            source_type="COMPANY_INTERNAL_WORKBOOK",
            title="Nguồn hư cấu " + name,
            source_uri="company-internal://fictional/" + name.lower(),
            public_url=None,
            issuing_authority=None,
            jurisdiction=scope,
            procedure_code="CODE-" + name,
            collected_at=None,
            last_verified_at=None,
            effective_from=None,
            effective_to=None,
            validity_status="UNKNOWN",
            content_sha256="a" * 64,
            raw_locator=dict(workbook_sha256="b" * 64, sheet="Fictional", row_numbers=[ordinal]),
            parser_version="fictional-v1",
            review=copy.deepcopy(review),
        )
        proc = dict(
            base,
            record_type="PROCEDURE_RECORD",
            procedure_id=pid,
            title="Thủ tục hư cấu " + name,
            aliases=["Mẫu " + name],
            category_code="FICTIONAL",
            category_label="Lĩnh vực hư cấu",
            jurisdiction=scope,
            **{field: [] for field in SECTIONS},
            source_ids=[sid],
            field_evidence={field: [] for field in SECTIONS},
            missing_fields=[field for field in SECTIONS if field != "fees"]
            + ["issuing_authority", "jurisdiction", "effective_dates", "public_url"],
            version=VERSION,
            review=copy.deepcopy(review),
        )
        proc["fees"] = [dict(raw_text=text, amount_vnd=0, condition=None)]
        proc["field_evidence"]["fees"] = [fid]
        frag = dict(
            base,
            record_type="PROCEDURE_FRAGMENT",
            fragment_id=fid,
            procedure_id=pid,
            source_id=sid,
            section_type="FEES",
            text=text,
            ordinal=0,
            content_sha256=digest(text.encode()),
            source_locator=dict(
                sheet="Fictional",
                row_number=ordinal,
                column_name="Lệ phí",
                column_index=8,
                raw_cell_sha256="c" * 64,
            ),
        )
        for group, row in zip(groups, [source, proc, frag]):
            group.append(row)
        for suffix, question, status, refs in [
            ("fee", "Lệ phí của Mẫu " + name + " là gì?", "ANSWER", [fid]),
            ("missing", "Mẫu " + name + " nộp ở đâu?", "INSUFFICIENT_DATA", []),
        ]:
            groups[4].append(
                dict(
                    base,
                    record_type="GOLD_QUESTION",
                    question_id="q-" + name.lower() + "-" + suffix,
                    question=question,
                    procedure_id=pid,
                    facts={},
                    expected_status=status,
                    expected_points=[text] if refs else [],
                    forbidden_points=[],
                    gold_source_ids=[sid] if refs else [],
                    gold_fragment_ids=refs,
                    contains_pii=False,
                    split="DEV" if name == "Alpha" else "TEST",
                    author_role="fictional-author",
                    reviewer_role="fictional-reviewer",
                )
            )
    return groups


def write_dataset(root, groups):
    for (filename, _, key), rows in zip(FILES, groups):
        path = root / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(
                json.dumps(r, ensure_ascii=False) + "\n" for r in sorted(rows, key=lambda r: r[key])
            ),
            encoding="utf-8",
            newline="\n",
        )
    return root


@pytest.fixture
def dataset(tmp_path):
    return write_dataset(tmp_path, fixture_groups())


def test_determinism(dataset):
    a = load(dataset, VERSION, 2)
    assert a.fingerprint == load(dataset, VERSION, 2).fingerprint
    assert len(a.accepted) == 2 and a.row_count == 2
    assert a.report()["readiness"] == "READY_FOR_DEMO"


def test_runtime_projects_private_dataset_without_internal_locator(dataset):
    load_active_dataset.cache_clear()
    expected_hash = load_serving(dataset, VERSION, 2).fingerprint
    data = load_active_dataset(str(dataset), VERSION, 2, expected_hash)
    bundle, status, missing = retrieve_active_dataset(
        data,
        RetrievalInput(query="Lệ phí của Mẫu Alpha?"),
        uuid4(),
    )

    assert status == "ANSWER" and not missing
    assert bundle.data_classification == "D2_COMPANY_REAL"
    assert data.groups[3] == {} and data.groups[4] == {}
    assert bundle.evidence[0].url is None
    projection = bundle.model_dump(mode="json")
    assert "source_uri" not in str(projection)
    assert "source_locator" not in str(projection)


def test_direct_catalog_projects_bound_field_without_ranking(dataset):
    data = load_serving(dataset, VERSION, 2)
    bundle, status, missing = retrieve_direct_active_dataset(
        data,
        RetrievalInput(
            query="câu chữ không cần khớp dữ liệu",
            field_intents=["fees"],
            filters={"procedure_id": "fictional-alpha"},
            acquisition_mode="direct_catalog",
        ),
        uuid4(),
    )

    assert status == "ANSWER" and missing == []
    assert [item.fragment_id for item in bundle.evidence] == ["frag-alpha"]
    assert bundle.evidence[0].metadata["acquisition"] == "direct_catalog"
    projection = bundle.model_dump(mode="json")
    assert "source_locator" not in str(projection)
    assert "source_uri" not in str(projection)


@pytest.mark.parametrize(
    ("procedure_id", "fields", "status", "missing"),
    [
        (None, ["fees"], "NEED_CLARIFICATION", ["procedure_id"]),
        ("fictional-alpha", [], "NEED_CLARIFICATION", ["field_intents"]),
        ("fictional-alpha", ["steps"], "INSUFFICIENT_DATA", ["steps"]),
    ],
)
def test_direct_catalog_fails_closed(dataset, procedure_id, fields, status, missing):
    data = load_serving(dataset, VERSION, 2)
    bundle, actual_status, actual_missing = retrieve_direct_active_dataset(
        data,
        RetrievalInput(
            query="kiểm tra",
            field_intents=fields,
            filters={"procedure_id": procedure_id},
            acquisition_mode="direct_catalog",
        ),
        uuid4(),
    )
    assert actual_status == status
    assert actual_missing == missing
    assert bundle.evidence == []


def test_runtime_rejects_a_changed_corpus_under_the_same_version(dataset):
    load_active_dataset.cache_clear()
    with pytest.raises(ValueError, match="G3_CORPUS_HASH_MISMATCH"):
        load_active_dataset(str(dataset), VERSION, 2, "0" * 64)


@pytest.mark.parametrize(
    "query",
    [
        "Lệ phí của Mẫu Alpha?",
        "Phí CODE-Alpha là gì?",
        "Lệ phí Thủ tục hư cấu Alpha?",
        "Hư cấu Alpha có lệ phí gì?",
        "Tôi muốn làm hư cấu Alpha, lệ phí bao nhiêu?",
        "Alpha có lệ phí gì?",
    ],
)
def test_route_binding(dataset, query):
    result = retrieve(load(dataset, VERSION, 2), query)
    assert result["status"] == "ANSWER"
    evidence = result["evidence"][0]
    assert evidence["fragment_id"] == "frag-alpha" and evidence["url"] is None
    assert "source_locator" not in evidence and "source_uri" not in evidence


def test_longest_explicit_procedure_name_wins_over_contained_shorter_name(tmp_path):
    groups = fixture_groups()
    groups[1][1]["title"] = "Thủ tục hư cấu Alpha mở rộng"
    data = load(write_dataset(tmp_path, groups), VERSION, 2)

    result = retrieve(data, "Hư cấu Alpha mở rộng có lệ phí gì?")

    assert result["status"] == "ANSWER"
    assert result["procedure_id"] == "fictional-beta"


@pytest.mark.parametrize(
    "query,status",
    [
        ("Mẫu Alpha nộp ở đâu?", "INSUFFICIENT_DATA"),
        ("Mẫu Alpha lệ phí và nộp ở đâu?", "INSUFFICIENT_DATA"),
        ("Lệ phí Mẫu Alpha và Mẫu Beta?", "NEED_CLARIFICATION"),
        ("Lệ phí thủ tục?", "NEED_CLARIFICATION"),
        ("Hư cấu có lệ phí gì?", "NEED_CLARIFICATION"),
        ("Tôi cần chuẩn bị giấy tờ gì?", "NEED_CLARIFICATION"),
        ("zzyyxx", "INSUFFICIENT_DATA"),
    ],
)
def test_abstention(dataset, query, status):
    result = retrieve(load(dataset, VERSION, 2), query, top_k=1)
    assert result["status"] == status and not result["evidence"]


@pytest.mark.parametrize(
    "case,code",
    [
        ("hash", "FRAGMENT_HASH_MISMATCH"),
        ("missing", "MISSING_FIELD_UNDECLARED"),
        ("binding", "FIELD_EVIDENCE_MISMATCH"),
        ("version", "DATASET_VERSION_MISMATCH"),
        ("schema", "SCHEMA_ERROR"),
        ("split", "GOLD_SPLIT_LEAKAGE"),
        ("row", "LOCATOR_SOURCE_MISMATCH"),
        ("review", "SCHEMA_ERROR"),
        ("pii", "PII_PATTERN_DETECTED"),
        ("phone", "PII_PATTERN_DETECTED"),
        ("cccd", "PII_PATTERN_DETECTED"),
        ("gold", "GOLD_BINDING_MISMATCH"),
    ],
)
def test_reject(tmp_path, case, code):
    g = fixture_groups()
    if case == "hash":
        g[2][0]["text"] += " changed"
    if case == "missing":
        g[1][0]["missing_fields"].remove("receiving_authority")
    if case == "binding":
        g[1][0]["field_evidence"]["fees"] = ["frag-beta"]
    if case == "version":
        g[2][0]["dataset_version"] = "wrong"
    if case == "schema":
        g[1][0]["extra"] = True
    if case == "split":
        g[4][1]["split"] = "TEST"
    if case == "row":
        g[2][0]["source_locator"]["row_number"] = 9
    if case == "review":
        g[0][0]["review"]["reviewer_role"] = None
    if case == "pii":
        g[1][0]["title"] = "test" + "@" + "example.invalid"
    if case == "phone":
        g[1][0]["title"] = "0" + "912345678"
    if case == "cccd":
        g[1][0]["title"] = "123456" + "789012"
    if case == "gold":
        g[4][0]["gold_fragment_ids"] = ["frag-beta"]
    with pytest.raises(CorpusError, match=code):
        load(write_dataset(tmp_path, g), VERSION, 2)


def test_review_production_gate(dataset):
    g = fixture_groups()
    g[0][0]["review"]["status"] = "PENDING_REVIEW"
    d = load(write_dataset(dataset, g), VERSION, 2)
    assert d.rejected["fictional-alpha"] == "SOURCE_NOT_APPROVED"
    assert not retrieve(d, "Lệ phí Mẫu Alpha?")["evidence"]
    assert not load(dataset, VERSION, 2, production=True).accepted


def test_metadata_missing_fields_must_match_source_data(tmp_path):
    groups = fixture_groups()
    groups[0][0]["procedure_code"] = None
    with pytest.raises(CorpusError, match="METADATA_MISSING_FIELD_MISMATCH"):
        load(write_dataset(tmp_path, groups), VERSION, 2)


def test_query_is_normalized_without_mutating_dataset(dataset):
    decomposed = "  " + unicodedata.normalize("NFD", "Lệ phí của Mẫu Alpha?") + "  "
    result = retrieve(load(dataset, VERSION, 2), decomposed)
    assert result["status"] == "ANSWER"
    assert result["procedure_id"] == "fictional-alpha"


def test_conflict(tmp_path):
    g = fixture_groups()
    g[1][0]["review"]["status"] = "QUARANTINED"
    g[3] = [
        dict(
            record_type="CONFLICT_RECORD",
            schema_version="g3-data-v1",
            dataset_version=VERSION,
            conflict_id="conflict-test",
            candidate_procedure_id="fictional-alpha",
            source_ids=["source-alpha", "source-beta"],
            row_numbers=[2, 3],
            conflict_fields=["fees"],
            status="OPEN",
            resolution=None,
            reviewer_role=None,
            reviewed_at=None,
        )
    ]
    assert not load(write_dataset(tmp_path, g), VERSION, 2).accepted
    g[1][0]["review"]["status"] = "APPROVED_FOR_DEMO"
    with pytest.raises(CorpusError, match="OPEN_CONFLICT_NOT_QUARANTINED"):
        load(write_dataset(tmp_path, g), VERSION, 2)


def test_accounting(dataset):
    with pytest.raises(CorpusError, match="ROW_ACCOUNTING_MISMATCH"):
        load(dataset, VERSION)


def test_offline_evaluation(dataset, monkeypatch):
    import socket

    def forbidden(*args, **kwargs):
        pytest.fail("Network access attempted")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    d = load(dataset, VERSION, 2)
    for split in ["DEV", "TEST"]:
        report = evaluate(d, split)
        assert report["recall_at_k"] == report["routing_accuracy"] == 1
        assert all(r["pass"] for r in report["results"])


def test_cli_safe_closed(dataset, capsys):
    args = ["--dataset", str(dataset), "--version", VERSION, "--expected-rows", "2"]
    assert main(["query", *args, "--query", "Lệ phí Mẫu Alpha?"]) == 0
    out = capsys.readouterr().out
    assert "hư cấu" not in out and "company-internal" not in out
    assert main(["ingest", *args]) == 1
    assert "INGEST_BLOCKED" in capsys.readouterr().out
    bad = "test" + "@" + "example.invalid"
    assert main(["query", *args, "--query", bad]) == 1
    assert bad not in capsys.readouterr().out


def test_encoding_and_duplicate_keys(dataset):
    path = dataset / FILES[0][0]
    old = path.read_bytes()
    path.write_bytes(b"\xef\xbb\xbf" + old)
    with pytest.raises(CorpusError, match="JSONL_ENCODING_ERROR"):
        load(dataset, VERSION, 2)
    path.write_bytes(old.replace(b"{", b'{"source_id":"duplicate",', 1))
    with pytest.raises(CorpusError, match="DUPLICATE_JSON_KEY"):
        load(dataset, VERSION, 2)


def test_runtime_schema_matches_frozen_contract():
    runtime = Path(__file__).parents[1] / "app/rag/g3/data-contract-v1.schema.json"
    contract = Path(__file__).parents[2] / "docs/giai-doan-3/schema/data-contract-v1.schema.json"
    assert runtime.read_bytes() == contract.read_bytes()


def test_symlink(dataset, tmp_path):
    path = dataset / FILES[0][0]
    outside = tmp_path.parent / (tmp_path.name + "-outside.jsonl")
    outside.write_bytes(path.read_bytes())
    path.unlink()
    try:
        path.symlink_to(outside)
    except OSError as error:
        if os.name == "nt" and getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows symlink privilege is unavailable")
        raise
    with pytest.raises(CorpusError, match="FILE_OUTSIDE_DATASET"):
        load(dataset, VERSION, 2)


def test_freshness(dataset):
    d = load(dataset, VERSION, 2)
    assert not retrieve(d, "Lệ phí Mẫu Alpha?", as_of="2026-09-09")["evidence"]
