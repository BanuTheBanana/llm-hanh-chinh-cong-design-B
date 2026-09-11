"""Run approved DEV multi-turn scenarios through the real local G4 HTTP stack.

The script never prints company questions, answers, procedure IDs, or source text.
TEST/TEST_V2 inputs are rejected before they are opened.
"""

import argparse
import json
from pathlib import Path
from uuid import uuid4

import httpx


def read_approved_dev(path: Path) -> list[dict]:
    path = path.resolve()
    if path.name != "scenario_dev.jsonl" or path.is_symlink():
        raise ValueError("DEV_FILE_REQUIRED")
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if not rows or any(
        row.get("split") != "DEV" or row.get("review", {}).get("status") != "APPROVED"
        for row in rows
    ):
        raise ValueError("APPROVED_DEV_REQUIRED")
    return [row for row in rows if row.get("is_multiturn")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8004")
    args = parser.parse_args()
    rows = read_approved_dev(args.dev)
    if not rows:
        raise ValueError("MULTITURN_DEV_REQUIRED")

    passed = answerable = abstained = 0
    with httpx.Client(base_url=args.base_url, timeout=120, trust_env=False) as client:
        if client.get("/health/rag").status_code != 200:
            raise RuntimeError("RAG_HEALTH_FAILED")
        login = client.post("/api/v1/auth/login", json={"display_name": "G4 multi-turn smoke"})
        if login.status_code != 200:
            raise RuntimeError("LOGIN_FAILED")
        for row in rows:
            conversation = client.post("/api/v1/conversations", json={})
            if conversation.status_code != 201:
                raise RuntimeError("CONVERSATION_FAILED")
            endpoint = f"/api/v1/conversations/{conversation.json()['id']}/messages"
            response = None
            for turn in row["turns"]:
                if turn["role"] != "user":
                    continue
                response = client.post(
                    endpoint,
                    json={"content": turn["text"], "client_message_id": str(uuid4())},
                )
                if response.status_code != 200:
                    raise RuntimeError("MESSAGE_FAILED")
            if response is None:
                raise RuntimeError("FINAL_USER_TURN_REQUIRED")
            grounding = response.json()["assistant_message"]["grounding"]
            if grounding["status"] != row["expected_status"]:
                raise AssertionError("STATUS_MISMATCH")
            cited = {item["fragment_id"] for item in grounding["sources"]}
            if cited != set(row["gold_fragment_ids"]):
                raise AssertionError("CITATION_MISMATCH")
            verification = grounding.get("verification")
            if row["expected_status"] == "ANSWER" and (
                not verification or verification["plan_version"] != "g4-answer-plan-v1"
            ):
                raise AssertionError("PLAN_VERSION_MISMATCH")
            answerable += row["expected_status"] == "ANSWER"
            abstained += row["expected_status"] == "INSUFFICIENT_DATA"
            passed += 1
    print(
        json.dumps(
            {
                "status": "PASS",
                "split": "DEV",
                "multiturn_scenarios": len(rows),
                "passed": passed,
                "answerable": answerable,
                "safe_abstentions": abstained,
            }
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        safe_codes = {
            "RAG_HEALTH_FAILED",
            "LOGIN_FAILED",
            "CONVERSATION_FAILED",
            "MESSAGE_FAILED",
            "FINAL_USER_TURN_REQUIRED",
            "STATUS_MISMATCH",
            "CITATION_MISMATCH",
            "PLAN_VERSION_MISMATCH",
            "DEV_FILE_REQUIRED",
            "APPROVED_DEV_REQUIRED",
            "MULTITURN_DEV_REQUIRED",
        }
        code = str(exc) if str(exc) in safe_codes else "G4_MULTITURN_SMOKE_FAILED"
        print(json.dumps({"status": "FAIL", "error": code}))
        raise SystemExit(2) from None
