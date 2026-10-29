"""Real official SDKs + HTTPX MockTransport: protocol integration, no billable calls."""
import json
import httpx
import openai
import anthropic
import pytest
from src.gateway import UnifiedLLMGateway


def openai_sse():
    def event(choices,usage=None):
        return "data: "+json.dumps({"id":"chatcmpl-test","object":"chat.completion.chunk","created":0,
            "model":"gpt-4o-mini","choices":choices,"usage":usage})+"\n\n"
    s=""
    for text in ["Hello"," world"]:
        s+=event([{"index":0,"delta":{"content":text},"finish_reason":None}])
    s+=event([{"index":0,"delta":{},"finish_reason":"stop"}])
    s+=event([],{"prompt_tokens":12,"completion_tokens":2,"total_tokens":14})
    return s+"data: [DONE]\n\n"


def anthropic_sse():
    events=[{"type":"message_start","message":{"id":"msg_test","type":"message","role":"assistant",
        "model":"claude-haiku-4-5-20251001","content":[],"stop_reason":None,"stop_sequence":None,
        "usage":{"input_tokens":12,"output_tokens":0}}},
        {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}},
        {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}},
        {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" world"}},
        {"type":"content_block_stop","index":0},
        {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":None},"usage":{"output_tokens":2}},
        {"type":"message_stop"}]
    return "".join("event: "+e["type"]+"\ndata: "+json.dumps(e)+"\n\n" for e in events)

@pytest.mark.parametrize("provider,model",[("openai","gpt-4o-mini"),("anthropic","claude-haiku-4-5-20251001")])
async def test_real_sdk_sse_parsing(settings,provider,model):
    captured=[]
    async def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200,headers={"content-type":"text/event-stream"},text=openai_sse() if provider=="openai" else anthropic_sse())
    http=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client=openai.AsyncOpenAI(api_key=settings.key_for(provider),http_client=http,max_retries=0) if provider=="openai" else anthropic.AsyncAnthropic(api_key=settings.key_for(provider),http_client=http,max_retries=0)
    gateway=UnifiedLLMGateway(settings,clients={provider:client})
    try:
        chunks=[c async for c in gateway.stream("hello",model)]
        assert "".join(c.delta_text for c in chunks)=="Hello world"
        assert chunks[-1].telemetry.input_tokens==12
        assert chunks[-1].telemetry.output_tokens==2
        assert chunks[-1].is_final and chunks[-1].telemetry.usage_source=="provider_final"
        assert captured[0]["stream"] is True
    finally:
        await gateway.aclose()
