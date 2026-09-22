"""Native tool-calling adapters: the exact wire shapes sent to each SDK and the parse of
tool calls, stop reasons, refusals, truncation and malformed arguments. SDK clients are
mocked; nothing touches the network."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from ombs.providers.anthropic import AnthropicProvider
from ombs.providers.base import (
    AssistantMsg,
    GenerationOptions,
    SystemMsg,
    ToolResult,
    ToolResultsMsg,
    ToolSpec,
    UserMsg,
)
from ombs.providers.ollama import OllamaProvider
from ombs.providers.openai import OpenAIProvider

TOOLS = [
    ToolSpec(name="read_file", description="Return the contents of a workspace file.",
             parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"], "additionalProperties": False}),
    ToolSpec(name="run_check", description="Run the report check.", parameters={"type": "object", "properties": {}, "required": [], "additionalProperties": False}),
]
OPTS = GenerationOptions(max_tokens=4096, timeout_seconds=60)


class _Block(SimpleNamespace):
    def model_dump(self, exclude_none=True):
        return {k: v for k, v in vars(self).items() if v is not None}


class _Resp(SimpleNamespace):
    def model_dump_json(self):
        return json.dumps({"stop_reason": getattr(self, "stop_reason", None)})


class _FakeSDK:
    class APIStatusError(Exception):
        status_code = 500
        message = "boom"

    class APIConnectionError(Exception):
        pass


def _anthropic() -> AnthropicProvider:
    prov = AnthropicProvider.__new__(AnthropicProvider)
    prov._anthropic = _FakeSDK
    prov._client = MagicMock()
    return prov


def _openai() -> OpenAIProvider:
    prov = OpenAIProvider.__new__(OpenAIProvider)
    prov._openai = _FakeSDK
    prov._client = MagicMock()
    return prov


def _conversation(replay):
    return [
        SystemMsg("You are the reporting assistant."),
        UserMsg("Bring the report into agreement."),
        AssistantMsg(text="", tool_calls=[], replay=replay),
        ToolResultsMsg(results=[ToolResult(call_id="tu_1", name="read_file", content="a,b\n1,2\n"),
                                ToolResult(call_id="tu_2", name="run_check", content="Error: x", is_error=True)],
                       extra_text="Workspace files:\n- report.csv"),
    ]


# -- Anthropic ------------------------------------------------------------------------- #


def test_anthropic_request_shape_and_replay():
    replay = [{"type": "thinking", "thinking": "...", "signature": "sig"}, {"type": "text", "text": "Reading."},
              {"type": "tool_use", "id": "tu_1", "name": "read_file", "input": {"path": "ledger.csv"}},
              {"type": "tool_use", "id": "tu_2", "name": "run_check", "input": {}}]
    kw = AnthropicProvider._tools_request(messages=_conversation(replay), tools=TOOLS, model="claude-opus-5", options=OPTS)
    assert kw["model"] == "claude-opus-5" and kw["max_tokens"] == 4096 and kw["system"] == "You are the reporting assistant."
    assert "thinking" not in kw and "temperature" not in kw and "top_p" not in kw
    assert kw["messages"][0] == {"role": "user", "content": [{"type": "text", "text": "Bring the report into agreement."}]}
    assert kw["messages"][1] == {"role": "assistant", "content": replay}  # verbatim, thinking block included
    assert kw["messages"][2] == {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "tu_1", "content": "a,b\n1,2\n"},
        {"type": "tool_result", "tool_use_id": "tu_2", "content": "Error: x", "is_error": True},
        {"type": "text", "text": "Workspace files:\n- report.csv"},
    ]}
    assert kw["tools"][0] == {"name": "read_file", "description": "Return the contents of a workspace file.",
                              "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"], "additionalProperties": False}}
    cached = AnthropicProvider._tools_request(messages=_conversation(replay), tools=TOOLS, model="m",
                                              options=GenerationOptions(prompt_caching=True))
    assert cached["system"] == [{"type": "text", "text": "You are the reporting assistant.", "cache_control": {"type": "ephemeral"}}]
    assert cached["messages"][-1]["content"][-1]["cache_control"] == {"type": "ephemeral"}


def test_anthropic_parse_tool_use_refusal_and_truncation():
    prov = _anthropic()
    resp = _Resp(
        content=[_Block(type="thinking", thinking="hm", signature="s"), _Block(type="text", text="On it."),
                 _Block(type="tool_use", id="tu_9", name="read_file", input={"path": "ledger.csv"})],
        stop_reason="tool_use", model="claude-opus-5-2026",
        usage=SimpleNamespace(input_tokens=120, output_tokens=30, cache_read_input_tokens=100, cache_creation_input_tokens=0),
    )
    prov._client.messages.create.return_value = resp
    r = prov.chat_tools(messages=[SystemMsg("s"), UserMsg("u")], tools=TOOLS, model="claude-opus-5", options=OPTS)
    assert r.ok and r.stop == "tool_use" and r.text == "On it."
    assert [(c.id, c.name, c.arguments) for c in r.tool_calls] == [("tu_9", "read_file", {"path": "ledger.csv"})]
    assert r.replay[0] == {"type": "thinking", "thinking": "hm", "signature": "s"}
    assert r.provider_metadata["cache_read_input_tokens"] == 100 and r.provider_metadata["truncated"] is False
    assert r.provider_metadata["n_tool_calls"] == 1 and r.model_digest == "claude-opus-5-2026"
    prov._client.messages.create.return_value = _Resp(content=[], stop_reason="refusal", model="m", usage=SimpleNamespace(input_tokens=1, output_tokens=0))
    r = prov.chat_tools(messages=[UserMsg("u")], tools=TOOLS, model="m", options=OPTS)
    assert r.ok and r.stop == "refusal" and r.provider_metadata["stop_reason"] == "refusal" and r.tool_calls == []
    prov._client.messages.create.return_value = _Resp(content=[_Block(type="text", text="partial")], stop_reason="max_tokens", model="m", usage=SimpleNamespace(input_tokens=1, output_tokens=4096))
    r = prov.chat_tools(messages=[UserMsg("u")], tools=TOOLS, model="m", options=OPTS)
    assert r.provider_metadata["truncated"] is True and r.stop == "max_tokens"
    prov._client.messages.create.side_effect = _FakeSDK.APIStatusError()
    r = prov.chat_tools(messages=[UserMsg("u")], tools=TOOLS, model="m", options=OPTS)
    assert not r.ok and r.error.startswith("http_500")


# -- OpenAI ------------------------------------------------------------------------------ #


def test_openai_request_shape_and_replay():
    replay = {"role": "assistant", "content": None, "tool_calls": [
        {"id": "tu_1", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "ledger.csv"}'}},
        {"id": "tu_2", "type": "function", "function": {"name": "run_check", "arguments": "{}"}},
    ]}
    kw = OpenAIProvider._tools_request(messages=_conversation(replay), tools=TOOLS, model="gpt-5.5", options=OPTS)
    assert kw["model"] == "gpt-5.5" and kw["max_completion_tokens"] == 4096 and kw["timeout"] == 60
    assert "temperature" not in kw and "top_p" not in kw and "response_format" not in kw
    assert kw["messages"] == [
        {"role": "system", "content": "You are the reporting assistant."},
        {"role": "user", "content": "Bring the report into agreement."},
        replay,
        {"role": "tool", "tool_call_id": "tu_1", "content": "a,b\n1,2\n"},
        {"role": "tool", "tool_call_id": "tu_2", "content": "Error: x"},
        {"role": "user", "content": "Workspace files:\n- report.csv"},
    ]
    assert kw["tools"][0] == {"type": "function", "function": {
        "name": "read_file", "description": "Return the contents of a workspace file.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"], "additionalProperties": False},
        "strict": True}}


def _openai_resp(tool_calls, *, content=None, finish="tool_calls", refusal=None, reasoning=7):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls, refusal=refusal)
    return _Resp(choices=[SimpleNamespace(message=msg, finish_reason=finish)], model="gpt-5.5-2026",
                 usage=SimpleNamespace(prompt_tokens=200, completion_tokens=40,
                                       prompt_tokens_details=SimpleNamespace(cached_tokens=64),
                                       completion_tokens_details=SimpleNamespace(reasoning_tokens=reasoning)))


def test_openai_parse_calls_malformed_arguments_refusal_and_length():
    prov = _openai()
    prov._client.chat.completions.create.return_value = _openai_resp([
        SimpleNamespace(id="call_1", function=SimpleNamespace(name="read_file", arguments='{"path": "ledger.csv"}')),
        SimpleNamespace(id="call_2", function=SimpleNamespace(name="run_check", arguments="{not json")),
    ])
    r = prov.chat_tools(messages=[SystemMsg("s"), UserMsg("u")], tools=TOOLS, model="gpt-5.5", options=OPTS)
    assert r.ok and r.stop == "tool_use" and r.model_digest == "gpt-5.5-2026"
    assert r.tool_calls[0].arguments == {"path": "ledger.csv"} and r.tool_calls[0].arguments_error is None
    assert r.tool_calls[1].arguments == {} and r.tool_calls[1].arguments_error.startswith("json")
    assert r.replay["tool_calls"][1]["function"]["arguments"] == "{not json"  # replayed verbatim
    m = r.provider_metadata
    assert m["input_tokens"] == 136 and m["cached_input_tokens"] == 64 and m["reasoning_tokens"] == 7 and m["n_tool_calls"] == 2
    prov._client.chat.completions.create.return_value = _openai_resp(None, content="", finish="length")
    r = prov.chat_tools(messages=[UserMsg("u")], tools=TOOLS, model="gpt-5.5", options=OPTS)
    assert r.provider_metadata["truncated"] is True and r.stop == "max_tokens" and r.tool_calls == []
    prov._client.chat.completions.create.return_value = _openai_resp(None, content=None, finish="stop", refusal="I can't help with that.")
    r = prov.chat_tools(messages=[UserMsg("u")], tools=TOOLS, model="gpt-5.5", options=OPTS)
    assert r.provider_metadata["refusal"] is True and r.stop == "refusal" and r.text == "I can't help with that."
    prov._client.chat.completions.create.return_value = _openai_resp(None, content="All done.", finish="stop")
    r = prov.chat_tools(messages=[UserMsg("u")], tools=TOOLS, model="gpt-5.5", options=OPTS)
    assert r.stop == "end_turn" and r.tool_calls == [] and r.text == "All done."


# -- Ollama ------------------------------------------------------------------------------- #


def test_ollama_request_shape_ids_and_tools_unsupported(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"], captured["payload"] = url, json
        return SimpleNamespace(status_code=200, text="", json=lambda: {
            "model": "qwen3:8b", "done_reason": "stop",
            "message": {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "read_file", "arguments": {"path": "ledger.csv"}}},
                {"function": {"name": "run_check", "arguments": "oops"}},
            ]},
            "prompt_eval_count": 50, "eval_count": 12,
        })

    monkeypatch.setattr(httpx, "post", fake_post)
    prov = OllamaProvider(host="http://h:1")
    replay = {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "ledger.csv"}}}]}
    r = prov.chat_tools(messages=_conversation(replay), tools=TOOLS, model="qwen3:8b", options=GenerationOptions(think=False))
    p = captured["payload"]
    assert captured["url"] == "http://h:1/api/chat" and "format" not in p and p["stream"] is False and p["think"] is False
    assert p["tools"][0] == {"type": "function", "function": {"name": "read_file", "description": "Return the contents of a workspace file.",
                                                              "parameters": TOOLS[0].parameters}}
    assert p["messages"][2] == replay
    assert p["messages"][3] == {"role": "tool", "content": "a,b\n1,2\n", "tool_name": "read_file"}
    assert p["messages"][5] == {"role": "user", "content": "Workspace files:\n- report.csv"}
    assert r.ok and len(r.tool_calls) == 2 and r.tool_calls[0].id != r.tool_calls[1].id and r.tool_calls[0].id.startswith("ol_")
    assert r.tool_calls[1].arguments_error and r.provider_metadata["prompt_eval_count"] == 50 and r.stop == "tool_use"

    monkeypatch.setattr(httpx, "post", lambda url, json=None, timeout=None: SimpleNamespace(
        status_code=400, text='{"error":"registry.ollama.ai/library/llama2:latest does not support tools"}', json=lambda: {}))
    r = prov.chat_tools(messages=[UserMsg("u")], tools=TOOLS, model="llama2", options=GenerationOptions())
    assert not r.ok and r.error.startswith("tools_unsupported")

    monkeypatch.setattr(httpx, "post", lambda url, json=None, timeout=None: SimpleNamespace(
        status_code=200, text="", json=lambda: {"model": "m", "done_reason": "length", "message": {"role": "assistant", "content": "x"}}))
    r = prov.chat_tools(messages=[UserMsg("u")], tools=TOOLS, model="m", options=GenerationOptions())
    assert r.provider_metadata["truncated"] is True and r.stop == "max_tokens"


def test_base_provider_reports_tools_unsupported():
    from ombs.providers.base import ProviderClient

    class Bare(ProviderClient):
        name = "bare"

        def generate(self, *, system, prompt, model, options):
            raise NotImplementedError

    r = Bare().chat_tools(messages=[UserMsg("u")], tools=TOOLS, model="m", options=GenerationOptions())
    assert not r.ok and r.error.startswith("tools_unsupported") and Bare.supports_tools is False


@pytest.mark.parametrize("provider_cls", [AnthropicProvider, OpenAIProvider, OllamaProvider])
def test_all_three_declare_native_tool_support(provider_cls):
    assert provider_cls.supports_tools is True
