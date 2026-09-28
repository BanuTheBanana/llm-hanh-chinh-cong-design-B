"""Live G3 smoke through Backend, RAG, local Qwen and PostgreSQL history."""

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

    def request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        expected: int = 200,
    ):
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.base_url + path, data=payload, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=45)
            status, raw = response.status, response.read()
        except HTTPError as error:
            status, raw = error.code, error.read()
        assert status == expected, f"{method} {path}: HTTP {status}: {raw!r}"
        return None if not raw else json.loads(raw)


def _assert_grounded_answer(pair: dict, expected_source_id: str, expected_url: str) -> dict:
    assistant = pair["assistant_message"]
    grounding = assistant["grounding"]
    assert assistant["content"].strip(), "local model returned an empty answer"
    assert grounding["status"] == "ANSWER", grounding
    assert grounding["corpus_version"] == "synthetic-demo-v1", grounding
    assert grounding["data_classification"] == "D0_SYSTEM_SMOKE", grounding
    assert grounding["prompt_version"] == "g2-grounded-v2", grounding
    assert grounding["provider"] == "local", grounding
    assert grounding["model"] == "Qwen3-1.7B", grounding
    sources = grounding["sources"]
    assert sources, "ANSWER must contain at least one hydrated citation"
    assert any(
        source["source_id"] == expected_source_id and source["url"] == expected_url
        for source in sources
    ), sources
    return grounding


def main() -> int:
    try:
        api = API()
        assert api.request("GET", "/health") == {"status": "ok"}
        api.request("POST", "/api/v1/auth/login", {"display_name": f"g3-{uuid4().hex[:8]}"})
        conversation = api.request("POST", "/api/v1/conversations", {}, 201)
        path = f"/api/v1/conversations/{conversation['id']}/messages"
        checks = (
            (
                "Lệ phí của Đăng ký khai sinh Sao Mai là bao nhiêu?",
                "src_synthetic_birth_star",
                "https://fixture.invalid/d0/birth_star",
            ),
            (
                "Cần giấy tờ gì để làm căn cước Ánh Trăng?",
                "src_synthetic_identity_moon",
                "https://fixture.invalid/d0/identity_moon",
            ),
            (
                "Khai tử Mây Trắng được xử lý trong bao lâu?",
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
            expected_groundings.append(_assert_grounded_answer(pair, source_id, source_url))

        history = api.request("GET", path)
        assert len(history) == 6, f"expected 6 persisted messages, got {len(history)}"
        assert [history[index]["grounding"] for index in (1, 3, 5)] == expected_groundings
        print("PASS - three G3 D0 queries used local Qwen with valid citations and history.")
        return 0
    except Exception as error:  # noqa: BLE001 - smoke CLI maps failures to exit code.
        detail = str(error) or repr(error)
        print(f"FAIL - {type(error).__name__}: {detail}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
