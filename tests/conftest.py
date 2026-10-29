import asyncio
from types import SimpleNamespace as NS
from pathlib import Path
import pytest
from src.security import Settings

@pytest.fixture(autouse=True)
def project_folder(monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])

@pytest.fixture
def settings():
    # Deliberately fake credentials; no real provider requests in default tests.
    return Settings(openai_api_key="sk-" + "X" * 32, anthropic_api_key="sk-ant-" + "Y" * 32)


def open_event(text=None, finish=None, usage=None):
    choices = [] if text is None and finish is None else [NS(delta=NS(content=text),finish_reason=finish)]
    return NS(choices=choices,usage=usage)


def open_usage(input=100, output=5, cached=0):
    return NS(prompt_tokens=input,completion_tokens=output,prompt_tokens_details=NS(cached_tokens=cached))


def anthro_events(input=100, output=5):
    return [NS(type="message_start",message=NS(usage=NS(input_tokens=input,output_tokens=0))),
        NS(type="ping"),
        NS(type="content_block_delta",delta=NS(type="text_delta",text="Hello")),
        NS(type="content_block_delta",delta=NS(type="text_delta",text=" world")),
        NS(type="message_delta",delta=NS(stop_reason="end_turn"),usage=NS(output_tokens=output)),
        NS(type="message_stop")]


class FakeStream:
    def __init__(self, events):
        self.events = events
        self.closed = False
    async def __aiter__(self):
        for event in self.events:
            await asyncio.sleep(.002)
            if isinstance(event,Exception):
                raise event
            yield event
    async def close(self):
        self.closed = True
    async def __aenter__(self):
        return self
    async def __aexit__(self,*args):
        self.closed = True


class FakeClient:
    def __init__(self,events,provider):
        self.events,self.provider = events,provider
        self.calls=[]
        self.streams=[]
        self.closed=False
        self.chat=NS(completions=NS(create=self.create))
        self.messages=NS(stream=self.anthro_stream)
    async def create(self,**kwargs):
        self.calls.append(kwargs)
        response=FakeStream(self.events)
        self.streams.append(response)
        return response
    def anthro_stream(self,**kwargs):
        self.calls.append(kwargs)
        response=FakeStream(self.events)
        self.streams.append(response)
        return response
    async def close(self):
        self.closed=True
