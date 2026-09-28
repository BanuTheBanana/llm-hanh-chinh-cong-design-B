from app.grounding import validate_grounded_result
from app.providers.base import ProviderPolicyError, ProviderResponseError
from app.providers.grounded_base import GroundedGenerationResult, GroundedProvider
from app.schemas import GroundedGenerateRequest


async def run_grounded_generation(
    *, payload: GroundedGenerateRequest, provider: GroundedProvider
) -> GroundedGenerationResult:
    """Run G2 generation with a no-evidence short circuit and citation validation."""

    if payload.evidence:
        try:
            allowed_classifications = provider.allowed_data_classifications
            provider_name = provider.name
            model_name = provider.model_name
        except (AttributeError, TypeError) as exc:
            raise ProviderResponseError("grounded provider capability metadata is invalid") from exc
        if payload.data_classification not in allowed_classifications:
            raise ProviderPolicyError

        result = await provider.generate_grounded(
            query=payload.query,
            evidence=payload.evidence,
            as_of=payload.as_of,
            data_classification=payload.data_classification,
            max_output_tokens=payload.max_output_tokens,
        )
    else:
        # Defense-in-depth: never pay or ask a model to answer without evidence.
        result = GroundedGenerationResult(
            answer="Tôi chưa có đủ nguồn đã được kiểm chứng để trả lời câu hỏi này.",
            status="INSUFFICIENT_DATA",
            cited_fragment_ids=(),
            missing_information=(),
            provider="guardrail",
            model="no-evidence-v1",
        )
        provider_name = "guardrail"
        model_name = "no-evidence-v1"

    return validate_grounded_result(
        result=result,
        allowed_fragment_ids={fragment.fragment_id for fragment in payload.evidence},
        provider_name=provider_name,
        model_name=model_name,
    )
