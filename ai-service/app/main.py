import logging
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.dependencies import get_grounded_provider, get_provider
from app.grounded_service import run_grounded_generation
from app.grounding import PROMPT_VERSION
from app.providers.base import (
    AIProvider,
    ProviderError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from app.providers.grounded_base import GroundedProvider
from app.schemas import (
    ErrorDetail,
    ErrorResponse,
    GenerateRequest,
    GenerateResponse,
    GroundedGenerateRequest,
    GroundedGenerateResponse,
    GroundedHealthResponse,
    HealthResponse,
    Usage,
)

logger = logging.getLogger("ai_service")


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: UUID,
) -> JSONResponse:
    payload = ErrorResponse(error=ErrorDetail(code=code, message=message, request_id=request_id))
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def _request_id_from_invalid_body(request_error: RequestValidationError) -> UUID:
    body = request_error.body
    if isinstance(body, dict):
        candidate = body.get("request_id")
        if candidate is not None:
            try:
                return UUID(str(candidate))
            except (TypeError, ValueError):
                pass
    return uuid4()


async def _request_id_from_request(request: Request) -> UUID:
    try:
        body = await request.json()
    except (RuntimeError, ValueError):
        return uuid4()

    if isinstance(body, dict):
        candidate = body.get("request_id")
        if candidate is not None:
            try:
                return UUID(str(candidate))
            except (TypeError, ValueError):
                pass
    return uuid4()


def create_app() -> FastAPI:
    logger.setLevel(get_settings().log_level.upper())
    application = FastAPI(
        title="Hành chính công AI Service",
        version="2.0.0",
        description="G1 mock boundary plus the offline grounded G2 foundation.",
    )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return _error_response(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Request payload is invalid.",
            request_id=_request_id_from_invalid_body(exc),
        )

    @application.exception_handler(ProviderError)
    async def provider_exception_handler(
        request: Request,
        exc: ProviderError,
    ) -> JSONResponse:
        request_id = await _request_id_from_request(request)
        if isinstance(exc, ProviderTimeoutError):
            status_code = 504
        elif isinstance(exc, ProviderResponseError):
            status_code = 502
        else:
            status_code = 503
        logger.warning(
            "provider_dependency_error request_id=%s code=%s path=%s",
            request_id,
            exc.code,
            request.url.path,
        )
        return _error_response(
            status_code=status_code,
            code=exc.code,
            message=exc.public_message,
            request_id=request_id,
        )

    @application.get("/health", response_model=HealthResponse, tags=["health"])
    async def health(provider: AIProvider = Depends(get_provider)) -> HealthResponse:
        return HealthResponse(provider=provider.name)

    @application.post(
        "/internal/v1/generate",
        response_model=GenerateResponse,
        responses={
            422: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
            504: {"model": ErrorResponse},
        },
        tags=["generation"],
    )
    async def generate(
        payload: GenerateRequest,
        provider: AIProvider = Depends(get_provider),
    ) -> GenerateResponse | JSONResponse:
        started_at = perf_counter()
        try:
            result = await provider.generate(
                messages=payload.messages,
                max_output_tokens=payload.max_output_tokens,
            )
        except ProviderTimeoutError as exc:
            latency_ms = round((perf_counter() - started_at) * 1000)
            logger.warning(
                "generation_timeout request_id=%s latency_ms=%d",
                payload.request_id,
                latency_ms,
            )
            return _error_response(
                status_code=504,
                code=exc.code,
                message=exc.public_message,
                request_id=payload.request_id,
            )
        except ProviderError as exc:
            latency_ms = round((perf_counter() - started_at) * 1000)
            logger.warning(
                "generation_error request_id=%s code=%s latency_ms=%d",
                payload.request_id,
                exc.code,
                latency_ms,
            )
            return _error_response(
                status_code=503,
                code=exc.code,
                message=exc.public_message,
                request_id=payload.request_id,
            )

        latency_ms = round((perf_counter() - started_at) * 1000)
        logger.info(
            "generation_success request_id=%s provider=%s model=%s latency_ms=%d",
            payload.request_id,
            result.provider,
            result.model,
            latency_ms,
        )
        return GenerateResponse(
            request_id=payload.request_id,
            text=result.text,
            provider=result.provider,
            model=result.model,
            usage=Usage(
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            ),
            latency_ms=latency_ms,
        )

    @application.post(
        "/internal/v2/generate",
        response_model=GroundedGenerateResponse,
        responses={
            422: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
            504: {"model": ErrorResponse},
        },
        tags=["grounded-generation"],
    )
    async def generate_grounded(
        payload: GroundedGenerateRequest,
        provider: GroundedProvider = Depends(get_grounded_provider),
    ) -> GroundedGenerateResponse | JSONResponse:
        started_at = perf_counter()
        try:
            result = await run_grounded_generation(payload=payload, provider=provider)
        except ProviderError as exc:
            latency_ms = round((perf_counter() - started_at) * 1000)
            status_code = 502 if isinstance(exc, ProviderResponseError) else 503
            if isinstance(exc, ProviderTimeoutError):
                status_code = 504
            logger.warning(
                "grounded_generation_error request_id=%s evidence_bundle_id=%s "
                "code=%s latency_ms=%d",
                payload.request_id,
                payload.evidence_bundle_id,
                exc.code,
                latency_ms,
            )
            return _error_response(
                status_code=status_code,
                code=exc.code,
                message=exc.public_message,
                request_id=payload.request_id,
            )

        latency_ms = round((perf_counter() - started_at) * 1000)
        logger.info(
            "grounded_generation_success request_id=%s evidence_bundle_id=%s "
            "corpus_version=%s data_classification=%s evidence_count=%d "
            "provider=%s model=%s latency_ms=%d",
            payload.request_id,
            payload.evidence_bundle_id,
            payload.corpus_version,
            payload.data_classification,
            len(payload.evidence),
            result.provider,
            result.model,
            latency_ms,
        )
        return GroundedGenerateResponse(
            request_id=payload.request_id,
            evidence_bundle_id=payload.evidence_bundle_id,
            corpus_version=payload.corpus_version,
            data_classification=payload.data_classification,
            prompt_version=PROMPT_VERSION,
            answer=result.answer,
            status=result.status,
            cited_fragment_ids=list(result.cited_fragment_ids),
            missing_information=list(result.missing_information),
            provider=result.provider,
            model=result.model,
            usage=Usage(
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            ),
            latency_ms=latency_ms,
        )

    @application.get(
        "/internal/v2/health",
        response_model=GroundedHealthResponse,
        responses={503: {"model": ErrorResponse}},
        tags=["grounded-generation"],
    )
    async def grounded_health(
        provider: GroundedProvider = Depends(get_grounded_provider),
    ) -> GroundedHealthResponse:
        return GroundedHealthResponse(
            provider=provider.name,
            prompt_version=PROMPT_VERSION,
            external_calls_enabled=provider.external_calls_enabled,
        )

    return application


app = create_app()
