import os
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app

@pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='Needs isolated PostgreSQL TEST_DATABASE_URL')
def test_api_real_postgres():
    cfg=Settings(database_url=os.environ['TEST_DATABASE_URL'],bootstrap_demo=True,allow_draft=True,
        auth_cookie_secure=False,allow_registration=True,enable_dev_trace=True)
    suffix=uuid4().hex[:10]
    session_id='integration-session'
    with TestClient(create_app(cfg)) as alice:
        assert alice.get('/health').json()['database']=='postgresql'
        assert alice.post('/api/v1/answer',json={'query_text_raw':'demo alpha'}).status_code==401
        assert alice.post('/api/v1/auth/register',json={'username':f'alice-{suffix}','password':'alice-password-long'}).status_code==200
        r=alice.post('/api/v1/answer',json={'query_text_raw':'demo alpha lệ phí','session_id':session_id})
        assert r.status_code==200,r.text
        assert r.json()['status']=='answered'
        cookie=alice.cookies.get(cfg.auth_cookie_name)
        r=alice.post('/api/v1/retrieve',json={'query_text_raw':'còn thời gian thì sao','session_id':session_id})
        assert r.json()['resolved_procedure_id']=='DEMO-A'
        assert r.json()['evidence'][0]['section_type']=='processing_time'
        grounded_trace=alice.post('/api/v1/answer/trace',json={
            'query_text_raw':'demo alpha lệ phí','session_id':session_id
        })
        assert grounded_trace.status_code==200,grounded_trace.text
        grounded_stages=grounded_trace.json()['stage_trace']
        assert grounded_stages['grounding']['sufficiency']['status']=='passed'
        assert grounded_stages['grounding']['citation_binding']['status']=='passed'
        assert grounded_stages['evidence'][0]['source_locator']
        missing_trace=alice.post('/api/v1/answer/trace',json={
            'query_text_raw':'demo alpha điều kiện','session_id':session_id
        }).json()
        assert missing_trace['grounded_answer']['status']=='insufficient_data'
        assert missing_trace['stage_trace']['grounding']['sufficiency']['missing_section_types']==['eligibility']
        exact_trace=alice.post('/api/v1/retrieve/trace',json={
            'query_text_raw':'demo alpha lệ phí','session_id':session_id
        }).json()['diagnostics']
        assert exact_trace['selected_retrieval_mode']=='exact_match'
        assert exact_trace['ranked_candidates'][0]['procedure_id']=='DEMO-A'
        trace=alice.post('/api/v1/interpret',json={'query_text_raw':'còn lệ phí','session_id':session_id}).json()
        assert trace['prior_state']['exists'] is True
        ambiguous_trace=alice.post('/api/v1/retrieve/trace',json={
            'query_text_raw':'demo chung lệ phí','session_id':session_id
        }).json()['diagnostics']
        assert ambiguous_trace['confidence_status']=='ambiguous'
        assert len(ambiguous_trace['ranked_candidates'])>=2
        r=alice.post('/api/v1/answer',json={'query_text_raw':'demo chung lệ phí'})
        assert r.json()['status']=='clarification_needed'
        r=alice.post('/api/v1/answer',json={'query_text_raw':'zzzzzzzz'})
        assert r.json()['status']=='insufficient_data'
        assert alice.post('/api/v1/retrieve',json={'query_text_raw':'demo alpha','filters':{'effective_date':'invalid'}}).status_code==422
        assert alice.post('/api/v1/retrieve',json={'query_text_raw':'demo alpha','top_k':0}).status_code==422
        final_state=alice.post('/api/v1/answer',json={
            'query_text_raw':'demo alpha lệ phí','session_id':session_id
        })
        assert final_state.status_code==200,final_state.text
    with TestClient(create_app(cfg)) as bob:
        assert bob.post('/api/v1/auth/register',json={'username':f'bob-{suffix}','password':'bob-password-long'}).status_code==200
        bob_trace=bob.post('/api/v1/interpret',json={'query_text_raw':'còn lệ phí','session_id':session_id}).json()
        assert bob_trace['prior_state']['exists'] is False
        bob.post('/api/v1/answer',json={'query_text_raw':'demo beta lệ phí','session_id':session_id})
    with TestClient(create_app(cfg)) as alice_reopened:
        alice_reopened.cookies.set(cfg.auth_cookie_name,cookie)
        r=alice_reopened.post('/api/v1/retrieve',json={'query_text_raw':'còn lệ phí','session_id':session_id})
        assert r.json()['resolved_procedure_id']=='DEMO-A'
