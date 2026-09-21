import hashlib
import logging
from contextlib import asynccontextmanager
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import AIClient
from app.config import get_settings
from app.db import engine
from app.errors import APIError
from app.models import Conversation, Message, utcnow
from app.rag.catalog_policy import needs_realtime_offer
from app.rag.corpus import CorpusError
from app.rag.g3.runtime import load_active_dataset
from app.rag.g4.context import prepare_turn
from app.rag.g5.intent_context import (
    IntentContextState,
    load_context,
    merge_legacy_context,
    model_state,
    prepare_model_turn,
    procedure_candidates,
    record_grounded_turn,
    to_legacy_context,
)
from app.rag.g5.topic_gate import decide_topic
from app.rag.grounding import answer_with_rag
from app.rag.schemas import Filters, RetrievalInput
from app.schemas import MessageInput, MessagePair

AI_CONTEXT_MAX_MESSAGES = 100
logger = logging.getLogger("backend.chat")


async def owned_conversation(db: AsyncSession, conversation_id: UUID, user_id: UUID):
    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
    )
    if conversation is None:
        raise APIError(404, "NOT_FOUND", "Không tìm thấy cuộc trò chuyện.")
    return conversation


@asynccontextmanager
async def conversation_lock(conversation_id: UUID):
    # Session-level PostgreSQL lock spans commits and works across backend workers.
    # Try-lock returns immediately; one conversation can have only one generation in flight.
    key = int.from_bytes(
        hashlib.blake2b(conversation_id.bytes, digest_size=8).digest(), "big", signed=True
    )
    async with engine.connect() as connection:
        locked = False
        try:
            locked = await connection.scalar(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
            )
            await connection.commit()
            if not locked:
                raise APIError(409, "MESSAGE_IN_PROGRESS", "Đang xử lý tin nhắn. Thử lại sau.")
            async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                yield db
        finally:
            if locked:
                try:
                    await connection.rollback()
                    await connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
                    await connection.commit()
                except BaseException:
                    # Never return a session-locked connection to the pool.
                    await connection.invalidate()
                    raise


