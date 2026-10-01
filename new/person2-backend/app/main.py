import asyncio,hashlib,logging
from contextlib import asynccontextmanager
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI,HTTPException,Depends,Request,Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel,Field,ConfigDict,field_validator
from sqlalchemy import text,select
from sqlalchemy.exc import IntegrityError
from app.config import Settings,get_settings
from app.db import make_database
from app.models import Base,Account,LoginSession
from app.auth import hash_password,verify_password,new_session_token,digest_session_token
from app.corpus import read_corpus
from app.repository import import_corpus,load_active,get_state,save_state,log_event
from app.contracts import validate
from app.interpretation_trace import build_interpretation_trace
from app.legacy.conversation_state import explain_state_transition
from app.service import ground_and_answer,ground_and_answer_with_diagnostics,inspect_sufficiency
from app.legacy.conversation_state import build_conversation_state
from person1_retrieval import VietnameseSegmenter,SegmenterConfig
from person1_retrieval.retriever import LexicalRetriever
from person1_retrieval.dense import HybridRetriever,LocalSentenceEncoder

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

class Credentials(BaseModel):
    model_config=ConfigDict(extra='forbid')
    username: str=Field(min_length=3,max_length=32,pattern=r'^[A-Za-z0-9_.-]+$')
    password: str=Field(min_length=12,max_length=128)

    @field_validator('username')
    @classmethod
    def normalize_username(cls,value):return value.casefold()

def build_retriever(corpus,segmenter,fingerprint,settings,encoder=None):
    if settings.retrieval_mode=='lexical':
        return LexicalRetriever(corpus,segmenter,fingerprint,allow_draft=settings.allow_draft,
            score_floor=settings.bm25_score_floor,margin_floor=settings.bm25_margin)
    if settings.retrieval_mode not in {'dense','hybrid'}:
        raise ValueError('retrieval_mode must be lexical, dense, or hybrid')
    if encoder is None:
        raise ValueError('A local dense encoder is required for dense/hybrid retrieval')
    return HybridRetriever(corpus,segmenter,fingerprint,encoder=encoder,mode=settings.retrieval_mode,
        allow_draft=settings.allow_draft,score_floor=settings.dense_score_floor,
        margin_floor=settings.dense_margin_floor,dense_min_similarity=settings.dense_min_similarity,
        rrf_k=settings.dense_rrf_k)

async def require_account(request:Request):
    token=request.cookies.get(request.app.state.settings.auth_cookie_name)
    if not token:raise HTTPException(401,'Sign in required')
    async with request.app.state.sessions() as db:
        login=await db.get(LoginSession,digest_session_token(token))
        if login is None or login.expires_at<=datetime.now(timezone.utc):raise HTTPException(401,'Sign in required')
        account=await db.get(Account,login.account_id)
        if account is None:raise HTTPException(401,'Sign in required')
        return {'account_id':account.account_id,'username':account.username}

def set_auth_cookie(response,token,settings):
    response.set_cookie(settings.auth_cookie_name,token,max_age=settings.auth_session_hours*3600,
        httponly=True,secure=settings.auth_cookie_secure,samesite='strict',path='/')

def create_login_session(db,account_id,settings):
    token=new_session_token()
    db.add(LoginSession(token_hash=digest_session_token(token),account_id=account_id,
        expires_at=datetime.now(timezone.utc)+timedelta(hours=settings.auth_session_hours)))
    return token

