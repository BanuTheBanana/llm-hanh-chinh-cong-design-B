import json
from pathlib import Path

import pytest

from app.evaluation import evaluate_suite, load_suite
from app.evaluation.models import EvalChecks, MatchRule
from app.evaluation.runner import _normalize
from app.providers.grounded_base import GroundedGenerationResult, GroundedProvider
from app.providers.template_grounded import TemplateGroundedProvider

REPO_ROOT = Path(__file__).resolve().parents[2]
SUITE_PATH = REPO_ROOT / "evaluation" / "fixtures" / "offline-smoke-v1" / "manifest.json"


class SecretFailureProvider(GroundedProvider):
    name = "secret-failure"
    model_name = "secret-failure-v1"
    allowed_data_classifications = frozenset({"D0_SYSTEM_SMOKE"})

    async def generate_grounded(self, **_: object) -> GroundedGenerationResult:
        raise RuntimeError("sensitive-provider-detail")


def test_offline_fixture_loads_with_hash_and_contract_validation() -> None:
    suite = load_suite(SUITE_PATH)

    assert suite.manifest.usage == "D0_SYSTEM_SMOKE"
    assert len(suite.cases) == 8


@pytest.mark.anyio
async def test_template_evaluation_reports_separate_quality_and_safety_metrics() -> None:
    suite = load_suite(SUITE_PATH)

    report = await evaluate_suite(
        suite=suite,
        provider=TemplateGroundedProvider(),
        candidate="template",
        split="DEV",
    )

    assert report.summary.case_count == 8
    assert report.summary.completed_count == 8
    assert report.summary.error_rate == 0
    assert report.summary.citation_id_validity == 1
    assert report.summary.strict_safety_pass_rate == 1
    assert report.summary.retrieval_recall_at_1 == pytest.approx(1 / 2)
    assert report.summary.retrieval_recall_in_bundle == pytest.approx(3 / 4)
    assert report.summary.retrieval_query_fail_rate == pytest.approx(1 / 4)
    assert report.summary.mean_reciprocal_rank == pytest.approx(5 / 8)
    assert report.summary.lexical_expected_point_coverage == 1
    assert report.summary.abstention_accuracy == 1
    assert report.summary.unsafe_answer_rate == 0
    assert report.summary.over_abstention_rate == 0
    assert report.cases_sha256 == suite.manifest.cases_sha256
    assert report.citation_support_review == "PENDING_HUMAN_REVIEW"


@pytest.mark.anyio
async def test_evaluation_error_report_does_not_include_exception_message() -> None:
    suite = load_suite(SUITE_PATH)

    report = await evaluate_suite(
        suite=suite,
        provider=SecretFailureProvider(),
        candidate="secret-failure",
        split="DEV",
    )
    serialized = json.dumps(report.model_dump(mode="json"))

    assert "sensitive-provider-detail" not in serialized
    assert report.summary.error_rate == pytest.approx(7 / 8)
    assert report.summary.citation_id_validity == pytest.approx(1 / 8)
    failed_cases = [case for case in report.cases if case.error_code is not None]
    assert failed_cases
    assert all(case.latency_ms is not None for case in failed_cases)


def test_lexical_normalization_is_unicode_and_whitespace_stable() -> None:
    assert _normalize("  PHIẾU\tA  ") == _normalize("phiếu a")


def test_eval_checks_reject_duplicate_rule_points() -> None:
    duplicate = MatchRule(point="Điểm A", match_any=["a"])

    with pytest.raises(ValueError, match="unique"):
        EvalChecks(expected_points=[duplicate, duplicate])


def test_loader_rejects_tampered_cases_file(tmp_path: Path) -> None:
    manifest = json.loads(SUITE_PATH.read_text(encoding="utf-8"))
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "cases.jsonl").write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256"):
        load_suite(tmp_path / "manifest.json")
