# Start here — Windows

This is the **Week 1 multi-provider streaming assignment**. Keep it separate from
the invoice extractor. You can reuse the same OpenAI API key and credit balance.
The real comparison also needs an Anthropic API key with API access/credits.

## 1. Extract and open the project

Extract the ZIP. Open the folder containing `pyproject.toml` in File Explorer.
Type `powershell` into File Explorer's address bar and press Enter. This opens a
terminal in the correct folder. Alternatively, use `cd` with your actual path.

## 2. Install and launch

You already installed uv for the invoice project. Run:

```powershell
uv sync --frozen
uv run streamlit run src/app.py
```

Open **http://localhost:8501**. Stop the invoice app first with Ctrl+C in its
terminal if it is using that port. Or use another port:

```powershell
uv run streamlit run src/app.py --server.port 8502
```

Double-clicking `start-windows.bat` also installs dependencies and launches.

## 3. Check the interface without spending credits

Turn **Offline fixture preview** on, then click **Stream response**. You should
see text arrive with token/timing metrics. This mode is clearly simulated; it is
not the live provider comparison required for your video.

## 4. Add keys privately

In a second terminal in this project folder:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

In Notepad, put your existing OpenAI key after `OPENAI_API_KEY=` and your
Anthropic key after `ANTHROPIC_API_KEY=`. Do not put the keys in any other file.
Save and close Notepad. Click **Cancel / clear result** in the app to rerun it;
the server rereads `.env`. The sidebar should show both providers configured.

These API keys are not the names of keys or shortened dashboard previews. Use
the complete secret values. Do not send them in chat or show them on video.

Keys are read from server configuration, not browser password fields. `.env` and
`.streamlit/secrets.toml` are excluded from Git. See the README for security limits.

## 5. Run both real providers

Turn **Offline fixture preview off**. Keep this same short prompt for both:

> Explain three ways to protect API keys in a Python application. Keep the answer under 150 words.

1. Select **OpenAI** and **gpt-4o-mini**, then **Stream response**.
2. Confirm text streams and the final usage label is **provider_final**.
3. Select **Anthropic** and **claude-haiku-4-5-20251001**, then run again.
4. Compare the two rows under **Recent live requests**.
5. Download each response and telemetry if you want to retain demo evidence.

Keep maximum output tokens at 512 or lower for this short demo. API requests can
incur charges. A model-unavailable error requires checking your account access;
the app never silently substitutes a different model.

## 6. Tests

```powershell
uv run pytest -v
```

The default suite runs without provider credentials or billable calls. Two live
smoke tests are skipped on purpose. To explicitly run those BILLABLE checks:

```powershell
$env:RUN_LIVE_TESTS = "1"
uv run pytest -v -m live
Remove-Item Env:RUN_LIVE_TESTS
```

## 7. Deploy on Streamlit Community Cloud

Create a **new** GitHub repository named `multi-provider-llm-gateway` and upload
this project's files, keeping the invoice repository separate.

On https://share.streamlit.io/ create another app with:

- Repository: your new multi-provider gateway repository
- Branch: `main`
- Main file path: `src/app.py`
- Python: 3.11

In **Advanced settings > Secrets**, privately add:

```toml
OPENAI_API_KEY = "your complete OpenAI API key"
ANTHROPIC_API_KEY = "your complete Anthropic API key"
```

These are placeholders. Enter actual values only in the hosting secret manager.
Do not place them in GitHub files or send screenshots containing them.
Deploy, then repeat the live comparison on the hosted app. Keep access private
while using your funded server keys, or remove the keys after evaluation: people
with access to the app can otherwise trigger requests against those balances.

## 8. Record and submit

Review `ai_prompt_log.md` and add your own review/verification notes. Rehearse the
script in `VIDEO_SCRIPT.md`. Record 5–7 minutes with your webcam visible, showing
both live providers, cost/timing metrics, the audit, safe error handling, and tests.
Use `SUBMISSION_TEMPLATE.md` to submit actual GitHub, deployment and YouTube links.
