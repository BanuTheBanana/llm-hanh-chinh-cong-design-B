"""Aggregate procedure/field metrics. No raw queries or source text in reports."""
from time import perf_counter
import numpy as np


def evaluate(retriever,cases):
    if not cases:raise ValueError('Empty benchmark')
    ids=[c['case_id'] for c in cases]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate benchmark IDs')
    correct=0;status_correct=0;resolved=0;correct_resolved=0
    tp=fp=fn=0;all_fields=0;field_cases=0;latencies=[]
    ambiguity_hits=ambiguity_total=0;rows=[]
    for case in cases:
        raw=case['query'];req={'query_text_raw':raw,'query_text_segmented':retriever.segmenter.segment(raw),
            'filters':case.get('filters',{}),'top_k':case.get('top_k',5)}
        start=perf_counter();bundle=retriever.retrieve(req,case.get('state'));latencies.append((perf_counter()-start)*1000)
        expected=case.get('procedure_id');status=case['status'];actual=bundle['resolved_procedure_id']
        status_correct+=bundle['confidence_status']==status
        correct+=actual==expected and bundle['confidence_status']==status
        if bundle['confidence_status']=='resolved':
            resolved+=1;correct_resolved+=actual==expected and status=='resolved'
        gold={(expected,s) for s in case.get('section_types',[])}
        got={(e['procedure_id'],e['section_type']) for e in bundle['evidence']}
        if gold:
            field_cases+=1;tp+=len(got&gold);fp+=len(got-gold);fn+=len(gold-got);all_fields+=gold<=got
        if status=='ambiguous':
            expected_candidates=set(case.get('candidate_ids',[]))
            if expected_candidates:
                ambiguity_total+=len(expected_candidates)
                ambiguity_hits+=len(expected_candidates & {c['procedure_id'] for c in bundle['ambiguous_candidates']})
        rows.append({'case_id':case['case_id'],'status':bundle['confidence_status'],'procedure_id':actual,
                     'top_score':bundle['top_score'],'second_score':bundle['second_score'],'margin':bundle['margin']})
    total=len(cases)
    return {'count':total,'corpus_fingerprint':retriever.fingerprint,'fusion_method':retriever.fusion_method,
            'score_floor':retriever.score_floor,'margin_floor':retriever.margin_floor,
            'procedure_and_status_accuracy':correct/total,'status_accuracy':status_correct/total,
            'resolved_precision':correct_resolved/resolved if resolved else None,'resolved_coverage':resolved/total,
            'field_precision':tp/(tp+fp) if tp+fp else None,'field_recall':tp/(tp+fn) if tp+fn else None,
            'all_requested_fields_rate':all_fields/field_cases if field_cases else None,
            'ambiguity_candidate_recall':ambiguity_hits/ambiguity_total if ambiguity_total else None,
            'latency_ms':{'p50':float(np.percentile(latencies,50)),'p95':float(np.percentile(latencies,95))},'cases':rows}


def tune(factory,cases,score_floors,margin_floors):
    if not cases or any(c.get('split')!='dev' for c in cases):
        raise ValueError('Threshold tuning accepts DEV cases only')
    results=[]
    for score in score_floors:
        for margin in margin_floors:
            report=evaluate(factory(score,margin),cases)
            results.append({k:v for k,v in report.items() if k not in {'cases','latency_ms'}})
    return sorted(results,key=lambda r:(-r['procedure_and_status_accuracy'],-(r['resolved_precision'] or 0),-r['score_floor'],-r['margin_floor']))
