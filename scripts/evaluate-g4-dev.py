"""Freeze DEV inputs or aggregate private model runs. Never unlock/use TEST for selection.

Run with the backend uv environment. Generated artifacts must stay in the ignored
evaluation/reports directory; stdout contains counts and aggregate metrics only.
"""

# ruff: noqa: E402 -- Direct CLI adds the project path before app imports.

import argparse
import hashlib
import json
import math
import statistics
import sys
from datetime import date
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.answer_plan import AnswerPlan, build_answer_plan, verify_candidate
from app.rag.g3.runtime import _jurisdiction_label, retrieve_active_dataset
from app.rag.g3.validator import load
from app.rag.schemas import Evidence, EvidenceBundle, GroundedAnswer, RetrievalInput


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def private_path(path):
    path = path.resolve()
    if not path.is_relative_to((ROOT / "evaluation/reports").resolve()):
        raise ValueError("IGNORED_EVALUATION_PATH_REQUIRED")
    return path


def write_new(path, value):
    path = private_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def prepare(args):
    data = load(args.dataset, args.version, 10)
    if data.fingerprint != args.corpus_sha256 or data.report()["readiness"] != "READY_FOR_DEMO":
        raise ValueError("APPROVED_CORPUS_REQUIRED")
    rows = sorted(
        (q for q in data.groups[4].values() if q["split"] == "DEV"), key=lambda q: q["question_id"]
    )
    if not rows:
        raise ValueError("EMPTY_DEV")
    cases = []
    for i, question in enumerate(rows):
        bundle, status, missing = retrieve_active_dataset(
            data,
            RetrievalInput(query=question["question"], top_k=5),
            uuid5(NAMESPACE_URL, "g4-dev-v1/" + question["question_id"]),
        )
        if args.mode == "gold_evidence":
            # Diagnostic oracle arm, DEV only. Gold IDs choose source fragments;
            # labels/expected answers remain outside the model payload.
            gold_evidence = []
            for fid in question["gold_fragment_ids"]:
                fragment = data.fragments[fid]
                source = data.sources[fragment["source_id"]]
                procedure = data.procedures[fragment["procedure_id"]]
                gold_evidence.append(
                    Evidence(
                        fragment_id=fid,
                        source_id=fragment["source_id"],
                        procedure_id=fragment["procedure_id"],
                        section_type=fragment["section_type"],
                        title=procedure["title"],
                        text=fragment["text"],
                        score=1,
                        url=source["public_url"],
                        metadata={"source_type": source["source_type"]},
                        jurisdiction=_jurisdiction_label(procedure["jurisdiction"]),
                        effective_from=date.fromisoformat(source["effective_from"])
                        if source["effective_from"]
                        else None,
                        effective_to=date.fromisoformat(source["effective_to"])
                        if source["effective_to"]
                        else None,
                        validity_status=source["validity_status"],
                    )
                )
            bundle = EvidenceBundle.model_validate(
                {
                    **bundle.model_dump(),
                    "evidence": gold_evidence,
                }
            )
            status, missing = ("ANSWER" if gold_evidence else "INSUFFICIENT_DATA"), []
        pids = {item.procedure_id for item in bundle.evidence}
        procedure = data.procedures.get(next(iter(pids)), {}) if len(pids) == 1 else {}
        plan = build_answer_plan(bundle, field_evidence=procedure.get("field_evidence", {}))
        cases.append(
            {
                "case_index": i,
                "bundle": bundle.model_dump(mode="json"),
                "retrieval_status": status,
                "retrieval_missing_fields": missing,
                "plan": plan.model_dump(mode="json"),
                # Evaluation labels remain outside the generation payload.
                "expected_status": question["expected_status"],
                "gold_fragment_ids": question["gold_fragment_ids"],
                "expected_points": question["expected_points"],
                "forbidden_points": question["forbidden_points"],
            }
        )
    value = {
        "schema_version": "g4-dev-benchmark-v1",
        "split": "DEV",
        "corpus_sha256": data.fingerprint,
        "cases": cases,
    }
    if args.mode == "gold_evidence":
        value["mode"] = "gold_evidence"
    value["fixture_sha256"] = digest(value)
    write_new(args.output, value)
    print(
        json.dumps(
            {
                "frozen_dev_cases": len(cases),
                "fixture_sha256": value["fixture_sha256"],
                "model_cases": sum(bool(c["bundle"]["evidence"]) for c in cases),
                "answerable_plans": sum(c["plan"]["status"] == "ANSWER" for c in cases),
            }
        )
    )


def bound_answer(bundle, result):
    return GroundedAnswer(
        request_id=bundle.request_id,
        evidence_bundle_id=bundle.evidence_bundle_id,
        corpus_version=bundle.corpus_version,
        data_classification=bundle.data_classification,
        prompt_version="g2-grounded-v2",
        answer=result["answer"],
        status=result["status"],
        cited_fragment_ids=result["cited_fragment_ids"],
        missing_information=result["missing_information"],
        provider="local",
        model="benchmark",
        usage={"input_tokens": 0, "output_tokens": 0},
        latency_ms=0,
    )


