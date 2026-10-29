import asyncio
from decimal import Decimal
from types import SimpleNamespace as NS
import pytest
import tiktoken
from src.gateway import UnifiedLLMGateway
from src.schemas import StreamChunk
from src.errors import InvalidRequestError, IncompleteStreamError
from src.pricing import calculate_cost
from src.normalization import Usage, anthropic_event
from tests.conftest import FakeClient,open_event,open_usage,anthro_events


def open_events(input=100,output=5):
    return [open_event(""),open_event("Hello"),open_event(" world"),open_event(finish="stop"),open_event(usage=open_usage(input,output))]

@pytest.mark.parametrize("provider,model",[("openai","gpt-4o-mini"),("anthropic","claude-haiku-4-5-20251001")])
async def test_unified_stream_protocol(settings,provider,model):
    client=FakeClient(open_events() if provider=="openai" else anthro_events(),provider)
    gateway=UnifiedLLMGateway(settings,clients={provider:client})
    try:
        chunks=[c async for c in gateway.stream("Say hello",model)]
        assert all(isinstance(c,StreamChunk) for c in chunks)
        assert "".join(c.delta_text for c in chunks)=="Hello world"
        assert sum(c.is_final for c in chunks)==1 and chunks[-1].is_final
        t=chunks[-1].telemetry
        assert (t.input_tokens,t.output_tokens,t.total_tokens)==(100,5,105)
        assert t.usage_source=="provider_final"
        assert t.total_cost_usd>0 and t.ttft_ms>0 and t.tokens_per_second>0
        assert client.streams[0].closed
        if provider=="openai":
            assert client.calls[0]["stream_options"]=={"include_usage":True}
    finally:
        await gateway.aclose()


async def test_50_word_prompt_local_token_count_and_provider_overhead(settings):
    words=["infrastructure","asynchronous","normalization","telemetry","configuration"]*10
    prompt=" ".join(words)
    assert len(prompt.split())==50
    expected=len(tiktoken.get_encoding("o200k_base").encode(prompt))
    client=FakeClient(open_events(input=expected+7),"openai")
    gateway=UnifiedLLMGateway(settings,clients={"openai":client})
    chunks=[c async for c in gateway.stream(prompt,"gpt-4o-mini")]
    final=chunks[-1].telemetry
    assert final.local_prompt_tokens==expected
    # Provider prompt usage includes chat-message framing; raw text tokens do not.
    request_estimate=expected+7
    assert chunks[0].telemetry.input_tokens==request_estimate
    assert abs(final.input_tokens-request_estimate)/request_estimate<=.10
    await gateway.aclose()


async def test_ttft_only_on_first_nonempty_text(settings):
    client=FakeClient(open_events(),"openai")
    gateway=UnifiedLLMGateway(settings,clients={"openai":client})
    chunks=[c async for c in gateway.stream("hello","gpt-4o-mini")]
    assert chunks[0].telemetry.ttft_ms is None
    assert chunks[1].delta_text=="" and chunks[1].telemetry.ttft_ms is None
    first=next(c for c in chunks if c.delta_text)
    assert first.telemetry.ttft_ms>0
    assert chunks[-1].telemetry.ttft_ms==first.telemetry.ttft_ms
    await gateway.aclose()


async def test_anthropic_cumulative_counts_not_summed(settings):
    events=anthro_events(output=3)
    events.insert(-1,NS(type="message_delta",delta=NS(stop_reason="end_turn"),usage=NS(output_tokens=5)))
    client=FakeClient(events,"anthropic")
    gateway=UnifiedLLMGateway(settings,clients={"anthropic":client})
    chunks=[c async for c in gateway.stream("hello","claude-haiku-4-5-20251001")]
    assert chunks[-1].telemetry.output_tokens==5
    await gateway.aclose()


async def test_no_usage_metadata_is_labeled_estimate(settings):
    client=FakeClient(open_events()[:-1],"openai")
    gateway=UnifiedLLMGateway(settings,clients={"openai":client})
    chunks=[c async for c in gateway.stream("hello","gpt-4o-mini")]
    assert chunks[-1].is_final
    assert chunks[-1].telemetry.usage_source=="estimate_missing_final_usage"
    assert "estimates" in chunks[-1].telemetry.warning
    await gateway.aclose()


async def test_unfinished_stream_is_not_success(settings):
    client=FakeClient([open_event("partial")],"openai")
    gateway=UnifiedLLMGateway(settings,clients={"openai":client})
    with pytest.raises(IncompleteStreamError):
        _=[c async for c in gateway.stream("hello","gpt-4o-mini")]
    assert client.streams[0].closed
    await gateway.aclose()


async def test_persistent_client_reused_across_calls(settings):
    client=FakeClient(open_events(),"openai")
    gateway=UnifiedLLMGateway(settings,clients={"openai":client})
    for _ in range(2):
        _=[c async for c in gateway.stream("hello","gpt-4o-mini")]
    assert len(client.calls)==2 and gateway._clients["openai"] is client
    assert not client.closed
    await gateway.aclose()
    assert client.closed


