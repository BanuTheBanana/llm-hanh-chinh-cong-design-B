import os
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app

@pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='Needs isolated PostgreSQL TEST_DATABASE_URL')
def test_api_real_postgres():
    cfg=Settings(database_url=os.environ['TEST_DATABASE_URL'],bootstrap_demo=True,allow_draft=True,api_token='test-token')
    headers={'Authorization':'Bearer test-token'}
    with TestClient(create_app(cfg)) as c:
        assert c.get('/health').json()['database']=='postgresql'
        assert c.post('/api/v1/answer',json={'query_text_raw':'demo alpha'}).status_code==401
        r=c.post('/api/v1/answer',headers=headers,json={'query_text_raw':'demo alpha lệ phí','session_id':'integration-session'})
        assert r.status_code==200,r.text
        assert r.json()['status']=='answered'
        r=c.post('/api/v1/retrieve',headers=headers,json={'query_text_raw':'còn thời gian thì sao','session_id':'integration-session'})
        assert r.json()['resolved_procedure_id']=='DEMO-A'
        assert r.json()['evidence'][0]['section_type']=='processing_time'
        r=c.post('/api/v1/answer',headers=headers,json={'query_text_raw':'demo chung lệ phí'})
        assert r.json()['status']=='clarification_needed'
        r=c.post('/api/v1/answer',headers=headers,json={'query_text_raw':'zzzzzzzz'})
        assert r.json()['status']=='insufficient_data'
        assert c.post('/api/v1/retrieve',headers=headers,json={'query_text_raw':'demo alpha','filters':{'effective_date':'invalid'}}).status_code==422
        assert c.post('/api/v1/retrieve',headers=headers,json={'query_text_raw':'demo alpha','top_k':0}).status_code==422
    # New app instance reads prior state from PostgreSQL (not process memory).
    with TestClient(create_app(cfg)) as c:
        r=c.post('/api/v1/retrieve',headers=headers,json={'query_text_raw':'còn lệ phí','session_id':'integration-session'})
        assert r.json()['resolved_procedure_id']=='DEMO-A'