async def send_message(
    conversation_id: UUID, user_id: UUID, body: MessageInput, request_id: UUID, ai: AIClient
) -> MessagePair:
    if get_settings().rag_enabled and len(body.content) > 4_000:
        raise APIError(422, "VALIDATION_ERROR", "Tin nhắn RAG không được vượt quá 4.000 ký tự.")
    filters = body.retrieval_filters.model_dump(mode="json")
    async with conversation_lock(conversation_id) as db:
        conversation = await owned_conversation(db, conversation_id, user_id)
        user_message = await db.scalar(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.client_message_id == body.client_message_id,
                Message.role == "user",
            )
        )
        if user_message:
            if (
                user_message.content != body.content
                or (user_message.retrieval_filters or Filters().model_dump(mode="json")) != filters
            ):
                raise APIError(
                    409, "IDEMPOTENCY_CONFLICT", "client_message_id đã được dùng với nội dung khác."
                )
            assistant = await db.scalar(
                select(Message).where(
                    Message.conversation_id == conversation.id,
                    Message.request_id == user_message.request_id,
                    Message.role == "assistant",
                )
            )
            if assistant:
                return MessagePair(user_message=user_message, assistant_message=assistant)
            # Reject retry of an old failed turn after a newer turn, preserving ordered history.
            latest = await db.scalar(
                select(Message.id)
                .where(Message.conversation_id == conversation.id, Message.role == "user")
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(1)
            )
            if latest != user_message.id:
                raise APIError(
                    409, "RETRY_OUT_OF_ORDER", "Hãy gửi lại nội dung bằng client_message_id mới."
                )
            user_message.status = "pending"
            user_message.request_id = request_id
        else:
            user_message = Message(
                conversation_id=conversation.id,
                client_message_id=body.client_message_id,
                role="user",
                content=body.content,
                retrieval_filters=filters,
                status="pending",
                request_id=request_id,
            )
            db.add(user_message)
        conversation.updated_at = utcnow()
        await db.commit()  # Durable even if AI fails or this worker exits.
        # The internal AI contract accepts at most 100 messages. Select newest first
        # so long conversations keep the most relevant context, then restore chronology.
        newest_history = (
            await db.scalars(
                select(Message)
                .where(
                    Message.conversation_id == conversation.id,
                    ((Message.status == "completed") | (Message.id == user_message.id)),
                )
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(AI_CONTEXT_MAX_MESSAGES)
            )
        ).all()
        history = list(reversed(newest_history))
        await db.commit()  # No idle database transaction during network I/O.
        try:
            grounding = None
            next_context = None
            policy_answer = None
            if get_settings().rag_enabled:
                retrieval_query = RetrievalInput(
                    query=body.content,
                    filters=body.retrieval_filters,
                    top_k=get_settings().rag_top_k,
                )
                if get_settings().g3_d2_enabled:
                    settings = get_settings()
                    try:
                        data = load_active_dataset(
                            str(settings.g3_private_dataset_path),
                            settings.rag_corpus_version,
                            settings.g3_expected_rows,
                            settings.g3_corpus_sha256,
                        )
                        previous_model = load_context(
                            conversation.rag_context,
                            corpus_version=data.version,
                        )
                        use_legacy = not settings.g5_intent_context_enabled
                        if settings.g5_intent_context_enabled:
                            candidates = procedure_candidates(data)
                            try:
                                topic_decision = await decide_topic(
                                    data,
                                    body.content,
                                    previous_model.procedure_id,
                                    ai.hybrid_router if settings.g5_hybrid_enabled else None,
                                )
                                intent_output = await ai.analyze_intent_context(
                                    request_id=request_id,
                                    current_message_id=user_message.id,
                                    current_user_message=body.content,
                                    state_before=model_state(previous_model),
                                    procedure_candidates=candidates,
                                    data_classification="D2_COMPANY_REAL",
                                )
                                retrieval_query, next_context, policy_answer = prepare_model_turn(
                                    data,
                                    retrieval_query,
                                    previous_model,
                                    intent_output,
                                    message_id=str(user_message.id),
                                    topic_decision=topic_decision,
                                    evidence_mode=settings.g8_evidence_mode,
                                )
                                logger.info(
                                    "topic_gate request_id=%s action=%s reason=%s",
                                    request_id,
                                    topic_decision.action,
                                    topic_decision.reason,
                                )
                            except (APIError, ValueError, ValidationError) as exc:
                                if not settings.g5_intent_context_fallback_enabled:
                                    raise
                                logger.warning(
                                    "intent_context_fallback request_id=%s error=%s",
                                    request_id,
                                    type(exc).__name__,
                                )
                                use_legacy = True
                        if use_legacy:
                            previous = to_legacy_context(previous_model)
                            retrieval_query, legacy_context, query_context = prepare_turn(
                                data,
                                retrieval_query,
                                previous,
                                user_message.id,
                            )
                            # Dense routing is a bounded fallback for the legacy path.
                            if (
                                query_context.procedure_id is None
                                and settings.g5_hybrid_enabled
                                and ai.hybrid_router is not None
                            ):
                                candidate = await ai.hybrid_router.route(data, body.content)
                                if candidate is not None:
                                    retrieval_query, legacy_context, _ = prepare_turn(
                                        data,
                                        RetrievalInput(
                                            query=body.content,
                                            filters=body.retrieval_filters,
                                            top_k=settings.rag_top_k,
                                        ),
                                        previous,
                                        user_message.id,
                                        procedure_hint=candidate.procedure_id,
                                    )
                            if settings.g5_intent_context_enabled:
                                next_context = merge_legacy_context(
                                    previous_model,
                                    legacy_context,
                                    message_id=str(user_message.id),
                                    explicit_as_of=body.retrieval_filters.as_of,
                                )
                            else:
                                next_context = legacy_context
                    except (CorpusError, ValueError, ValidationError) as exc:
                        raise APIError(
                            503, "RAG_CORPUS_UNAVAILABLE", "Corpus RAG chưa sẵn sàng."
                        ) from exc
                if policy_answer is not None:
                    answer = policy_answer
                else:
                    answer, grounding = await answer_with_rag(
                        db,
                        retrieval_query,
                        request_id,
                        ai,
                    )
                    if (
                        isinstance(next_context, IntentContextState)
                        and grounding
                        and needs_realtime_offer(
                            next_context.procedure_id,
                            {
                                item.get("field")
                                for item in grounding.get("checklist") or []
                                if isinstance(item, dict) and item.get("field")
                            },
                        )
                    ):
                        answer += (
                            "\n\nBạn có muốn kiểm tra thông tin hiện tại trên Cổng Dịch vụ "
                            "công Quốc gia không? Chức năng đối chiếu thời gian thực sẽ được "
                            "kết nối qua MCP ở bước tiếp theo."
                        )
            else:
                answer = await ai.generate(
                    request_id,
                    [{"role": message.role, "content": message.content} for message in history],
                )
        except APIError:
            user_message.status = "failed"
            conversation.updated_at = utcnow()
            await db.commit()
            raise
        if isinstance(next_context, IntentContextState):
            next_context = record_grounded_turn(
                next_context,
                user_query=body.content,
                message_id=str(user_message.id),
                grounding=grounding,
            )
        if next_context is not None:
            conversation.rag_context = next_context.model_dump(mode="json")
        user_message.status = "completed"
        assistant = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
            grounding=grounding,
            status="completed",
            request_id=request_id,
        )
        db.add(assistant)
        conversation.updated_at = utcnow()
        await db.commit()
        return MessagePair(user_message=user_message, assistant_message=assistant)
