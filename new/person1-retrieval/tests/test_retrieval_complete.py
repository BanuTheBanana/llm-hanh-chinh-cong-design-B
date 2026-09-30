from copy import deepcopy
from pathlib import Path
import hashlib
import json
import logging
import numpy as np
import pytest
from person1_retrieval.corpus import read_corpus,fingerprint,canonical_corpus
from person1_retrieval.retriever import LexicalRetriever
from person1_retrieval.dense import HybridRetriever,unit_rows
from person1_retrieval.evaluation import evaluate,tune

ROOT=Path(__file__).resolve().parents[2]
class Identity:
    def segment(self,text):return ' '.join(text.split())
    def metadata(self):return {'backend':'test_identity'}

@pytest.fixture
def corpus():return read_corpus(ROOT/'person2-backend/fixtures/demo')
def request(text,**kw):return dict(query_text_raw=text,query_text_segmented=Identity().segment(text),filters={},**kw)
def engine(corpus,**kw):return LexicalRetriever(corpus,Identity(),fingerprint(corpus),allow_draft=True,**kw)
def state():return {'unresolved_references':['DEMO-B','DEMO-A'],'last_resolved_procedure_id':'DEMO-C','last_requested_section_types':['fee']}

@pytest.mark.parametrize('text,pid',[('cái đầu tiên','DEMO-B'),('chọn cái thứ hai','DEMO-A'),('Không, cái thứ hai','DEMO-A'),('số 2','DEMO-A')])
def test_ordered_candidate_choice(corpus,text,pid):
    prior=state();before=deepcopy(prior);b=engine(corpus).retrieve(request(text),prior)
    assert b['resolved_procedure_id']==pid
    assert {e['section_type'] for e in b['evidence']}=={'fee'}
    assert prior==before

@pytest.mark.parametrize('text',['cái thứ ba','số 0','số 999'])
def test_invalid_choice_abstains(corpus,text):
    assert engine(corpus).retrieve(request(text),state())['confidence_status']=='low_confidence'

@pytest.mark.parametrize('refs',[['gone','DEMO-A'],['DEMO-A','DEMO-A'],[]])
def test_stale_and_duplicate_candidates(corpus,refs):
    prior=state();prior['unresolved_references']=refs
    assert engine(corpus).retrieve(request('cái đầu tiên'),prior)['confidence_status']=='low_confidence'

@pytest.mark.parametrize('text',['demo gamma hồ sơ','không, tôi muốn demo gamma hồ sơ','còn demo gamma hồ sơ'])
def test_new_topic_overrides_prior_candidates(corpus,text):
    b=engine(corpus).retrieve(request(text),state())
    assert b['resolved_procedure_id']=='DEMO-C'
    assert {e['section_type'] for e in b['evidence']}=={'required_documents'}

def test_selection_respects_filters(corpus):
    req=request('cái đầu tiên');req['filters']={'jurisdiction':'other'}
    assert engine(corpus).retrieve(req,state())['confidence_status']=='low_confidence'

def test_distinct_procedure_confidence_with_small_top_k(corpus):
    b=engine(corpus).retrieve(request('demo chung lệ phí',top_k=1))
    assert b['confidence_status']=='ambiguous' and b['second_score'] is not None
    assert len({x['procedure_id'] for x in b['ambiguous_candidates']})==3
    assert not b['evidence']

def test_mixed_source_rejected(corpus):
    c=deepcopy(corpus);source=deepcopy(c['sources'][0]);source['source_id']='other';c['sources'].append(source)
    c['fragments'][0]['source_id']='other'
    with pytest.raises(ValueError,match='Mixed sources'):canonical_corpus(c)

def test_hash_and_reproducible_snapshot(corpus):
    c=deepcopy(corpus)
    for values in c.values():values.reverse()
    for p in c['procedures']:p['fragment_ids'].reverse()
    assert fingerprint(c)==fingerprint(corpus)
    c['fragments'][0]['text']='changed'
    with pytest.raises(ValueError):canonical_corpus(c)

