from pathlib import Path
from copy import deepcopy
import pytest
from app.corpus import read_corpus,fingerprint,canonical_corpus
from app.contracts import validate
from app.service import ground_and_answer
from person1_retrieval import VietnameseSegmenter,SegmenterConfig
from person1_retrieval.retriever import LexicalRetriever

@pytest.fixture
def corpus():return read_corpus(Path(__file__).resolve().parents[1]/'fixtures/demo')
@pytest.fixture
def engine():return VietnameseSegmenter(SegmenterConfig('underthesea'))
def query(engine,text,**kw):return {'query_text_raw':text,'query_text_segmented':engine.segment(text),'filters':{},'top_k':5,**kw}
def make(corpus,engine,**kw):return LexicalRetriever(corpus,engine,fingerprint(corpus),allow_draft=True,**kw)

def test_resolved_and_citations(corpus,engine):
    b=make(corpus,engine).retrieve(query(engine,'demo alpha lệ phí'))
    assert b['confidence_status']=='resolved' and b['resolved_procedure_id']=='DEMO-A'
    assert all(e['section_type']=='fee' for e in b['evidence'])
    validate('evidence_bundle',b)
    a=ground_and_answer(b,'demo alpha lệ phí');validate('grounded_answer',a);assert a['status']=='answered'
    assert a['citations'][0]['claim_text']==b['evidence'][0]['text']

def test_ambiguous_and_absent(corpus,engine):
    r=make(corpus,engine)
    b=r.retrieve(query(engine,'demo chung lệ phí',top_k=1));assert b['confidence_status']=='ambiguous'
    assert len(b['ambiguous_candidates'])==3 and b['second_score'] is not None and not b['evidence']
    assert b['margin']==pytest.approx(b['top_score']-b['second_score'])
    assert ground_and_answer(b,'demo chung lệ phí')['status']=='clarification_needed'
    b=r.retrieve(query(engine,'zzzzzzzzz'));assert b['confidence_status']=='low_confidence' and b['top_score'] is None

def test_filters_fail_closed(corpus,engine):
    for filters in [{'scope':'người nước ngoài'},{'jurisdiction':'khác'},{'effective_date':'2000-01-01'}]:
        assert make(corpus,engine).retrieve(query(engine,'demo alpha',filters=filters))['confidence_status']=='low_confidence'
    r=LexicalRetriever(corpus,engine,fingerprint(corpus),allow_draft=False)
    assert r.retrieve(query(engine,'demo alpha'))['confidence_status']=='low_confidence'

def test_followup_and_switch(corpus,engine):
    r=make(corpus,engine);state={'last_resolved_procedure_id':'DEMO-A'}
    assert r.retrieve(query(engine,'còn thời gian thì sao'),state)['resolved_procedure_id']=='DEMO-A'
    assert r.retrieve(query(engine,'demo beta lệ phí'),state)['resolved_procedure_id']=='DEMO-B'
    assert r.retrieve(query(engine,'zzzzzz'),state)['resolved_procedure_id'] is None

def test_multifield_and_bound(corpus,engine):
    r=make(corpus,engine);q=query(engine,'demo alpha lệ phí và hồ sơ',top_k=1)
    b=r.retrieve(q);assert len(b['evidence'])==1
    assert ground_and_answer(b,q['query_text_raw'])['status']=='insufficient_data'
    q['top_k']=2;b=r.retrieve(q);assert ground_and_answer(b,q['query_text_raw'])['status']=='answered'

def test_fingerprint_and_hash(corpus):
    c=deepcopy(corpus)
    for values in c.values():values.reverse()
    assert fingerprint(c)==fingerprint(corpus)
    c['fragments'][0]['text']='tampered'
    with pytest.raises(ValueError):canonical_corpus(c)
