"""Read-only G3 D2 corpus activation and projection into the grounded contract."""

from datetime import date
from functools import lru_cache
from pathlib import Path
from uuid import UUID, uuid5

from app.rag.g3.retrieval import retrieve
from app.rag.g3.validator import Dataset, load_serving
from app.rag.schemas import Evidence, EvidenceBundle, RetrievalInput


@lru_cache(maxsize=4)
def load_active_dataset(
    path: str, version: str, expected_rows: int, expected_sha256: str
) -> Dataset:
    data = load_serving(Path(path), version, expected_rows)
    if data.fingerprint != expected_sha256:
        raise ValueError("G3_CORPUS_HASH_MISMATCH")
    if data.report()["readiness"] != "READY_FOR_DEMO":
        raise ValueError("G3_DATASET_NOT_READY")
    # Gold/evaluation files are never opened. Conflict records have been validated;
    # retrieval retains only the three corpus groups.
    return Dataset(
        version=data.version,
        groups=[data.sources, data.procedures, data.fragments, {}, {}],
        fingerprint=data.fingerprint,
        accepted=data.accepted,
        rejected=data.rejected,
        row_count=data.row_count,
    )


def _jurisdiction_label(value: dict) -> str | None:
    parts = [value.get("ward"), value.get("district"), value.get("province")]
    selected = [item for item in parts if item]
    return ", ".join(selected) if selected else None


def retrieve_active_dataset(
    data: Dataset,
    query: RetrievalInput,
    request_id: UUID,
) -> tuple[EvidenceBundle, str, list[str]]:
    found = retrieve(
        data,
        query.query,
        query.top_k,
        procedure_id=query.filters.procedure_id,
        as_of=query.filters.as_of.isoformat() if query.filters.as_of else None,
        jurisdiction=query.filters.jurisdiction,
        field_intents=query.field_intents,
    )
    evidence = []
    for item in found["evidence"]:
        source = data.sources[item["source_id"]]
        procedure = data.procedures[item["procedure_id"]]
        evidence.append(
            Evidence(
                fragment_id=item["fragment_id"],
                source_id=item["source_id"],
                procedure_id=item["procedure_id"],
                section_type=item["section_type"],
                title=item["title"],
                url=item["url"],
                text=item["text"],
                score=item["score"],
                jurisdiction=_jurisdiction_label(procedure["jurisdiction"]),
                effective_from=(
                    date.fromisoformat(source["effective_from"])
                    if source["effective_from"]
                    else None
                ),
                effective_to=(
                    date.fromisoformat(source["effective_to"]) if source["effective_to"] else None
                ),
                validity_status=source["validity_status"],
                metadata={"source_type": source["source_type"]},
            )
        )
    bundle = EvidenceBundle(
        request_id=request_id,
        evidence_bundle_id=uuid5(request_id, "g3-grounded-evidence-bundle"),
        corpus_version=data.version,
        data_classification="D2_COMPANY_REAL",
        query=query.query,
        evidence=evidence,
        as_of=query.filters.as_of,
    )
    return bundle, found["status"], found["missing_fields"]
