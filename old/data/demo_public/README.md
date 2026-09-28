# D1_PUBLIC_DEMO data

This directory contains a **draft one-procedure public-data spike** for G2. The
snapshot and normalization are present, but every source remains `PENDING` and
the detailed procedure source is still missing. It must not be ingested as an
approved D1 corpus or sent to a hosted provider yet. Do not add content copied
from blogs, search snippets, chat output, or private case files.

## Layout

- `source_manifest.jsonl`: one `SourceManifest` per immutable raw snapshot.
- `raw/<procedure>/<retrieved-date>/`: original HTML/PDF snapshots. Never overwrite.
- `normalized/procedures.jsonl`: normalized `ProcedureRecord` objects.
- `normalized/fragments.jsonl`: retrieval-sized `ProcedureFragment` objects.
- `gold/questions.jsonl`: reviewed `GoldQuestion` records.
- `fixtures/`: canonical bundle, projected AI request and grounded response
  examples for contract v0.2.
- `reports/data-quality.md`: validation output and manual review notes.

## Spike workflow

1. Record the candidate URL, authority, jurisdiction, access date, terms and
   robots result in the review notes before downloading.
2. Use only an approved official domain and HTTPS where the source supports it.
3. Save the original response unchanged, calculate SHA-256, and add a manifest
   record. If automatic access is blocked, stop and use a manual export; do not
   bypass CAPTCHA, login, or anti-bot controls.
4. Normalize only facts visible in the snapshot. Use `null` or `UNKNOWN` when
   the source does not establish a value.
5. Split fragments by business section and link every fragment to its source.
6. Add approximately 10 questions for the spike. Every expected point needs a
   supporting fragment; every question needs a second reviewer.
7. Run technical preflight from the repository root:

```text
python tools/data/validate_dataset.py --root . --mode preflight
```

For a new approved URL, use the downloader so robots and overwrite checks are
enforced before a manifest record is added:

```text
python tools/data/crawl_or_download.py --url https://official.example/source --output data/demo_public/raw/<procedure>/<retrieved-date>/source.html
```

Before publication, run the strict gate. It is expected to fail until human
review and the 2–3 procedure/30–50 question scope are complete:

```text
python tools/data/validate_dataset.py --root . --mode publish
```

## Contract notes

The five contracts are defined in the G2 assignment document. This directory is
`D1_PUBLIC_DEMO`; it must not contain PII. Raw snapshots are immutable and their
`content_sha256` values must match the manifest. A passing preflight means the
draft is technically consistent; it is not legal, policy or source approval.
