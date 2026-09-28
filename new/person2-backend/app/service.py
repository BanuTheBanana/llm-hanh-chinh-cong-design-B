from datetime import datetime,timezone
from app.contracts import validate
from app.legacy.grounding import verify_citations
from app.legacy.templates import clarification_prompt
from person1_retrieval.retriever import sections

class MockGenerator:
    """Deterministic extractive mock: no invented fee/date; no model/API needed."""
    def generate(self,bundle):
        lines=[];citations=[]
        for e in bundle['evidence']:
            lines.append(e['text'])
            citations.append({'fragment_id':e['fragment_id'],'source_id':e['source_id'],
                'source_locator':e['source_locator'],'claim_text':e['text']})
        return {'answer_text':'[MOCK AI — trích nguyên văn dữ liệu thử nghiệm]\n'+'\n\n'.join(lines),'citations':citations}

def ground_and_answer(bundle,query):
    validate('evidence_bundle',bundle)
    status=bundle['confidence_status'];answer='';citations=[];prompt=None
    if status=='ambiguous':
        result_status='clarification_needed';prompt=clarification_prompt(bundle['ambiguous_candidates'])
    elif status=='low_confidence':
        result_status='insufficient_data';prompt='Chưa tìm thấy bằng chứng phù hợp. Bạn cho biết tên thủ tục và nội dung cần hỏi nhé.'
    else:
        requested=set(sections(query));present={e['section_type'] for e in bundle['evidence']}
        if not bundle['evidence'] or requested-present:
            result_status='insufficient_data';prompt='Chưa đủ bằng chứng cho tất cả nội dung được hỏi.'
        else:
            generated=MockGenerator().generate(bundle)
            check=verify_citations(bundle,generated['answer_text'],generated['citations'])
            if not check.ok:raise ValueError('Mock generation citation mismatch')
            result_status='answered';answer=generated['answer_text'];citations=generated['citations']
    result={'status':result_status,'answer_text':answer,'citations':citations,'clarification_prompt':prompt,
        'evidence_bundle_id':bundle['bundle_id'],'created_at':datetime.now(timezone.utc).isoformat()}
    validate('grounded_answer',result)
    return result
