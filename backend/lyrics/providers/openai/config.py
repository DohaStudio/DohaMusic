"""Validated settings passed only to the OpenAI lyrics adapter."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class OpenAILyricsConfig:
    api_key: str = field(repr=False)
    model: str
    base_url: str
    timeout_seconds: float
    total_deadline_seconds: float
    max_retries: int
    temperature: float | None
    max_output_tokens: int
    input_cost_per_million: float | None
    output_cost_per_million: float | None
    pricing_version: str
    max_cost_per_request: float | None
