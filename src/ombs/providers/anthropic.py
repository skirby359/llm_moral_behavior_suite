"""Anthropic (Claude) frontier provider — brief §2, Phase 8.

Implemented against the same ``ProviderClient`` interface as Ollama, so the
runner, multi-turn runner, and tool runner use it with no changes.

Notes specific to current Claude models (per the Claude API reference):
- Opus 4.8/4.7 reject ``temperature``/``top_p``/``top_k`` and ``budget_tokens``
  (HTTP 400). We therefore omit all sampling params; behavior is steered by the
  prompt. ``GenerationOptions.temperature``/``top_p`` are recorded in run
  metadata but not sent.
- Thinking is left off (omitted); the prompt already requires JSON-only output
  and the shared JSON extractor strips any stray prose defensively.
- ``max_tokens`` here is small (~800), so non-streaming is safe.

``generation.format`` support was added 2026-08-04. Before that this provider
**silently ignored it**: a config setting ``format: "schema"`` got unconstrained
output with no warning, which would have made any Ollama-vs-Anthropic comparison
under that setting quietly non-comparable. It is now sent as
``output_config.format`` (probed: Opus 5 rejects the raw pydantic schema with
"For 'object' type, 'additionalProperties' must be explicitly set to false", and
accepts it after ``utils.json_schema.to_strict_schema`` — the same transform the
OpenAI path needs).

No previously-recorded run is affected: every Anthropic config in ``configs/``
had ``format: null``, so the ignored value was always a no-op.

Auth: ``anthropic.Anthropic()`` reads ``ANTHROPIC_API_KEY`` from the env.
"""

from __future__ import annotations

import json
import os
import time

from ..utils.json_schema import to_strict_schema
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

DEFAULT_MODEL = "claude-opus-4-8"

_STOP_MAP = {"tool_use": "tool_use", "end_turn": "end_turn", "max_tokens": "max_tokens", "refusal": "refusal"}


