import io
import logging
import traceback
from types import SimpleNamespace as NS
import httpx
import openai
import pytest
from src.security import Settings,SecretFilter,redact
from src.gateway import UnifiedLLMGateway
from src.errors import AuthenticationError,RateLimitExceededError,GatewayConnectionError,GatewayProviderError
from tests.conftest import FakeClient,open_event

@pytest.mark.parametrize("provider,model",[("openai","gpt-4o-mini"),("anthropic","claude-haiku-4-5-20251001")])
@pytest.mark.parametrize("key",[None,"","your_api_key_here","sk-short","sk-foo bar"])
async def test_missing_or_malformed_keys(provider,model,key):
    settings=Settings(**{provider+"_api_key":key})
    gateway=UnifiedLLMGateway(settings)
    with pytest.raises(AuthenticationError,match=provider):
        _=[c async for c in gateway.stream("hello",model)]
    await gateway.aclose()


def test_settings_repr_and_serialization_hide_keys(settings):
    secret=settings.openai_api_key.get_secret_value()
    assert secret not in repr(settings)
    assert secret not in settings.model_dump_json()
    assert settings.model_dump()=={}


def test_secret_redaction_in_logger():
    key="sk-"+"sensitive"*5
    out=io.StringIO()
    handler=logging.StreamHandler(out)
    handler.addFilter(SecretFilter())
    logger=logging.getLogger("security-test")
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    try:
        logger.warning("Provider said key %s is invalid",key)
        assert key not in out.getvalue() and "sensitive" not in out.getvalue()
        assert "[REDACTED]" in out.getvalue()
    finally:
        logger.removeHandler(handler)


@pytest.mark.parametrize("status,expected",[(401,AuthenticationError),(429,RateLimitExceededError),(400,GatewayProviderError),(500,GatewayProviderError)])
async def test_sdk_errors_are_typed_and_redacted(settings,status,expected,caplog):
    key=settings.openai_api_key.get_secret_value()
    async def handler(request):
        return httpx.Response(status,json={"error":{"message":f"Rejected credential {key}","type":"test_error","code":"test_code"}})
    client=openai.AsyncOpenAI(api_key=key,max_retries=0,http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    gateway=UnifiedLLMGateway(settings,clients={"openai":client})
    try:
        with pytest.raises(expected) as err:
            _=[c async for c in gateway.stream("hello","gpt-4o-mini")]
        formatted="".join(traceback.format_exception(err.value))
        assert key not in str(err.value) and key not in repr(err.value)
        assert key not in formatted and key not in caplog.text
    finally:
        await gateway.aclose()


async def test_connection_error_is_typed(settings):
    client=FakeClient([openai.APIConnectionError(request=httpx.Request("POST","https://api.openai.com/v1/chat/completions"))],"openai")
    gateway=UnifiedLLMGateway(settings,clients={"openai":client})
    with pytest.raises(GatewayConnectionError):
        _=[c async for c in gateway.stream("hello","gpt-4o-mini")]
    await gateway.aclose()


def test_redact_both_key_families():
    assert redact("sk-ant-abc123 sk-proj-def456")=="[REDACTED] [REDACTED]"


async def test_unexpected_provider_exception_does_not_expose_detail(settings):
    key=settings.openai_api_key.get_secret_value()
    client=FakeClient([ValueError("internal secret="+key)],"openai")
    gateway=UnifiedLLMGateway(settings,clients={"openai":client})
    with pytest.raises(GatewayProviderError) as err:
        _=[c async for c in gateway.stream("hello","gpt-4o-mini")]
    assert key not in str(err.value)
    await gateway.aclose()
