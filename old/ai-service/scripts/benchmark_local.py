"""Local-only DEV replay using the actual provider, including retry and fallback.

The model sees query/evidence/as_of ONLY. Labels/plans never enter its prompt.
Raw candidate outputs and reviewer material stay in ignored private artifacts.
"""

# ruff: noqa: E402 -- Direct CLI adds the project path before app imports.

import argparse
import asyncio
import hashlib
import json
import logging
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-service"))

from app.grounding import parse_and_validate_grounded_output
from app.providers.base import ProviderError
from app.providers.local_grounded import LocalGroundedProvider
from app.schemas import GroundingEvidenceFragment

RUNTIME_IMAGE = (
    "ghcr.io/ggml-org/llama.cpp@sha256:"
    "93e3b8da7ce2d7c501e826e3c87b6fde980fac18a8058d38e24529a5b3b83b94"
)


def gpu_memory():
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    return int(result.stdout.strip().splitlines()[0])


def inspect_runtime(container, model_file, model_name):
    result = subprocess.run(
        ["docker", "inspect", container], capture_output=True, text=True, timeout=15, check=True
    )
    runtime = json.loads(result.stdout)[0]
    args = runtime["Config"]["Cmd"]
    mount = next(item for item in runtime["Mounts"] if item["Destination"] == "/models/model.gguf")
    if (
        runtime["Config"]["Image"] != RUNTIME_IMAGE
        or not runtime["State"]["Running"]
        or mount["RW"]
        or Path(mount["Source"]).resolve() != model_file.resolve()
        or args[args.index("--alias") + 1] != model_name
    ):
        raise ValueError("RUNTIME_MODEL_BINDING_MISMATCH")
    return {"image": RUNTIME_IMAGE, "command": args, "model_mount_read_only": True}


class ObservedProvider(LocalGroundedProvider):
    """Instrumentation only; no changes to the production prompt/decoder."""

    async def _request_completion(self, payload):
        raw, used_input, used_output = await super()._request_completion(payload)
        try:
            output = parse_and_validate_grounded_output(
                raw_text=raw, allowed_fragment_ids=self.allowed_ids
            )
            item = {"valid": True, "output": output.model_dump(mode="json")}
        except ProviderError:
            item = {"valid": False}
        self.attempts.append(item)
        return raw, used_input, used_output

    def _extractive_fallback(self, *args, **kwargs):
        self.used_fallback = True
        return super()._extractive_fallback(*args, **kwargs)


def private_path(path):
    path = path.resolve()
    if not path.is_relative_to((ROOT / "evaluation/reports").resolve()):
        raise ValueError("IGNORED_EVALUATION_PATH_REQUIRED")
    return path


async def run(args):
    fixture = json.loads(private_path(args.fixture).read_text(encoding="utf-8"))
    checksum_input = {key: value for key, value in fixture.items() if key != "fixture_sha256"}
    checksum = hashlib.sha256(
        json.dumps(
            checksum_input, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    if fixture["split"] != "DEV" or checksum != fixture["fixture_sha256"]:
        raise ValueError("FROZEN_DEV_REQUIRED")
    output_path = private_path(args.output)
    if output_path.exists():
        raise ValueError("OUTPUT_ALREADY_EXISTS")
    with args.model_file.open("rb") as stream:
        model_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    provider = ObservedProvider(
        base_url=args.base_url,
        model_name=args.model,
        timeout_seconds=90,
        context_tokens=4096,
        max_prompt_characters=8000,
        max_output_tokens=500,
        seed=args.seed,
        allow_d2_company_data=True,
        allowed_hosts=frozenset({"127.0.0.1", "localhost"}),
    )
    runtime = inspect_runtime(args.runtime_container, args.model_file, args.model)
    # Do not trust an alias alone: pin the container's mounted file and model list.
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
        for _ in range(60):
            try:
                ready = await client.get(args.base_url.rstrip("/").removesuffix("/v1") + "/health")
                if ready.status_code == 200:
                    break
            except httpx.TransportError:
                pass
            await asyncio.sleep(0.5)
        else:
            raise ValueError("MODEL_NOT_READY")
        response = await client.get(args.base_url.rstrip("/") + "/models")
        response.raise_for_status()
        if args.model not in {model["id"] for model in response.json()["data"]}:
            raise ValueError("MODEL_ALIAS_MISMATCH")
    started_at = datetime.now(timezone.utc).isoformat()
    memory_samples = [gpu_memory()]
    results = []
    try:
        # One fictional warm-up excluded from metrics, never from the held-out set.
        provider.attempts, provider.allowed_ids, provider.used_fallback = [], {"warmup"}, False
        await provider.generate_grounded(
            query="Thủ tục giả lập cần giấy tờ gì?",
            evidence=[
                GroundingEvidenceFragment(
                    fragment_id="warmup",
                    source_id="fixture",
                    procedure_id="fictional",
                    section_type="REQUIRED_DOCUMENTS",
                    title="D0 fixture",
                    text="Giấy A (bản chính).",
                )
            ],
            as_of=None,
            data_classification="D0_SYSTEM_SMOKE",
            max_output_tokens=500,
        )
        for case in fixture["cases"]:
            bundle = case["bundle"]
            if not bundle["evidence"]:
                results.append({"case_index": case["case_index"], "skipped": True})
                continue
            evidence = [
                GroundingEvidenceFragment.model_validate(
                    {
                        key: value
                        for key, value in item.items()
                        if key in GroundingEvidenceFragment.model_fields
                    }
                )
                for item in bundle["evidence"]
            ]
            provider.attempts, provider.used_fallback = [], False
            provider.allowed_ids = {item.fragment_id for item in evidence}
            start = time.perf_counter()
            output, error = None, None
            try:
                output = asdict(
                    await provider.generate_grounded(
                        query=bundle["query"],
                        evidence=evidence,
                        as_of=date.fromisoformat(bundle["as_of"]) if bundle["as_of"] else None,
                        data_classification=bundle["data_classification"],
                        max_output_tokens=500,
                    )
                )
            except ProviderError as exc:
                error = exc.code
            results.append(
                {
                    "case_index": case["case_index"],
                    "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                    "attempts": provider.attempts,
                    "provider_fallback": provider.used_fallback,
                    "output": output,
                    "error": error,
                }
            )
            # Outside the timed request; whole-GPU samples, not model-only peak VRAM.
            memory_samples.append(gpu_memory())
            print(
                json.dumps(
                    {"model": args.model, "completed": len(results), "total": len(fixture["cases"])}
                ),
                flush=True,
            )
    finally:
        await provider.aclose()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as stream:
        json.dump(
            {
                "fixture_sha256": checksum,
                "model": args.model,
                "model_sha256": model_hash,
                "seed": args.seed,
                "started_at": started_at,
                "runtime": runtime,
                "gpu_memory_mib_sampled_max": max(memory_samples),
                "gpu_memory_note": "Whole GPU, post-request sampling; not model-only or true peak.",
                "config": {
                    "context": 4096,
                    "max_output_tokens": 500,
                    "temperature": 0.2,
                    "top_p": 0.8,
                    "top_k": 20,
                    "min_p": 0,
                    "presence_penalty": 1.5,
                },
                "results": results,
            },
            stream,
            ensure_ascii=False,
            indent=2,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-file", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8081/v1")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--runtime-container", required=True)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    try:
        asyncio.run(run(args))
    except Exception:
        print('{"status":"FAIL","error":"LOCAL_BENCHMARK_FAILED"}')
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
