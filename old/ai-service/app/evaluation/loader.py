import hashlib
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from app.evaluation.models import EvalCase, EvalSuiteManifest
from app.grounding import PROMPT_VERSION


@dataclass(frozen=True, slots=True)
class LoadedSuite:
    manifest: EvalSuiteManifest
    cases: tuple[EvalCase, ...]
    manifest_path: Path
    cases_path: Path


def load_suite(manifest_path: str | Path) -> LoadedSuite:
    resolved_manifest = Path(manifest_path).resolve()
    manifest = EvalSuiteManifest.model_validate_json(resolved_manifest.read_text(encoding="utf-8"))
    if manifest.prompt_version != PROMPT_VERSION:
        raise ValueError("suite prompt_version does not match the running AI Service")

    suite_directory = resolved_manifest.parent.resolve()
    cases_path = (suite_directory / manifest.cases_file).resolve()
    if not cases_path.is_relative_to(suite_directory):
        raise ValueError("cases_file must stay inside the suite directory")

    cases_bytes = cases_path.read_bytes()
    actual_hash = hashlib.sha256(cases_bytes).hexdigest()
    if actual_hash != manifest.cases_sha256:
        raise ValueError("cases file SHA-256 does not match manifest")

    cases: list[EvalCase] = []
    for line_number, line in enumerate(cases_bytes.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            cases.append(EvalCase.model_validate_json(line))
        except ValidationError as exc:
            raise ValueError(f"invalid evaluation case on line {line_number}") from exc

    if not cases:
        raise ValueError("evaluation suite must contain at least one case")

    question_ids = [case.gold_question.question_id for case in cases]
    request_ids = [case.grounding_request.request_id for case in cases]
    bundle_ids = [case.grounding_request.evidence_bundle_id for case in cases]
    if len(question_ids) != len(set(question_ids)):
        raise ValueError("question_id values must be unique within a suite")
    if len(request_ids) != len(set(request_ids)):
        raise ValueError("request_id values must be unique within a suite")
    if len(bundle_ids) != len(set(bundle_ids)):
        raise ValueError("evidence_bundle_id values must be unique within a suite")

    for case in cases:
        if case.gold_question.split not in manifest.allowed_splits:
            raise ValueError("case split is not allowed by the suite manifest")
        if case.grounding_request.corpus_version != manifest.corpus_version:
            raise ValueError("case corpus_version does not match suite manifest")
        if case.grounding_request.data_classification != manifest.usage:
            raise ValueError("case data_classification does not match suite usage")

    return LoadedSuite(
        manifest=manifest,
        cases=tuple(cases),
        manifest_path=resolved_manifest,
        cases_path=cases_path,
    )
