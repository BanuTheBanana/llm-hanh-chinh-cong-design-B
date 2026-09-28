from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.schemas import GroundedDataClassification, IntentContextModelOutput, IntentContextRequest


@dataclass(frozen=True, slots=True)
class IntentContextGenerationResult:
    output: IntentContextModelOutput
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    policy_actions: tuple[str, ...] = ()


class IntentContextProvider(ABC):
    name: str
    model_name: str
    external_calls_enabled: bool
    allowed_data_classifications: frozenset[GroundedDataClassification]

    @abstractmethod
    async def analyze(self, payload: IntentContextRequest) -> IntentContextGenerationResult:
        raise NotImplementedError
