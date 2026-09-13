"""Run a deterministic, local-only intent/context pilot against GGUF candidates.

The fixture is fictional D0 data. Generated reports/logs stay under ignored local paths.
This is a candidate-selection pilot, not the final held-out legal-quality evaluation.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import shutil
import statistics
import subprocess
import sys
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ai-service"))

from app.intent_context_policy import (
    POLICY_VERSION,
    apply_intent_context_policy,
    resolve_high_confidence_without_model,
)

from training.intent_context import (
    CONTEXT_SLOTS,
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_VERSION,
    apply_output_to_state,
    build_messages,
    build_target,
)

DEFAULT_FIXTURE = ROOT / "evaluation/fixtures/intent-context-pilot-v1"
DEFAULT_SCHEMA = ROOT / "docs/giai-doan-5/schema/intent-context-v2.schema.json"
ALLOWED_OUTPUT_ROOT = (ROOT / "evaluation/reports").resolve()
FIELD_INTENTS = (
    "receiving_authority",
    "required_documents",
    "fees",
    "processing_times",
    "submission_methods",
    "steps",
    "legal_bases",
    "applicant_scope",
)
RUNTIME_CANDIDATE_PATHS = (
    "ai-service/app/config.py",
    "ai-service/app/intent_context_policy.py",
    "ai-service/app/prompts/intent-context-v2.txt",
    "ai-service/app/providers/intent_context_base.py",
    "ai-service/app/providers/local_intent_context.py",
    "ai-service/app/schemas.py",
    "backend/app/ai.py",
    "backend/app/chat.py",
    "backend/app/rag/g5/intent_context.py",
    "compose.g5.yaml",
)
FINAL_REFERENCE_FIXTURES = (
    ROOT / "evaluation/fixtures/intent-context-train-hard-v2",
    ROOT / "evaluation/fixtures/intent-context-pilot-v1",
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_locked_candidate(candidate_commit: str) -> str:
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    subprocess.run(
        ["git", "rev-parse", "--verify", f"{candidate_commit}^{{commit}}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True
    )
    if dirty:
        raise SystemExit("FINAL_TEST_REQUIRES_CLEAN_WORKTREE")
    unchanged = subprocess.run(
        ["git", "diff", "--quiet", candidate_commit, head, "--", *RUNTIME_CANDIDATE_PATHS],
        cwd=ROOT,
        check=False,
    )
    if unchanged.returncode != 0:
        raise SystemExit("CANDIDATE_RUNTIME_CHANGED_AFTER_LOCK")
    return head


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[math.ceil(len(ordered) * fraction) - 1], 3)


def request_json(url: str, *, body: dict | None = None, timeout: float = 90) -> dict:
    payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=payload,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_ready(base_url: str, process: subprocess.Popen, timeout: float) -> float:
    started = time.perf_counter()
    while time.perf_counter() - started < timeout:
        if process.poll() is not None:
            raise RuntimeError(f"LLAMA_SERVER_EXITED_{process.returncode}")
        try:
            status = request_json(base_url + "/health", timeout=2)
            if status.get("status") == "ok":
                return time.perf_counter() - started
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            pass
        time.sleep(0.25)
    raise TimeoutError("LLAMA_SERVER_START_TIMEOUT")


def gpu_memory_mib() -> int | None:
    command = [
        "nvidia-smi",
        "--query-gpu=memory.used",
        "--format=csv,noheader,nounits",
    ]
    try:
        value = subprocess.check_output(command, text=True, timeout=10).splitlines()[0]
        return int(value.strip())
    except (FileNotFoundError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def normalize_patch(slot: str, patch: dict) -> tuple[str | None, object]:
    op = patch.get("op")
    value = patch.get("value")
    if slot == "field_intents" and isinstance(value, list):
        value = tuple(sorted(value))
    return op, value


def patch_equal(slot: str, predicted: dict, expected: dict) -> bool:
    return normalize_patch(slot, predicted) == normalize_patch(slot, expected)


def empty_runtime_state(state: dict) -> dict:
    return {
        "procedure_id": state.get("procedure_id"),
        "field_intents": sorted(state.get("field_intents") or []),
        "jurisdiction": state.get("jurisdiction"),
        "as_of": state.get("as_of"),
    }


def canonical_jurisdiction(value: object) -> str | None:
    """Normalize administrative classifiers for semantic state comparison only."""

    if not isinstance(value, str) or not value.strip():
        return None
    plain = unicodedata.normalize("NFD", value.casefold())
    plain = "".join(char for char in plain if unicodedata.category(char) != "Mn")
    plain = plain.replace("đ", "d")
    tokens = "".join(char if char.isalnum() else " " for char in plain).split()
    administrative = {"tinh", "thanh", "pho", "quan", "huyen", "thi", "xa", "phuong"}
    return " ".join(token for token in tokens if token not in administrative)


def state_equal(predicted: dict, expected: dict) -> bool:
    return (
        predicted.get("procedure_id") == expected.get("procedure_id")
        and sorted(predicted.get("field_intents") or [])
        == sorted(expected.get("field_intents") or [])
        and canonical_jurisdiction(predicted.get("jurisdiction"))
        == canonical_jurisdiction(expected.get("jurisdiction"))
        and predicted.get("as_of") == expected.get("as_of")
    )


def macro_f1(counts: dict[str, Counter]) -> float:
    scores = []
    for label in FIELD_INTENTS:
        item = counts[label]
        precision = item["tp"] / (item["tp"] + item["fp"]) if item["tp"] + item["fp"] else 1
        recall = item["tp"] / (item["tp"] + item["fn"]) if item["tp"] + item["fn"] else 1
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0)
    return round(statistics.fmean(scores), 6)


def update_field_scores(
    counts: dict[str, Counter], expected_state: dict, predicted_state: dict
) -> bool:
    expected_fields = set(expected_state["field_intents"])
    predicted_fields = set(predicted_state["field_intents"])
    for label in FIELD_INTENTS:
        if label in expected_fields and label in predicted_fields:
            counts[label]["tp"] += 1
        elif label in predicted_fields:
            counts[label]["fp"] += 1
        elif label in expected_fields:
            counts[label]["fn"] += 1
    return predicted_fields == expected_fields


def parse_candidate(value: str) -> tuple[str, Path, Path | None]:
    if "=" not in value:
        raise SystemExit("CANDIDATE_FORMAT_NAME_EQUALS_PATH")
    name, raw_path = value.split("=", 1)
    model_part, separator, lora_part = raw_path.partition("::")
    if not name or not model_part or (separator and not lora_part):
        raise SystemExit("CANDIDATE_FORMAT_NAME_EQUALS_PATH")
    model_path = Path(model_part).resolve()
    lora_path = Path(lora_part).resolve() if separator else None
    if not model_path.is_file():
        raise SystemExit(f"MODEL_NOT_FOUND:{name}")
    if lora_path is not None and not lora_path.is_file():
        raise SystemExit(f"LORA_NOT_FOUND:{name}")
    return name, model_path, lora_path


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value).casefold()
    return re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE).strip()


def validate_no_final_test_leakage(
    cases: list[dict], manifest: dict, additional_fixtures: tuple[Path, ...] = ()
) -> bool:
    audit = manifest.get("leakage_audit") or {}
    threshold = audit.get("near_duplicate_threshold")
    if threshold != 0.9:
        return False

    reference_messages: list[str] = []
    reference_hashes: dict[str, str] = {}
    for fixture in (*FINAL_REFERENCE_FIXTURES, *additional_fixtures):
        reference_manifest = read_json(fixture / "manifest.json")
        source = fixture / reference_manifest["source_file"]
        if sha256(source) != reference_manifest["content_sha256"]:
            return False
        reference_hashes[fixture.name] = sha256(source)
        reference_messages.extend(
            normalize_text(json.loads(line)["current_user_message"])
            for line in source.read_text(encoding="utf-8").splitlines()
        )

    if audit.get("reference_hashes") != reference_hashes:
        return False
    final_messages = [normalize_text(case["current_user_message"]) for case in cases]
    if len(set(final_messages)) != len(final_messages):
        return False
    exact_overlap = sum(message in set(reference_messages) for message in final_messages)
    near_overlap = sum(
        max(SequenceMatcher(None, message, reference).ratio() for reference in reference_messages)
        >= threshold
        for message in final_messages
    )
    return (
        exact_overlap == 0
        and near_overlap == 0
        and audit.get("exact_overlap_count") == 0
        and audit.get("near_duplicate_count") == 0
    )


def validate_final_conversations(cases: list[dict]) -> bool:
    conversations: dict[str, list[int]] = {}
    replay_states: dict[str, dict] = {}
    case_ids: set[str] = set()
    for case in cases:
        case_id = case.get("case_id")
        conversation_id = case.get("conversation_id")
        turn_index = case.get("turn_index")
        if (
            not isinstance(case_id, str)
            or case_id in case_ids
            or not isinstance(conversation_id, str)
            or type(turn_index) is not int
            or (turn_index == 1 and case.get("assistant_message_before") is not None)
            or (
                turn_index > 1
                and not isinstance(case.get("assistant_message_before"), str)
            )
        ):
            return False
        if turn_index != len(conversations.get(conversation_id, [])) + 1:
            return False
        expected_before = replay_states.get(
            conversation_id,
            {
                "procedure_id": None,
                "field_intents": [],
                "jurisdiction": None,
                "as_of": None,
            },
        )
        if empty_runtime_state(case.get("state_before") or {}) != expected_before:
            return False
        case_ids.add(case_id)
        conversations.setdefault(conversation_id, []).append(turn_index)
        replay_states[conversation_id] = apply_output_to_state(
            case["state_before"], case["expected"]
        )
    return len(conversations) == 20 and all(
        sorted(turns) == [1, 2, 3] for turns in conversations.values()
    )


def semantic_errors(case: dict, predicted: dict) -> list[str]:
    errors = []
    allowed_ids = {item["id"] for item in case["procedure_candidates"]}
    procedure = predicted["patch"]["procedure_id"]
    if procedure["op"] == "SET" and procedure["value"] not in allowed_ids:
        errors.append("PROCEDURE_NOT_IN_CATALOG")
    message = case["current_user_message"]
    for slot in ("procedure_id", "field_intents", "jurisdiction", "as_of"):
        for item in predicted["patch"][slot]["evidence"]:
            if item["message_id"] != "current-user":
                errors.append("EVIDENCE_MESSAGE_ID")
            if item["quote"] not in message:
                errors.append("EVIDENCE_QUOTE_NOT_IN_MESSAGE")
    return errors


def evaluate_candidate(
    base_url: str,
    model_name: str,
    cases: list[dict],
    schema: dict,
    *,
    apply_policy: bool,
    apply_fast_route: bool,
) -> dict:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    latencies = []
    failures = Counter()
    group_counts = Counter()
    group_passes = Counter()
    score_counts = Counter()
    raw_rows = []
    input_tokens = []
    output_tokens = []
    slots = CONTEXT_SLOTS
    replay_states: dict[str, dict] = {}
    conversation_passes: dict[str, bool] = {}
    field_counts = {label: Counter() for label in FIELD_INTENTS}
    route_counts = Counter()

    for case in cases:
        evaluation_case = copy.deepcopy(case)
        conversation_id = case.get("conversation_id")
        if conversation_id:
            turn_index = case.get("turn_index")
            if type(turn_index) is not int or turn_index < 1:
                raise ValueError("INVALID_CONVERSATION_TURN")
            if turn_index == 1:
                replay_states[conversation_id] = empty_runtime_state(case["state_before"])
                conversation_passes[conversation_id] = True
            elif conversation_id not in replay_states:
                raise ValueError("CONVERSATION_TURN_ORDER_INVALID")
            evaluation_case["state_before"] = {
                **replay_states[conversation_id],
                "pending_clarification": case["state_before"].get("pending_clarification"),
            }
        group_counts[case["group"]] += 1
        policy_payload = {
            "message_id": "current-user",
            "current_user_message": case["current_user_message"],
            "state_before": evaluation_case["state_before"],
            "procedure_candidates": case["procedure_candidates"],
        }
        request_body = {
            "model": model_name,
            "messages": build_messages(evaluation_case),
            "temperature": 0,
            "top_k": 1,
            "seed": 42,
            "max_tokens": 384,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_object"},
            "json_schema": schema,
        }
        started = time.perf_counter()
        content = ""
        predicted = None
        raw_predicted = None
        policy_actions: list[str] = []
        error_codes = []
        try:
            deterministic = (
                resolve_high_confidence_without_model(policy_payload)
                if apply_fast_route
                else None
            )
            if deterministic is not None:
                predicted, policy_actions = deterministic
                route_counts["fast_path"] += 1
                input_tokens.append(0)
                output_tokens.append(0)
                latencies.append((time.perf_counter() - started) * 1000)
            else:
                route_counts["model_fallback"] += 1
                response = request_json(base_url + "/v1/chat/completions", body=request_body)
                latencies.append((time.perf_counter() - started) * 1000)
                choice = response["choices"][0]
                content = choice["message"].get("content") or ""
                usage = response.get("usage", {})
                input_tokens.append(int(usage.get("prompt_tokens", 0)))
                output_tokens.append(int(usage.get("completion_tokens", 0)))
                raw_predicted = json.loads(content)
                predicted = raw_predicted
            schema_errors = list(validator.iter_errors(predicted))
            if schema_errors:
                error_codes.append("SCHEMA_INVALID")
            else:
                if apply_policy and deterministic is None:
                    predicted, policy_actions = apply_intent_context_policy(
                        predicted,
                        policy_payload,
                    )
                score_counts["schema_valid"] += 1
                error_codes.extend(semantic_errors(case, predicted))
        except (
            HTTPError,
            URLError,
            TimeoutError,
            KeyError,
            IndexError,
            json.JSONDecodeError,
        ) as exc:
            latencies.append((time.perf_counter() - started) * 1000)
            error_codes.append(type(exc).__name__.upper())

        expected = case["expected"]
        expected_state = apply_output_to_state(case["state_before"], expected)
        semantic_ok = predicted is not None and not error_codes
        if semantic_ok:
            score_counts["semantic_valid"] += 1
            act_ok = predicted["dialogue_act"] == expected["dialogue_act"]
            topic_ok = predicted["topic_action"] == expected["topic_action"]
            patch_results = {
                slot: patch_equal(slot, predicted["patch"][slot], expected["patch"][slot])
                for slot in slots
            }
            exact_patch_ok = all(patch_results.values())
            predicted_state = apply_output_to_state(
                evaluation_case["state_before"], predicted
            )
            state_ok = state_equal(predicted_state, expected_state)
            field_state_ok = update_field_scores(
                field_counts, expected_state, predicted_state
            )
            score_counts["field_state_exact"] += int(field_state_ok)
            exact_full_ok = act_ok and topic_ok and exact_patch_ok
            full_ok = act_ok and topic_ok and state_ok
            score_counts["dialogue_act"] += int(act_ok)
            score_counts["topic_action"] += int(topic_ok)
            score_counts["joint_patch"] += int(exact_patch_ok)
            score_counts["joint_state"] += int(state_ok)
            score_counts["full_exact_patch_case"] += int(exact_full_ok)
            score_counts["full_state_case"] += int(full_ok)
            for slot, ok in patch_results.items():
                score_counts[f"slot_{slot}"] += int(ok)
            if full_ok:
                group_passes[case["group"]] += 1
        else:
            full_ok = False
            predicted_state = empty_runtime_state(evaluation_case["state_before"])
            update_field_scores(field_counts, expected_state, predicted_state)
        if conversation_id:
            replay_states[conversation_id] = predicted_state
            conversation_passes[conversation_id] &= full_ok
        failures.update(error_codes)
        raw_rows.append(
            {
                "case_id": case["case_id"],
                "group": case["group"],
                "passed": full_ok,
                "exact_patch_passed": exact_full_ok if semantic_ok else False,
                "errors": sorted(set(error_codes)),
                "predicted": predicted,
                "raw_predicted": raw_predicted if policy_actions else None,
                "policy_actions": policy_actions,
                "state_input": evaluation_case["state_before"] if conversation_id else None,
                "predicted_state": predicted_state,
                "raw_content": content if predicted is None else None,
            }
        )

    count = len(cases)
    metrics = {
        key: round(score_counts[key] / count, 6)
        for key in (
            "schema_valid",
            "semantic_valid",
            "dialogue_act",
            "topic_action",
            "joint_patch",
            "joint_state",
            "full_exact_patch_case",
            "full_state_case",
            "slot_procedure_id",
            "slot_field_intents",
            "slot_jurisdiction",
            "slot_as_of",
            "field_state_exact",
        )
    }
    metrics["field_macro_f1"] = macro_f1(field_counts)
    conversation_count = len(conversation_passes)
    conversation_success = (
        round(sum(conversation_passes.values()) / conversation_count, 6)
        if conversation_count
        else None
    )
    return {
        "candidate": model_name,
        "case_count": count,
        "metrics": metrics,
        "per_group_full_state_case": {
            group: {
                "correct": group_passes[group],
                "count": group_counts[group],
                "accuracy": round(group_passes[group] / group_counts[group], 6),
            }
            for group in sorted(group_counts)
        },
        "errors": dict(sorted(failures.items())),
        "latency_ms": {
            "p50": percentile(latencies, 0.5),
            "p95": percentile(latencies, 0.95),
            "mean": round(statistics.fmean(latencies), 3),
        },
        "tokens": {
            "prompt_mean": round(statistics.fmean(input_tokens), 3) if input_tokens else None,
            "completion_mean": round(statistics.fmean(output_tokens), 3) if output_tokens else None,
        },
        "routes": dict(sorted(route_counts.items())),
        "conversation_count": conversation_count,
        "conversation_success": conversation_success,
        "raw_rows": raw_rows,
    }


def safe_name(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate",
        action="append",
        required=True,
        help="NAME=GGUF_PATH or NAME=GGUF_PATH::LORA_GGUF_PATH",
    )
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "evaluation/reports/g5/intent-context-baseline-v1",
    )
    parser.add_argument("--llama-server", default=shutil.which("llama-server"))
    parser.add_argument("--port", type=int, default=18085)
    parser.add_argument("--startup-timeout", type=float, default=120)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--apply-policy",
        action="store_true",
        help="Apply the same deterministic intent/context policy as the AI service.",
    )
    parser.add_argument(
        "--apply-fast-route",
        action="store_true",
        help="Resolve narrow high-confidence turns before model inference.",
    )
    parser.add_argument("--final-test", action="store_true")
    parser.add_argument(
        "--opened-regression",
        action="store_true",
        help="Re-score an already opened final fixture; never use this as final acceptance.",
    )
    parser.add_argument(
        "--prior-fixture",
        action="append",
        type=Path,
        default=[],
        help="Prior opened holdout to exclude from a new final test; may be repeated.",
    )
    parser.add_argument("--candidate-commit")
    args = parser.parse_args()
    if args.final_test and args.opened_regression:
        raise SystemExit("FINAL_TEST_AND_OPENED_REGRESSION_ARE_EXCLUSIVE")
    if args.apply_fast_route and not args.apply_policy:
        raise SystemExit("FAST_ROUTE_REQUIRES_POLICY")
    output_dir = args.output_dir.resolve()
    if not output_dir.is_relative_to(ALLOWED_OUTPUT_ROOT):
        raise SystemExit("PRIVATE_EVALUATION_OUTPUT_REQUIRED")
    if not args.llama_server:
        raise SystemExit("LLAMA_SERVER_NOT_FOUND")
    manifest = read_json(args.fixture / "manifest.json")
    cases_path = args.fixture / manifest["source_file"]
    cases = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines()]
    if len(cases) != manifest["case_count"]:
        raise SystemExit("FIXTURE_MANIFEST_COUNT_INVALID")
    schema = read_json(args.schema)
    Draft202012Validator.check_schema(schema)
    expected_validator = Draft202012Validator(schema, format_checker=FormatChecker())
    try:
        for case in cases:
            expected_validator.validate(build_target(case))
    except Exception as exc:
        raise SystemExit("FIXTURE_GOLD_CONTRACT_INVALID") from exc
    if args.final_test:
        if not args.candidate_commit:
            raise SystemExit("FINAL_TEST_CANDIDATE_COMMIT_REQUIRED")
        final_manifest_ok = (
            manifest.get("final_test") is True
            and manifest.get("review_status") == "LOCKED"
            and manifest.get("answer_visibility") == "PRIVATE_GOLD_ONLY"
            and manifest.get("candidate_commit") == args.candidate_commit
            and manifest.get("content_sha256") == sha256(cases_path)
            and manifest.get("case_count") == 60
            and manifest.get("conversation_count") == 20
            and validate_final_conversations(cases)
            and manifest.get("prior_holdout_count", 0) == len(args.prior_fixture)
            and validate_no_final_test_leakage(
                cases,
                manifest,
                tuple(path.resolve() for path in args.prior_fixture),
            )
            and all(case.get("split") == "FINAL_TEST" for case in cases)
        )
        if (
            not final_manifest_ok
            or args.limit
            or len(args.candidate) != 1
            or not args.apply_policy
        ):
            raise SystemExit("LOCKED_FINAL_TEST_MANIFEST_REQUIRED")

        _, final_model_path, final_lora_path = parse_candidate(args.candidate[0])
        if final_lora_path is None:
            raise SystemExit("FINAL_TEST_LORA_REQUIRED")
        if (
            manifest.get("model_sha256") != sha256(final_model_path)
            or manifest.get("adapter_sha256") != sha256(final_lora_path)
            or manifest.get("prompt_sha256")
            != hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()
            or manifest.get("policy_version") != POLICY_VERSION
        ):
            raise SystemExit("FINAL_TEST_CANDIDATE_FINGERPRINT_MISMATCH")

        evaluation_commit = verify_locked_candidate(args.candidate_commit)
        output_dir.mkdir(parents=True, exist_ok=True)
        marker_path = output_dir / "FINAL_TEST_ATTEMPT.json"
        if marker_path.exists() or (output_dir / "summary.json").exists():
            raise SystemExit("FINAL_TEST_ALREADY_ATTEMPTED")
        marker_path.write_text(
            json.dumps(
                {
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "candidate_commit": args.candidate_commit,
                    "evaluation_commit": evaluation_commit,
                    "test_sha256": sha256(cases_path),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    elif args.opened_regression:
        opened_manifest_ok = (
            manifest.get("final_test") is True
            and manifest.get("review_status") == "LOCKED"
            and manifest.get("answer_visibility") == "PRIVATE_GOLD_ONLY"
            and manifest.get("content_sha256") == sha256(cases_path)
            and validate_final_conversations(cases)
            and all(case.get("split") == "FINAL_TEST" for case in cases)
        )
        if not opened_manifest_ok or args.limit or not args.apply_policy:
            raise SystemExit("LOCKED_OPENED_REGRESSION_MANIFEST_REQUIRED")
        output_dir.mkdir(parents=True, exist_ok=True)
    elif manifest.get("final_test") is not False:
        raise SystemExit("PILOT_FIXTURE_MANIFEST_INVALID")
    else:
        if args.prior_fixture:
            raise SystemExit("PRIOR_FIXTURE_ONLY_ALLOWED_FOR_FINAL_TEST")
        output_dir.mkdir(parents=True, exist_ok=True)
    if args.limit:
        cases = cases[: args.limit]
    base_url = f"http://127.0.0.1:{args.port}"
    baseline_gpu = gpu_memory_mib()
    summaries = []

    for candidate_arg in args.candidate:
        name, model_path, lora_path = parse_candidate(candidate_arg)
        log_path = output_dir / f"{safe_name(name)}-server.log"
        command = [
            args.llama_server,
            "--model",
            str(model_path),
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
            "--ctx-size",
            "4096",
            "--parallel",
            "1",
            "--n-gpu-layers",
            "99",
            "--flash-attn",
            "on",
            "--jinja",
            "--reasoning",
            "off",
            "--chat-template-kwargs",
            '{"enable_thinking":false}',
            "--temperature",
            "0",
            "--top-k",
            "1",
            "--seed",
            "42",
            "--no-context-shift",
        ]
        if lora_path is not None:
            command.extend(["--lora", str(lora_path)])
        loaded_gpu = None
        with log_path.open("w", encoding="utf-8") as log_handle:
            process = subprocess.Popen(command, stdout=log_handle, stderr=subprocess.STDOUT)
            try:
                load_seconds = wait_ready(base_url, process, args.startup_timeout)
                loaded_gpu = gpu_memory_mib()
                result = evaluate_candidate(
                    base_url,
                    name,
                    cases,
                    schema,
                    apply_policy=args.apply_policy,
                    apply_fast_route=args.apply_fast_route,
                )
            finally:
                process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
        result.update(
            {
                "model_file": model_path.name,
                "model_sha256": sha256(model_path),
                "model_bytes": model_path.stat().st_size,
                "adapter_file": lora_path.name if lora_path else None,
                "adapter_sha256": sha256(lora_path) if lora_path else None,
                "adapter_bytes": lora_path.stat().st_size if lora_path else None,
                "load_seconds": round(load_seconds, 3),
                "gpu_memory_loaded_mib": loaded_gpu,
                "gpu_memory_baseline_mib": baseline_gpu,
                "gpu_memory_delta_mib": (
                    loaded_gpu - baseline_gpu
                    if loaded_gpu is not None and baseline_gpu is not None
                    else None
                ),
            }
        )
        (output_dir / f"{safe_name(name)}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        summaries.append({key: value for key, value in result.items() if key != "raw_rows"})

    summary = {
        "schema_version": "g5-intent-context-benchmark-v2",
        "scope": (
            "Locked private G5 intent/context final test; not legal-answer evaluation"
            if args.final_test
            else (
                "Opened G5 intent/context regression; not final acceptance or legal-answer evaluation"
                if args.opened_regression
                else "D0 fictional pilot; not final TEST and not legal-answer evaluation"
            )
        ),
        "fixture_sha256": sha256(cases_path),
        "schema_sha256": sha256(args.schema),
        "system_prompt_version": SYSTEM_PROMPT_VERSION,
        "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        "policy_applied": args.apply_policy,
        "fast_route_applied": args.apply_fast_route,
        "policy_version": POLICY_VERSION if args.apply_policy else None,
        "llama_server": str(args.llama_server),
        "llama_server_version": subprocess.check_output(
            [args.llama_server, "--version"], text=True, stderr=subprocess.STDOUT
        ).splitlines()[0],
        "candidate_count": len(summaries),
        "candidates": summaries,
    }
    if args.final_test:
        metrics = summaries[0]["metrics"]
        group_gate = all(
            item["accuracy"] >= 0.7
            for item in summaries[0]["per_group_full_state_case"].values()
        )
        gate_passed = (
            metrics["schema_valid"] == 1
            and metrics["semantic_valid"] == 1
            and metrics["dialogue_act"] >= 0.9
            and metrics["topic_action"] >= 0.9
            and metrics["field_macro_f1"] >= 0.95
            and metrics["field_state_exact"] >= 0.9
            and metrics["joint_state"] >= 0.9
            and metrics["full_state_case"] >= 0.9
            and summaries[0]["conversation_success"] >= 0.9
            and group_gate
        )
        summary["final_test_gate"] = {
            "status": "PASS" if gate_passed else "FAIL",
            "thresholds_locked_before_run": True,
            "group_minimum": 0.7,
        }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not args.final_test or gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