def test_supersession_dates(corpus):
    c=deepcopy(corpus);old=c['sources'][0]
    old.update(review_status='deprecated',effective_date='2020-01-01',superseded_by='new')
    new=deepcopy(old);new.update(source_id='new',review_status='published',effective_date='2025-01-01',superseded_by=None,version='2')
    c['sources'].append(new);r=LexicalRetriever(c,Identity(),fingerprint(c))
    req=request('demo alpha');req['filters']={'effective_date':'2024-01-01'}
    assert r.retrieve(req)['confidence_status']=='resolved'
    req['filters']={'effective_date':'2025-01-01'}
    assert r.retrieve(req)['confidence_status']=='low_confidence'

def test_cycles(corpus):
    corpus['sources'][0]['superseded_by']=corpus['sources'][0]['source_id']
    with pytest.raises(ValueError):canonical_corpus(corpus)

def test_bad_query_segmentation_and_topk(corpus):
    r=engine(corpus);req=request('demo alpha');req['query_text_segmented']='demo beta'
    with pytest.raises(ValueError,match='segmentation'):r.retrieve(req)
    with pytest.raises(ValueError):r.retrieve(request('demo alpha',top_k=0))

def test_logs_exclude_text(corpus,caplog):
    with caplog.at_level(logging.INFO,logger='rag.retrieval'):engine(corpus).retrieve(request('PRIVATE_RAW_8383'))
    assert 'PRIVATE_RAW_8383' not in caplog.text
    assert 'elapsed_ms=' in caplog.text
    assert all(f['text'] not in caplog.text for f in corpus['fragments'])

class ToyEncoder:
    """Deterministic test vectors, NOT a language model or semantic benchmark."""
    def encode(self,texts,*,query=False):
        def vector(t):
            t=t.casefold()
            if 'alpha' in t or 'ẩn dụ a' in t:return [1,0,0,0]
            if 'beta' in t:return [0,1,0,0]
            if 'gamma' in t:return [0,0,1,0]
            return [0,0,0,1]
        return np.array([vector(t) for t in texts])
    def metadata(self):return {'kind':'test_fixture_only'}

def hybrid(corpus,mode='hybrid'):
    return HybridRetriever(corpus,Identity(),fingerprint(corpus),encoder=ToyEncoder(),mode=mode,
        allow_draft=True,score_floor=0.02 if mode=='hybrid' else 0.7,margin_floor=0.001,dense_min_similarity=0.6)

@pytest.mark.parametrize('mode',['dense','hybrid'])
def test_dense_semantic_route_and_provenance(corpus,mode):
    r=hybrid(corpus,mode);b=r.retrieve(request('ẩn dụ a'))
    assert b['resolved_procedure_id']=='DEMO-A'
    assert {e['method'] for e in b['evidence']}==({'dense'} if mode=='dense' else {'fused'})
    assert all(e['source_version'] and 'effective_date' in e and e['section_type'] for e in b['evidence'])
    assert r.retrieve(request('unknown'))['confidence_status']=='low_confidence'
    req=request('ẩn dụ a');req['filters']={'jurisdiction':'other'}
    assert r.retrieve(req)['confidence_status']=='low_confidence'

def test_save_dense_index(corpus,tmp_path):
    r=hybrid(corpus);r.save_index(tmp_path)
    meta=json.loads((tmp_path/'index.json').read_text())
    assert meta['corpus_fingerprint']==fingerprint(corpus)
    with np.load(tmp_path/'dense.npz',allow_pickle=False) as values:assert values['fragments'].shape==(9,4)

@pytest.mark.parametrize('values',[[[0,0]],[[float('nan'),1]],[1,2]])
def test_invalid_vectors(values):
    with pytest.raises(ValueError):unit_rows(values,1)

