# AI Assistance and Code Audit

## Assistance used

ChatGPT was used for implementation drafting, test creation, and documentation.
The assignment requirements guided the provider wrapper, interface, and telemetry.
The manual-review and local-verification record is at the end of this file.

Actual project request:

> now can you get started on the other assignment i need to get that done asap

Implementation brief derived from the supplied assignment:

> Build a Python 3.11 async gateway with official OpenAI and Anthropic clients,
> normalized Pydantic chunks, live timing and token metrics, Decimal costs,
> typed errors, protected credentials, persistent clients, tests, and a web UI.

This brief summarizes the implementation requirements; it is not a verbatim
additional prompt from the conversation.

## Audit examples and saved evidence

`audit/initial_gateway.py` contains a minimal AI-assisted event-handling example.
It isolates two common bugs for comparison with the final normalizer. It is not
a complete first version of the application. The running app never imports it.

The observed failures are in `audit/baseline_probe.txt`. The before/after source
comparison is in `audit/normalization.diff`. Regression tests reproduce the
failures and check the final behavior.

## Finding 1: OpenAI empty choices

Initial example:

```python
def openai_delta(event):
    return event.choices[0].delta.content or ""
```

OpenAI can send a final usage-only event with `choices=[]`. This code raises
`IndexError`, preventing final token accounting.

Final handling in `src/normalization.py`:

```python
if not raw.choices:
    return Event(usage=usage)
choice = raw.choices[0]
```

Usage is read separately from text, and empty content becomes an empty string.
The gateway requests `include_usage=True` and continues reading after the text
finish event to receive the usage-only tail.

Verification: `test_openai_empty_choices_regression` and the two-provider
protocol/official-SDK SSE parsing tests.

## Finding 2: Anthropic cumulative usage

Initial example:

```python
return previous_output + event.usage.output_tokens
```

Anthropic output-token snapshots are cumulative. A previous count of five and a
new snapshot of ten mean ten total, not fifteen. Adding them inflates both tokens
and cost.

Final handling:

```python
output = getattr(raw.usage, "output_tokens", None)
output = previous.output if output is None else output
```

The latest output snapshot replaces the previous count. Input and cache categories
are preserved. Message-start, text-delta, usage-delta, and message-stop events have
separate handling.

Verification: `test_anthropic_cumulative_usage_regression`,
`test_anthropic_cumulative_counts_not_summed`, and official-SDK SSE parsing tests.

## Additional checks

| Area | Implementation check |
| --- | --- |
| Event-loop blocking | Official async clients; local tokenization runs through `asyncio.to_thread` |
| Client reuse | Clients live on the gateway instance and the same session event loop; configuration changes close the old gateway |
| Cancellation | `aclosing` owns stream lifetimes, including cancellation during consumer backpressure |
| TTFT | Timer ends on the first non-empty text delta, not a role, ping, or usage event |
| Cost precision | Decimal arithmetic; six-decimal display formatting does not alter stored precision |
| Cumulative text | Local output estimates tokenize the accumulated response instead of adding counts for separate chunks |
| Usage authority | Live estimates, partial provider counts, and final provider usage are labeled separately |
| Key handling | Server-side configuration, protected settings fields, fixed public errors, and redaction tests |
| Request limits | Prompt/output bounds, timeout, and no automatic stream replay |

An initial token-count test also needed correction: it compared raw prompt text
against a mock provider count that included chat-message framing. Raw text was
51 tokens; the request fixture included seven additional framing tokens. The
corrected test compares the same quantities and keeps the raw local count separate.
The seven-token framing value is an estimate, not a guarantee for live requests.
Anthropic final counts come from its own usage metadata, not tiktoken.

## Automated verification

Build-environment result: **53 passed, 2 skipped**. The skipped tests require
explicitly enabled, billable provider calls. Full output is saved in
`audit/pytest_output.txt`.

The tests include real SDK parsers over mocked HTTP streams, concurrency,
cancellation, costs, credential failures, and Streamlit widget flows. Live API
calls and deployment still require local verification. See `QA_REPORT.md`.

## Manual review and local verification

Complete after reviewing and running the project:

- Date and operating system:
- Files reviewed and findings:
- Additional changes made:
- Local test result:
- Live OpenAI result and telemetry:
- Live Anthropic result and telemetry:
- Invalid-key or network-error result:
- Deployment URL or Docker evidence:
