from pathlib import Path
from streamlit.testing.v1 import AppTest

APP=Path(__file__).resolve().parents[1]/"src"/"app.py"


def test_offline_ui_streaming_and_metrics(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY",raising=False)
    app=AppTest.from_file(APP,default_timeout=20).run()
    try:
        assert not app.exception
        app.toggle[0].set_value(True).run()
        app.button[0].click().run(timeout=20)
        assert not app.exception
        assert any("Offline fixture complete" in s.value for s in app.success)
        assert any(m.label=="Output tokens" and int(m.value)>0 for m in app.metric)
        assert app.session_state["last_run"]["mode"]=="offline_fixture"
        assert app.session_state["last_run"]["complete"] is True
    finally:
        runtime=app.session_state.get("runtime") if hasattr(app.session_state,"get") else app.session_state["runtime"]
        runtime.close()


def test_ui_simulated_authentication_error():
    app=AppTest.from_file(APP,default_timeout=10).run()
    try:
        app.button[1].click().run()
        assert not app.exception
        assert any("authentication" in e.value for e in app.error)
    finally:
        app.session_state["runtime"].close()
