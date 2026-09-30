"""Deterministic self-consistency checks, not a labeled retrieval benchmark.

Only aggregates/record IDs are written. Corpus text remains in local memory.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from person1_retrieval.corpus import read_corpus,fingerprint
from person1_retrieval.retriever import LexicalRetriever
from person1_retrieval import VietnameseSegmenter


def run(directory):
    corpus=read_corpus(directory);segmenter=VietnameseSegmenter()
    r=LexicalRetriever(corpus,segmenter,fingerprint(corpus),allow_draft=True)
    def query(raw):
        return r.retrieve({'query_text_raw':raw,'query_text_segmented':segmenter.segment(raw),'filters':{},'top_k':5})
    titles=Counter(p['canonical_name'].casefold() for p in corpus['procedures'])
    stats=Counter();unresolved=[]
    phrases={'fee':'lệ phí','processing_time':'bao lâu','required_documents':'hồ sơ','legal_basis':'căn cứ pháp lý','submission_location':'nơi nộp'}
    for p in corpus['procedures']:
        pid=p['procedure_id'];b=query(p['canonical_name'])
        if b['resolved_procedure_id']==pid:stats['canonical_name_correct']+=1
        else:
            stats['canonical_name_unresolved']+=1
            unresolved.append({'procedure_id':pid,'status':b['confidence_status'],'duplicate_canonical_name':titles[p['canonical_name'].casefold()]>1})
        for section in sorted({f['section_type'] for f in corpus['fragments'] if f['procedure_id']==pid}&phrases.keys()):
            b=query(p['canonical_name']+' '+phrases[section]);stats['field_queries']+=1
            if b['resolved_procedure_id']==pid and b['evidence'] and all(e['procedure_id']==pid and e['section_type']==section for e in b['evidence']):
                stats['field_queries_correct']+=1
            elif b['confidence_status'] in {'ambiguous','low_confidence'}:stats['field_queries_abstained']+=1
            else:stats['field_queries_wrong']+=1
    # Default production policy must not serve a draft source with unknown dates.
    strict=LexicalRetriever(corpus,segmenter,fingerprint(corpus),allow_draft=False)
    for p in corpus['procedures']:
        raw=p['canonical_name'];b=strict.retrieve({'query_text_raw':raw,'query_text_segmented':segmenter.segment(raw),'filters':{}})
        if b['confidence_status']=='low_confidence':stats['strict_mode_abstained']+=1
    return {'corpus_fingerprint':fingerprint(corpus),'counts':{k:len(v) for k,v in corpus.items()},
            'review_status_counts':dict(Counter(s['review_status'] for s in corpus['sources'])),
            'missing_effective_dates':sum(s.get('effective_date') is None for s in corpus['sources']),
            'duplicate_name_groups':sum(n>1 for n in titles.values()),'checks':dict(stats),
            'unresolved_records':unresolved,'segmenter':segmenter.metadata(),
            'quality_claim':'self_consistency_only_not_independent_gold_accuracy'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();summary=run(args.corpus)
    Path(args.output).write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in {'unresolved_records','segmenter'}},ensure_ascii=False,indent=2))
