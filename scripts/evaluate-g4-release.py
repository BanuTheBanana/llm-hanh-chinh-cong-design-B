"""Run the locked TEST_V2 once after the release commit is frozen.

Only aggregate metrics and immutable hashes are emitted. The one-time marker and
result must remain under the ignored evaluation/reports directory.
"""

# ruff: noqa: E402 -- The CLI adds backend to sys.path before importing the app.

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.answer_plan import build_answer_plan, plan_citations, render_plan
from app.rag.g3.runtime import retrieve_active_dataset
from app.rag.g3.validator import load_serving
from app.rag.g4.evaluation import benchmark, prepare_scenario_target, read_locked_test_v2
from app.rag.retrieval import normalize


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def private_output(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to((ROOT / "evaluation" / "reports").resolve()):
        raise ValueError("IGNORED_RELEASE_OUTPUT_REQUIRED")
    return resolved


def frozen_commit(expected: str) -> str:
    actual = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    if actual != expected:
        raise ValueError("RELEASE_COMMIT_MISMATCH")
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if dirty:
        raise ValueError("RELEASE_WORKTREE_NOT_CLEAN")
    return actual


def evaluate_rows(data, rows: list[dict], *, expected_split="TEST_V2") -> dict:
    retrieval = benchmark(data, rows, expected_split=expected_split)
    plan_passed = multiturn_passed = critical_errors = 0
    answerable = abstentions = 0
    for row in rows:
        query = prepare_scenario_target(data, row, 5)
        bundle, retrieval_status, _ = retrieve_active_dataset(
            data,
            query,
            uuid5(NAMESPACE_URL, "g4-release-v1/" + row["scenario_id"]),
        )
        pids = {item.procedure_id for item in bundle.evidence}
        procedure = data.procedures.get(next(iter(pids)), {}) if len(pids) == 1 else {}
        plan = build_answer_plan(
            bundle,
            fields=query.field_intents,
            field_evidence=procedure.get("field_evidence", {}),
        )
        rendered = render_plan(plan)
        status_ok = plan.status == row["expected_status"] == retrieval_status
        citations_ok = set(plan_citations(plan)) == set(row["gold_fragment_ids"])
        normalized_rendered = normalize(rendered)
        include_ok = all(
            normalize(point) in normalized_rendered for point in row["must_include"]
        )
        if row["field_expected"] == "submission_methods":
            # The gold contains canonical enums (DIRECT/ONLINE/POSTAL/OTHER), while
            # the safe answer deliberately renders the complete reviewed raw fragment.
            include_ok = set(row["must_include"]) == set(
                data.procedures[row["procedure_id"]]["submission_methods"]
            )
        content_ok = include_ok and not any(
            normalize(point) in normalized_rendered for point in row["must_exclude"]
        )
        passed = status_ok and citations_ok and content_ok
        plan_passed += passed
        multiturn_passed += bool(row["is_multiturn"] and passed)
        if row["field_expected"] in {"fees", "processing_times", "receiving_authority"}:
            critical_errors += not passed
        answerable += row["expected_status"] == "ANSWER"
        abstentions += row["expected_status"] == "INSUFFICIENT_DATA"

    total = len(rows)
    multiturn_total = sum(row["is_multiturn"] for row in rows)
    plan_accuracy = plan_passed / total
    multiturn_accuracy = multiturn_passed / multiturn_total if multiturn_total else 1
    gate_passed = (
        retrieval["field_accuracy"] >= 0.9
        and retrieval["routing_accuracy"] >= 0.9
        and retrieval["status_accuracy"] >= 0.9
        and (retrieval["recall_at_5"] or 0) >= 0.9
        and plan_accuracy >= 0.9
        and multiturn_accuracy >= 0.9
        and critical_errors == 0
    )
    return {
        "gate_passed": gate_passed,
        "scenario_count": total,
        "answerable": answerable,
        "safe_abstentions": abstentions,
        "field_accuracy": retrieval["field_accuracy"],
        "routing_accuracy": retrieval["routing_accuracy"],
        "status_accuracy": retrieval["status_accuracy"],
        "recall_at_5": retrieval["recall_at_5"],
        "mrr_at_5": retrieval["mrr_at_5"],
        "plan_answer_accuracy": plan_accuracy,
        "multiturn_chain_accuracy": multiturn_accuracy,
        "critical_claim_errors": critical_errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--corpus-sha256", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--marker", type=Path, required=True)
    parser.add_argument("--acknowledge-locked-test", action="store_true")
    args = parser.parse_args()

    if not args.acknowledge_locked_test:
        raise ValueError("LOCKED_TEST_ACKNOWLEDGEMENT_REQUIRED")
    commit = frozen_commit(args.commit)
    dataset = args.dataset.resolve()
    manifest_path = dataset / "g4_eval" / "scenario_manifest.json"
    test_path = dataset / "g4_eval" / "scenario_test_v2.jsonl"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("scenario_set") != "G4-01-evaluation-v4"
        or manifest.get("review_status") != "LOCKED"
        or manifest.get("test_v2_lock", {}).get("status") != "LOCKED"
        or manifest.get("dataset_version") != args.version
    ):
        raise ValueError("LOCKED_MANIFEST_REQUIRED")

    marker = private_output(args.marker)
    output = private_output(args.output)
    marker.parent.mkdir(parents=True, exist_ok=True)
    if marker.exists() or output.exists():
        raise ValueError("TEST_V2_ALREADY_ATTEMPTED")
    attempt = {
        "schema_version": "g4-release-attempt-v1",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "commit": commit,
        "scenario_set": manifest["scenario_set"],
        "test_v2_sha256_expected": manifest["sha256"]["test_v2"],
        "corpus_sha256_expected": args.corpus_sha256,
    }
    with marker.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(attempt, stream, indent=2)
        stream.write("\n")

    rows, test_hash = read_locked_test_v2(test_path, acknowledged=True)
    if test_hash != manifest["sha256"]["test_v2"]:
        raise ValueError("LOCKED_TEST_HASH_MISMATCH")
    data = load_serving(dataset, args.version, 10)
    if data.fingerprint != args.corpus_sha256 or data.report()["readiness"] != "READY_FOR_DEMO":
        raise ValueError("APPROVED_SERVING_CORPUS_REQUIRED")

    metrics = evaluate_rows(data, rows)
    gate_passed = metrics.pop("gate_passed")
    result = {
        "schema_version": "g4-release-result-v1",
        "status": "PASS" if gate_passed else "FAIL",
        "split": "TEST_V2",
        "commit": commit,
        "scenario_set": manifest["scenario_set"],
        "test_v2_sha256": test_hash,
        "corpus_sha256": data.fingerprint,
        **metrics,
    }
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result, indent=2))
    return 0 if gate_passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        safe = {
            "LOCKED_TEST_ACKNOWLEDGEMENT_REQUIRED",
            "RELEASE_COMMIT_MISMATCH",
            "RELEASE_WORKTREE_NOT_CLEAN",
            "LOCKED_MANIFEST_REQUIRED",
            "TEST_V2_ALREADY_ATTEMPTED",
            "LOCKED_TEST_HASH_MISMATCH",
            "APPROVED_SERVING_CORPUS_REQUIRED",
            "IGNORED_RELEASE_OUTPUT_REQUIRED",
        }
        code = str(exc) if str(exc) in safe else "G4_RELEASE_EVALUATION_FAILED"
        print(json.dumps({"status": "ERROR", "error": code}))
        raise SystemExit(2) from None