def summarize(args):
    fixture = json.loads(private_path(args.fixture).read_text(encoding="utf-8"))
    if fixture["split"] != "DEV" or fixture["fixture_sha256"] != digest(
        {key: value for key, value in fixture.items() if key != "fixture_sha256"}
    ):
        raise ValueError("FROZEN_DEV_REQUIRED")
    plan_fixture = None
    if args.plan_fixture:
        plan_fixture = json.loads(private_path(args.plan_fixture).read_text(encoding="utf-8"))
        if plan_fixture["fixture_sha256"] != digest(
            {key: value for key, value in plan_fixture.items() if key != "fixture_sha256"}
        ):
            raise ValueError("PLAN_FIXTURE_HASH_MISMATCH")

        # Only plan may change in this verifier ablation. Questions, evidence,
        # order and labels must remain byte-for-byte equivalent after canonicalization.
        def without_plan(case):
            return {key: value for key, value in case.items() if key != "plan"}

        if [without_plan(c) for c in fixture["cases"]] != [
            without_plan(c) for c in plan_fixture["cases"]
        ]:
            raise ValueError("GENERATION_INPUTS_CHANGED")
    summaries = []
    for run_path in args.runs:
        run = json.loads(private_path(run_path).read_text(encoding="utf-8"))
        if run["fixture_sha256"] != fixture["fixture_sha256"]:
            raise ValueError("FIXTURE_MISMATCH")
        cases = {case["case_index"]: case for case in (plan_fixture or fixture)["cases"]}
        if (
            len(run["results"]) != len(cases)
            or {r["case_index"] for r in run["results"]} != cases.keys()
        ):
            raise ValueError("INCOMPLETE_RUN")
        calls = errors = retries = fallbacks = raw_valid = raw_status = guarded_status = 0
        provider_status = guard_checks = guard_pass = first_guard_pass = 0
        latencies, gold_recalls, retrieval_recalls = [], [], []
        for result in run["results"]:
            case = cases[result["case_index"]]
            bundle = EvidenceBundle.model_validate(case["bundle"])
            plan = AnswerPlan.model_validate(case["plan"])
            expected = case["expected_status"]
            gold = set(case["gold_fragment_ids"])
            if gold:
                retrieval_recalls.append(
                    len(gold & {e.fragment_id for e in bundle.evidence}) / len(gold)
                )
            guarded_status += (
                plan.status if bundle.evidence else case["retrieval_status"]
            ) == expected
            if result.get("skipped"):
                provider_status += case["retrieval_status"] == expected
                continue
            calls += 1
            latencies.append(result["latency_ms"])
            errors += result.get("error") is not None
            attempts = result["attempts"]
            retries += len(attempts) > 1
            fallbacks += result["provider_fallback"]
            first = attempts[0] if attempts else {}
            raw_valid += first.get("valid", False)
            if first.get("valid"):
                raw_status += first["output"]["status"] == expected
                if plan.status == "ANSWER":
                    first_guard_pass += not verify_candidate(
                        plan, bound_answer(bundle, first["output"])
                    )
            if gold:
                cited = set(first.get("output", {}).get("cited_fragment_ids", []))
                gold_recalls.append(len(gold & cited) / len(gold))
            if result.get("output"):
                output = result["output"]
                provider_status += output["status"] == expected
                if plan.status == "ANSWER":
                    guard_checks += 1
                    guard_pass += not verify_candidate(plan, bound_answer(bundle, output))
        summaries.append(
            {
                "model": run["model"],
                "model_sha256": run["model_sha256"],
                "seed": run["seed"],
                "cases": len(cases),
                "model_calls": calls,
                "first_contract_valid": raw_valid,
                "first_status_correct_of_calls": raw_status,
                "provider_status_correct_of_all": provider_status,
                "guarded_status_correct_of_all": guarded_status,
                "errors": errors,
                "retried_calls": retries,
                "provider_fallbacks": fallbacks,
                "exact_guard_pass": guard_pass,
                "exact_guard_checked": guard_checks,
                "first_exact_guard_pass": first_guard_pass,
                "first_gold_citation_recall": round(statistics.mean(gold_recalls), 4)
                if gold_recalls
                else None,
                "retrieval_recall_at_5": round(statistics.mean(retrieval_recalls), 4)
                if retrieval_recalls and fixture.get("mode") != "gold_evidence"
                else None,
                "latency_mean_ms": round(statistics.mean(latencies), 1),
                "latency_p50_ms": round(statistics.median(latencies), 1),
                "latency_p95_ms": round(sorted(latencies)[math.ceil(len(latencies) * 0.95) - 1], 1),
                "gpu_memory_mib_sampled_max": run.get("gpu_memory_mib_sampled_max"),
            }
        )
    output = {
        "split": "DEV",
        "mode": fixture.get("mode", "retrieved_evidence"),
        "fixture_sha256": fixture["fixture_sha256"],
        "plan_fixture_sha256": (plan_fixture or fixture)["fixture_sha256"],
        "note": "Pilot model selection, not independent TEST or human semantic accuracy.",
        "models": summaries,
    }
    write_new(args.output, output)
    print(json.dumps(output, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--dataset", type=Path, required=True)
    prep.add_argument("--version", required=True)
    prep.add_argument("--corpus-sha256", required=True)
    prep.add_argument("--output", type=Path, required=True)
    prep.add_argument(
        "--mode", choices=("retrieved_evidence", "gold_evidence"), default="retrieved_evidence"
    )
    summary = sub.add_parser("summarize")
    summary.add_argument("--fixture", type=Path, required=True)
    summary.add_argument("--runs", type=Path, nargs="+", required=True)
    summary.add_argument("--output", type=Path, required=True)
    summary.add_argument("--plan-fixture", type=Path)
    args = parser.parse_args()
    try:
        (prepare if args.action == "prepare" else summarize)(args)
    except Exception:
        # Input errors must not echo company records in a public terminal/log.
        print('{"status":"FAIL","error":"PRIVATE_EVALUATION_FAILED"}')
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
