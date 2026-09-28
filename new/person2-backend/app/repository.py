from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.models import CorpusSnapshot, ActiveCorpus, Conversation, AuditEvent
from app.corpus import canonical_corpus, fingerprint

async def import_corpus(db, corpus, activate=True):
    corpus=canonical_corpus(corpus);fp=fingerprint(corpus)
    await db.execute(insert(CorpusSnapshot).values(fingerprint=fp,corpus=corpus).on_conflict_do_nothing())
    if activate:
        await db.execute(insert(ActiveCorpus).values(id=1,fingerprint=fp).on_conflict_do_update(index_elements=['id'],set_={'fingerprint':fp}))
    return fp

async def load_active(db):
    row=await db.scalar(select(CorpusSnapshot).join(ActiveCorpus,ActiveCorpus.fingerprint==CorpusSnapshot.fingerprint).where(ActiveCorpus.id==1))
    if row is None: return None
    return row.fingerprint,row.corpus

async def get_state(db,session_id):
    row=await db.get(Conversation,session_id)
    return row.state if row else None

async def save_state(db,state):
    await db.execute(insert(Conversation).values(session_id=state['session_id'],state=state).on_conflict_do_update(index_elements=['session_id'],set_={'state':state}))

async def log_event(db,session_id,payload):
    db.add(AuditEvent(session_id=session_id,payload=payload))
