"""Local-only Qwen provider for the G5 intent/context contract."""

import json
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from app.providers.base import (
    ProviderError,
    ProviderPolicyError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from app.providers.intent_context_base import (
    IntentContextGenerationResult,
    IntentContextProvider,
)
from app.schemas import IntentContextModelOutput, IntentContextRequest

SYSTEM_PROMPT = """Bạn là bộ phân tích intent và context cho trợ lý hành chính Việt Nam.
Chỉ trả JSON theo schema. Không trả lời thủ tục.

dialogue_act:
- ASK_INFORMATION: hỏi thông tin thủ tục, kể cả câu nối tiếp hoặc câu còn mơ hồ.
- PROVIDE_CLARIFICATION: cung cấp dữ kiện mà pending_clarification đang hỏi.
- CORRECT_CONTEXT: sửa, phủ định hoặc chuyển dữ kiện/chủ đề trước.
- RESET_CONTEXT: yêu cầu xóa cuộc hỏi hiện tại.
- GREET: chào hoặc cảm ơn.
- OUT_OF_SCOPE: không thuộc hành chính công.

topic_action: SWITCH khi chọn/chuyển sang procedure cụ thể, KEEP khi giữ chủ đề,
RESET khi bắt đầu lại, UNRESOLVED khi chưa xác định được procedure và state chưa có.

Với procedure_id, field_intents, jurisdiction, as_of:
- KEEP: giữ state; value=null, evidence=[].
- SET: đặt giá trị từ đúng câu hiện tại; evidence chứa current_message_id và quote là
  đoạn nguyên văn, liên tục, có trong current_user_message.
- CLEAR: xóa giá trị cũ do lời hiện tại; value=null và evidence như SET.
Khi chuyển procedure, dữ kiện phụ thuộc cũ sẽ được Backend xóa an toàn.
Không đặt procedure ngoài procedure_candidates. field_intents chỉ gồm:
receiving_authority, required_documents, fees, processing_times, submission_methods,
steps, legal_bases, applicant_scope. Ngày SET phải là YYYY-MM-DD."""

INTENT_OUTPUT_JSON_SCHEMA = IntentContextModelOutput.model_json_schema()


class LocalIntentContextProvider(IntentContextProvider):
    name = "local-intent-context"
    external_calls_enabled = False

    def __init__(
        self,
        *,
        base_url: str,
        model_name: str,
        timeout_seconds: float,
        context_tokens: int,
        max_prompt_characters: int,
        max_output_tokens: int,
        seed: int,
        allow_d2_company_data: bool,
        allowed_hosts: frozenset[str],
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model_name = model_name
        self._base_url = self._validate_base_url(base_url, allowed_hosts)
        if context_tokens < 512 or not 64 <= max_output_tokens < context_tokens:
            raise ValueError("intent model token limits are invalid")
        if max_prompt_characters < 1_000:
            raise ValueError("intent prompt character cap is too small")
        if not model_name.strip():
            raise ValueError("intent model name must not be blank")
        self._max_prompt_characters = max_prompt_characters
        self._max_output_tokens = max_output_tokens
        self._seed = seed
        self.allowed_data_classifications = frozenset(
            {"D0_SYSTEM_SMOKE", "D2_COMPANY_REAL"} if allow_d2_company_data else {"D0_SYSTEM_SMOKE"}
        )
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            follow_redirects=False,
            trust_env=False,
        )

    @staticmethod
    def _validate_base_url(base_url: str, allowed_hosts: frozenset[str]) -> str:
        parsed = urlsplit(base_url)
        allowed = {host.strip().lower() for host in allowed_hosts if host.strip()}
        hostname = parsed.hostname.lower() if parsed.hostname else None
        if (
            parsed.scheme != "http"
            or hostname not in allowed
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("intent model URL must be an allowlisted HTTP origin/path")
        return base_url.rstrip("/")

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, request_payload: dict) -> tuple[str, int, int]:
        try:
            response = await self._client.post(
                f"{self._base_url}/chat/completions", json=request_payload
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError() from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderResponseError("intent model returned HTTP error") from exc
        except httpx.RequestError as exc:
            raise ProviderError("intent model request failed") from exc
        try:
            envelope = response.json()
            message = envelope["choices"][0]["message"]
            content = message["content"]
            if message.get("reasoning_content") not in (None, ""):
                raise ValueError("reasoning content is forbidden")
            if not isinstance(content, str) or not content.strip() or "<think>" in content:
                raise ValueError("missing or thinking content")
            usage = envelope.get("usage") or {}
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            if type(input_tokens) is not int or input_tokens < 0:
                raise ValueError("invalid input token usage")
            if type(output_tokens) is not int or output_tokens < 0:
                raise ValueError("invalid output token usage")
            return content, input_tokens, output_tokens
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderResponseError("intent model returned an invalid envelope") from exc

    @staticmethod
    def _validate_semantics(
        output: IntentContextModelOutput, payload: IntentContextRequest
    ) -> None:
        candidate_ids = {candidate.id for candidate in payload.procedure_candidates}
        procedure = output.patch.procedure_id
        if procedure.op == "SET" and procedure.value not in candidate_ids:
            raise ProviderResponseError("intent model selected an unknown procedure")
        for slot in ("procedure_id", "field_intents", "jurisdiction", "as_of"):
            operation = getattr(output.patch, slot)
            for evidence in operation.evidence:
                if evidence.message_id != payload.current_message_id:
                    raise ProviderResponseError("intent evidence used another message")
                if evidence.quote not in payload.current_user_message:
                    raise ProviderResponseError("intent evidence quote was not in the user message")
        is_reset_act = output.dialogue_act == "RESET_CONTEXT"
        is_reset_topic = output.topic_action == "RESET"
        if is_reset_act != is_reset_topic:
            raise ProviderResponseError("intent reset act and topic disagree")
        if output.topic_action == "SWITCH" and procedure.op != "SET":
            raise ProviderResponseError("intent switch requires a procedure SET")
        if procedure.op == "SET" and output.topic_action != "SWITCH":
            raise ProviderResponseError("procedure SET requires a topic switch")
        if output.topic_action in {"RESET", "UNRESOLVED"} and procedure.op == "SET":
            raise ProviderResponseError("intent topic contradicts the procedure patch")
        if output.dialogue_act in {"GREET", "OUT_OF_SCOPE"}:
            if output.topic_action not in {"KEEP", "UNRESOLVED"} or any(
                getattr(output.patch, slot).op != "KEEP"
                for slot in ("procedure_id", "field_intents", "jurisdiction", "as_of")
            ):
                raise ProviderResponseError("policy intent must not mutate context")
        pending = payload.state_before.pending_clarification
        if output.dialogue_act == "PROVIDE_CLARIFICATION" and pending is not None:
            if getattr(output.patch, pending).op != "SET":
                raise ProviderResponseError("clarification did not set the pending slot")

    async def analyze(self, payload: IntentContextRequest) -> IntentContextGenerationResult:
        if payload.data_classification not in self.allowed_data_classifications:
            raise ProviderPolicyError()
        user_payload = {
            "message_id": payload.current_message_id,
            "current_user_message": payload.current_user_message,
            "state_before": payload.state_before.model_dump(mode="json"),
            "procedure_candidates": [
                candidate.model_dump(mode="json") for candidate in payload.procedure_candidates
            ],
        }
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False, separators=(",", ":")),
            },
        ]
        if sum(len(message["content"]) for message in messages) > self._max_prompt_characters:
            raise ProviderResponseError("intent prompt exceeds the configured budget")
        request_payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "max_tokens": min(payload.max_output_tokens, self._max_output_tokens),
            "temperature": 0,
            "top_k": 1,
            "seed": self._seed,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_object"},
            "json_schema": INTENT_OUTPUT_JSON_SCHEMA,
        }
        total_input = total_output = 0
        for attempt in range(2):
            raw, input_tokens, output_tokens = await self._request(request_payload)
            total_input += input_tokens
            total_output += output_tokens
            try:
                output = IntentContextModelOutput.model_validate_json(raw)
                self._validate_semantics(output, payload)
                return IntentContextGenerationResult(
                    output=output,
                    provider=self.name,
                    model=self.model_name,
                    input_tokens=total_input,
                    output_tokens=total_output,
                )
            except (ValidationError, ProviderResponseError):
                if attempt == 1:
                    raise ProviderResponseError(
                        "intent model violated its contract twice"
                    ) from None
                request_payload = {
                    **request_payload,
                    "messages": [
                        *messages,
                        {
                            "role": "user",
                            "content": (
                                "Tạo lại đúng JSON schema. Chỉ dùng procedure candidate và "
                                "evidence nguyên văn từ current_user_message."
                            ),
                        },
                    ],
                    "seed": self._seed + 1,
                }
        raise AssertionError("unreachable")
