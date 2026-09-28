import hashlib,json
from pathlib import Path
from app.contracts import validate

FILES={'sources':'source_manifest.json','procedures':'procedure_records.json','fragments':'procedure_fragments.json'}
SCHEMAS={'sources':'source_manifest','procedures':'procedure_record','fragments':'procedure_fragment'}
KEYS={'sources':'source_id','procedures':'procedure_id','fragments':'fragment_id'}

def read_corpus(directory):
    c={k:json.loads((Path(directory)/n).read_text(encoding='utf-8-sig')) for k,n in FILES.items()}
    # Explicit adaptation of the previously generated draft JSON. No fake dates.
    for s in c['sources']: s.setdefault('effective_date',None)
    for p in c['procedures']:
        if p.get('jurisdiction')=='unknown': p['jurisdiction']=None
    return canonical_corpus(c)

def canonical_corpus(c):
    if set(c)!=set(FILES): raise ValueError('Corpus must contain sources/procedures/fragments')
    out={}
    for kind in FILES:
        if not isinstance(c[kind],list) or not c[kind]: raise ValueError('Empty/invalid corpus collection')
        ids=set()
        for item in c[kind]:
            validate(SCHEMAS[kind],item)
            ident=item[KEYS[kind]]
            if not ident or ident in ids: raise ValueError('Duplicate/empty corpus ID')
            ids.add(ident)
        out[kind]=sorted(c[kind],key=lambda x:x[KEYS[kind]])
    sources={s['source_id']:s for s in out['sources']};procs={p['procedure_id']:p for p in out['procedures']}
    frags={f['fragment_id']:f for f in out['fragments']}
    for s in sources.values():
        seen=set();current=s
        while current.get('superseded_by'):
            target=current['superseded_by']
            if target not in sources or target in seen: raise ValueError('Invalid source replacement chain')
            seen.add(target);current=sources[target]
    for p in procs.values():
        if p['source_id'] not in sources or len(p['fragment_ids'])!=len(set(p['fragment_ids'])):raise ValueError('Invalid procedure source/fragment list')
        if not p['canonical_name'].strip():raise ValueError('Empty procedure name')
        for fid in p['fragment_ids']:
            if fid not in frags or frags[fid]['procedure_id']!=p['procedure_id']:raise ValueError('Invalid procedure fragment link')
    for f in frags.values():
        if f['procedure_id'] not in procs or f['source_id'] not in sources:raise ValueError('Invalid fragment link')
        if f['source_id'] != procs[f['procedure_id']]['source_id']:raise ValueError('Mixed sources within procedure version')
        if f['fragment_id'] not in procs[f['procedure_id']]['fragment_ids']:raise ValueError('Unlisted fragment')
        if not f['text'].strip() or hashlib.sha256(f['text'].encode()).hexdigest()!=f['content_hash']:raise ValueError('Invalid fragment text/hash')
    return out

def fingerprint(c):
    return hashlib.sha256(json.dumps(canonical_corpus(c),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
