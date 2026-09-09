"""Live G2 smoke through Web-facing Backend, RAG, AI v2 and PostgreSQL."""

from __future__ import annotations

import json
import sys
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4


class API:
    def __init__(self, base_url: str = "http://127.0.0.1:8000") -> None:
        self.base_url = base_url
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(self, method: str, path: str, body: dict | None = None, expected: int = 200):
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.base_url + path, data=payload, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=10)
            status, raw = response.status, response.read()
        except HTTPError as error:
            status, raw = error.code, error.read()
        assert status == expected, f"{method} {path}: HTTP {status}: {raw!r}"
        return None if not raw else json.loads(raw)


def main() -> int:
    try:
        api = API()
        assert api.request("GET", "/health") == {"status": "ok"}
        api.request("POST", "/api/v1/auth/login", {"display_name": f"g2-{uuid4().hex[:8]}"})
        conversation = api.request("POST", "/api/v1/conversations", {}, 201)
        path = f"/api/v1/conversations/{conversation['id']}/messages"
        pair = api.request(
            "POST",
            path,
            {
                "client_message_id": str(uuid4()),
                "content": "Thủ tục demo sao xanh có lệ phí bao nhiêu?",
            },
        )
        assistant = pair["assistant_message"]
        grounding = assistant["grounding"]
        assert assistant["content"].startswith("BẢN MÔ PHỎNG D0")
        assert grounding["status"] == "ANSWER"
        assert grounding["corpus_version"] == "fixture-v1"
        assert grounding["data_classification"] == "D0_SYSTEM_SMOKE"
        assert grounding["prompt_version"] == "g2-grounded-v2"
        assert grounding["provider"] == "template"
        assert grounding["sources"][0]["fragment_id"] == "frag_fees"
        assert grounding["sources"][0]["url"] == "https://fixture.invalid/synthetic"
        history = api.request("GET", path)
        assert len(history) == 2 and history[1]["grounding"] == grounding
        print("PASS - G2 D0 full-stack grounded answer, citation and history are valid.")
        return 0
    except Exception as error:  # noqa: BLE001 - smoke CLI maps failures to exit code.
        print(f"FAIL - {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
