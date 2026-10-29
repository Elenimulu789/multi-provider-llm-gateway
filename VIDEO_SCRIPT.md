# Video script — target about 6 minutes

Keep your webcam visible for the entire final recording. Rehearse and check the
actual duration; word count and demo delays cannot guarantee 5–7 minutes.
Read the paragraphs; perform the bold screen actions silently.

## Prepare

- Configure both server keys privately and verify both live providers first.
- Have VS Code, app, GitHub, and the terminal open. Do not show `.env` or the
  hosting secret manager. The UI never asks you to paste API keys in the browser.
- The default tests should pass; live smoke tests are intentionally skipped unless
  you opt in. State the actual passed/skipped totals shown in your terminal.
- Use a genuine invalid-key request for the rubric, not only the simulation button.
  Offscreen, prepare to change one `.env` key temporarily to the fake value
  `sk-invalid-for-class-demo-0000000000000000`, save, then rerun that provider.
  The shape passes local checks but the provider rejects it. Restore the real
  key offscreen afterward. If demonstrating the hosted app, change its server
  secret privately instead and never show the secret settings on video.
- Review the code and add your observations to `ai_prompt_log.md` before recording.

## 0:00–1:00 — Introduction and architecture

**Show the project folders and the README architecture diagram.**

Hi, my name is Eleni Mulu. This project is a multi-provider language-model gateway.
It lets the same interface send a prompt to either OpenAI or Anthropic, stream
the response, and display timing, token usage and a calculated request cost.

The main idea is to keep provider-specific code separate from the interface.
The application calls UnifiedLLMGateway, which returns the same kind of chunk
regardless of the provider. Pydantic defines the shared chunk and telemetry fields.

The gateway uses official asynchronous clients. These allow network requests to
wait without blocking the event loop. A session keeps its clients and event loop
between requests, so it can reuse connections rather than rebuilding everything
for each prompt.

A background asyncio loop handles provider work, while a bounded queue delivers
updates to the Streamlit interface. Each request has its own counters and timers.

## 1:00–2:20 — AI audit and corrections

**Open ai_prompt_log.md, audit/initial_gateway.py, and src/normalization.py.**

I used an AI coding assistant for the initial implementation, tests, and
documentation. The audit log includes a minimal event-handling example that
makes two normalization problems easy to reproduce and compare with the final code.

The first was indexing the first OpenAI choice without checking whether any
choices existed. OpenAI can send a final usage-only event with an empty choices
list. The draft would crash at that point and lose the final token counts.

The final parser reads usage separately and checks for empty choices before
trying to extract text. The gateway also keeps reading after the text-ending
event so it receives the usage information.

The second problem was adding Anthropic's output-token snapshots together.
Those values are cumulative. A count of five followed by ten means ten total,
not fifteen. The corrected normalizer replaces the previous output count while
preserving the input information.

**Show audit/normalization.diff and the regression tests.**

The source diff compares the example with the final implementation. The
regression tests reproduce both failures and verify the corrected behavior.
The audit also checks client reuse, cancellation, secret handling and timing.

## 2:20–3:50 — Live provider comparison

**Keep Offline fixture preview OFF. Select OpenAI / gpt-4o-mini. Run the default prompt.**

I am now making a real OpenAI request. The response appears incrementally rather
than waiting for the complete answer.

The dashboard shows time to first token, generation speed, input tokens, output
tokens, and calculated cost. Time to first token starts at API dispatch and ends
when the first non-empty text arrives, so it includes network and provider delay.

During generation, local token counts are estimates. When the final provider
usage arrives, the dashboard switches to provider-final counts. That distinction
matters because separately tokenizing text chunks can give misleading totals.

**Select Anthropic / claude-haiku-4-5-20251001. Run the identical prompt.**

I am sending the same prompt to Anthropic. The interface consumes the same shared
chunk format, even though Anthropic sends a different event protocol.

Its local tiktoken estimate is only a proxy because Anthropic uses its own
tokenizer. The final displayed counts come from Anthropic's usage metadata.

**Show the two rows in Recent live requests. Read the actual results.**

These rows let me compare the actual response timing, output length and cost.
One run is not a universal performance benchmark; network conditions and the
amount of generated text affect the result.

## 3:50–4:50 — Cost calculation and security

**Expand Rates, token accounting, and timing definitions; show src/pricing.py.**

The pricing table stores input and output rates per million tokens. The gateway
multiplies each token count by its corresponding rate and divides by one million.
It uses Decimal arithmetic, and the interface displays six decimal places.
The downloadable telemetry preserves the unrounded value.

The final figure is a calculation using listed standard prices, not an account
balance or a provider receipt. Interrupted requests may still incur charges.

**Show a genuine invalid-key request prepared offscreen. Do not reveal credentials.**

For this request, the provider credential has been temporarily invalidated.
The application shows a typed authentication error without exposing the raw
provider exception or credential. It remains available for another request.

Real keys stay in server environment configuration or the hosting secret manager.
They are not in browser form fields, telemetry exports, or the GitHub repository.
The application does not automatically replay a failed stream, which helps avoid
duplicated output or additional billable requests.

## 4:50–5:40 — Tests

**Run uv run pytest -v. Show the actual final summary.**

The automated suite checks normalized output from both providers, token counting,
Decimal costs, timing, missing keys, redaction, and request boundaries. It also
checks concurrency, stream cancellation and persistent-client reuse.

Some integration tests use the real official SDKs with mocked HTTP streams.
That verifies parsing without making paid requests. The separately marked live
tests are skipped by default and can be explicitly enabled with funded API keys.
The live provider behavior was demonstrated separately in the interface.

## 5:40–6:10 — Deployment and close

**Show the actual hosted app URL and GitHub repository, or verified Docker execution.**

The repository contains the source, locked dependencies, configuration example,
tests, architecture diagram, pricing table and audit log.

The interface is available through the deployment shown here. The remaining
limitations include static pricing that needs maintenance, approximate metrics
while a response is still streaming, and no production authentication or
per-user spending limits.

The result is one application interface that can switch between two providers
while keeping their streaming differences, usage accounting and errors behind
a shared gateway.

## Submission reminders

Verify deployment before recording the closing section. Use the actual results
shown in your demonstration. Keep the video between 5:00 and 7:00 and upload it
as unlisted or public.
