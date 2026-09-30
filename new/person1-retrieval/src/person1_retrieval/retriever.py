"""Lexical-only demo. Scores are BM25, not probabilities. No external calls."""
import math,re,logging,time
from .corpus import canonical_corpus, fingerprint as corpus_fingerprint
from .contracts import validate
from .segmenter import normalize_text
from collections import Counter
from datetime import date,datetime,timezone
from uuid import uuid4

log=logging.getLogger('rag.retrieval')
STOP={'tôi','cho','xin','hỏi','về','và','thì','ạ','nhé','là','của','có','không'}
SECTION_TERMS={'fee':['lệ phí','chi phí','mức thu','phí'],
 'processing_time':['bao lâu','thời gian','ngày làm việc'],
 'required_documents':['hồ sơ','giấy tờ','cần nộp'],
 'submission_location':['ở đâu','nơi nộp','địa điểm'],
 'legal_basis':['căn cứ','nghị định','thông tư'],
 'eligibility':['điều kiện','đối tượng'],'validity_period':['thời hạn sử dụng','hiệu lực bao lâu']}

def sections(text):
    t=' '.join(text.casefold().split())
    return [k for k,terms in SECTION_TERMS.items() if any(re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',t) for term in terms)]

def tokens(text):return [t for t in re.findall(r'\w+',text.casefold()) if t not in STOP]

class LexicalRetriever:
    def __init__(self, corpus, segmenter, fingerprint, *, allow_draft=False, score_floor=0.5, margin_floor=0.15):
        corpus=canonical_corpus(corpus)
        if fingerprint != corpus_fingerprint(corpus): raise ValueError('Corpus fingerprint mismatch')
        if not math.isfinite(score_floor) or not math.isfinite(margin_floor) or margin_floor<0:
            raise ValueError('Invalid confidence thresholds')
        self.corpus=corpus;self.segmenter=segmenter;self.fingerprint=fingerprint
        self.fusion_method='lexical_bm25_procedure_max'
        self.evidence_method='lexical' 
        self.allow_draft=allow_draft;self.score_floor=score_floor;self.margin_floor=margin_floor
        self.sources={s['source_id']:s for s in corpus['sources']}
        self.procedures={p['procedure_id']:p for p in corpus['procedures']}
        self.fragments=corpus['fragments']
        self.names={pid:[segmenter.segment(name).casefold() for name in [p['canonical_name'],*p.get('aliases',[]),*p.get('official_codes',[])] if name.strip()] for pid,p in self.procedures.items()}
        self.docs=[Counter(tokens(segmenter.segment(self.procedures[f['procedure_id']]['canonical_name']+' '+f['text']))) for f in self.fragments]
        df=Counter(t for doc in self.docs for t in doc)
        n=len(self.docs);self.idf={t:math.log(1+(n-freq+0.5)/(freq+0.5)) for t,freq in df.items()}
        self.avg_len=sum(sum(d.values()) for d in self.docs)/max(1,n)

    def _allowed(self,fragment,filters):
        src=self.sources[fragment['source_id']];p=self.procedures[fragment['procedure_id']]
        status=src['review_status'];effective=src.get('effective_date');asof=filters.get('effective_date')
        if filters.get('scope'): return False  # no scope metadata: do not silently ignore filter
        if filters.get('jurisdiction') and (p.get('jurisdiction') or '').casefold()!=filters['jurisdiction'].casefold():return False
        if status=='draft' and not self.allow_draft:return False
        if not self.allow_draft and effective is None:return False
        if status=='deprecated' and not asof:return False
        cutoff=asof or date.today().isoformat()
        if effective and effective>cutoff:return False
        if asof and effective is None:return False
        successor=src.get('superseded_by')
        if successor:
            newer=self.sources[successor];new_date=newer.get('effective_date')
            if new_date is None or new_date<=cutoff:return False
        return True

    def exact_matches(self,raw):
        # Conservative explicit correction only; arbitrary negation needs intent modeling.
        text=normalize_text(raw)
        correction=re.fullmatch(r'không phải .+? mà (?:là )?(.+)',text,re.I)
        if correction:text=correction.group(1)
        segmented=self.segmenter.segment(text).casefold()
        hits=[(pid,m.start(),m.end(),name==names[0]) for pid,names in self.names.items() for name in names
              for m in re.finditer(r'(?<!\w)'+re.escape(name)+r'(?!\w)',segmented)]
        return {pid for pid,start,end,canonical in hits if not any(
            (other_start<=start and end<=other_end and (other_start<start or end<other_end))
            or (other_start==start and other_end==end and other_canonical and not canonical)
            for _,other_start,other_end,other_canonical in hits)}

    def requested_sections(self,raw):
        # A term embedded in a procedure title is not a field request by itself.
        text=normalize_text(raw).casefold()
        names={normalize_text(n).casefold() for p in self.procedures.values()
               for n in [p['canonical_name'],*p.get('aliases',[]),*p.get('official_codes',[])] if n.strip()}
        for name in sorted(names,key=lambda n:(-len(n),n)):
            text=re.sub(r'(?<!\w)'+re.escape(name)+r'(?!\w)',' ',text)
        return sections(text)

    def carries_context(self,raw,state):
        if self.exact_matches(raw):return False
        context=resolve_context(raw,state,self.procedures)
        if context['selected']:return True
        if context['invalid']:return False
        return bool(re.match(r'^(còn\b|vậy\b|thế\b|thủ tục đó\b|cái đó\b)',raw.strip().casefold()))

    def _score(self, indices, query, raw):
        scored=[]
        for i in indices:
            d=self.docs[i];length=sum(d.values())
            score=sum(self.idf.get(t,0)*d.get(t,0)*2.5/(d.get(t,0)+1.5*(0.25+0.75*length/max(self.avg_len,1))) for t in query)
            scored.append((score,self.fragments[i]))
        return scored

    def retrieve(self,request, state=None):
        start=time.perf_counter()
        validate('retrieval_input',request)
        # Contract keeps the supplied field, but never permits a different index/query tokenizer.
        expected=self.segmenter.segment(request['query_text_raw'])
        if request['query_text_segmented'] != expected:
            raise ValueError('Query segmentation does not match index configuration')
        raw=request['query_text_raw'];seg=request['query_text_segmented'];q=set(tokens(seg))
        requested=self.requested_sections(raw)
        context=resolve_context(raw,state,self.procedures)
        if context['carry'] and not requested:
            requested=list((state or {}).get('last_requested_section_types') or [])
        matches=self.exact_matches(raw)
        # Only short explicit follow-up references may use prior identity.
        follow=bool(re.match(r'^(còn\b|vậy\b|thế\b|thủ tục đó\b|cái đó\b)',raw.strip().casefold()))
        prior=(state or {}).get('last_resolved_procedure_id')
        restricted=matches or ({context['selected']} if context['selected'] else ({prior} if follow and prior in self.procedures and not context['invalid'] else set()))
        indices=[]
        for i,f in enumerate(self.fragments):
            if context['invalid'] and not matches: continue
            if not self._allowed(f,request.get('filters',{})):continue
            if restricted and f['procedure_id'] not in restricted:continue
            if requested and f['section_type'] not in requested:continue
            indices.append(i)
        scored=[(score,f) for score,f in self._score(indices,q,raw) if score>0 or restricted]
        scored.sort(key=lambda x:(-x[0],x[1]['fragment_id']))
        proc_scores={}
        for score,f in scored:proc_scores.setdefault(f['procedure_id'],score)
        ranked=sorted(proc_scores.items(),key=lambda x:(-x[1],x[0]))
        top=ranked[0][1] if ranked else None;second=ranked[1][1] if len(ranked)>1 else None
        gap=top-second if second is not None else None
        status='low_confidence';selected=None;ambiguous=[];evidence=[]
        if ranked:
            if len(matches)>1:
                status='ambiguous' if len(ranked)>1 else 'resolved'
            elif len(matches)==1 or (restricted and len(ranked)==1):status='resolved'
            elif top>=self.score_floor:
                status='ambiguous' if gap is not None and gap<self.margin_floor else 'resolved'
        if status=='ambiguous':
            ambiguous=[{'procedure_id':pid,'canonical_name':self.procedures[pid]['canonical_name'],'score':score} for pid,score in ranked if len(matches)>1 or top-score<self.margin_floor]
        if status=='ambiguous' and len({self.procedures[p]['canonical_name'].casefold() for p,_ in ranked})<2:
            status='low_confidence';ambiguous=[]
        if status=='resolved':
            selected=ranked[0][0]
            candidates=[(s,f) for s,f in scored if f['procedure_id']==selected]
            # Round-robin requested fields before filling remaining top_k slots.
            chosen=[]
            for section in requested:
                hit=next((pair for pair in candidates if pair[1]['section_type']==section),None)
                if hit:chosen.append(hit)
            used={f['fragment_id'] for _,f in chosen}
            chosen.extend(pair for pair in candidates if pair[1]['fragment_id'] not in used)
            for score,f in chosen[:request.get('top_k',5)]:
                src=self.sources[f['source_id']]
                evidence.append({'fragment_id':f['fragment_id'],'procedure_id':selected,'section_type':f['section_type'],
                    'text':f['text'],'score':score,'method':'exact_match' if matches else self.evidence_method,
                    'source_id':f['source_id'],'source_version':src['version'],'effective_date':src.get('effective_date'),'source_locator':f['source_locator']})
        bundle={'bundle_id':str(uuid4()),'query_text_segmented':seg,'resolved_procedure_id':selected,
            'top_score':top,'second_score':second,'margin':gap,'confidence_status':status,
            'ambiguous_candidates':ambiguous,'evidence':evidence,'fusion_method':self.fusion_method,
            'created_at':datetime.now(timezone.utc).isoformat()}
        validate('evidence_bundle',bundle)
        log.info('snapshot=%s method=%s top=%s second=%s margin=%s status=%s elapsed_ms=%.3f evidence_count=%s',self.fingerprint,self.fusion_method,top,second,gap,status,(time.perf_counter()-start)*1000,len(evidence))
        return bundle


ORDINALS={'đầu tiên':0,'đầu':0,'nhất':0,'một':0,'hai':1,'ba':2,'bốn':3,'năm':4}
CHOICE=re.compile(r'^(?:(?:không|nhầm|sửa lại)[, :;.!-]*\s*)?(?:tôi\s+)?(?:chọn\s+)?(?:cái|thủ tục|mục|số|phương án)\s+(?:thứ\s+)?(đầu tiên|đầu|nhất|một|hai|ba|bốn|năm|[0-9]+)(?:\s*(?:nhé|ạ|đi))?[.!?]*$',re.I)

def resolve_context(raw,state,procedures):
    """Proposed v1 semantics: only a whole-turn ordinal can select an ordered candidate.

    State is read-only. An explicit new named procedure always wins in retrieve().
    Invalid/out-of-range/stale choices abstain, never fall back to the old procedure.
    """
    state=state or {};match=CHOICE.fullmatch(normalize_text(raw))
    result={'selected':None,'invalid':False,'carry':False}
    if not match:return result
    result['carry']=True
    refs=state.get('unresolved_references') or []
    token=match.group(1).casefold()
    index=int(token)-1 if token.isdigit() else ORDINALS[token]
    if len(refs)!=len(set(refs)) or not 0<=index<len(refs) or refs[index] not in procedures:
        result['invalid']=True
    else:result['selected']=refs[index]
    return result
