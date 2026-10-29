"""uv run streamlit run src/app.py"""
import os
import sys
import json
from pathlib import Path
from decimal import Decimal
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import streamlit as st
from dotenv import load_dotenv
from src.security import Settings
from src.runtime import SessionRuntime
from src.pricing import PRICES, PRICING_DATE

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
st.set_page_config(page_title="Relay · LLM Gateway",page_icon="◈",layout="wide")
st.markdown('''<style>.block-container{max-width:1450px;padding-top:2rem}
[data-testid="stMetric"]{background:#fff;border:1px solid #e0e5ee;border-radius:12px;padding:14px}
h1{letter-spacing:-1.5px}.eyebrow{color:#6366f1;letter-spacing:2.5px;font-weight:700;font-size:12px}</style>''',unsafe_allow_html=True)
st.markdown('<div class="eyebrow">RELAY / MULTI-PROVIDER LLM GATEWAY</div>',unsafe_allow_html=True)
st.title("One interface. Two providers.")
st.caption("Stream responses, compare latency, and track every token with a transparent cost calculation.")

def secret(name):
    try:
        return st.secrets.get(name) or os.getenv(name) or None
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return os.getenv(name) or None

settings = Settings(openai_api_key=secret("OPENAI_API_KEY"), anthropic_api_key=secret("ANTHROPIC_API_KEY"))
with st.sidebar:
    st.header("Request settings")
    provider = st.selectbox("Provider",["OpenAI", "Anthropic"])
    provider_id = provider.lower()
    models = [m for m,p in PRICES.items() if p.provider == provider_id]
    model = st.selectbox("Model",models)
    temperature = st.slider("Temperature",0.0,1.0,0.7,0.1)
    max_tokens = st.slider("Maximum output tokens",64,1024,512,64)
    demo = st.toggle("Offline fixture preview",value=False)
    if demo:
        st.warning("Simulated stream. No LLM call. Displayed cost is hypothetical.")
    st.divider()
    st.caption("SERVER CREDENTIAL STATUS")
    for name in ["openai", "anthropic"]:
        st.write(f"{'✓' if settings.configured(name) else '○'} {name.title()}: {'configured' if settings.configured(name) else 'missing / malformed'}")
    with st.expander("How to configure keys"):
        st.write("Local: copy .env.example to .env, set both keys, then rerun. Hosted: add both keys in the hosting Secrets settings. Never commit .env or secrets.toml.")
    st.caption("Keys stay in server configuration. They are never placed in browser input fields, telemetry or downloads.")
    st.caption("Live requests use API credits. Output is limited and requests do not retry automatically.")

prompt = st.text_area("Your prompt",value="Explain three ways to protect API keys in a Python application. Keep the answer under 150 words.",height=115,max_chars=20000)
a,b,c = st.columns([1,1,2])
with a:
    run = st.button("Stream response",type="primary",use_container_width=True)
with b:
    simulate = st.button("Simulate authentication error",use_container_width=True)
with c:
    clear = st.button("Cancel / clear result")
if clear:
    st.session_state.pop("last_run",None)

left,right = st.columns([1.8,1],gap="large")
with left:
    st.subheader("01 / Response stream")
    output = st.empty()
    status = st.empty()
with right:
    st.subheader("02 / Live telemetry")
    dashboard = st.empty()
    accounting = st.empty()
    detail = st.empty()

def draw(telemetry, hypothetical=False):
    with dashboard.container():
        r1,r2 = st.columns(2)
        r1.metric("First token", "—" if telemetry.ttft_ms is None else f"{telemetry.ttft_ms:,.0f} ms")
        r2.metric("Generation speed", f"{telemetry.tokens_per_second:,.1f} tok/s")
        r3,r4 = st.columns(2)
        r3.metric("Input tokens",telemetry.input_tokens)
        r4.metric("Output tokens",telemetry.output_tokens)
        st.metric("Hypothetical cost" if hypothetical else "Request cost · USD",f"${telemetry.total_cost_usd:.6f}")
    accounting.caption(f"{telemetry.usage_source} · elapsed {telemetry.latency_seconds:.2f}s · rates dated {telemetry.pricing_date}")
    if telemetry.warning:
        detail.warning(telemetry.warning)
    else:
        detail.empty()

