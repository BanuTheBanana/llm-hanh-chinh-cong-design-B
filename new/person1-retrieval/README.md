# Person 1 — Corpus & Retrieval

Clean track; no old G3/G4/G5 RAG code is copied here.

Owns corpus validation/snapshots, Vietnamese segmentation, exact-string shortcut, lexical retrieval, dense retrieval, fusion, top-2/margin confidence, ambiguity candidates, provenance-rich EvidenceBundle, and retrieval logs.

Contract:
- input: `../contracts/retrieval_input.schema.json`
- output: `../contracts/evidence_bundle.schema.json`

First deliverables:
1. `segment(text)`
2. corpus/index builder
3. `retrieve(RetrievalInput) -> EvidenceBundle`
4. top-2/margin retrieval logs
5. fixtures for procedure-level and field-level evaluation