async def test_concurrent_requests_keep_independent_metrics(settings):
    client=FakeClient(open_events(),"openai")
    gateway=UnifiedLLMGateway(settings,clients={"openai":client})
    async def run(prompt):
        return [c async for c in gateway.stream(prompt,"gpt-4o-mini")]
    a,b=await asyncio.gather(run("short"),run("a much longer prompt "*20))
    assert a[-1].telemetry.local_prompt_tokens < b[-1].telemetry.local_prompt_tokens
    assert "".join(c.delta_text for c in a)=="Hello world"
    assert "".join(c.delta_text for c in b)=="Hello world"
    await gateway.aclose()


async def test_event_loop_remains_responsive(settings):
    client=FakeClient(open_events(),"openai")
    gateway=UnifiedLLMGateway(settings,clients={"openai":client})
    ticks=0
    finished=False
    async def heartbeat():
        nonlocal ticks
        while not finished:
            ticks+=1
            await asyncio.sleep(.001)
    task=asyncio.create_task(heartbeat())
    try:
        _=[c async for c in gateway.stream("hello","gpt-4o-mini")]
    finally:
        finished=True
        await task
        await gateway.aclose()
    assert ticks>=5


async def test_early_consumer_close_closes_upstream(settings):
    client=FakeClient(open_events(),"openai")
    gateway=UnifiedLLMGateway(settings,clients={"openai":client})
    stream=gateway.stream("hello","gpt-4o-mini")
    await anext(stream)  # initial telemetry
    await anext(stream)  # upstream opened, empty role delta
    await stream.aclose()
    assert client.streams[0].closed
    await gateway.aclose()


@pytest.mark.parametrize("kwargs",[{"prompt":""},{"prompt":"a"*20001},{"model":"unsupported"},{"temperature":2},{"temperature":True},{"max_tokens":0},{"max_tokens":True}])
async def test_request_boundaries(settings,kwargs):
    gateway=UnifiedLLMGateway(settings,demo=True)
    request={"prompt":"hello","model":"gpt-4o-mini"}
    request.update(kwargs)
    with pytest.raises(InvalidRequestError):
        _=[c async for c in gateway.stream(**request)]
    await gateway.aclose()


def test_decimal_cost_and_cache_discount():
    assert calculate_cost("gpt-4o-mini",1000,500)==Decimal("0.00045")
    assert calculate_cost("gpt-4o-mini",1000,500,cached_read=200)==Decimal("0.000435")
    assert calculate_cost("claude-haiku-4-5-20251001",1000,500,cached_read=200,cache_write_5m=100,cache_write_1h=100)==Decimal("0.003445")

@pytest.mark.parametrize("counts",[(-1,0),(1,True),(1,1,2)])
def test_invalid_cost_counts(counts):
    with pytest.raises(ValueError):
        calculate_cost("gpt-4o-mini",*counts)


def test_anthropic_cache_input_categories_normalized():
    raw=NS(type="message_start",message=NS(usage=NS(input_tokens=100,output_tokens=0,
        cache_read_input_tokens=20,cache_creation_input_tokens=30,
        cache_creation=NS(ephemeral_1h_input_tokens=10,ephemeral_5m_input_tokens=20))))
    usage=anthropic_event(raw,Usage()).usage
    assert (usage.input,usage.cached_read,usage.write_5m,usage.write_1h)==(150,20,20,10)


async def test_truncation_warning(settings):
    client=FakeClient([open_event("Hi"),open_event(finish="length"),open_event(usage=open_usage())],"openai")
    gateway=UnifiedLLMGateway(settings,clients={"openai":client})
    chunks=[c async for c in gateway.stream("hello","gpt-4o-mini")]
    assert "truncated" in chunks[-1].telemetry.warning
    await gateway.aclose()


async def test_cancelled_task_closes_upstream(settings):
    client=FakeClient(open_events(),"openai")
    gateway=UnifiedLLMGateway(settings,clients={"openai":client})
    opened=asyncio.Event()
    async def consume():
        from contextlib import aclosing
        async with aclosing(gateway.stream("hello","gpt-4o-mini")) as stream:
            async for c in stream:
                if c.delta_text:
                    opened.set()
                    await asyncio.sleep(10)
    task=asyncio.create_task(consume())
    await asyncio.wait_for(opened.wait(),timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert client.streams[0].closed
    await gateway.aclose()


async def test_sdk_constructor_is_lazy_and_reused(settings,monkeypatch):
    import openai
    client=FakeClient(open_events(),"openai")
    creations=[]
    def constructor(**kwargs):
        creations.append(kwargs)
        return client
    monkeypatch.setattr(openai,"AsyncOpenAI",constructor)
    gateway=UnifiedLLMGateway(settings)
    for _ in range(2):
        _=[c async for c in gateway.stream("hello","gpt-4o-mini")]
    assert len(creations)==1
    assert creations[0]["base_url"]=="https://api.openai.com/v1"
    assert creations[0]["max_retries"]==0
    await gateway.aclose()