class AnthropicProvider(ProviderClient):
    name = "anthropic"

    def __init__(self):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise ImportError(
                "anthropic SDK not installed. Run: uv sync --extra frontier"
            ) from exc
        from ..utils.env import load_dotenv

        load_dotenv()  # safety net for non-CLI use; CLI also loads it at startup
        if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to a .env file in the project "
                "root (copy .env.example to .env), or export it in your shell:\n"
                '  $env:ANTHROPIC_API_KEY = "sk-ant-..."'
            )
        self._anthropic = anthropic
        # reads ANTHROPIC_API_KEY (loaded from .env by the CLI / safety net above)
        self._client = anthropic.Anthropic()

    def _text_from_content(self, content) -> str:
        parts = [b.text for b in content if getattr(b, "type", None) == "text"]
        return "\n".join(parts)

    @staticmethod
    def _output_config(fmt: str | dict | None) -> dict | None:
        """Map this repo's ``generation.format`` onto ``output_config``.

        A dict (what ``format: "schema"`` resolves to) becomes a json_schema
        constraint. ``"json"`` has no Anthropic equivalent — there is no free
        JSON mode — so it is rejected loudly rather than silently downgraded to
        unconstrained decoding, which is the bug this method was added to fix.
        """
        if not fmt:
            return None
        if isinstance(fmt, dict):
            return {"format": {"type": "json_schema", "schema": to_strict_schema(fmt)}}
        raise ValueError(
            f"generation.format={fmt!r} has no Anthropic equivalent (no free JSON mode). "
            'Use format: "schema" for a constrained shape, or null for unconstrained.'
        )

    def _call(
        self, *, system: str, messages: list[dict], model: str, options: GenerationOptions
    ) -> ModelCallResult:
        anthropic = self._anthropic
        kwargs = {
            "model": model or DEFAULT_MODEL,
            "max_tokens": options.max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        try:
            oc = self._output_config(options.format)
        except ValueError as exc:
            return ModelCallResult(model=model, raw_response="", ok=False, error=str(exc))
        if oc:
            kwargs["output_config"] = oc
        start = time.perf_counter()
        try:
            resp = self._client.messages.create(**kwargs)
        except anthropic.APIStatusError as exc:
            return ModelCallResult(
                model=model, raw_response="", ok=False,
                latency_seconds=time.perf_counter() - start,
                error=f"http_{exc.status_code}: {getattr(exc, 'message', str(exc))[:300]}",
            )
        except anthropic.APIConnectionError as exc:
            return ModelCallResult(model=model, raw_response="", ok=False,
                                   error=f"connect_error: {exc}")
        except Exception as exc:  # noqa: BLE001 - never kill a batch on one bad call
            return ModelCallResult(
                model=model, raw_response="", ok=False,
                latency_seconds=time.perf_counter() - start,
                error=f"{type(exc).__name__}: {str(exc)[:300]}",
            )
        latency = time.perf_counter() - start

        raw = self._text_from_content(resp.content)
        meta = {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "stop_reason": resp.stop_reason,
            # max_tokens caps thinking + output together; a cut-off response is not a
            # measurement (same contract as the OpenAI provider's finish_reason == "length").
            "truncated": resp.stop_reason == "max_tokens",
            "sampling_params_omitted": True,  # Opus 4.8/4.7 reject temperature/top_p
        }
        return ModelCallResult(
            model=model, raw_response=raw, ok=True, latency_seconds=latency,
            model_digest=resp.model, provider_metadata=meta,
        )

    def generate(
        self, *, system: str, prompt: str, model: str, options: GenerationOptions
    ) -> ModelCallResult:
        return self._call(
            system=system,
            messages=[{"role": "user", "content": prompt}],
            model=model, options=options,
        )

    def chat(
        self, *, messages: list[dict], model: str, options: GenerationOptions
    ) -> ModelCallResult:
        # Ollama-style messages may carry a leading system-role entry; Anthropic
        # takes the system prompt as a separate parameter.
        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        convo = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m["role"] in ("user", "assistant")
        ]
        return self._call(
            system="\n\n".join(system_parts),
            messages=convo, model=model, options=options,
        )

    # -- native tool calling (Wave 3) --------------------------------------------- #

    supports_tools = True

    @staticmethod
    def _tools_request(
        *, messages: list, tools: list[ToolSpec], model: str, options: GenerationOptions
    ) -> dict:
        """Pure: the exact kwargs for ``messages.create``. Tested against the wire shape.

        Assistant turns are replayed verbatim from the stored response content (text,
        tool_use and thinking blocks, unchanged); all of a turn's tool results go in ONE
        user message, followed by an optional text block. No thinking parameter is sent
        (Opus 5 runs its default; ``thinking: disabled`` is documented to push tool calls
        into visible text). Sampling params are omitted as in ``_call``.
        """
        system_parts = [m.text for m in messages if isinstance(m, SystemMsg)]
        convo: list[dict] = []
        for m in messages:
            if isinstance(m, UserMsg):
                convo.append({"role": "user", "content": [{"type": "text", "text": m.text}]})
            elif isinstance(m, AssistantMsg):
                content = m.replay if m.replay is not None else [{"type": "text", "text": m.text or "(no content)"}]
                convo.append({"role": "assistant", "content": content})
            elif isinstance(m, ToolResultsMsg):
                blocks: list[dict] = []
                for r in m.results:
                    block = {"type": "tool_result", "tool_use_id": r.call_id, "content": r.content}
                    if r.is_error:
                        block["is_error"] = True
                    blocks.append(block)
                if m.extra_text:
                    blocks.append({"type": "text", "text": m.extra_text})
                convo.append({"role": "user", "content": blocks})
        kwargs: dict = {
            "model": model or DEFAULT_MODEL,
            "max_tokens": options.max_tokens,
            "messages": convo,
            "tools": [
                {"name": t.name, "description": t.description, "input_schema": to_strict_schema(t.parameters)}
                for t in tools
            ],
        }
        if system_parts:
            text = "\n\n".join(system_parts)
            if options.prompt_caching:
                kwargs["system"] = [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]
            else:
                kwargs["system"] = text
        if options.prompt_caching and convo and convo[-1]["role"] == "user" and convo[-1]["content"]:
            convo[-1]["content"][-1]["cache_control"] = {"type": "ephemeral"}
        return kwargs

    @staticmethod
    def _parse_tools_response(resp, *, model: str, latency: float) -> ToolCallResult:
        text_parts, calls, replay = [], [], []
        for b in resp.content:
            btype = getattr(b, "type", None)
            if btype == "text":
                text_parts.append(b.text)
            elif btype == "tool_use":
                args = b.input if isinstance(b.input, dict) else {}
                calls.append(ToolCall(id=b.id, name=b.name, arguments=dict(args)))
            replay.append(b.model_dump(exclude_none=True) if hasattr(b, "model_dump") else dict(vars(b)))
        u = resp.usage
        meta = {
            "input_tokens": getattr(u, "input_tokens", 0) or 0,
            "output_tokens": getattr(u, "output_tokens", 0) or 0,
            "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
            "stop_reason": resp.stop_reason,
            "truncated": resp.stop_reason == "max_tokens",
            "sampling_params_omitted": True,
            "n_tool_calls": len(calls),
        }
        raw = resp.model_dump_json() if hasattr(resp, "model_dump_json") else json.dumps(replay)
        return ToolCallResult(
            model=model, raw_response=raw, ok=True, latency_seconds=latency,
            model_digest=getattr(resp, "model", None), provider_metadata=meta,
            text="\n".join(text_parts), tool_calls=calls, replay=replay,
            stop=_STOP_MAP.get(resp.stop_reason, "other"),
        )

    def chat_tools(
        self, *, messages: list, tools: list[ToolSpec], model: str, options: GenerationOptions
    ) -> ToolCallResult:
        anthropic = self._anthropic
        kwargs = self._tools_request(messages=messages, tools=tools, model=model, options=options)
        start = time.perf_counter()
        try:
            resp = self._client.messages.create(**kwargs)
        except anthropic.APIStatusError as exc:
            return ToolCallResult(model=model, raw_response="", ok=False, latency_seconds=time.perf_counter() - start,
                                  error=f"http_{exc.status_code}: {getattr(exc, 'message', str(exc))[:300]}")
        except anthropic.APIConnectionError as exc:
            return ToolCallResult(model=model, raw_response="", ok=False, error=f"connect_error: {exc}")
        except Exception as exc:  # noqa: BLE001
            return ToolCallResult(model=model, raw_response="", ok=False, latency_seconds=time.perf_counter() - start,
                                  error=f"{type(exc).__name__}: {str(exc)[:300]}")
        return self._parse_tools_response(resp, model=model, latency=time.perf_counter() - start)
