"""Project-owner catalog adjudications that preserve immutable source rows."""

PREFERRED_PROCEDURES = {
    # Workbook row 26 is a heading-only duplicate; row 28 is canonical.
    "d2_title_70d8a7c53c19": "d2_title_c98b4aa39036",
    # Workbook row 17 is the more complete cremation-support record.
    "d2_title_1df9a1a807f0": "d2_title_10ed2a9ea4a7",
}
REALTIME_REVIEW_FIELDS = frozenset({"processing_times", "receiving_authority"})
REALTIME_REVIEW_PROCEDURES = frozenset(
    {
        "d2_title_c98b4aa39036",  # Construction permit: preferred workbook row 28.
        "d2_title_7677bda9d6bd",  # Worship allowance: conflicting source rows.
        "d2_title_f29de859e25e",  # Survivor benefits: branch-dependent timing.
        "d2_title_85fb93f4cc41",  # Social retirement allowance.
    }
)


def preferred_procedure_id(procedure_id: str | None) -> str | None:
    """Map a retained source record to its serving-time canonical procedure."""

    return PREFERRED_PROCEDURES.get(procedure_id, procedure_id)


def is_serving_candidate(procedure_id: str) -> bool:
    """Keep shadow records auditable while excluding them from routing choices."""

    return procedure_id not in PREFERRED_PROCEDURES


def needs_realtime_offer(procedure_id: str | None, fields: set[str]) -> bool:
    """Flag source-sensitive time/place answers for an explicit future MCP check."""

    return bool(
        preferred_procedure_id(procedure_id) in REALTIME_REVIEW_PROCEDURES
        and fields & REALTIME_REVIEW_FIELDS
    )
