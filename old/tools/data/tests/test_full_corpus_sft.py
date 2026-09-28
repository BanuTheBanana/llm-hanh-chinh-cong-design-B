import hashlib
import json

from g3_pipeline.common import write_json, write_jsonl
from g5_pipeline import full_corpus_sft


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _release(tmp_path):
    release = tmp_path / "release"
    version = "controlled-fixture-v1"
    sources = []
    procedures = []
    fragments = []
    decisions = []
    for index in range(4):
        source_id = f"source-{index}"
        procedure_id = f"procedure-{index}"
        fragment_id = f"fragment-{index}"
        text = f"Giấy tờ mẫu số {index}."
        sources.append(
            {
                "source_id": source_id,
                "dataset_version": version,
                "jurisdiction": {"country_code": "VN", "province": "Tỉnh mẫu"},
                "effective_from": None,
                "effective_to": None,
                "validity_status": "UNKNOWN",
            }
        )
        fragments.append(
            {
                "fragment_id": fragment_id,
                "source_id": source_id,
                "procedure_id": procedure_id,
                "dataset_version": version,
                "section_type": "REQUIRED_DOCUMENTS",
                "text": text,
            }
        )
        procedures.append(
            {
                "procedure_id": procedure_id,
                "dataset_version": version,
                "title": f"Thủ tục mẫu số {index}",
            }
        )
        for field in full_corpus_sft.FIELDS:
            approved = field == "required_documents"
            decisions.append(
                {
                    "procedure_id": procedure_id,
                    "field": field,
                    "dataset_version": version,
                    "decision_status": "APPROVED" if approved else "INSUFFICIENT_DATA",
                    "fragment_ids": [fragment_id] if approved else [],
                }
            )
    files = {
        "source_manifest.jsonl": (sources, "source_id"),
        "normalized/procedures.jsonl": (procedures, "procedure_id"),
        "normalized/fragments.jsonl": (fragments, "fragment_id"),
        "field-decisions.jsonl": (decisions, "procedure_id"),
    }
    for relative, (rows, key) in files.items():
        write_jsonl(release / relative, rows, key)
    artifacts = [{"path": relative, "sha256": _sha(release / relative)} for relative in files]
    write_json(
        release / "release-manifest.json",
        {
            "artifacts": artifacts,
            "dataset_version": version,
            "status": "READY_FOR_CONTROLLED_RAG",
            "usage_policy": "ALLOWLISTED_FIELDS_ONLY",
        },
    )
    return release


def test_builds_locked_procedure_disjoint_full_sft(tmp_path, monkeypatch):
    release = _release(tmp_path)
    monkeypatch.setattr(full_corpus_sft, "ROOT", tmp_path)
    training = tmp_path / "training/output/full-sft"
    test = tmp_path / "holdout_private"

    result = full_corpus_sft.build_full_sft(
        release,
        training,
        test,
        train_variants=2,
        validation_procedures=1,
        test_procedures=1,
    )

    assert result["status"] == "PASS"
    assert result["procedure_counts"] == {"TRAIN": 2, "VALIDATION": 1, "TEST": 1}
    assert result["row_counts"] == {"TRAIN": 32, "VALIDATION": 8, "TEST": 8}
    assert full_corpus_sft.validate_full_sft(training, test, release)["status"] == "PASS"
    training_manifest = json.loads((training / "manifest.json").read_text())
    assert training_manifest["test_data_used"] is False
    assert training_manifest["split_strategy"] == "PROCEDURE_DISJOINT_FEATURE_BALANCED_2_1_1"
    assert json.loads((test / "manifest.json").read_text())["review_status"] == "LOCKED"


def test_validation_rejects_dataset_version_tamper(tmp_path, monkeypatch):
    release = _release(tmp_path)
    monkeypatch.setattr(full_corpus_sft, "ROOT", tmp_path)
    training = tmp_path / "training/output/full-sft"
    test = tmp_path / "holdout_private"
    full_corpus_sft.build_full_sft(
        release,
        training,
        test,
        validation_procedures=1,
        test_procedures=1,
    )
    train_path = training / "train.jsonl"
    rows = [json.loads(line) for line in train_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["dataset_version"] = "wrong-version"
    write_jsonl(train_path, rows, "example_id")
    manifest_path = training / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["train"]["sha256"] = _sha(train_path)
    write_json(manifest_path, manifest)

    report = full_corpus_sft.validate_full_sft(training, test, release)
    assert report["status"] == "FAIL"
    assert report["errors"]["DATASET_VERSION_MISMATCH"] >= 1


def test_validation_rejects_release_binding_tamper(tmp_path, monkeypatch):
    release = _release(tmp_path)
    monkeypatch.setattr(full_corpus_sft, "ROOT", tmp_path)
    training = tmp_path / "training/output/full-sft"
    test = tmp_path / "holdout_private"
    full_corpus_sft.build_full_sft(
        release,
        training,
        test,
        validation_procedures=1,
        test_procedures=1,
    )
    manifest_path = test / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["release_manifest_sha256"] = "0" * 64
    write_json(manifest_path, manifest)

    report = full_corpus_sft.validate_full_sft(training, test, release)
    assert report["status"] == "FAIL"
    assert report["errors"]["SOURCE_RELEASE_BINDING_INVALID"] == 1
