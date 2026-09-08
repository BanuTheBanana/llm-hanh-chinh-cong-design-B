from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Sequence

from app.schemas import (
    GroundedDataClassification,
    GroundedStatus,
    GroundingEvidenceFragment,
)


@dataclass(frozen=True, slots=True)
class GroundedGenerationResult:
    answer: str
    status: GroundedStatus
    cited_fragment_ids: tuple[str, ...]
    missing_information: tuple[str, ...]
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class GroundedProvider(ABC):
    """G2 provider boundary. Implementations never receive browser-controlled sources."""

    name: str
    model_name: str
    external_calls_enabled: bool = False
    allowed_data_classifications: frozenset[GroundedDataClassification] = frozenset()

    @abstractmethod
    async def generate_grounded(
        self,
        *,
        query: str,
        evidence: Sequence[GroundingEvidenceFragment],
        as_of: date | None,
        data_classification: GroundedDataClassification,
        max_output_tokens: int,
    ) -> GroundedGenerationResult:
        raise NotImplementedError
