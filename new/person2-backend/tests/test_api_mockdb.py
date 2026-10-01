"""Endpoint tests with mocked DB transport; NOT a PostgreSQL connectivity test."""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi.testclient import TestClient
import app.main as main
from app.config import Settings
from app.corpus import read_corpus,fingerprint

class FakeConnection:
    async def run_sync(self,fn):pass
class FakeEngine:
    @asynccontextmanager
    async def begin(self):yield FakeConnection()
    async def dispose(self):pass
class FakeDB:
    async def execute(self,*args,**kwargs):pass
class FakeSessions:
    @asynccontextmanager
    async def begin(self):yield FakeDB()
    @asynccontextmanager
    async def __call__(self):yield FakeDB()

def test_endpoints_with_mocked_storage(monkeypatch):
    corpus=read_corpus(Path(__file__).resolve().parents[1]/'fixtures/demo')
    states={};logs=[];identity={'account_id':'account-a','username':'alice'}
    monkeypatch.setattr(main,'make_database',lambda settings:(FakeEngine(),FakeSessions()))
    async def active(db):return fingerprint(corpus),corpus
    async def get(db,account_id,sid):return states.get((account_id,sid))
    async def save(db,account_id,state):states[(account_id,state['session_id'])]=state
    async def log(db,account_id,sid,payload):logs.append((account_id,payload))
    monkeypatch.setattr(main,'load_active',active);monkeypatch.setattr(main,'get_state',get)
    monkeypatch.setattr(main,'save_state',save);monkeypatch.setattr(main,'log_event',log)
    async def current_account():return identity
    cfg=Settings(bootstrap_demo=False,allow_draft=True,enable_dev_trace=True)
    app=main.create_app(cfg)
    with TestClient(app) as unauthenticated_client:
        assert unauthenticated_client.post('/api/v1/answer',json={'query_text_raw':'demo alpha'}).status_code==401
        assert unauthenticated_client.post('/api/v1/auth/register',json={
            'username':'demo-user','password':'local-password-long'
        }).status_code==404
    app.dependency_overrides[main.require_account]=current_account
    with TestClient(app) as client:
        assert client.get('/health').status_code==200
        def call(text,endpoint='answer',**kwargs):
            return client.post('/api/v1/'+endpoint,json={'query_text_raw':text,'session_id':'test-session',**kwargs})
        response=call('demo alpha lệ phí');assert response.status_code==200,response.text
        assert response.json()['status']=='answered'
        assert response.headers['X-Conversation-Session-Id']=='test-session'
        exact_trace=call('demo alpha lệ phí','retrieve/trace').json()
        assert exact_trace['diagnostics']['selected_retrieval_mode']=='exact_match'
        assert exact_trace['diagnostics']['ranked_candidates'][0]['procedure_id']=='DEMO-A'
        assert exact_trace['diagnostics']['exact_matches'][0]['matched_term']=='demo alpha'
        identity['account_id']='account-b'
        foreign=call('còn thời gian','retrieve').json()
        assert foreign['resolved_procedure_id'] is None
        identity['account_id']='account-a'
        assert call('còn thời gian','retrieve').json()['resolved_procedure_id']=='DEMO-A'
        assert call('demo beta lệ phí','retrieve').json()['resolved_procedure_id']=='DEMO-B'
        assert call('demo chung lệ phí').json()['status']=='clarification_needed'
        assert call('zzzzzzzz').json()['status']=='insufficient_data'
        assert states[('account-a','test-session')]['last_resolved_procedure_id'] is None
        assert states[('account-b','test-session')]['last_resolved_procedure_id'] is None
        ambiguous_trace=call('demo chung lệ phí','retrieve/trace').json()['diagnostics']
        assert ambiguous_trace['confidence_status']=='ambiguous'
        assert len(ambiguous_trace['ranked_candidates'])>=2
        low_trace=call('zzzzzzzz','retrieve/trace').json()['diagnostics']
        assert low_trace['confidence_status']=='low_confidence'
        assert low_trace['ranked_candidates']==[]
        filtered_trace=call('demo alpha lệ phí','retrieve/trace',filters={'jurisdiction':'Tỉnh Sai'}).json()
        assert filtered_trace['diagnostics']['filters_applied']['jurisdiction']=='Tỉnh Sai'
        assert filtered_trace['diagnostics']['eligible_fragment_count']==0
        assert call('demo alpha',filters={'effective_date':'bad'}).status_code==422
        assert call('demo alpha',top_k=0).status_code==422
        trace=call('Hồ sơ ở tỉnh Bình Dương ngày 02/03/2025 dành cho cá nhân','interpret').json()
        assert trace['explicit_filters']['jurisdiction']=='tỉnh Bình Dương'
        assert trace['explicit_filters']['effective_date']=='2025-03-02'
        assert trace['requested_section_types']==['required_documents']
        assert trace['retrieval_input_valid'] is True
        answer_trace=call('demo alpha lệ phí','answer/trace')
        assert answer_trace.status_code==200,answer_trace.text
        answer_stages=answer_trace.json()['stage_trace']
        assert answer_trace.json()['grounded_answer']['status']=='answered'
        assert answer_stages['grounding']['sufficiency']['status']=='passed'
        assert answer_stages['grounding']['citation_binding']['status']=='passed'
        source_fragment=answer_stages['evidence'][0]
        assert source_fragment['source_version'] and source_fragment['source_locator']
        followup_trace=call('còn lệ phí','answer/trace').json()['stage_trace']
        assert followup_trace['conversation']['follow_up'] is True
        assert followup_trace['conversation']['previous_state']['last_resolved_procedure_id']=='DEMO-A'
        missing_trace=call('demo alpha lệ phí và căn cứ pháp lý','answer/trace').json()
        assert missing_trace['grounded_answer']['status']=='insufficient_data'
        assert missing_trace['stage_trace']['grounding']['sufficiency']['missing_section_types']==['legal_basis']
        switched_trace=call('demo beta lệ phí','answer/trace').json()['stage_trace']
        assert switched_trace['conversation']['state_reset_or_replacement_reason']=='new_topic_replaced_prior_procedure'
    assert len(logs)==14
    assert all('top_score' in p and 'second_score' in p and 'margin' in p for _,p in logs)
    assert all('snapshot' in p and 'bundle_id' in p and 'segmenter' in p for _,p in logs)
    assert all(not {'query_text_raw','query','text','answer_text','source_text'} & p.keys() for _,p in logs)
    disabled=main.create_app(Settings(bootstrap_demo=False,allow_draft=True,enable_dev_trace=False))
    disabled.dependency_overrides[main.require_account]=current_account
    with TestClient(disabled) as client:
        response=client.post('/api/v1/retrieve/trace',json={'query_text_raw':'demo alpha'})
        assert response.status_code==404
        response=client.post('/api/v1/answer/trace',json={'query_text_raw':'demo alpha'})
        assert response.status_code==404
