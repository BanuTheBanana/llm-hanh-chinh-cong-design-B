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
        checks = (
            (
                "khai sinh sao mai",
                "src_synthetic_birth_star",
                "https://fixture.invalid/d0/birth_star",
            ),
            (
                "căn cước ánh trăng",
                "src_synthetic_identity_moon",
                "https://fixture.invalid/d0/identity_moon",
            ),
            (
                "khai tử mây trắng",
                "src_synthetic_death_cloud",
                "https://fixture.invalid/d0/death_cloud",
            ),
        )
        expected_groundings = []
        for content, source_id, source_url in checks:
            pair = api.request(
                "POST",
                path,
                {"client_message_id": str(uuid4()), "content": content},
            )
            assistant = pair["assistant_message"]
            grounding = assistant["grounding"]
            assert assistant["content"].startswith("BẢN MÔ PHỎNG D0")
            assert grounding["status"] == "ANSWER"
            assert grounding["corpus_version"] == "synthetic-demo-v1"
            assert grounding["data_classification"] == "D0_SYSTEM_SMOKE"
            assert grounding["prompt_version"] == "g2-grounded-v2"
            assert grounding["provider"] == "template"
            assert grounding["sources"][0]["source_id"] == source_id
            assert grounding["sources"][0]["url"] == source_url
            expected_groundings.append(grounding)
        history = api.request("GET", path)
        assert len(history) == 6
        assert [history[index]["grounding"] for index in (1, 3, 5)] == expected_groundings
        print("PASS - all three G2 D0 procedures have valid answers, citations and history.")
        return 0
    except Exception as error:  # noqa: BLE001 - smoke CLI maps failures to exit code.
        print(f"FAIL - {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
