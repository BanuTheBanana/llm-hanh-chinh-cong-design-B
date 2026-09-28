# Person 2 — Backend & Grounding

Only generic FastAPI/PostgreSQL/Alembic infrastructure is reused.

Owns API, ConversationState persistence, explicit filter/follow-up interpretation, orchestration, clarification/abstention, grounding, storage, audit logs, and cross-object validation.

Do not copy old `backend/app/rag/` orchestration or resolver logic into this track by default.
