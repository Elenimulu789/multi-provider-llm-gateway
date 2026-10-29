# QA report

## Completed in the build environment

- Linux, Python 3.11.17, OpenAI SDK 2.54.0, Anthropic SDK 0.125.0,
  Pydantic 2.14.1, tiktoken 0.14.0 and Streamlit 1.66.1.
  Exact transitive versions are locked in `uv.lock`.
- `uv sync` completed.
- `uv run pytest -v`: **53 passed, 2 skipped** in the final run.
  Full terminal output is retained at `audit/pytest_output.txt`.
- Two-provider normalized text and metadata tests passed.
- Both official async SDKs consumed realistic SSE payloads through HTTPX
  MockTransport and produced the expected final text and exact fixture counts.
- First non-empty text timing, missing final usage, truncation, cancelled task
  cleanup, early generator close, concurrent metric isolation and event-loop
  responsiveness were tested.
- Decimal calculations, OpenAI cache discounts and Anthropic cache input classes
  were checked with exact expected numeric values.
- Missing/malformed credentials, 401/429/provider failures, connection failure,
  public exception strings/tracebacks, settings serialization and logging
  redaction tests passed with fake keys and mocked provider failures.
- Client constructor reuse, same-loop session reuse and credential-change cleanup
  were tested. Streamlit AppTest exercised an offline streaming request and a
  visibly simulated authentication error without a script exception.
- Real local tiktoken assets loaded and produced token counts.
- Streamlit subprocess health check returned HTTP **200**, body **ok**.
- Initial normalization probe reproduced both documented draft flaws;
  regression tests verify the final fixes. A genuine first-run token-overhead
  test failure and its correction are documented in the audit log.

## What is not verified

- No real OpenAI or Anthropic requests were sent. The two skipped tests are
  explicitly opt-in BILLABLE live smoke tests. SDK mocks do not prove account
  access, available credit, current model availability or real network latency.
- Docker was unavailable. Verify the container locally if using that option.
- Repository upload, hosted deployment, manual review, and video recording remain
  local submission steps.
- Browser visual screenshot QA was not performed. AppTest checked actual widget
  flows and outputs, not the final appearance in your browser. Review desktop
  layout before recording.
- Listed pricing was checked against official documentation, but this is not
  provider invoice reconciliation. Final usage cannot be known if a stream is
  interrupted before its final metadata arrives.

## Remaining checks on your machine

1. Start the app and configure both server credentials privately.
2. Run the default tests and retain your own result.
3. Run the same short prompt through both live providers. Confirm text streaming,
   final provider usage, positive timing/throughput and plausible cost. Save both
   downloadable telemetry records if useful for your evidence.
4. Demonstrate a genuine invalid-key request or network interruption, verifying
   that UI and server output do not reveal the key. The simulation button is a
   supplementary control-flow demonstration, not a real SDK authentication test.
5. Deploy to Streamlit Community Cloud with secrets, or verify Docker locally.
6. Review and annotate the AI audit, record the 5–7 minute webcam walkthrough,
   and submit actual repository, hosting and YouTube links.
