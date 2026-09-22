"""Gemini through the OpenAI-compatible endpoint: key scoping, base URL, request shape, and the
"not tuned to the vendor" guard. The SDK is faked; nothing touches the network and no real key
is ever read (the .env loader is patched out and both key variables are set to fakes)."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from ombs.providers import get_provider
from ombs.providers import google as google_mod
from ombs.providers.base import GenerationOptions, SystemMsg, ToolSpec, UserMsg
from ombs.providers.google import GEMINI_OPENAI_BASE_URL, GoogleProvider
from ombs.providers.openai import OpenAIProvider

TOOLS = [ToolSpec(name="read_file", description="Return a file.",
                  parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"],
                              "additionalProperties": False})]
OPTS = GenerationOptions(max_tokens=512, timeout_seconds=30)


class _FakeClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.models = SimpleNamespace(list=lambda: [SimpleNamespace(id="gemini-3.1-pro"), SimpleNamespace(id="gemini-2.5-flash")])
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.last_create = None

    def _create(self, **kw):
        self.last_create = kw
        msg = SimpleNamespace(content="ok", tool_calls=None, refusal=None)
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=3, prompt_tokens_details=None,
                                completion_tokens_details=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")],
                               model="gemini-3.1-pro-001", usage=usage,
                               model_dump_json=lambda: "{}")


class _FakeSDK:
    OpenAI = _FakeClient

    class APIStatusError(Exception):
        status_code = 500
        message = "boom"

    class APIConnectionError(Exception):
        pass


@pytest.fixture
def fake_sdk(monkeypatch):
    import openai as real_openai

    monkeypatch.setattr(real_openai, "OpenAI", _FakeClient)
    monkeypatch.setattr(google_mod, "load_dotenv", lambda *a, **k: False)  # never touch the real .env
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-google-key")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return real_openai


def test_client_is_scoped_to_the_gemini_base_url_and_its_own_key(fake_sdk, caplog):
    caplog.set_level(logging.DEBUG)
    prov = GoogleProvider()
    assert prov._client.kwargs["base_url"] == GEMINI_OPENAI_BASE_URL
    assert prov._client.kwargs["api_key"] == "fake-google-key"  # GOOGLE_API_KEY wins when both are set
    # OPENAI_API_KEY absence does not block; OPENAI_BASE_URL is never touched
    import os
    assert "OPENAI_BASE_URL" not in os.environ
    assert "fake-google-key" not in caplog.text


def test_either_key_variable_is_accepted_and_both_are_named_when_missing(fake_sdk, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY")
    prov = GoogleProvider()
    assert prov._client.kwargs["api_key"] == "fake-gemini-key"
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY.*GEMINI_API_KEY"):
        GoogleProvider()


def test_factory_serves_google_and_gemini_names(fake_sdk):
    assert isinstance(get_provider("google"), GoogleProvider)
    assert isinstance(get_provider("gemini"), GoogleProvider)


def test_request_shape_equals_openai_unless_a_hook_is_flipped(fake_sdk):
    kw_g = GoogleProvider._tools_request(messages=[SystemMsg("s"), UserMsg("u")], tools=TOOLS, model="gemini-3.1-pro", options=OPTS)
    kw_o = OpenAIProvider._tools_request(messages=[SystemMsg("s"), UserMsg("u")], tools=TOOLS, model="gemini-3.1-pro", options=OPTS)
    assert kw_g == kw_o  # byte-identical shape by default: nothing is tuned for the vendor

    class Loose(GoogleProvider):
        TOKEN_BUDGET_KEY = "max_tokens"
        STRICT_TOOLS = False

    kw_l = Loose._tools_request(messages=[UserMsg("u")], tools=TOOLS, model="gemini-3.1-pro", options=OPTS)
    assert kw_l["max_tokens"] == 512 and "max_completion_tokens" not in kw_l
    fn = kw_l["tools"][0]["function"]
    assert "strict" not in fn and "additionalProperties" not in fn["parameters"]
    assert fn["parameters"]["required"] == ["path"]


def test_no_default_model_and_resolved_id_recorded(fake_sdk):
    prov = GoogleProvider()
    with pytest.raises(ValueError, match="no default model"):
        prov.generate(system="s", prompt="p", model="", options=OPTS)
    r = prov.generate(system="s", prompt="p", model="gemini-3.1-pro", options=OPTS)
    assert r.ok and r.model_digest == "gemini-3.1-pro-001"
    assert r.provider_metadata["model"] == "gemini-3.1-pro-001"
    assert r.provider_metadata["input_tokens"] == 10 and r.provider_metadata["output_tokens"] == 3
    assert prov._client.last_create["model"] == "gemini-3.1-pro"
    assert prov._client.last_create["max_completion_tokens"] == 512


def test_list_models_prints_ids_only(fake_sdk):
    prov = GoogleProvider()
    assert prov.list_models() == ["gemini-2.5-flash", "gemini-3.1-pro"]


def test_google_adds_no_scenario_aware_behaviour():
    """The reviewer's rule in code form: everything Gemini-specific is a declared hook or the
    key/base-url plumbing. A new method here would be a vendor-specific behaviour to justify."""
    added = set(vars(GoogleProvider)) - set(vars(OpenAIProvider)) - {"__doc__", "__module__", "__qualname__"}
    allowed = {"name", "default_model", "__init__", "list_models", "_call", "chat_tools", "TOKEN_BUDGET_KEY", "STRICT_TOOLS"}
    assert added <= allowed, added - allowed
    assert GoogleProvider.supports_tools is True
    assert GoogleProvider.TOKEN_BUDGET_KEY == OpenAIProvider.TOKEN_BUDGET_KEY
    assert GoogleProvider.STRICT_TOOLS is OpenAIProvider.STRICT_TOOLS