def create_app(settings:Settings|None=None):
    settings=settings or get_settings()
    if settings.retrieval_mode not in {'lexical','dense','hybrid'}:
        raise ValueError('retrieval_mode must be lexical, dense, or hybrid')
    @asynccontextmanager
    async def lifespan(app):
        engine,sessions=make_database(settings)
        app.state.engine=engine;app.state.sessions=sessions;app.state.retriever=None;app.state.lock=asyncio.Lock()
        app.state.encoder=None
        try:
            async with engine.begin() as db:await db.run_sync(Base.metadata.create_all)
            async with sessions.begin() as db:
                # Transaction advisory lock serializes startup seeding across workers.
                await db.execute(text('SELECT pg_advisory_xact_lock(70123001)'))
                active=await load_active(db)
                if active is None and settings.bootstrap_demo:
                    await import_corpus(db,read_corpus(Path(__file__).resolve().parents[1]/'fixtures/demo'))
            app.state.segmenter=VietnameseSegmenter(SegmenterConfig(settings.segmenter_backend))
            if settings.retrieval_mode!='lexical':
                if not settings.dense_model_path:raise RuntimeError('DENSE_MODEL_PATH is required for dense/hybrid retrieval')
                app.state.encoder=await run_in_threadpool(lambda:LocalSentenceEncoder(
                    settings.dense_model_path,query_prefix=settings.dense_query_prefix,
                    document_prefix=settings.dense_document_prefix,device=settings.dense_device,
                    batch_size=settings.dense_batch_size))
            yield
        finally:await engine.dispose()
    app=FastAPI(title='Hành chính — Backend + lexical RAG + account isolation',lifespan=lifespan)
    app.state.settings=settings
    @app.post('/api/v1/auth/register')
    async def register(credentials:Credentials,response:Response):
        if not settings.allow_registration:raise HTTPException(404,'Account registration is disabled')
        account_id=str(uuid4())
        try:
            async with app.state.sessions.begin() as db:
                existing=await db.scalar(select(Account).where(Account.username==credentials.username))
                if existing:raise HTTPException(409,'Username is already registered')
                account=Account(account_id=account_id,username=credentials.username,password_hash=hash_password(credentials.password))
                db.add(account)
                token=create_login_session(db,account_id,settings)
        except IntegrityError:raise HTTPException(409,'Username is already registered') from None
        set_auth_cookie(response,token,settings)
        return {'account_id':account_id,'username':credentials.username}
    @app.post('/api/v1/auth/login')
    async def login(credentials:Credentials,response:Response):
        async with app.state.sessions.begin() as db:
            account=await db.scalar(select(Account).where(Account.username==credentials.username))
            if account is None or not verify_password(credentials.password,account.password_hash):
                raise HTTPException(401,'Username or password is incorrect')
            token=create_login_session(db,account.account_id,settings)
            result={'account_id':account.account_id,'username':account.username}
        set_auth_cookie(response,token,settings)
        return result
    @app.post('/api/v1/auth/logout',status_code=204)
    async def logout(request:Request,response:Response):
        token=request.cookies.get(settings.auth_cookie_name)
        if token:
            async with app.state.sessions.begin() as db:
                login=await db.get(LoginSession,digest_session_token(token))
                if login:await db.delete(login)
        response.delete_cookie(settings.auth_cookie_name,path='/',secure=settings.auth_cookie_secure,
            httponly=True,samesite='strict')
    @app.get('/api/v1/auth/me')
    async def current_account(account=Depends(require_account)):return account
    @app.get('/health')
    async def health():
        try:
            async with app.state.sessions() as db:
                await db.execute(text('SELECT 1'));active=await load_active(db)
            return {'status':'ok','database':'postgresql','generator':'mock_extractive','allow_draft':settings.allow_draft,
                'active_snapshot':active[0] if active else None,'thresholds':'uncalibrated_demo',
                'retrieval_mode':settings.retrieval_mode,
                'embedding':app.state.encoder.metadata() if app.state.encoder else None}
        except Exception:raise HTTPException(503,'Database unavailable') from None
    async def execute(request,respond,account,include_diagnostics=False,include_stage_trace=False):
        sid=request.session_id or str(uuid4())
        account_id=account['account_id']
        async with app.state.sessions.begin() as db:
            # Preserve same-session ordering, including across worker processes.
            key=int.from_bytes(hashlib.sha256(f'{account_id}:{sid}'.encode()).digest()[:8],signed=True)
            await db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':key})
            state=await get_state(db,account_id,sid)
            active=await load_active(db)
            if active is None:raise HTTPException(503,'No active corpus; import one first')
            fp,corpus=active
            if app.state.retriever is None or app.state.retriever.fingerprint!=fp:
                async with app.state.lock:
                    if app.state.retriever is None or app.state.retriever.fingerprint!=fp:
                        app.state.retriever=await run_in_threadpool(lambda:build_retriever(
                            corpus,app.state.segmenter,fp,settings,app.state.encoder))
            retriever=app.state.retriever
            supplied_filters=request.filters.model_dump(exclude_unset=True)
            trace=await run_in_threadpool(build_interpretation_trace,request.query_text_raw,app.state.segmenter,
                supplied_filters,state,sid,request.top_k)
            ri=trace['retrieval_input'];filters=trace['resolved_filters'];raw=request.query_text_raw
            try:validate('retrieval_input',ri)
            except ValueError:raise HTTPException(422,'Invalid retrieval filters/input') from None
            if include_diagnostics or include_stage_trace:
                bundle,retrieval_diagnostics=await run_in_threadpool(retriever.retrieve_with_diagnostics,ri,state)
            else:
                bundle=await run_in_threadpool(retriever.retrieve,ri,state)
                retrieval_diagnostics=None
            validate('evidence_bundle',bundle)
            if respond:
                result,grounding_diagnostics=ground_and_answer_with_diagnostics(bundle,raw)
            else:
                result=bundle
                _,sufficiency=inspect_sufficiency(bundle,raw)
                grounding_diagnostics={
                    'sufficiency':sufficiency,
                    'citation_binding':{'status':'skipped_not_generated','checked_count':0,'problems':[]},
                    'generation':{'mode':'mock_extractive','status':'skipped_retrieval_only'},
                }
            # Clear prior on new topic or ambiguity instead of leaking old identity.
            new=build_conversation_state(sid,filters,bundle,raw,datetime.now(timezone.utc).isoformat())
            state_transition=explain_state_transition(raw,state,new,supplied_filters,trace['explicit_filters'])
            validate('conversation_state',new);await save_state(db,account_id,new)
            await log_event(db,account_id,sid,{'snapshot':fp,'bundle_id':bundle['bundle_id'],'top_score':bundle['top_score'],
                'second_score':bundle['second_score'],'margin':bundle['margin'],'confidence_status':bundle['confidence_status'],
                'procedure_id':bundle['resolved_procedure_id'],'fragment_ids':[e['fragment_id'] for e in bundle['evidence']],
                'generator':'mock_extractive','retrieval_mode':settings.retrieval_mode,'fusion_method':retriever.fusion_method,
                'embedding_fingerprint':retriever.encoder.model_fingerprint if hasattr(retriever,'encoder') else None,
                'thresholds':'uncalibrated_demo','segmenter':retriever.segmenter.metadata()['config_fingerprint']})
        if include_stage_trace:
            stage_trace={
                'trace_id':trace['trace_id'],
                'interpretation':{key:value for key,value in trace.items() if key!='retrieval_input'},
                'retrieval':retrieval_diagnostics,
                'evidence':[{key:item.get(key) for key in (
                    'fragment_id','procedure_id','section_type','text','score','method',
                    'source_id','source_version','effective_date','source_locator'
                )} for item in bundle['evidence']],
                'grounding':grounding_diagnostics,
                'conversation':state_transition,
            }
            return result,sid,retrieval_diagnostics,stage_trace
        return (result,sid,retrieval_diagnostics) if include_diagnostics else (result,sid)
    @app.post('/api/v1/interpret')
    async def interpret_request(request:Query,response:Response,account=Depends(require_account)):
        if not settings.enable_dev_trace:raise HTTPException(404,'Development trace is disabled')
        sid=request.session_id or str(uuid4())
        async with app.state.sessions() as db:state=await get_state(db,account['account_id'],sid)
        trace=await run_in_threadpool(build_interpretation_trace,request.query_text_raw,app.state.segmenter,
            request.filters.model_dump(exclude_unset=True),state,sid,request.top_k)
        try:validate('retrieval_input',trace['retrieval_input'])
        except ValueError:raise HTTPException(422,'Invalid retrieval filters/input') from None
        trace['retrieval_input_valid']=True
        trace.pop('retrieval_input')
        response.headers['X-Conversation-Session-Id']=sid
        return trace
    @app.post('/api/v1/retrieve')
    async def retrieve(request:Query,response:Response,account=Depends(require_account)):
        result,sid=await execute(request,False,account);response.headers['X-Conversation-Session-Id']=sid;return result
    @app.post('/api/v1/retrieve/trace')
    async def retrieve_trace(request:Query,response:Response,account=Depends(require_account)):
        if not settings.enable_dev_trace:raise HTTPException(404,'Development trace is disabled')
        bundle,sid,diagnostics,stage_trace=await execute(request,False,account,
            include_diagnostics=True,include_stage_trace=True)
        response.headers['X-Conversation-Session-Id']=sid
        return {'trace_id':stage_trace['trace_id'],'evidence_bundle':bundle,'diagnostics':diagnostics,'stage_trace':stage_trace}
    @app.post('/api/v1/answer')
    async def answer(request:Query,response:Response,account=Depends(require_account)):
        result,sid=await execute(request,True,account);response.headers['X-Conversation-Session-Id']=sid;return result
    @app.post('/api/v1/answer/trace')
    async def answer_trace(request:Query,response:Response,account=Depends(require_account)):
        if not settings.enable_dev_trace:raise HTTPException(404,'Development trace is disabled')
        result,sid,_,stage_trace=await execute(request,True,account,include_stage_trace=True)
        response.headers['X-Conversation-Session-Id']=sid
        return {'grounded_answer':result,'stage_trace':stage_trace}
    return app

app=create_app()
