from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

ProviderName = Literal["openai", "anthropic"]

class ChunkTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    local_prompt_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    cache_write_5m_tokens: int = Field(default=0, ge=0)
    cache_write_1h_tokens: int = Field(default=0, ge=0)
    ttft_ms: float | None = Field(default=None, ge=0)
    latency_seconds: float = Field(ge=0)
    tokens_per_second: float = Field(ge=0)
    total_cost_usd: Decimal = Field(ge=0)
    usage_source: Literal["local_estimate", "provider_partial", "provider_final", "estimate_missing_final_usage"]
    pricing_date: str
    finish_reason: str | None = None
    warning: str | None = None

class StreamChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delta_text: str = ""
    provider: ProviderName
    model: str
    is_final: bool = False
    mode: Literal["live", "offline_fixture"] = "live"
    telemetry: ChunkTelemetry
