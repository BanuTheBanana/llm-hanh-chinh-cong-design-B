from datetime import datetime, timezone
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, ForeignKey, DateTime, BigInteger, Identity, Integer
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
