import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from src.normalization import Usage,openai_event,anthropic_event


def baseline():
    spec=importlib.util.spec_from_file_location("draft",Path(__file__).resolve().parents[1]/"audit"/"initial_gateway.py")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_openai_empty_choices_regression():
    raw=NS(choices=[],usage=NS(prompt_tokens=100,completion_tokens=10))
    with pytest.raises(IndexError):
        baseline().openai_delta(raw)
    normalized=openai_event(raw)
    assert normalized.text=="" and normalized.usage.output==10


def test_anthropic_cumulative_usage_regression():
    raw=NS(type="message_delta",usage=NS(output_tokens=10),delta=NS(stop_reason="end_turn"))
    assert baseline().anthropic_usage(5,raw)==15
    normalized=anthropic_event(raw,Usage(input=100,output=5))
    assert normalized.usage.output==10
