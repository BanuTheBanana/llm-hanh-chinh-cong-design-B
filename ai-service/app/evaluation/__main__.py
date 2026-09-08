import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.evaluation.loader import load_suite
from app.evaluation.models import EvaluationReport
from app.evaluation.runner import evaluate_suite
from app.providers.template_grounded import TemplateGroundedProvider


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate or run a G2 offline eval suite.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate manifest, hash and JSONL cases.")
    validate.add_argument("--suite", required=True, help="Path to suite manifest.json")

    run = subparsers.add_parser("run", help="Run the deterministic template candidate.")
    run.add_argument("--suite", required=True, help="Path to suite manifest.json")
    run.add_argument("--candidate", choices=["template"], default="template")
    run.add_argument("--split", choices=["TRAIN", "DEV", "TEST"], default="DEV")
    run.add_argument("--json-out", help="Optional JSON report path")
    run.add_argument("--md-out", help="Optional Markdown summary path")
    run.add_argument(
        "--strict-safety",
        action="store_true",
        help="Exit non-zero if any schema/provider/citation safety invariant fails.",
    )
    return parser


def _write_text(path_value: str | None, content: str) -> None:
    if path_value is None:
        return
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _markdown_report(report: EvaluationReport) -> str:
    summary = report.summary

    def show(value: float | int | None) -> str:
        return (
            "N/A" if value is None else f"{value:.4f}" if isinstance(value, float) else str(value)
        )

    lines = [
        f"# Offline evaluation – {report.suite_id}",
        "",
        "> Đây là fixture kỹ thuật, không phải đánh giá độ đúng nghiệp vụ hành chính.",
        "",
        f"- Candidate: `{report.candidate}`",
        f"- Split: `{report.split}`",
        f"- Corpus: `{report.corpus_version}`",
        f"- Prompt: `{report.prompt_version}`",
        f"- Cases SHA-256: `{report.cases_sha256}`",
        f"- Citation support: `{report.citation_support_review}`",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Case count | {summary.case_count} |",
        f"| Error rate | {show(summary.error_rate)} |",
        f"| Status accuracy | {show(summary.status_accuracy)} |",
        f"| Retrieval Recall@1 | {show(summary.retrieval_recall_at_1)} |",
        f"| Retrieval recall in returned bundle | {show(summary.retrieval_recall_in_bundle)} |",
        f"| Retrieval query-fail rate | {show(summary.retrieval_query_fail_rate)} |",
        f"| MRR | {show(summary.mean_reciprocal_rank)} |",
        f"| Citation ID validity | {show(summary.citation_id_validity)} |",
        f"| Gold citation recall | {show(summary.gold_citation_recall)} |",
        (f"| Lexical expected-point coverage | {show(summary.lexical_expected_point_coverage)} |"),
        (f"| Lexical forbidden-claim rate | {show(summary.lexical_forbidden_claim_rate)} |"),
        f"| Abstention accuracy | {show(summary.abstention_accuracy)} |",
        f"| Unsafe-answer rate | {show(summary.unsafe_answer_rate)} |",
        f"| Over-abstention rate | {show(summary.over_abstention_rate)} |",
        f"| Strict safety pass rate | {show(summary.strict_safety_pass_rate)} |",
        f"| Latency p50 (ms) | {show(summary.latency_p50_ms)} |",
        f"| Latency p95 (ms) | {show(summary.latency_p95_ms)} |",
        "",
        "## Per case",
        "",
        "| Question | Expected | Actual | Safe | Error |",
        "|---|---|---|---:|---|",
    ]
    for case in report.cases:
        lines.append(
            f"| `{case.question_id}` | `{case.expected_status}` | "
            f"`{case.actual_status or 'ERROR'}` | "
            f"{'yes' if case.strict_safety_pass else 'no'} | "
            f"`{case.error_code or ''}` |"
        )
    return "\n".join(lines) + "\n"


async def _run(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite)
    report = await evaluate_suite(
        suite=suite,
        provider=TemplateGroundedProvider(),
        candidate=args.candidate,
        split=args.split,
    )
    json_report = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    _write_text(args.json_out, json_report)
    _write_text(args.md_out, _markdown_report(report))
    if not args.json_out:
        print(json_report, end="")

    if args.strict_safety and any(not case.strict_safety_pass for case in report.cases):
        return 2
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _parser().parse_args()
    if args.command == "validate":
        suite = load_suite(args.suite)
        print(
            json.dumps(
                {
                    "suite_id": suite.manifest.suite_id,
                    "case_count": len(suite.cases),
                    "status": "valid",
                },
                ensure_ascii=False,
            )
        )
        return 0
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
