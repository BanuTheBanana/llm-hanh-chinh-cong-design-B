# Person 3 — Generation & Evaluation

Clean track; no old intent/context prompts, adapters, training scripts, or acceptance fixtures are copied here.

## Generation
- quantized local LLM runtime
- EvidenceBundle -> GroundedAnswer client
- prompt contract
- citation output format
- latency/resource measurement

## Evaluation
- benchmark/regression harness
- procedure-level and field-level retrieval accuracy
- coverage, groundedness, citation binding
- abstention/ambiguity metrics
- threshold tuning from Person 1 logs
- failure taxonomy
- end-to-end acceptance report

Use mock EvidenceBundle objects to work in parallel. Do not fine-tune by default; establish the baseline first.
