"""Run from the supplied repository so ../contracts remains authoritative."""
import argparse
import json
from pathlib import Path
from .corpus import read_corpus,fingerprint
from .segmenter import VietnameseSegmenter,SegmenterConfig,load_protected_terms
from .retriever import LexicalRetriever


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['validate','build','query','evaluate','tune'])
    parser.add_argument('--corpus',required=True)
    parser.add_argument('--output')
    parser.add_argument('--query')
    parser.add_argument('--state',help='Local JSON conversation state')
    parser.add_argument('--filters',default='{}',help='JSON RetrievalInput filters')
    parser.add_argument('--top-k',type=int,default=5)
    parser.add_argument('--benchmark')
    parser.add_argument('--split',choices=['dev','test'],default='dev')
    parser.add_argument('--backend',choices=['underthesea','pyvi'],default='underthesea')
    parser.add_argument('--protected-terms')
    parser.add_argument('--mode',choices=['lexical','dense','hybrid'],default='lexical')
    parser.add_argument('--model-path')
    parser.add_argument('--query-prefix',default='')
    parser.add_argument('--document-prefix',default='')
    parser.add_argument('--device',default='cpu')
    parser.add_argument('--batch-size',type=int,default=1)
    parser.add_argument('--score-floor',type=float)
    parser.add_argument('--margin-floor',type=float)
    parser.add_argument('--dense-min-similarity',type=float)
    parser.add_argument('--allow-draft',action='store_true')
    parser.add_argument('--scores',default='0,0.5,1,2')
    parser.add_argument('--margins',default='0,0.15,0.3,0.5')
    args=parser.parse_args()
    corpus=read_corpus(args.corpus);fp=fingerprint(corpus)
    report={'corpus_fingerprint':fp,'counts':{k:len(v) for k,v in corpus.items()},
            'review_status_counts':{s:sum(x['review_status']==s for x in corpus['sources']) for s in ['draft','reviewed','published','deprecated']}}
    if args.command=='validate':
        if args.output:Path(args.output).write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2));return
    terms=load_protected_terms(args.protected_terms) if args.protected_terms else ()
    segmenter=VietnameseSegmenter(SegmenterConfig(args.backend,terms))
    score=args.score_floor if args.score_floor is not None else 0.5
    margin=args.margin_floor if args.margin_floor is not None else 0.15
    dense=None
    if args.mode!='lexical':
        if not args.model_path or args.score_floor is None or args.margin_floor is None or args.dense_min_similarity is None:
            parser.error('dense/hybrid require local model and explicit score/margin/cosine thresholds')
        from .dense import LocalSentenceEncoder,HybridRetriever
        dense=LocalSentenceEncoder(args.model_path,query_prefix=args.query_prefix,document_prefix=args.document_prefix,
            device=args.device,batch_size=args.batch_size)
    def factory(s,m):
        kwargs=dict(allow_draft=args.allow_draft,score_floor=s,margin_floor=m)
        if dense:return HybridRetriever(corpus,segmenter,fp,encoder=dense,mode=args.mode,dense_min_similarity=args.dense_min_similarity,**kwargs)
        return LexicalRetriever(corpus,segmenter,fp,**kwargs)
    engine=factory(score,margin)
    report['segmenter']=segmenter.metadata()
    if args.command=='build':
        if not args.output:parser.error('build requires --output directory')
        path=Path(args.output);path.mkdir(parents=True,exist_ok=True)
        (path/'corpus.json').write_text(json.dumps(corpus,ensure_ascii=False,indent=2),encoding='utf-8')
        report['lexical_docs']=[dict(doc) for doc in engine.docs]
        report['fragment_ids']=[f['fragment_id'] for f in engine.fragments]
        report['idf']=engine.idf;report['avg_len']=engine.avg_len
        (path/'snapshot.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        if dense:engine.save_index(path)
        print(json.dumps({'corpus_fingerprint':fp,'counts':report['counts']}));return
    if args.command=='query':
        if not args.query:parser.error('query requires --query')
        state=json.loads(Path(args.state).read_text(encoding='utf-8')) if args.state else None
        report=engine.retrieve({'query_text_raw':args.query,'query_text_segmented':segmenter.segment(args.query),
                'filters':json.loads(args.filters),'top_k':args.top_k},state)
    else:
        if not args.benchmark:parser.error('evaluate/tune require --benchmark')
        if args.command=='tune' and args.split!='dev':parser.error('tune only accepts DEV')
        from .evaluation import evaluate,tune
        cases=json.loads(Path(args.benchmark).read_text(encoding='utf-8'))
        cases=[c for c in cases if c.get('split')==args.split]
        report=evaluate(engine,cases) if args.command=='evaluate' else tune(factory,cases,[float(x) for x in args.scores.split(',')],[float(x) for x in args.margins.split(',')])
    encoded=json.dumps(report,ensure_ascii=False,indent=2)
    if args.output:Path(args.output).write_text(encoded,encoding='utf-8')
    print(encoded)

if __name__=='__main__':main()
