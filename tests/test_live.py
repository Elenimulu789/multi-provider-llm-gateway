"""Explicitly opt-in BILLABLE verification; skipped by default."""
import os
import pytest
from dotenv import load_dotenv
from src.security import Settings
from src.gateway import UnifiedLLMGateway

load_dotenv()
pytestmark=[pytest.mark.live,pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS")!="1",reason="Live API tests require explicit RUN_LIVE_TESTS=1 and incur charges")]

@pytest.mark.parametrize("model",["gpt-4o-mini","claude-haiku-4-5-20251001"])
async def test_live_provider(model):
    settings=Settings(openai_api_key=os.getenv("OPENAI_API_KEY"),anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"))
    gateway=UnifiedLLMGateway(settings)
    try:
        chunks=[c async for c in gateway.stream("Reply with one short greeting.",model,max_tokens=64)]
        assert any(c.delta_text for c in chunks)
        assert chunks[-1].is_final and chunks[-1].mode=="live"
        assert chunks[-1].telemetry.usage_source=="provider_final"
    finally:
        await gateway.aclose()
