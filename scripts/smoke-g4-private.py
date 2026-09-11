"""Local DEV smoke: self-contained turns, claim rendering, history and isolation.

Not a multi-turn-context acceptance test. Never prints company questions/answers.
"""

# ruff: noqa: E402

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.answer_plan import AnswerPlan, plan_citations, render_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    if fixture["split"] != "DEV":
        raise ValueError("DEV_ONLY")
    cases = []
    for field in ("required_documents", "fees", "processing_times"):
        cases.append(
            next(
                case
                for case in fixture["cases"]
                if case["plan"]["status"] == "ANSWER"
                and case["plan"]["requested_fields"] == [field]
            )
        )
    cases.append(
        next(case for case in fixture["cases"] if case["plan"]["status"] == "INSUFFICIENT_DATA")
    )
    with httpx.Client(base_url="http://127.0.0.1:8004", timeout=90, trust_env=False) as client:
        assert client.get("/health/rag").status_code == 200
        cors = client.options(
            "/api/v1/auth/login",
            headers={"Origin": "http://localhost:3004", "Access-Control-Request-Method": "POST"},
        )
        assert cors.headers["access-control-allow-origin"] == "http://localhost:3004"
        assert (
            client.post("/api/v1/auth/login", json={"display_name": "G4 smoke"}).status_code == 200
        )
        conv = client.post("/api/v1/conversations", json={})
        assert conv.status_code == 201
        path = f"/api/v1/conversations/{conv.json()['id']}/messages"
        expected = []
        for case in cases:
            body = {"client_message_id": str(uuid4()), "content": case["bundle"]["query"]}
            response = client.post(path, json=body)
            assert response.status_code == 200
            pair = response.json()
            assistant = pair["assistant_message"]
            plan = AnswerPlan.model_validate(case["plan"])
            assert assistant["content"] == render_plan(plan)
            assert assistant["grounding"]["status"] == plan.status
            assert {s["fragment_id"] for s in assistant["grounding"]["sources"]} == set(
                plan_citations(plan)
            )
            assert assistant["grounding"]["verification"]["plan_version"] == "g4-answer-plan-v1"
            assert client.post(path, json=body).json() == pair
            expected.extend([pair["user_message"], assistant])
        assert client.get(path).json() == expected
        assert (
            client.post("/api/v1/auth/login", json={"display_name": "Isolated smoke"}).status_code
            == 200
        )
        assert client.get(path).status_code == 404
    assert httpx.get("http://127.0.0.1:3004", trust_env=False).status_code == 200
    print(
        "PASS: 4 DEV turns, claims, citations, idempotency, history, isolation, CORS, Web."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("FAIL: G4 smoke (private diagnostic details withheld).")
        raise SystemExit(2) from None
