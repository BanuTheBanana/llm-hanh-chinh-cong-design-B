from datetime import datetime, timezone
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, ForeignKey, DateTime, BigInteger, Identity, Integer, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import JSONB

class Base(DeclarativeBase): pass

class CorpusSnapshot(Base):
    __tablename__ = 'rag_corpus_snapshots'
    fingerprint: Mapped[str] = mapped_column(String(64), primary_key=True)
    corpus: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))

class ActiveCorpus(Base):
    __tablename__ = 'rag_active_corpus'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(ForeignKey('rag_corpus_snapshots.fingerprint'))

class Conversation(Base):
    __tablename__ = 'rag_conversation_states'
    session_id: Mapped[str] = mapped_column(String(100),primary_key=True)
    state: Mapped[dict] = mapped_column(JSONB)

class AuditEvent(Base):
    __tablename__ = 'rag_audit_events'
    event_id: Mapped[int] = mapped_column(BigInteger,Identity(),primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    session_id: Mapped[str | None] = mapped_column(String(100),nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB)

class Account(Base):
    __tablename__ = 'rag_accounts'
    account_id: Mapped[str] = mapped_column(String(36),primary_key=True)
    username: Mapped[str] = mapped_column(String(32),unique=True,index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class LoginSession(Base):
    __tablename__ = 'rag_login_sessions'
    token_hash: Mapped[str] = mapped_column(String(64),primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey('rag_accounts.account_id'),index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class AccountConversation(Base):
    __tablename__ = 'rag_account_conversation_states'
    account_id: Mapped[str] = mapped_column(ForeignKey('rag_accounts.account_id'))
    session_id: Mapped[str] = mapped_column(String(100))
    state: Mapped[dict] = mapped_column(JSONB)
    __table_args__ = (PrimaryKeyConstraint('account_id','session_id'),)

class AccountAuditEvent(Base):
    __tablename__ = 'rag_account_audit_events'
    event_id: Mapped[int] = mapped_column(BigInteger,Identity(),primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey('rag_accounts.account_id'),index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    session_id: Mapped[str | None] = mapped_column(String(100),nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB)
