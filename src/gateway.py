"""Persistent async SDK clients, request-local state, normalized streaming output."""
import asyncio
from contextlib import aclosing
import logging
from time import perf_counter
from collections.abc import AsyncGenerator
from src.errors import (GatewayProviderError, AuthenticationError, RateLimitExceededError,
    GatewayConnectionError, InvalidRequestError, IncompleteStreamError)
from src.normalization import Usage, Event, openai_event, anthropic_event
from src.pricing import PRICES, PRICING_DATE, calculate_cost
from src.schemas import StreamChunk, ChunkTelemetry
from src.security import Settings, configure_logging
from src.tokenizer import count_text

logger = configure_logging()


class UnifiedLLMGateway:
    def __init__(self, settings: Settings, *, clients=None, demo=False, clock=perf_counter):
        self._settings = settings
        self._clients = dict(clients or {})
        self._demo = demo
        self._clock = clock
        self._closed = False

    def _client(self, provider):
        key = self._settings.key_for(provider)
        if provider not in self._clients:
            if provider == "openai":
                from openai import AsyncOpenAI
                self._clients[provider] = AsyncOpenAI(api_key=key, base_url="https://api.openai.com/v1", timeout=45, max_retries=0)
            else:
                from anthropic import AsyncAnthropic
                self._clients[provider] = AsyncAnthropic(api_key=key, base_url="https://api.anthropic.com", timeout=45, max_retries=0)
        return self._clients[provider]

    async def aclose(self):
        if self._closed:
            return
        self._closed = True
        for client in self._clients.values():
            try:
                await client.close()
            except Exception:
                logger.warning("Client cleanup failed; details suppressed")
        self._clients.clear()

    async def _events(self, provider, client, model, prompt, temperature, max_tokens):
        if self._demo:
            text = "This is an offline fixture stream. Configure server credentials to compare real provider responses."
            total = ""
            for word in text.split(" "):
                delta = (" " if total else "") + word
                total += delta
                await asyncio.sleep(0.025)
                yield Event(text=delta), False
            n_in = await asyncio.to_thread(count_text, prompt)
            n_out = await asyncio.to_thread(count_text, text)
            yield Event(usage=Usage(input=n_in + 7, output=n_out), done=True, finish_reason="stop"), True
            return
        if provider == "openai":
            response = await client.chat.completions.create(model=model,
                messages=[{"role": "user", "content": prompt}], temperature=temperature,
                max_completion_tokens=max_tokens, stream=True, service_tier="default",
                stream_options={"include_usage": True})
            try:
                async for raw in response:
                    event = openai_event(raw)
                    yield event, event.usage is not None
            finally:
                await response.close()
        else:
            usage = Usage()
            async with client.messages.stream(model=model, messages=[{"role": "user", "content": prompt}],
                    temperature=temperature, max_tokens=max_tokens) as response:
                async for raw in response:
                    event = anthropic_event(raw, usage)
                    if event.usage is not None:
                        usage = event.usage
                    yield event, raw.type == "message_delta" and getattr(raw.usage, "output_tokens", None) is not None

    @staticmethod
    def _safe_error(exc, provider):
        # Never include str(exc), SDK response bodies, headers, keys or prompt text.
        import openai
        import anthropic
        if isinstance(exc, (openai.AuthenticationError, anthropic.AuthenticationError)):
            return AuthenticationError(provider)
        if isinstance(exc, (openai.RateLimitError, anthropic.RateLimitError)):
            return RateLimitExceededError(provider)
        if isinstance(exc, (TimeoutError, openai.APIConnectionError, anthropic.APIConnectionError)):
            return GatewayConnectionError(provider)
        if isinstance(exc, (openai.BadRequestError, openai.NotFoundError, openai.PermissionDeniedError,
                            anthropic.BadRequestError, anthropic.NotFoundError, anthropic.PermissionDeniedError)):
            return InvalidRequestError(provider)
        return GatewayProviderError(provider)

    async def stream(self, prompt: str, model: str, temperature: float = 0.7,
                     max_tokens: int = 512) -> AsyncGenerator[StreamChunk, None]:
        if self._closed or model not in PRICES:
            raise InvalidRequestError()
        provider = PRICES[model].provider
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 20000:
            raise InvalidRequestError(provider)
        if isinstance(temperature, bool) or not isinstance(temperature, (int,float)) or not 0 <= temperature <= 1:
            raise InvalidRequestError(provider)
        if type(max_tokens) is not int or not 16 <= max_tokens <= 2048:
            raise InvalidRequestError(provider)
        client = None if self._demo else self._client(provider)
        # tiktoken can perform CPU work and first-run asset I/O: keep it off loop.
        local_prompt = await asyncio.to_thread(count_text, prompt)
        usage = Usage(input=local_prompt + (7 if provider == "openai" else 0))
        first_text = None
        start = self._clock()
        text = ""
        estimated_output = 0
        seen_usage = False
        final_usage = False
        seen_done = False
        finish_reason = None
        mode = "offline_fixture" if self._demo else "live"

        def chunk(delta="", final=False):
            now = self._clock()
            output = usage.output if final_usage else estimated_output
            elapsed = max(now-start, 0)
            generation = max(now-first_text, 0.001) if first_text is not None else 0
            source = "provider_final" if final_usage else "provider_partial" if seen_usage else "local_estimate"
            warning = None
            if final and not final_usage:
                source = "estimate_missing_final_usage"
                warning = "Final usage metadata absent: counts and cost remain estimates."
            if finish_reason in ("length", "max_tokens"):
                warning = "Output token limit reached; response may be truncated."
            if final and first_text is None:
                warning = "Provider completed without text; TTFT and text throughput are unavailable."
            if self._demo:
                warning = "Offline fixture: synthetic provider usage; cost is hypothetical, not billed."
            return StreamChunk(delta_text=delta, provider=provider, model=model, is_final=final, mode=mode,
                telemetry=ChunkTelemetry(input_tokens=usage.input, output_tokens=output,
                    total_tokens=usage.input+output, local_prompt_tokens=local_prompt,
                    cached_input_tokens=usage.cached_read, cache_write_5m_tokens=usage.write_5m,
                    cache_write_1h_tokens=usage.write_1h,
                    ttft_ms=(first_text-start)*1000 if first_text is not None else None,
                    latency_seconds=elapsed, tokens_per_second=output/generation if generation else 0,
                    total_cost_usd=calculate_cost(model,usage.input,output,usage.cached_read,usage.write_5m,usage.write_1h),
                    usage_source=source, pricing_date=PRICING_DATE, finish_reason=finish_reason, warning=warning))
        try:
            yield chunk()
            async with asyncio.timeout(90):
                async with aclosing(self._events(provider, client, model, prompt, temperature, max_tokens)) as events:
                    async for event, authoritative in events:
                        if event.text:
                            if first_text is None:
                                first_text = self._clock()
                            text += event.text
                            # Re-tokenize cumulative text, NOT each delta independently.
                            estimated_output = await asyncio.to_thread(count_text, text)
                        if event.usage is not None:
                            usage = event.usage
                            seen_usage = True
                        final_usage = final_usage or authoritative
                        seen_done = seen_done or event.done
                        if event.finish_reason:
                            allowed = {"stop", "length", "content_filter", "tool_calls", "end_turn", "max_tokens", "stop_sequence", "refusal"}
                            finish_reason = event.finish_reason if event.finish_reason in allowed else "other"
                        yield chunk(event.text)
            if not seen_done:
                raise IncompleteStreamError(provider)
            yield chunk(final=True)
        except GatewayProviderError:
            raise
        except asyncio.CancelledError:
            raise  # consumer cancellation must close upstream, not become success
        except Exception as exc:
            safe = self._safe_error(exc, provider)
            logger.warning("Provider request failed: %s / %s", provider, safe.code)
            raise safe from None


LLMGateway = UnifiedLLMGateway
