from src.config import resolve_credential
from src.security import Settings

NAME = "OPENAI_API_KEY"
FAKE = "sk-" + "fixture" * 8


def test_root_streamlit_secret_takes_precedence():
    result = resolve_credential(NAME, {NAME: FAKE}, {NAME: "old"})
    assert result.value.get_secret_value() == FAKE
    assert result.source == "Streamlit Secrets" and result.issue is None
    assert FAKE not in repr(result)


def test_common_toml_tables_resolved():
    for table in ("secrets", "api_keys"):
        result = resolve_credential(NAME, {table: {NAME: FAKE}}, {})
        assert result.value.get_secret_value() == FAKE
        assert table in result.source


def test_blank_streamlit_key_does_not_reuse_stale_environment():
    result = resolve_credential(NAME, {NAME: ""}, {NAME: FAKE})
    assert result.value is None and result.issue


def test_missing_and_wrong_toml_type_have_safe_diagnostics():
    assert resolve_credential(NAME, {}, {}).issue == "Key not found or empty"
    result = resolve_credential(NAME, {NAME: {"unexpected": FAKE}}, {})
    assert result.value is None and "TOML" in result.issue
    assert FAKE not in repr(result)


def test_environment_fallback():
    result = resolve_credential(NAME, {}, {NAME: FAKE})
    assert result.value.get_secret_value() == FAKE
    assert result.source == "server environment / .env"


def test_status_distinguishes_missing_placeholder_masked_and_wrong_provider():
    assert Settings().key_issue("openai") == "Key not found or empty"
    samples = [
        ("PASTE_YOUR_OPENAI_KEY_HERE", "Placeholder"),
        ("sk-" + "x" * 30 + "...", "Masked"),
        ('"' + FAKE + '"', "quotation"),
        ("sk-" + "a" * 30 + "\n" + "b" * 30, "line break"),
        ("sk-ant-" + "a" * 30, "Anthropic"),
    ]
    for value, message in samples:
        issue = Settings(openai_api_key=value).key_issue("openai")
        assert message in issue
        assert value not in issue


def test_opaque_printable_key_suffix_is_not_overconstrained():
    value = "sk-" + "a" * 30 + ".+/="
    settings = Settings(openai_api_key=value)
    assert settings.key_for("openai") == value


def test_streamlit_ui_reports_nested_secret_without_exposing_value():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "src/app.py", default_timeout=10)
    app.secrets["secrets"] = {NAME: FAKE}
    app.run()
    assert not app.exception
    text = "\n".join(item.value for item in app.markdown)
    captions = "\n".join(item.value for item in app.caption)
    assert "Openai: loaded" in text or "OpenAI: loaded" in text
    assert "Streamlit Secrets [secrets]" in captions
    assert FAKE not in text and FAKE not in captions
