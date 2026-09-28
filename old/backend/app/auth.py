import hashlib

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.errors import APIError
from app.models import SessionRecord, User, utcnow


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get(get_settings().session_cookie_name)
    if token:
        user = await db.scalar(
            select(User)
            .join(SessionRecord)
            .where(
                SessionRecord.token_hash == token_hash(token),
                SessionRecord.expires_at > utcnow(),
            )
        )
        if user:
            return user
    raise APIError(401, "UNAUTHORIZED", "Vui lòng đăng nhập.")
