"""Versioned standard text rates. Decimal values are USD per 1M tokens.

Verified 2026-10-28 against official model/pricing pages linked in README.
No batch, tools, extended thinking, long-context premium or priority tier is used.
"""
from dataclasses import dataclass
from decimal import Decimal

PRICING_DATE = "2026-10-28"
MILLION = Decimal(1000000)

@dataclass(frozen=True)
class Price:
    provider: str
    input: Decimal
    output: Decimal
    cached_read: Decimal
    write_5m: Decimal = Decimal(0)
    write_1h: Decimal = Decimal(0)

PRICES = {
    "gpt-4o-mini": Price("openai", Decimal("0.15"), Decimal("0.60"), Decimal("0.075")),
    "gpt-4o": Price("openai", Decimal("2.50"), Decimal("10.00"), Decimal("1.25")),
    "claude-haiku-4-5-20251001": Price("anthropic", Decimal("1"), Decimal("5"), Decimal("0.10"), Decimal("1.25"), Decimal("2")),
    "claude-sonnet-4-5-20250929": Price("anthropic", Decimal("3"), Decimal("15"), Decimal("0.30"), Decimal("3.75"), Decimal("6")),
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int,
                   cached_read: int = 0, cache_write_5m: int = 0, cache_write_1h: int = 0) -> Decimal:
    """input_tokens includes all input classes for BOTH providers.

    OpenAI already includes cached tokens in prompt_tokens. Anthropic's usage
    splits uncached reads/writes: the normalizer converts it to this total.
    """
    counts = [input_tokens, output_tokens, cached_read, cache_write_5m, cache_write_1h]
    if any(type(n) is not int or n < 0 for n in counts):
        raise ValueError("Token counts must be nonnegative integers")
    ordinary = input_tokens - cached_read - cache_write_5m - cache_write_1h
    if ordinary < 0:
        raise ValueError("Cache classes cannot exceed total input tokens")
    rate = PRICES[model]
    return (ordinary * rate.input + output_tokens * rate.output + cached_read * rate.cached_read
            + cache_write_5m * rate.write_5m + cache_write_1h * rate.write_1h) / MILLION
