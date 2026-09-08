"""G1 API smoke test using only the Python standard library.

Runs against live Core Backend + PostgreSQL + Mock AI Service.
It uses synthetic D0 data and never sends company data.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4


def fail(message: str) -> None:
    raise AssertionError(message)


class API:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        expected_status: int = 200,
    ) -> object:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.base_url}{path}", data=body, headers=headers, method=method
        )
        try:
            response = self.opener.open(request, timeout=10)
            status = response.status
            raw = response.read()
        except HTTPError as error:
            status = error.code
            raw = error.read()

        if status != expected_status:
            fail(
                f"{method} {path}: expected HTTP {expected_status}, got {status}: "
                f"{raw.decode('utf-8', errors='replace')}"
            )
        if not raw:
            return None
        return json.loads(raw)


def run(base_url: str) -> None:
    api = API(base_url)
    suffix = uuid4().hex[:10]
    user_a = f"smoke-a-{suffix}"
    user_b = f"smoke-b-{suffix}"

    print("[1/8] Core Backend health")
    health = api.request("GET", "/health")
    if health != {"status": "ok"}:
        fail(f"unexpected health response: {health!r}")

    print("[2/8] Login synthetic user A")
    logged_in = api.request("POST", "/api/v1/auth/login", {"display_name": user_a})
    if not isinstance(logged_in, dict) or logged_in.get("display_name") != user_a:
        fail(f"unexpected login response: {logged_in!r}")

    print("[3/8] Create conversation")
    conversation = api.request("POST", "/api/v1/conversations", {}, 201)
    if not isinstance(conversation, dict) or not conversation.get("id"):
        fail(f"unexpected conversation response: {conversation!r}")
    conversation_id = str(conversation["id"])
    messages_path = f"/api/v1/conversations/{conversation_id}/messages"

    print("[4/8] Send message through Backend -> Mock AI")
    message_payload = {
        "client_message_id": str(uuid4()),
        "content": "D0_SYSTEM_SMOKE: kiểm tra đường ống G1.",
    }
    send_started = time.perf_counter()
    pair = api.request("POST", messages_path, message_payload)
    send_latency_ms = (time.perf_counter() - send_started) * 1000
    if not isinstance(pair, dict):
        fail(f"unexpected message response: {pair!r}")
    if pair.get("user_message", {}).get("status") != "completed":
        fail(f"user message was not completed: {pair!r}")
    assistant = pair.get("assistant_message", {})
    if assistant.get("role") != "assistant" or not assistant.get("content"):
        fail(f"assistant message is invalid: {pair!r}")

    print("[5/8] Retry same idempotency key")
    retried = api.request("POST", messages_path, message_payload)
    if retried != pair:
        fail("idempotent retry did not return the original message pair")

    print("[6/8] Reload history and relogin user A")
    history = api.request("GET", messages_path)
    if not isinstance(history, list) or len(history) != 2:
        fail(f"expected two persisted messages, got: {history!r}")
    api.request("POST", "/api/v1/auth/logout", expected_status=204)
    api.request("POST", "/api/v1/auth/login", {"display_name": user_a})
    conversations = api.request("GET", "/api/v1/conversations")
    if not isinstance(conversations, list) or not any(
        item.get("id") == conversation_id for item in conversations
    ):
        fail("conversation was not restored after relogin")

    print("[7/8] Verify user isolation")
    api.request("POST", "/api/v1/auth/login", {"display_name": user_b})
    if api.request("GET", "/api/v1/conversations") != []:
        fail("synthetic user B unexpectedly sees conversations")
    denied = api.request("GET", messages_path, expected_status=404)
    if (
        not isinstance(denied, dict)
        or denied.get("error", {}).get("code") != "NOT_FOUND"
    ):
        fail(f"ownership error contract is invalid: {denied!r}")

    print("[8/8] Logout")
    api.request("POST", "/api/v1/auth/logout", expected_status=204)
    unauthorized = api.request("GET", "/api/v1/auth/me", expected_status=401)
    if (
        not isinstance(unauthorized, dict)
        or unauthorized.get("error", {}).get("code") != "UNAUTHORIZED"
    ):
        fail(f"logout/session error contract is invalid: {unauthorized!r}")

    print(
        "PASS - G1 live API smoke flow completed successfully "
        f"(message round-trip: {send_latency_ms:.2f} ms)."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    try:
        run(args.base_url)
    except Exception as error:  # noqa: BLE001 - CLI must convert failures to exit code.
        print(f"FAIL - {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
