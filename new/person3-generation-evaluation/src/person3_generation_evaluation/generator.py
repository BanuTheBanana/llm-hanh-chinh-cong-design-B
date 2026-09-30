from __future__ import annotations

import json
from dataclasses import dataclass

from .contracts import ContractValidationError, validate_contract
from .prompting import build_messages, build_repair_messages
from .runtime import ChatRuntime, RuntimeResponse


class GenerationContractError(ValueError):
    pass


@dataclass(frozen=True)
class GenerationMetrics:
    elapsed_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None
    repair_attempts: int


def _parse_json_object(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("~~~") or text.startswith("```"):
        lines = text.splitlines()
        if lines and (lines[0].startswith("~~~") or lines[0].startswith("```")):
            lines = lines[1:]
        if lines and (lines[-1].startswith("~~~") or lines[-1].startswith("```")):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GenerationContractError(f"model output is not valid JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise GenerationContractError("model output must be one JSON object")
    return parsed


def validate_generated_output(bundle: dict, output: dict) -> None:
    try:
        validate_contract("evidence_bundle", bundle)
    except ContractValidationError as exc:
        raise GenerationContractError(f"invalid EvidenceBundle: {exc}") from exc

    if bundle["confidence_status"] != "resolved":
        raise GenerationContractError("generation is only allowed for resolved EvidenceBundle")
    if not bundle["evidence"]:
        raise GenerationContractError("resolved EvidenceBundle contains no evidence")

    if set(output) != {"answer_text", "citations"}:
        raise GenerationContractError("output must contain exactly answer_text and citations")
    answer_text = output["answer_text"]
    citations = output["citations"]
    if not isinstance(answer_text, str) or not answer_text.strip():
        raise GenerationContractError("answer_text must be a non-empty string")
    if not isinstance(citations, list) or not citations:
        raise GenerationContractError("citations must be a non-empty list")

    evidence_by_id = {item["fragment_id"]: item for item in bundle["evidence"]}
    for index, citation in enumerate(citations):
        try:
            validate_contract("citation", citation)
        except ContractValidationError as exc:
            raise GenerationContractError(f"citation[{index}] violates schema: {exc}") from exc
        claim = citation["claim_text"]
        if not claim.strip():
            raise GenerationContractError(f"citation[{index}].claim_text is empty")
        if claim not in answer_text:
            raise GenerationContractError(f"citation[{index}].claim_text is not an exact answer span")
        evidence = evidence_by_id.get(citation["fragment_id"])
        if evidence is None:
            raise GenerationContractError(f"citation[{index}] references evidence outside this bundle")
        if citation["source_id"] != evidence["source_id"]:
            raise GenerationContractError(f"citation[{index}].source_id does not match evidence")
        if citation["source_locator"] != evidence["source_locator"]:
            raise GenerationContractError(f"citation[{index}].source_locator does not match evidence")


class GroundedGenerator:
    """Person 2 compatible generator: EvidenceBundle -> answer_text + citations."""

    def __init__(self, runtime: ChatRuntime, *, max_repair_attempts: int = 1):
        if max_repair_attempts < 0 or max_repair_attempts > 2:
            raise ValueError("max_repair_attempts must be between 0 and 2")
        self.runtime = runtime
        self.max_repair_attempts = max_repair_attempts
        self.last_metrics: GenerationMetrics | None = None

    def generate(self, evidence_bundle: dict) -> dict:
        output, metrics = self.generate_with_metrics(evidence_bundle)
        self.last_metrics = metrics
        return output

    def generate_with_metrics(self, evidence_bundle: dict) -> tuple[dict, GenerationMetrics]:
        if evidence_bundle.get("confidence_status") != "resolved":
            raise GenerationContractError("generation is only allowed for resolved EvidenceBundle")

        messages = build_messages(evidence_bundle)
        response: RuntimeResponse = self.runtime.complete(messages)
        total_ms = response.elapsed_ms
        prompt_tokens = response.prompt_tokens
        completion_tokens = response.completion_tokens
        repairs = 0
        raw = response.text

        while True:
            try:
                output = _parse_json_object(raw)
                validate_generated_output(evidence_bundle, output)
                return output, GenerationMetrics(
                    elapsed_ms=total_ms,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    repair_attempts=repairs,
                )
            except GenerationContractError as exc:
                if repairs >= self.max_repair_attempts:
                    raise
                repairs += 1
                repair = self.runtime.complete(build_repair_messages(evidence_bundle, raw, str(exc)))
                total_ms += repair.elapsed_ms
                prompt_tokens = (
                    None
                    if prompt_tokens is None or repair.prompt_tokens is None
                    else prompt_tokens + repair.prompt_tokens
                )
                completion_tokens = (
                    None
                    if completion_tokens is None or repair.completion_tokens is None
                    else completion_tokens + repair.completion_tokens
                )
                raw = repair.text
