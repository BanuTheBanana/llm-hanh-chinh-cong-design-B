"""Run one private G5 RAG turn and a reviewed MCP source lifecycle."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4

from mcp import Client

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_FIELDS = {
    "receiving_authority",
    "required_documents",
    "fees",
    "processing_times",
    "submission_methods",
    "steps",
    "legal_bases",
    "applicant_scope",
}


def _private_output(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to((ROOT / "evaluation" / "reports").resolve()):
        raise ValueError("G5_PRIVATE_OUTPUT_REQUIRED")
    if resolved.exists():
        raise ValueError("G5_OUTPUT_ALREADY_EXISTS")
    return resolved


class API:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(self, method: str, path: str, payload=None, expected=200):
        body = None if payload is None else json.dumps(payload).encode()
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=120)
            status, raw = response.status, response.read()
        except HTTPError as exc:
            status, raw = exc.code, exc.read()
        if status != expected:
            error_code = "UNKNOWN"
            try:
                error_code = json.loads(raw).get("error", {}).get("code", "UNKNOWN")
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
            raise ValueError(f"G5_HTTP_{status}_{error_code}")
        return json.loads(raw) if raw else None


def _tool_payload(result) -> dict:
    value = result.structured_content
    if isinstance(value, dict) and set(value) == {"result"}:
        value = value["result"]
    if not isinstance(value, dict):
        raise TypeError("G5_MCP_RESULT_INVALID")
    return value


async def _call(client, name: str, arguments: dict) -> dict:
    return _tool_payload(await client.call_tool(name, arguments))


async def run(args) -> int:
    output = _private_output(args.output)
    dev_bytes = args.dev.read_bytes()
    rows = [json.loads(line) for line in dev_bytes.decode("utf-8-sig").splitlines() if line]
    candidates = [
        row
        for row in rows
        if row.get("split") == "DEV"
        and row.get("expected_status") == "ANSWER"
        and not row.get("is_multiturn")
        and row.get("field_expected") in SUPPORTED_FIELDS
        and row.get("review", {}).get("status") == "APPROVED"
    ]
    if not candidates:
        raise ValueError("G5_NO_APPROVED_DEV_SMOKE_CASE")
    row = candidates[0]
    review_token = os.environ.get("G5_SOURCE_REVIEW_TOKEN", "")
    if len(review_token) < 12:
        raise ValueError("G5_REVIEW_TOKEN_REQUIRED")

    snapshot_id = None
    published = False
    source_version = None
    started = time.perf_counter()
    async with Client(args.source_url, read_timeout_seconds=20) as source:
        current = await _call(
            source,
            "get_procedure_update",
            {"procedure_id": row["procedure_id"], "field": row["field_expected"]},
        )
        if current.get("status") != "NO_PUBLISHED_UPDATE":
            raise ValueError("G5_SMOKE_ACTIVE_UPDATE_PRESENT")
        staged = await _call(
            source,
            "manage_source_update",
            {
                "action": "STAGE",
                "review_token": review_token,
                "procedure_id": row["procedure_id"],
                "field": row["field_expected"],
                "text": "Thông tin kiểm thử nguồn G5 đã được duyệt.",
                "title": "Nguồn kiểm thử G5",
            },
        )
        if staged.get("status") != "OK":
            raise ValueError("G5_MCP_STAGE_FAILED")
        snapshot_id = staged["snapshot"]["snapshot_id"]
        hidden = await _call(
            source,
            "get_procedure_update",
            {"procedure_id": row["procedure_id"], "field": row["field_expected"]},
        )
        if hidden.get("status") != "NO_PUBLISHED_UPDATE":
            raise ValueError("G5_UNREVIEWED_SOURCE_WAS_VISIBLE")
        for action in ("APPROVE", "PUBLISH"):
            transitioned = await _call(
                source,
                "manage_source_update",
                {
                    "action": action,
                    "snapshot_id": snapshot_id,
                    "reviewer": "G5 automated local smoke",
                    "review_token": review_token,
                },
            )
            if transitioned.get("status") != "OK":
                raise ValueError(f"G5_MCP_{action}_FAILED")
        published = True
        source_version = transitioned["snapshot"]["version"]
        try:
            api = API(args.base_url)
            display_name = "g5-smoke-" + uuid4().hex[:12]
            api.request("POST", "/api/v1/auth/login", {"display_name": display_name})
            conversation = api.request("POST", "/api/v1/conversations", {}, 201)
            pair = api.request(
                "POST",
                f"/api/v1/conversations/{conversation['id']}/messages",
                {"client_message_id": str(uuid4()), "content": row["question"]},
            )
            assistant = pair.get("assistant_message", {})
            grounding = assistant.get("grounding") or {}
            source_ids = {item.get("fragment_id") for item in grounding.get("sources", [])}
            checks = {
                "message_completed": assistant.get("status") == "completed",
                "answer_status": grounding.get("status") == "ANSWER",
                "published_source_used": snapshot_id in source_ids,
                "knowledge_version_bound": grounding.get("knowledge_version") == source_version,
                "checklist_present": bool(grounding.get("checklist")),
                "verification_present": bool(grounding.get("verification")),
                "rendered_update_present": (
                    "Thông tin kiểm thử nguồn G5 đã được duyệt." in assistant.get("content", "")
                ),
            }
            if not all(checks.values()):
                raise ValueError("G5_RAG_SOURCE_UPDATE_NOT_APPLIED")
        finally:
            if published:
                rolled_back = await _call(
                    source,
                    "manage_source_update",
                    {
                        "action": "ROLLBACK",
                        "snapshot_id": snapshot_id,
                        "reviewer": "G5 automated local smoke",
                        "review_token": review_token,
                    },
                )
                if rolled_back.get("status") != "OK":
                    raise ValueError("G5_MCP_ROLLBACK_FAILED")
                current = await _call(
                    source,
                    "get_procedure_update",
                    {
                        "procedure_id": row["procedure_id"],
                        "field": row["field_expected"],
                    },
                )
                if current.get("status") != "NO_PUBLISHED_UPDATE":
                    raise ValueError("G5_MCP_BASE_RESTORE_FAILED")

    report = {
        "schema_version": "g5-live-smoke-v1",
        "status": "PASS",
        "test_data_used": False,
        "dev_sha256": hashlib.sha256(dev_bytes).hexdigest(),
        "scenario_count": 1,
        "checks": checks,
        "source_lifecycle": [
            "PENDING_REVIEW",
            "APPROVED",
            "PUBLISHED",
            "ROLLED_BACK_TO_BASE",
        ],
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8005")
    parser.add_argument("--source-url", default="http://127.0.0.1:8096/mcp")
    parser.add_argument("--dev", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - do not expose private exception details.
        allowed = {
            "G5_PRIVATE_OUTPUT_REQUIRED",
            "G5_OUTPUT_ALREADY_EXISTS",
            "G5_NO_APPROVED_DEV_SMOKE_CASE",
            "G5_REVIEW_TOKEN_REQUIRED",
            "G5_SMOKE_ACTIVE_UPDATE_PRESENT",
            "G5_MCP_STAGE_FAILED",
            "G5_UNREVIEWED_SOURCE_WAS_VISIBLE",
            "G5_MCP_APPROVE_FAILED",
            "G5_MCP_PUBLISH_FAILED",
            "G5_RAG_SOURCE_UPDATE_NOT_APPLIED",
            "G5_MCP_ROLLBACK_FAILED",
            "G5_MCP_BASE_RESTORE_FAILED",
        }
        code = (
            str(exc)
            if str(exc) in allowed or str(exc).startswith("G5_HTTP_")
            else "G5_SMOKE_FAILED"
        )
        print(json.dumps({"status": "ERROR", "error": code}))
        raise SystemExit(2) from None
