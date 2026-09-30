from datetime import datetime,timezone
from app.contracts import validate
from app.legacy.grounding import check_sufficiency,verify_citations
from app.legacy.interpretation import requested_section_types
from app.legacy.templates import INSUFFICIENT_EVIDENCE_PROMPT,NO_MATCH_PROMPT,clarification_prompt

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
        candidates=bundle['ambiguous_candidates']
        distinct={c['procedure_id']:c for c in candidates if c['procedure_id'] and c['canonical_name'].strip()}
        distinct_names={c['canonical_name'].casefold() for c in distinct.values()}
        if len(distinct)>=2 and len(distinct_names)>=2:
            result_status='clarification_needed';prompt=clarification_prompt(list(distinct.values()))
        else:
            result_status='insufficient_data';prompt=NO_MATCH_PROMPT
    elif status=='low_confidence':
        result_status='insufficient_data';prompt=NO_MATCH_PROMPT
    else:
        sufficiency=check_sufficiency(bundle,requested_section_types(query))
        if not sufficiency.ok:
            result_status='insufficient_data';prompt=INSUFFICIENT_EVIDENCE_PROMPT
        else:
            generated=MockGenerator().generate(bundle)
            check=verify_citations(bundle,generated['answer_text'],generated['citations'])
            if not check.ok:raise ValueError('Mock generation citation mismatch')
            result_status='answered';answer=generated['answer_text'];citations=generated['citations']
    result={'status':result_status,'answer_text':answer,'citations':citations,'clarification_prompt':prompt,
        'evidence_bundle_id':bundle['bundle_id'],'created_at':datetime.now(timezone.utc).isoformat()}
    validate('grounded_answer',result)
    return result
