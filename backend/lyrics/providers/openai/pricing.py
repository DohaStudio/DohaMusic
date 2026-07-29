"""Token cost estimation using explicitly configured pricing snapshots."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CostEstimate:
    amount: float | None
    currency: str
    pricing_version: str | None


def estimate_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    input_cost_per_million: float | None,
    output_cost_per_million: float | None,
    pricing_version: str,
) -> CostEstimate:
    if input_cost_per_million is None or output_cost_per_million is None:
        return CostEstimate(None, "USD", pricing_version or None)
    amount = (
        input_tokens * input_cost_per_million + output_tokens * output_cost_per_million
    ) / 1_000_000
    return CostEstimate(round(amount, 8), "USD", pricing_version or None)
