import hashlib
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import AIClient
from app.db import engine
from app.errors import APIError
from app.models import Conversation, Message, utcnow
from app.schemas import MessageInput, MessagePair


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
            if user_message.content != body.content:
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
                status="pending",
                request_id=request_id,
            )
            db.add(user_message)
        conversation.updated_at = utcnow()
        await db.commit()  # Durable even if AI fails or this worker exits.
        history = (
            await db.scalars(
                select(Message)
                .where(
                    Message.conversation_id == conversation.id,
                    ((Message.status == "completed") | (Message.id == user_message.id)),
                )
                .order_by(Message.created_at, Message.id)
            )
        ).all()
        await db.commit()  # No idle database transaction during network I/O.
        try:
            answer = await ai.generate(
                request_id,
                [{"role": message.role, "content": message.content} for message in history],
            )
        except APIError:
            user_message.status = "failed"
            conversation.updated_at = utcnow()
            await db.commit()
            raise
        user_message.status = "completed"
        assistant = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
            status="completed",
            request_id=request_id,
        )
        db.add(assistant)
        conversation.updated_at = utcnow()
        await db.commit()
        return MessagePair(user_message=user_message, assistant_message=assistant)