if run or simulate:
    runtime = st.session_state.get("runtime")
    if runtime is None or not runtime.alive:
        runtime = SessionRuntime()
        st.session_state.runtime = runtime
    st.session_state.pop("last_run",None)
    text = ""
    final = None
    last_telemetry = None
    error = None
    status.info("Opening provider stream…")
    iterator = runtime.iter_events(settings,demo,prompt,model,temperature,max_tokens,simulate)
    try:
        for kind,value in iterator:
            if kind == "error":
                error = value
                status.error(f"{value['code']}: {value['message']}")
                break
            text += value.delta_text
            output.markdown(text + (" ▌" if not value.is_final else ""))
            last_telemetry = value.telemetry
            draw(value.telemetry,demo)
            if value.is_final:
                final = value
        if not error:
            if final:
                status.success("Offline fixture complete" if demo else "Stream completed")
            else:
                status.warning("Stream interrupted. Any displayed counts or cost may be incomplete.")
    finally:
        iterator.close()
    st.session_state.last_run = {"provider":provider_id,"model":model,"mode":"offline_fixture" if demo else "live",
        "text":text,"complete":final is not None,"telemetry":last_telemetry.model_dump(mode="json") if last_telemetry else None,
        "error":error,"prompt":prompt}
    if final and not demo:
        history = st.session_state.setdefault("comparisons",[])
        history.append({"Provider":provider,"Model":model,"Input":final.telemetry.input_tokens,"Output":final.telemetry.output_tokens,
            "TTFT ms":round(final.telemetry.ttft_ms or 0,1),"Tokens/sec":round(final.telemetry.tokens_per_second,2),
            "Cost USD":f"{final.telemetry.total_cost_usd:.8f}","Usage":final.telemetry.usage_source,
            "Prompt":prompt})
        del history[:-10]
else:
    cached = st.session_state.get("last_run")
    if cached:
        from src.schemas import ChunkTelemetry
        output.markdown(cached["text"])
        if cached["telemetry"]:
            draw(ChunkTelemetry.model_validate(cached["telemetry"]), cached["mode"] == "offline_fixture")
        if cached["error"]:
            status.error(cached["error"]["message"])
        else:
            status.caption(f"Previous result · {cached['model']} · {cached['mode']}")
    else:
        output.info("Submit a prompt to watch text and telemetry arrive. Configure server keys or use the labeled offline preview.")
        with dashboard.container():
            st.metric("First token","—")
            st.metric("Request cost · USD","$0.000000")

if st.session_state.get("last_run"):
    st.download_button("Download response & telemetry",json.dumps(st.session_state.last_run,indent=2),"gateway_result.json","application/json")
if st.session_state.get("comparisons"):
    st.subheader("03 / Recent live requests")
    st.dataframe(st.session_state.comparisons,use_container_width=True,hide_index=True)
    st.caption("Compare rows using the same prompt. Model outputs and generation lengths can differ. Cost is per request, not a cumulative account bill.")
with st.expander("Rates, token accounting, and timing definitions"):
    st.table([{"Model":m,"Provider":p.provider,"Input / 1M USD":str(p.input),"Output / 1M USD":str(p.output),"Cached read / 1M USD":str(p.cached_read)} for m,p in PRICES.items()])
    st.caption(f"Standard text rates checked {PRICING_DATE}. Live output token counts use a tiktoken proxy until final provider usage arrives. Anthropic uses its own tokenizer; local estimates are not billable counts. No tools, batch or extended thinking are requested.")
    st.caption("TTFT is measured from API request dispatch to the first non-empty text delta, including network/provider delay. Generation speed is output tokens divided by elapsed time since that delta; short responses are noisy. A provider delta can contain multiple tokens.")
    st.caption("Cost uses exact Decimal arithmetic, displayed to six decimal places. Download telemetry for the unrounded decimal value. Provider final usage can adjust earlier estimates downward as well as upward.")
