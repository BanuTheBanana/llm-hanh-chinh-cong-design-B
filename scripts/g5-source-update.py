"""Operate the local reviewed source workflow through its MCP tools."""

import argparse
import asyncio
import json
import os

from mcp import Client


def payload(result):
    value = result.structured_content
    if isinstance(value, dict) and set(value) == {"result"}:
        value = value["result"]
    if not isinstance(value, dict):
        raise TypeError("MCP_RESULT_INVALID")
    return value


async def run(args):
    async with Client(args.url, read_timeout_seconds=10) as client:
        if args.action == "get":
            result = await client.call_tool(
                "get_procedure_update",
                {"procedure_id": args.procedure_id, "field": args.field},
            )
        else:
            body = {
                "action": args.action.upper(),
                "procedure_id": args.procedure_id,
                "field": args.field,
                "text": args.text,
                "title": args.title,
                "source_url": args.source_url,
                "effective_from": args.effective_from,
                "effective_to": args.effective_to,
                "snapshot_id": args.snapshot_id,
                "reviewer": args.reviewer,
                "review_token": os.environ.get("G5_SOURCE_REVIEW_TOKEN"),
            }
            result = await client.call_tool("manage_source_update", body)
        value = payload(result)
        output = {"status": value.get("status"), "error": value.get("error")}
        if value.get("snapshot"):
            output.update(
                {
                    "snapshot_id": value["snapshot"].get("snapshot_id"),
                    "version": value["snapshot"].get("version"),
                    "snapshot_status": value["snapshot"].get("status"),
                }
            )
        print(json.dumps(output, ensure_ascii=False))
        return 0 if value.get("status") in {"OK", "PUBLISHED", "NO_PUBLISHED_UPDATE"} else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("get", "stage", "approve", "publish", "reject", "rollback")
    )
    parser.add_argument("--url", default="http://127.0.0.1:8096/mcp")
    parser.add_argument("--procedure-id")
    parser.add_argument("--field")
    parser.add_argument("--text")
    parser.add_argument("--title")
    parser.add_argument("--source-url")
    parser.add_argument("--effective-from")
    parser.add_argument("--effective-to")
    parser.add_argument("--snapshot-id")
    parser.add_argument("--reviewer", default="Hoan")
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except Exception:  # noqa: BLE001 - CLI must not print tool payloads on failure.
        print('{"status":"ERROR","error":"G5_MCP_COMMAND_FAILED"}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
