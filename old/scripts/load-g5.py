"""Run a bounded, private DEV-only concurrency check against live G5."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import time
from collections import Counter
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]


def _private_output(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to((ROOT / "evaluation" / "reports").resolve()):
        raise ValueError("G5_PRIVATE_OUTPUT_REQUIRED")
    if resolved.exists():
        raise ValueError("G5_OUTPUT_ALREADY_EXISTS")
    return resolved


async def run(args) -> int:
    output = _private_output(args.output)
    dev_bytes = args.dev.read_bytes()
    rows = [json.loads(line) for line in dev_bytes.decode("utf-8-sig").splitlines() if line]
    answerable = [
        row
        for row in rows
        if row.get("split") == "DEV"
        and row.get("expected_status") == "ANSWER"
        and not row.get("is_multiturn")
        and row.get("review", {}).get("status") == "APPROVED"
    ]
    if not answerable:
        raise ValueError("G5_NO_APPROVED_DEV_LOAD_CASE")
    selected = [answerable[index % len(answerable)] for index in range(args.requests)]
    timeout = httpx.Timeout(args.timeout)
    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"), timeout=timeout, trust_env=False
    ) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"display_name": "g5-load-" + uuid4().hex[:12]},
        )
        login.raise_for_status()
        conversations = []
        for _ in selected:
            response = await client.post("/api/v1/conversations", json={})
            response.raise_for_status()
            conversations.append(response.json()["id"])

        semaphore = asyncio.Semaphore(args.concurrency)

        async def send(index, row):
            async with semaphore:
                started = time.perf_counter()
                response = await client.post(
                    f"/api/v1/conversations/{conversations[index]}/messages",
                    json={
                        "client_message_id": str(uuid4()),
                        "content": row["question"],
                    },
                )
                elapsed = (time.perf_counter() - started) * 1000
                if response.status_code != 200:
                    return elapsed, f"HTTP_{response.status_code}"
                body = response.json().get("assistant_message", {})
                grounding = body.get("grounding") or {}
                if body.get("status") != "completed":
                    return elapsed, "MESSAGE_NOT_COMPLETED"
                if grounding.get("status") != row["expected_status"]:
                    return elapsed, "STATUS_MISMATCH"
                if not grounding.get("sources"):
                    return elapsed, "CITATION_MISSING"
                return elapsed, None

        started = time.perf_counter()
        results = await asyncio.gather(*(send(index, row) for index, row in enumerate(selected)))
        wall_ms = (time.perf_counter() - started) * 1000

    latencies = sorted(item[0] for item in results)
    failures = Counter(item[1] for item in results if item[1])
    report = {
        "schema_version": "g5-bounded-load-v1",
        "status": "PASS" if not failures else "FAIL",
        "test_data_used": False,
        "dev_sha256": hashlib.sha256(dev_bytes).hexdigest(),
        "request_count": len(results),
        "concurrency": args.concurrency,
        "success_count": len(results) - sum(failures.values()),
        "failures": dict(sorted(failures.items())),
        "wall_ms": round(wall_ms, 2),
        "throughput_requests_per_second": round(len(results) / (wall_ms / 1000), 3),
        "latency_ms": {
            "p50": round(latencies[math.ceil(0.50 * len(latencies)) - 1], 2),
            "p95": round(latencies[math.ceil(0.95 * len(latencies)) - 1], 2),
            "max": round(latencies[-1], 2),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8005")
    parser.add_argument("--dev", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--requests", type=int, choices=range(1, 51), default=12)
    parser.add_argument("--concurrency", type=int, choices=range(1, 9), default=2)
    parser.add_argument("--timeout", type=float, default=180)
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - do not expose private payloads.
        allowed = {
            "G5_PRIVATE_OUTPUT_REQUIRED",
            "G5_OUTPUT_ALREADY_EXISTS",
            "G5_NO_APPROVED_DEV_LOAD_CASE",
        }
        code = str(exc) if str(exc) in allowed else "G5_LOAD_FAILED"
        print(json.dumps({"status": "ERROR", "error": code}))
        raise SystemExit(2) from None
