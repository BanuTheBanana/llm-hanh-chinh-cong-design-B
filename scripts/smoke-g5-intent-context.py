"""Run one fictional D0 request through the real local intent provider."""

# ruff: noqa: E402 -- ai-service is added to sys.path before importing its package.

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai-service"))

from app.providers.local_intent_context import LocalIntentContextProvider
from app.schemas import IntentContextRequest


async def run(args) -> int:
    message_id = str(uuid4())
    message = "Đăng ký khai sinh có mất lệ phí không?"
    request = IntentContextRequest(
        request_id=uuid4(),
        current_message_id=message_id,
        current_user_message=message,
        state_before={
            "procedure_id": None,
            "field_intents": [],
            "jurisdiction": None,
            "as_of": None,
            "pending_clarification": None,
        },
        procedure_candidates=[
            {"id": "p_birth", "name": "Đăng ký khai sinh"},
            {"id": "p_marriage", "name": "Đăng ký kết hôn"},
        ],
        data_classification="D0_SYSTEM_SMOKE",
        max_output_tokens=384,
    )
    provider = LocalIntentContextProvider(
        base_url=args.base_url,
        model_name=args.model,
        timeout_seconds=args.timeout,
        context_tokens=4096,
        max_prompt_characters=12000,
        max_output_tokens=384,
        seed=42,
        allow_d2_company_data=False,
        allowed_hosts=frozenset({"127.0.0.1", "localhost"}),
    )
    try:
        result = await provider.analyze(request)
    finally:
        await provider.aclose()
    output = result.output
    print(json.dumps(output.model_dump(mode="json"), ensure_ascii=False, indent=2))
    if output.patch.procedure_id.value != "p_birth":
        raise SystemExit("SMOKE_WRONG_PROCEDURE")
    if output.patch.field_intents.value != ["fees"]:
        raise SystemExit("SMOKE_WRONG_FIELD")
    print("PASS - local intent/context provider returned verified p_birth + fees")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18087/v1")
    parser.add_argument("--model", default="Qwen3-4B-Intent-r16")
    parser.add_argument("--timeout", type=float, default=30)
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
