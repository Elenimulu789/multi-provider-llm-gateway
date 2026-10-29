# AI Assistance and Verification Log

## Project Overview

This project provides a shared interface for streaming responses from OpenAI and Anthropic. It normalizes provider events, validates response structures with Pydantic v2, and displays token usage, response timing, and calculated request costs.

AI assistance supported implementation drafting, testing, troubleshooting, and documentation.

## Summary of Development Requests

The development requests focused on:

- Designing an asynchronous wrapper for two providers using their official SDKs.
- Defining shared models for streamed text and telemetry.
- Handling differences between provider events and token-usage reporting.
- Calculating request costs using separate input and output rates.
- Measuring time to first token, latency, and generation speed.
- Reusing clients and keeping blocking operations outside the event loop.
- Protecting credentials and displaying clear errors.
- Building an interactive interface, automated tests, and deployment instructions.

These are summaries of the development requests rather than verbatim conversation transcripts.

## Code Audit and Corrections

### 1. OpenAI Usage-Only Events

A text-only parsing example accessed the first choice directly:

```python
return event.choices[0].delta.content or ""
```

OpenAI can send a final usage event with an empty choices list. Accessing the first element would raise an error and prevent final token accounting.

The final parser reads usage separately and checks for empty choices:

```python
if not raw.choices:
    return Event(usage=usage)
```

The gateway continues reading after the text finish event so it can receive the final usage totals.

### 2. Anthropic Cumulative Token Counts

The initial parsing example added each output-token snapshot to the previous count:

```python
return previous_output + event.usage.output_tokens
```

Anthropic reports cumulative output counts. A snapshot of five followed by ten means ten total, not fifteen.

The final implementation replaces the previous output count with the latest available snapshot:

```python
output = getattr(raw.usage, "output_tokens", None)
output = previous.output if output is None else output
```

Input and cache categories are preserved separately.

The retained file, `audit/initial_gateway.py`, is a minimal event-handling example rather than a complete early application. The failure observations, source comparison, and regression tests are available in:

- `audit/baseline_probe.txt`
- `audit/normalization.diff`
- `tests/test_audit_regressions.py`

### 3. Credential Configuration Diagnostics

During deployment, the interface used the same “missing / malformed” label for different configuration problems. This made it difficult to distinguish an unread key from an incorrectly formatted value.

The updated implementation separates missing values, placeholders, shortened keys, provider mismatches, and formatting problems. It also identifies the configuration source without displaying the credential.

Tests cover root-level and grouped Streamlit secrets, environment fallback, configuration precedence, and secret-safe diagnostics.

## Additional Review Areas

| Area | Implementation |
| --- | --- |
| Async behavior | Official asynchronous clients; local tokenization runs outside the event loop |
| Client reuse | Clients persist on the gateway instance and are closed when configuration changes |
| Cancellation | Stream ownership and cleanup use `aclosing` |
| Timing | TTFT is set on the first non-empty text delta |
| Precision | Decimal arithmetic preserves calculated cost precision |
| Token estimates | Accumulated response text is tokenized rather than summing separately tokenized chunks |
| Usage accuracy | Local estimates, partial usage, and final provider counts are labeled separately |
| Security | Server-side credentials, protected settings fields, sanitized errors, and redaction tests |
| Reliability | Request bounds, timeouts, and no automatic replay of failed streams |

Local text-token counts are distinct from provider request counts, which can include message framing. Anthropic final counts come from its provider metadata rather than the local tiktoken estimate.

## Verification Results

- **Latest local test result:** 61 passed, 2 skipped.
- **Local environment:** Windows, Python 3.11.18.
- **Live streaming:** Both OpenAI and Anthropic were successfully exercised through the interface.
- **Hosted configuration:** Credential loading was confirmed after saving the keys in the deployed app's Streamlit Secrets settings.

The two skipped tests are optional billable live checks requiring explicit activation. Default tests use mocks and fixtures, including official SDK parsing over mocked HTTP streams.

The retained `audit/pytest_output.txt` records the earlier build-environment run of 53 passed and 2 skipped. The latest local run includes the additional configuration tests.

## Deployment and Manual Review Notes

- Hosted application URL:
- Hosted OpenAI and Anthropic comparison results:
- Files reviewed and additional findings:
- Changes made after manual review:
- Invalid-key or network-error demonstration:
- Final video URL and duration:

## Limitations

Pricing is maintained in a static table and must be updated when provider rates change. Live token counts can remain estimates until final usage arrives. Interrupted requests may incur charges even when final usage is unavailable.

The application does not include production authentication, per-user spending limits, or provider-invoice reconciliation.
