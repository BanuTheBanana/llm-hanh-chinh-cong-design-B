# G2 contract fixtures

These fixtures implement grounded contract `g2-grounded-v0.2` using the draft
spike IDs:

- `evidence_bundle.json` is the canonical Backend bundle and retains URL, score
  and audit metadata;
- `grounding_request.json` is the allowlisted projection sent to AI Service and
  therefore contains no URL, score, arbitrary metadata or chat history;
- `grounded_answer.json` binds the response to request ID, bundle ID, corpus
  version and data classification. Its citations are a subset of the bundle.

The source is still `PENDING` cross-review. These are shape examples only, not
proof that a hosted provider ran and not a production response.
