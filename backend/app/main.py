import logging
import secrets
import time
from contextlib import asynccontextmanager
from datetime import timedelta
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException

from app.ai import AIClient, get_ai
from app.auth import current_user, token_hash
from app.chat import owned_conversation, send_message
from app.config import get_settings
from app.db import engine, get_db
from app.errors import APIError
from app.models import Conversation, Message, SessionRecord, User, utcnow
from app.schemas import (
    ConversationInput,
    ConversationOutput,
    ErrorOutput,
    LoginInput,
    MessageInput,
    MessageOutput,
    MessagePair,
    UserOutput,
)

logger = logging.getLogger("g1.requests")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient() as client:
        app.state.ai = AIClient(client)
        yield
    await engine.dispose()


app = FastAPI(title="G1 Core Backend", version="0.1.0", lifespan=lifespan)


def error_response(request: Request, status: int, code: str, message: str):
    request_id = str(getattr(request.state, "request_id", uuid4()))
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )


@app.middleware("http")
async def trace_request(request: Request, call_next):
    request.state.request_id = uuid4()
    started = time.perf_counter()
    try:
        # SameSite cookies plus explicit Origin validation for browser mutations.
        origin = request.headers.get("origin")
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and (
            (origin is not None and origin != settings.web_origin)
            or request.headers.get("sec-fetch-site") == "cross-site"
        ):
            response = error_response(request, 403, "FORBIDDEN_ORIGIN", "Origin không hợp lệ.")
        else:
            response = await call_next(request)
    except Exception as exc:
        # Exception messages can contain SQL, URLs or credentials. Log only safe metadata.
        route = request.scope.get("route")
        logger.error(
            "unhandled_request_error request_id=%s route=%s method=%s error_type=%s",
            request.state.request_id,
            getattr(route, "path", "unmatched"),
            request.method,
            type(exc).__name__,
        )
        response = error_response(request, 500, "INTERNAL_ERROR", "Lỗi hệ thống.")
    response.headers["X-Request-ID"] = str(request.state.request_id)
    response.headers["Cache-Control"] = "no-store"
    route = request.scope.get("route")
    logger.info(
        "request_id=%s route=%s method=%s status=%s latency_ms=%.2f",
        request.state.request_id,
        getattr(route, "path", "unmatched"),
        request.method,
        response.status_code,
        (time.perf_counter() - started) * 1000,
    )
    return response


# Outer CORS wrapper also decorates normalized error responses.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    expose_headers=["X-Request-ID"],
)


@app.exception_handler(APIError)
async def handle_api_error(request: Request, exc: APIError):
    return error_response(request, exc.status, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def handle_validation(request: Request, exc: RequestValidationError):
    return error_response(request, 422, "VALIDATION_ERROR", "Dữ liệu gửi lên không hợp lệ.")


@app.exception_handler(HTTPException)
async def handle_http(request: Request, exc: HTTPException):
    return error_response(request, exc.status_code, "HTTP_ERROR", "Yêu cầu không hợp lệ.")


router = APIRouter(
    prefix="/api/v1",
    responses={
        status: {"model": ErrorOutput} for status in (401, 403, 404, 409, 422, 500, 502, 503, 504)
    },
)


def set_cookie(response: Response, token: str):
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/auth/login", response_model=UserOutput)
async def login(
    body: LoginInput, request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
    await db.execute(
        insert(User)
        .values(display_name=body.display_name)
        .on_conflict_do_nothing(index_elements=[User.display_name])
    )
    user = await db.scalar(select(User).where(User.display_name == body.display_name))
    old_token = request.cookies.get(settings.session_cookie_name)
    if old_token:
        await db.execute(
            delete(SessionRecord).where(SessionRecord.token_hash == token_hash(old_token))
        )
    token = secrets.token_urlsafe(32)
    db.add(
        SessionRecord(
            user_id=user.id,
            token_hash=token_hash(token),
            expires_at=utcnow() + timedelta(seconds=settings.session_ttl_seconds),
        )
    )
    await db.commit()
    set_cookie(response, token)
    return user


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        await db.execute(delete(SessionRecord).where(SessionRecord.token_hash == token_hash(token)))
        await db.commit()
    response = Response(status_code=204)
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )
    return response


@router.get("/auth/me", response_model=UserOutput)
async def me(user: User = Depends(current_user)):
    return user


@router.get("/conversations", response_model=list[ConversationOutput])
async def conversations(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return (
        await db.scalars(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        )
    ).all()


@router.post("/conversations", response_model=ConversationOutput, status_code=201)
async def create_conversation(
    body: ConversationInput, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    conversation = Conversation(user_id=user.id, title=body.title)
    db.add(conversation)
    await db.commit()
    return conversation


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageOutput],
    response_model_exclude_none=True,
)
async def messages(
    conversation_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await owned_conversation(db, conversation_id, user.id)
    return (
        await db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at, Message.id)
        )
    ).all()


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessagePair,
    response_model_exclude_none=True,
)
async def post_message(
    conversation_id: UUID,
    body: MessageInput,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
    ai: AIClient = Depends(get_ai),
):
    # Ownership is checked before locking, so other users cannot observe in-flight state.
    await owned_conversation(db, conversation_id, user.id)
    await db.commit()
    return await send_message(conversation_id, user.id, body, request.state.request_id, ai)


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        raise APIError(503, "DATABASE_UNAVAILABLE", "Database chưa sẵn sàng.") from exc
    return {"status": "ok"}


app.include_router(router)
