"""Local dense fragment + procedure retrieval and reciprocal-rank fusion.

No model downloads or external inference. Encoder is injected for deterministic tests.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
from .retriever import LexicalRetriever
from .segmenter import normalize_text


class LocalSentenceEncoder:
    def __init__(self, path, *, query_prefix='', document_prefix='', device='cpu', batch_size=1):
        path=Path(path).resolve()
        if not path.is_dir(): raise ValueError('A local embedding model directory is required')
        if not isinstance(batch_size,int) or batch_size<1: raise ValueError('batch_size must be a positive integer')
        from sentence_transformers import SentenceTransformer
        self.model=SentenceTransformer(str(path),local_files_only=True,trust_remote_code=False,device=device)
        self.query_prefix=query_prefix;self.document_prefix=document_prefix;self.device=device;self.batch_size=batch_size
        digest=hashlib.sha256()
        for file in sorted(p for p in path.rglob('*') if p.is_file()):
            digest.update(str(file.relative_to(path)).encode())
            with file.open('rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
        self.model_fingerprint=digest.hexdigest()

    def encode(self,texts,*,query=False):
        prefix=self.query_prefix if query else self.document_prefix
        return self.model.encode([prefix+normalize_text(t) for t in texts],batch_size=self.batch_size,
            normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False)

    def metadata(self):
        return {'kind':'local_sentence_transformer','model_fingerprint':self.model_fingerprint,
            'query_prefix':self.query_prefix,'document_prefix':self.document_prefix,
            'device':self.device,'batch_size':self.batch_size}


def unit_rows(values,rows):
    array=np.asarray(values,dtype=np.float32)
    if array.ndim!=2 or array.shape[0]!=rows or not array.shape[1] or not np.isfinite(array).all():
        raise ValueError('Invalid embedding shape or non-finite values')
    lengths=np.linalg.norm(array,axis=1,keepdims=True)
    if (lengths<=0).any(): raise ValueError('Zero embedding vector')
    return array/lengths


class HybridRetriever(LexicalRetriever):
    def __init__(self,corpus,segmenter,fingerprint,*,encoder,mode='hybrid',score_floor,
                 margin_floor,dense_min_similarity,rrf_k=60,allow_draft=False):
        if mode not in {'dense','hybrid'}:raise ValueError('mode must be dense or hybrid')
        if not np.isfinite(dense_min_similarity) or not -1<=dense_min_similarity<=1:
            raise ValueError('dense_min_similarity must be in [-1,1]')
        if not np.isfinite(rrf_k) or rrf_k<1:raise ValueError('rrf_k must be >=1')
        super().__init__(corpus,segmenter,fingerprint,allow_draft=allow_draft,score_floor=score_floor,margin_floor=margin_floor)
        self.encoder=encoder;self.mode=mode;self.dense_min_similarity=dense_min_similarity;self.rrf_k=rrf_k
        self.fusion_method='dense_fragment_procedure_max' if mode=='dense' else f'rrf_lexical_dense_fragment_procedure_k{rrf_k}'
        self.evidence_method='dense' if mode=='dense' else 'fused'
        # Raw NFC text for sentence encoders; BM25 alone uses Vietnamese segmentation.
        texts=[self.procedures[f['procedure_id']]['canonical_name']+'\n'+f['text'] for f in self.fragments]
        self.fragment_vectors=unit_rows(encoder.encode(texts),len(texts))
        self.procedure_ids=list(self.procedures)
        texts=[' '.join([self.procedures[p]['canonical_name'],*self.procedures[p].get('aliases',[]),*self.procedures[p].get('official_codes',[])]) for p in self.procedure_ids]
        self.procedure_vectors=unit_rows(encoder.encode(texts),len(texts))
        if self.fragment_vectors.shape[1]!=self.procedure_vectors.shape[1]:raise ValueError('Embedding dimensions differ')
        self.procedure_positions={p:i for i,p in enumerate(self.procedure_ids)}

    def _score(self,indices,query,raw):
        if not indices:return []
        vector=unit_rows(self.encoder.encode([raw],query=True),1)[0]
        if len(vector)!=self.fragment_vectors.shape[1]:raise ValueError('Query embedding dimension differs')
        frag=self.fragment_vectors[indices]@vector
        ps=self.procedure_vectors@vector
        lexical=super()._score(indices,query,raw)
        if self.mode=='dense':
            scores=[max(float(frag[j]),float(ps[self.procedure_positions[self.fragments[i]['procedure_id']]])) for j,i in enumerate(indices)]
            # Keep zero-score eligible rows so exact IDs/names and state selections can
            # bypass confidence thresholds, but never metadata filters.
            return [(score if score>=self.dense_min_similarity else 0.0,self.fragments[i]) for i,score in zip(indices,scores)]
        scores={i:0.0 for i in indices}
        def add_ranking(items):
            # Equal scores receive equal ranks; ID breaks order only, not confidence.
            items=sorted(items,key=lambda pair:(-pair[1],str(pair[0])))
            last=None;rank=0
            for pos,(key,value) in enumerate(items,1):
                if value!=last:rank=pos;last=value
                yield key,1.0/(self.rrf_k+rank)
        for i,value in add_ranking([(i,pair[0]) for i,pair in zip(indices,lexical) if pair[0]>0]):scores[i]+=value
        for i,value in add_ranking([(i,float(frag[j])) for j,i in enumerate(indices) if frag[j]>=self.dense_min_similarity]):scores[i]+=value
        eligible={self.fragments[i]['procedure_id'] for i in indices}
        proc_ranks=dict(add_ranking([(p,float(ps[self.procedure_positions[p]])) for p in eligible if ps[self.procedure_positions[p]]>=self.dense_min_similarity]))
        for i in indices:scores[i]+=proc_ranks.get(self.fragments[i]['procedure_id'],0)
        return [(scores[i],self.fragments[i]) for i in indices]

    def save_index(self,directory):
        """Export numeric arrays without pickle; CLI rebuilds from verified corpus."""
        path=Path(directory);path.mkdir(parents=True,exist_ok=True)
        metadata={'corpus_fingerprint':self.fingerprint,'segmenter':self.segmenter.metadata(),
                  'encoder':self.encoder.metadata(),'fragment_ids':[f['fragment_id'] for f in self.fragments],
                  'procedure_ids':self.procedure_ids,'fusion_method':self.fusion_method}
        np.savez_compressed(path/'dense.npz',fragments=self.fragment_vectors,procedures=self.procedure_vectors)
        metadata['vectors_sha256']=hashlib.sha256((path/'dense.npz').read_bytes()).hexdigest()
        (path/'index.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
