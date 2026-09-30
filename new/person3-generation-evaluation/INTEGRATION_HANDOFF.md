# Person 3 Integration Handoff

Person 3 code is ready to be consumed by the other tracks. This note deliberately does
not modify Person 1 retrieval or Person 2 orchestration.

## Import boundary

Person 2 can construct the real generator with:

```python
from person3_generation_evaluation import GroundedGenerator, LlamaCppHTTPRuntime

runtime = LlamaCppHTTPRuntime(
    base_url="http://127.0.0.1:8080",
    model="local-model",
    temperature=0.0,
    seed=42,
)
generator = GroundedGenerator(runtime)
```

The object satisfies the existing Person 2 generator boundary:

```python
generator.generate(evidence_bundle)
# -> {"answer_text": str, "citations": [...]}
```

Person 2 remains responsible for deciding when generation is allowed, building the final
GroundedAnswer, persistence/audit, clarification/abstention, and API transport.

## Runtime ownership on the deployment machine

The machine running the integrated system must provide its own runtime dependencies:

- Docker Desktop/Engine when using the repository Compose setup;
- PostgreSQL, normally through the Compose postgres container, or a separately installed
  PostgreSQL instance if the team intentionally chooses native deployment;
- the Person 1/Person 2 Python dependencies;
- a local OpenAI-compatible model server and the selected quantized model for Person 3;
- Node.js only when running the benchmark frontend in development mode.

No model weights, database volume, credentials, private corpus exports, or real `.env`
files are part of the Person 3 source handoff.

## Frontend

`benchmark-frontend/` is a standalone client. In development it uses Vite proxying and
reads:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

If the backend is on another machine, use that backend machine's reachable address instead
of localhost. The frontend does not run PostgreSQL, Docker, retrieval, or the LLM.

The UI handles all three GroundedAnswer states and, for `insufficient_data`, displays
the backend-provided `clarification_prompt` first with a safe fallback.

## Acceptance that still requires execution

These cannot be honestly marked complete from source code alone:

1. select candidate quantized model/runtime after benchmark;
2. run real generation benchmark and semantic-groundedness review;
3. tune retrieval confidence thresholds from Person 1 DEV logs;
4. run locked TEST after choices are frozen;
5. run integrated Person 1 -> Person 2 -> Person 3 E2E with PostgreSQL/model runtime;
6. record hardware, latency, corpus fingerprint, retrieval configuration, model
   configuration, and failure report.

Those are integration/evaluation gates, not missing Person 3 source modules.
