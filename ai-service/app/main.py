import logging
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.dependencies import get_provider
from app.providers.base import AIProvider, ProviderError, ProviderTimeoutError
from app.schemas import (
    ErrorDetail,
    ErrorResponse,
    GenerateRequest,
    GenerateResponse,
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
    payload = ErrorResponse(
        error=ErrorDetail(code=code, message=message, request_id=request_id)
    )
    return JSONResponse(
        status_code=status_code, content=payload.model_dump(mode="json")
    )


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
        title="G1 Mock AI Service",
        version="1.0.0",
        description="Internal deterministic AI boundary for the G1 technical slice.",
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
        status_code = 504 if isinstance(exc, ProviderTimeoutError) else 503
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

    return application


app = create_app()
