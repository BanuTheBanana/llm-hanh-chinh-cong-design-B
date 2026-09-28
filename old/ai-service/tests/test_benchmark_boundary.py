"""Guard benchmark plumbing without contacting a model or accessing company data."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from app.schemas import GroundingEvidenceFragment


def test_grounding_can_be_imported_first_in_fresh_process():
    result = subprocess.run(
        [sys.executable, "-c", "import app.grounding"], capture_output=True, check=False
    )
    assert result.returncode == 0


async def test_observer_records_first_attempt_and_fallback_without_changing_payload():
    path = Path(__file__).parents[1] / "scripts/benchmark_local.py"
    spec = importlib.util.spec_from_file_location("benchmark_local", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "invalid"}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        provider = module.ObservedProvider(
            base_url="http://localhost:8081/v1",
            model_name="fixture",
            timeout_seconds=3,
            context_tokens=4096,
            max_prompt_characters=8000,
            max_output_tokens=500,
            client=http,
        )
        provider.attempts, provider.allowed_ids, provider.used_fallback = [], {"f1"}, False
        result = await provider.generate_grounded(
            query="Lệ phí?",
            evidence=[
                GroundingEvidenceFragment(
                    fragment_id="f1",
                    source_id="s1",
                    procedure_id="p1",
                    title="Fictional",
                    section_type="FEES",
                    text="Miễn phí nếu nộp trực tuyến.",
                )
            ],
            as_of=None,
            data_classification="D0_SYSTEM_SMOKE",
            max_output_tokens=500,
        )
    assert len(provider.attempts) == 2
    assert provider.used_fallback
    assert result.status == "ANSWER"
    assert "nếu nộp trực tuyến" in result.answer
    assert requests[0]["seed"] == 42 and requests[1]["seed"] == 43
    assert "gold_fragment_ids" not in json.dumps(requests)
    with pytest.raises(ValueError, match="IGNORED"):
        module.private_path(Path("public.json"))