def test_metrics_count_wrong_procedure_fields_as_wrong(corpus):
    cases=[{'case_id':'wrong','query':'demo alpha lệ phí','status':'resolved','procedure_id':'DEMO-B','section_types':['fee']}]
    report=evaluate(engine(corpus),cases)
    assert report['procedure_and_status_accuracy']==0 and report['field_recall']==0 and report['field_precision']==0

def test_tuning_rejects_test_split(corpus):
    cases=[{'case_id':'test','query':'demo alpha','split':'test','status':'resolved','procedure_id':'DEMO-A'}]
    with pytest.raises(ValueError,match='DEV'):tune(lambda s,m:engine(corpus,score_floor=s,margin_floor=m),cases,[0.5],[0.15])

def test_explicit_negative_correction(corpus):
    b=engine(corpus).retrieve(request('không phải demo alpha mà demo beta lệ phí'),state())
    assert b['resolved_procedure_id']=='DEMO-B'

def test_context_filter_policy(corpus):
    r=engine(corpus)
    assert r.carries_context('cái đầu tiên',state())
    assert r.carries_context('còn lệ phí',state())
    assert not r.carries_context('còn demo gamma lệ phí',state())
    assert not r.carries_context('cái thứ ba',state())

def test_exact_match_survives_dense_similarity_gate(corpus):
    class UnknownEncoder(ToyEncoder):
        def encode(self,texts,*,query=False):
            if query:return np.array([[0,0,0,1] for _ in texts])
            return super().encode(texts,query=query)
    r=HybridRetriever(corpus,Identity(),fingerprint(corpus),encoder=UnknownEncoder(),mode='dense',allow_draft=True,
        score_floor=.8,margin_floor=.1,dense_min_similarity=.6)
    assert r.retrieve(request('demo alpha'))['resolved_procedure_id']=='DEMO-A'

def test_rrf_ties_not_broken_by_id(corpus):
    class TiedEncoder(ToyEncoder):
        def encode(self,texts,*,query=False):return np.array([[1,0] for _ in texts])
    r=HybridRetriever(corpus,Identity(),fingerprint(corpus),encoder=TiedEncoder(),allow_draft=True,
        score_floor=.01,margin_floor=.001,dense_min_similarity=.6)
    b=r.retrieve(request('nonlexical'))
    assert b['confidence_status']=='ambiguous' and b['margin']==0

def test_specific_title_does_not_match_contained_short_title(corpus):
    corpus['procedures'][0]['canonical_name']='Thủ tục alpha'
    corpus['procedures'][1]['canonical_name']='Thủ tục alpha mở rộng'
    corpus['procedures'][0]['aliases']=[];corpus['procedures'][1]['aliases']=[]
    r=engine(corpus)
    assert r.retrieve(request('Thủ tục alpha mở rộng lệ phí'))['resolved_procedure_id']=='DEMO-B'
    assert r.exact_matches('Thủ tục alpha và Thủ tục alpha mở rộng')=={'DEMO-A','DEMO-B'}


def test_title_is_not_itself_a_field_request(corpus):
    corpus['procedures'][0]['canonical_name']='Thủ tục hồ sơ alpha'
    r=engine(corpus)
    assert r.requested_sections('Thủ tục hồ sơ alpha lệ phí')==['fee']
    b=r.retrieve(request('Thủ tục hồ sơ alpha lệ phí'))
    assert {e['section_type'] for e in b['evidence']}=={'fee'}


def test_duplicate_canonical_names_abstain_without_fabricating_labels(corpus):
    for p in corpus['procedures']:
        p['canonical_name']='Tên trùng';p['aliases']=[]
    assert engine(corpus).retrieve(request('Tên trùng'))['confidence_status']=='low_confidence'


def test_canonical_name_wins_over_another_records_identical_alias(corpus):
    corpus['procedures'][0]['canonical_name']='Thủ tục riêng alpha'
    corpus['procedures'][1]['aliases'].append('Thủ tục riêng alpha')
    r=engine(corpus)
    assert r.retrieve(request('Thủ tục riêng alpha lệ phí'))['resolved_procedure_id']=='DEMO-A'
