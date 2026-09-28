# New architecture workspace

This directory implements the proposed 3-person architecture without silently rebuilding the previous G6 core.

## Reused infrastructure
- `web/`: current frontend reused only as a UI shell.
- generic FastAPI/PostgreSQL/Alembic/Docker patterns.

## Deliberately NOT copied from old core
- Topic Gate and KEEP/SWITCH/CLARIFY/DEFER policy
- intent/context patch + reducer
- G3/G4/G5 retrieval implementations
- direct/guarded evidence routing policy
- AnswerPlan implementation
- old grounding/verifier implementation
- source-MCP runtime implementation
- old training/fine-tuning code
- old evaluation fixtures as the new acceptance benchmark

## Ownership
- `person1-retrieval/`: Corpus & Retrieval
- `person2-backend/`: Backend & Grounding
- `person3-generation-evaluation/`: Generation & Evaluation
- `contracts/`: shared JSON Schema contracts

Track code should depend on contracts, not another track's internals.
