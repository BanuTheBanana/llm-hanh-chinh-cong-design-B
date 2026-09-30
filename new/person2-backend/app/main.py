import asyncio,hashlib,hmac,logging
from contextlib import asynccontextmanager
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI,HTTPException,Header,Depends,Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import text
from app.config import Settings,get_settings
from app.db import make_database
from app.models import Base
from app.corpus import read_corpus
from app.repository import import_corpus,load_active,get_state,save_state,log_event
from app.contracts import validate
from app.service import ground_and_answer
from app.legacy.conversation_state import build_conversation_state,resolve_filters
from person1_retrieval import VietnameseSegmenter,SegmenterConfig
from person1_retrieval.retriever import LexicalRetriever

logging.basicConfig(level=logging.INFO)
class Filters(BaseModel):
    model_config=ConfigDict(extra='forbid')
    jurisdiction: str|None=None
    effective_date: str|None=None
    scope: str|None=None
class Query(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    query_text_raw: str=Field(min_length=1,max_length=4000)
    session_id: str|None=Field(default=None,min_length=1,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')
    filters: Filters=Field(default_factory=Filters)
    top_k: int=Field(default=5,ge=1,le=20,strict=True)

def create_app(settings=None):
    settings=settings or get_settings()
    @asynccontextmanager
    async def lifespan(app):
        engine,sessions=make_database(settings)
        app.state.engine=engine;app.state.sessions=sessions;app.state.retriever=None;app.state.lock=asyncio.Lock()
        try:
            async with engine.begin() as db:await db.run_sync(Base.metadata.create_all)
            async with sessions.begin() as db:
                # Transaction advisory lock serializes startup seeding across workers.
                await db.execute(text('SELECT pg_advisory_xact_lock(70123001)'))
                active=await load_active(db)
                if active is None and settings.bootstrap_demo:
                    await import_corpus(db,read_corpus(Path(__file__).resolve().parents[1]/'fixtures/demo'))
            app.state.segmenter=VietnameseSegmenter(SegmenterConfig(settings.segmenter_backend))
            yield
        finally:await engine.dispose()
    app=FastAPI(title='Hành chính — Backend + lexical RAG + mock AI',lifespan=lifespan)
    async def auth(authorization:str|None=Header(default=None)):
        if settings.api_token and not hmac.compare_digest(authorization or '', 'Bearer '+settings.api_token):
            raise HTTPException(401,'Bearer token required')
    @app.get('/health')
    async def health():
        try:
            async with app.state.sessions() as db:
                await db.execute(text('SELECT 1'));active=await load_active(db)
            return {'status':'ok','database':'postgresql','generator':'mock_extractive','allow_draft':settings.allow_draft,
                'active_snapshot':active[0] if active else None,'thresholds':'uncalibrated_demo'}
        except Exception:raise HTTPException(503,'Database unavailable') from None
    async def execute(request,respond):
        sid=request.session_id or str(uuid4())
        async with app.state.sessions.begin() as db:
            # Preserve same-session ordering, including across worker processes.
            key=int.from_bytes(hashlib.sha256(sid.encode()).digest()[:8],signed=True)
            await db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':key})
            state=await get_state(db,sid)
            active=await load_active(db)
            if active is None:raise HTTPException(503,'No active corpus; import one first')
            fp,corpus=active
            if app.state.retriever is None or app.state.retriever.fingerprint!=fp:
                async with app.state.lock:
                    if app.state.retriever is None or app.state.retriever.fingerprint!=fp:
                        app.state.retriever=await run_in_threadpool(lambda:LexicalRetriever(corpus,app.state.segmenter,fp,
                            allow_draft=settings.allow_draft,score_floor=settings.bm25_score_floor,margin_floor=settings.bm25_margin))
            retriever=app.state.retriever
            raw=request.query_text_raw
            provided=request.filters.model_dump(exclude_unset=True)
            filters=resolve_filters(raw,provided,state)
            ri={'query_text_raw':raw,'query_text_segmented':await run_in_threadpool(app.state.segmenter.segment,raw),
                'filters':filters,'conversation_session_id':sid,'top_k':request.top_k}
            try:validate('retrieval_input',ri)
            except ValueError:raise HTTPException(422,'Invalid retrieval filters/input') from None
            bundle=await run_in_threadpool(retriever.retrieve,ri,state)
            validate('evidence_bundle',bundle)
            result=ground_and_answer(bundle,raw) if respond else bundle
            # Clear prior on new topic or ambiguity instead of leaking old identity.
            new=build_conversation_state(sid,filters,bundle,raw,datetime.now(timezone.utc).isoformat())
            validate('conversation_state',new);await save_state(db,new)
            await log_event(db,sid,{'snapshot':fp,'bundle_id':bundle['bundle_id'],'top_score':bundle['top_score'],
                'second_score':bundle['second_score'],'margin':bundle['margin'],'confidence_status':bundle['confidence_status'],
                'procedure_id':bundle['resolved_procedure_id'],'fragment_ids':[e['fragment_id'] for e in bundle['evidence']],
                'generator':'mock_extractive','thresholds':'uncalibrated_demo','segmenter':retriever.segmenter.metadata()['config_fingerprint']})
        return result,sid
    @app.post('/api/v1/retrieve',dependencies=[Depends(auth)])
    async def retrieve(request:Query,response:Response):
        result,sid=await execute(request,False);response.headers['X-Conversation-Session-Id']=sid;return result
    @app.post('/api/v1/answer',dependencies=[Depends(auth)])
    async def answer(request:Query,response:Response):
        result,sid=await execute(request,True);response.headers['X-Conversation-Session-Id']=sid;return result
    return app

app=create_app()
