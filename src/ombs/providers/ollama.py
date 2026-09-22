"""Ollama local-HTTP provider.

Calls ``POST {host}/api/generate`` (single-turn) and ``/api/chat`` (multi-turn,
non-streaming). Connection refused, model-not-found, and timeouts are caught and
returned as ``ok=False`` results so the runner records them as failures rather
than crashing the batch.

Some non-reasoning models reject the top-level ``think`` flag; if a request
fails with a think-related error we transparently retry once without it.
"""

from __future__ import annotations

import os
import time
import uuid

import httpx

from .base import (
    AssistantMsg,
    GenerationOptions,
    ModelCallResult,
    ProviderClient,
    SystemMsg,
    ToolCall,
    ToolCallResult,
    ToolResultsMsg,
    ToolSpec,
    UserMsg,
)

DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def _options_dict(options: GenerationOptions) -> dict:
    opts = {
        "temperature": options.temperature,
        "top_p": options.top_p,
        "num_predict": options.max_tokens,
    }
    if options.seed is not None:
        opts["seed"] = options.seed
    return opts


class OllamaProvider(ProviderClient):
    name = "ollama"

    def __init__(self, host: str = DEFAULT_HOST):
        self.host = host.rstrip("/")

    def _post(self, endpoint: str, payload: dict, timeout: int) -> ModelCallResult:
        url = f"{self.host}{endpoint}"
        model = payload.get("model", "")
        start = time.perf_counter()
        try:
            resp = httpx.post(url, json=payload, timeout=timeout)
        except httpx.ConnectError as exc:
            return ModelCallResult(model=model, raw_response="", ok=False,
                                   error=f"connect_error: {exc}")
        except httpx.TimeoutException:
            return ModelCallResult(model=model, raw_response="", ok=False,
                                   latency_seconds=time.perf_counter() - start,
                                   error=f"timeout after {timeout}s")
        latency = time.perf_counter() - start

        if resp.status_code != 200:
            return ModelCallResult(model=model, raw_response=resp.text, ok=False,
                                   latency_seconds=latency,
                                   error=f"http_{resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        # /api/generate -> data["response"]; /api/chat -> data["message"]["content"]
        raw = data.get("response")
        if raw is None:
            raw = (data.get("message") or {}).get("content", "")
        meta = {
            k: data.get(k)
            for k in ("total_duration", "eval_count", "prompt_eval_count", "done_reason")
            if k in data
        }
        thinking = data.get("thinking") or (data.get("message") or {}).get("thinking")
        if thinking:
            meta["thinking_present"] = True
        return ModelCallResult(model=model, raw_response=raw, ok=True,
                               latency_seconds=latency, model_digest=data.get("model"),
                               provider_metadata=meta)

    def _post_with_think_fallback(
        self, endpoint: str, payload: dict, timeout: int
    ) -> ModelCallResult:
        result = self._post(endpoint, payload, timeout)
        if (
            not result.ok
            and "think" in payload
            and result.error
            and result.error.startswith("http_4")
            and "think" in result.error.lower()
        ):
            payload = {k: v for k, v in payload.items() if k != "think"}
            return self._post(endpoint, payload, timeout)
        return result

    def generate(
        self, *, system: str, prompt: str, model: str, options: GenerationOptions
    ) -> ModelCallResult:
        payload: dict = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": _options_dict(options),
            "think": options.think,
        }
        if options.format:
            payload["format"] = options.format
        return self._post_with_think_fallback(
            "/api/generate", payload, options.timeout_seconds
        )

    def chat(
        self, *, messages: list[dict], model: str, options: GenerationOptions
    ) -> ModelCallResult:
        """Multi-turn chat. ``messages`` is a list of {role, content} dicts."""
        payload: dict = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": _options_dict(options),
            "think": options.think,
        }
        if options.format:
            payload["format"] = options.format
        return self._post_with_think_fallback(
            "/api/chat", payload, options.timeout_seconds
        )

    def list_models(self) -> list[str]:
        try:
            resp = httpx.get(f"{self.host}/api/tags", timeout=10)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except (httpx.HTTPError, KeyError):
            return []

    # -- native tool calling (Wave 3) --------------------------------------------- #

    supports_tools = True

    @staticmethod
    def _tools_request(*, messages: list, tools: list[ToolSpec], model: str, options: GenerationOptions) -> dict:
        """Pure: the exact ``/api/chat`` payload. Ollama's native API carries no call ids;
        tool results are ``role: tool`` messages with ``tool_name``, in call order. ``format``
        is never combined with ``tools``."""
        msgs: list[dict] = []
        for m in messages:
            if isinstance(m, SystemMsg):
                msgs.append({"role": "system", "content": m.text})
            elif isinstance(m, UserMsg):
                msgs.append({"role": "user", "content": m.text})
            elif isinstance(m, AssistantMsg):
                msgs.append(m.replay if m.replay is not None else {"role": "assistant", "content": m.text or ""})
            elif isinstance(m, ToolResultsMsg):
                for r in m.results:
                    msgs.append({"role": "tool", "content": r.content, "tool_name": r.name})
                if m.extra_text:
                    msgs.append({"role": "user", "content": m.extra_text})
        return {
            "model": model,
            "messages": msgs,
            "tools": [
                {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
                for t in tools
            ],
            "stream": False,
            "options": _options_dict(options),
            "think": options.think,
        }

    @staticmethod
    def _parse_tools_response(data: dict, *, model: str, latency: float) -> ToolCallResult:
        msg = data.get("message") or {}
        calls: list[ToolCall] = []
        replay_calls: list[dict] = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            args = fn.get("arguments")
            err = None
            if not isinstance(args, dict):
                err, args = "arguments not a JSON object", {}
            calls.append(ToolCall(id=f"ol_{uuid.uuid4().hex[:8]}", name=str(fn.get("name", "")), arguments=args,
                                  arguments_error=err))
            replay_calls.append({"function": {"name": fn.get("name", ""), "arguments": args}})
        text = msg.get("content") or ""
        replay: dict = {"role": "assistant", "content": text}
        if replay_calls:
            replay["tool_calls"] = replay_calls
        meta = {k: data.get(k) for k in ("total_duration", "eval_count", "prompt_eval_count", "done_reason") if k in data}
        if data.get("done_reason") == "length":
            meta["truncated"] = True
        if msg.get("thinking"):
            meta["thinking_present"] = True
        meta["n_tool_calls"] = len(calls)
        stop = "max_tokens" if data.get("done_reason") == "length" else ("tool_use" if calls else "end_turn")
        return ToolCallResult(model=model, raw_response=httpx_json_dumps(data), ok=True, latency_seconds=latency,
                              model_digest=data.get("model"), provider_metadata=meta, text=text,
                              tool_calls=calls, replay=replay, stop=stop)

    def chat_tools(self, *, messages: list, tools: list[ToolSpec], model: str, options: GenerationOptions) -> ToolCallResult:
        payload = self._tools_request(messages=messages, tools=tools, model=model, options=options)
        url = f"{self.host}/api/chat"
        start = time.perf_counter()
        try:
            resp = httpx.post(url, json=payload, timeout=options.timeout_seconds)
        except httpx.ConnectError as exc:
            return ToolCallResult(model=model, raw_response="", ok=False, error=f"connect_error: {exc}")
        except httpx.TimeoutException:
            return ToolCallResult(model=model, raw_response="", ok=False, latency_seconds=time.perf_counter() - start,
                                  error=f"timeout after {options.timeout_seconds}s")
        latency = time.perf_counter() - start
        if resp.status_code != 200:
            body = resp.text[:300]
            if "does not support tools" in body.lower():
                return ToolCallResult(model=model, raw_response=resp.text, ok=False, latency_seconds=latency,
                                      error=f"tools_unsupported: {body}")
            return ToolCallResult(model=model, raw_response=resp.text, ok=False, latency_seconds=latency,
                                  error=f"http_{resp.status_code}: {body}")
        return self._parse_tools_response(resp.json(), model=model, latency=latency)


def httpx_json_dumps(data: dict) -> str:
    import json

    return json.dumps(data, ensure_ascii=False)
