"""OpenAI (GPT) frontier provider — brief §2, Phase 8.

Implemented against the same ``ProviderClient`` interface as Ollama and
Anthropic, so the runner, multi-turn runner, and tool runner use it unchanged.

PROBED, NOT ASSUMED. Every claim below was established by direct API call on
2026-08-04 against ``gpt-5.5`` (which resolves to ``gpt-5.5-2026-04-23``);
none of it is carried over from the Anthropic provider or from documentation:

- ``chat.completions`` works. (``responses`` also works; chat.completions is
  used because it maps 1:1 onto this repo's messages-in / text-out interface.)
- ``max_tokens`` is **rejected** with HTTP 400
  ("Unsupported parameter: 'max_tokens' ... Use 'max_completion_tokens'").
  ``GenerationOptions.max_tokens`` is therefore sent as
  ``max_completion_tokens``, which caps **reasoning + visible output together**.
- ``temperature`` accepts **only its default of 1**; ``temperature=0`` returns
  400 ("does not support 0 with this model"). ``top_p`` is rejected outright.
  Both are therefore omitted, exactly as in the Anthropic provider, and
  behavior is steered by the prompt.
- ``response_format`` with ``json_schema`` + ``strict: True`` works, but strict
  mode constrains the schema shape — see ``_to_strict_schema``.
- The ``system`` role is accepted (no need for the ``developer`` role).
- Usage: ``prompt_tokens`` / ``completion_tokens`` (the latter **includes**
  reasoning tokens), plus ``prompt_tokens_details.cached_tokens`` and
  ``completion_tokens_details.reasoning_tokens``.

Consequence worth carrying into the analysis: because temperature is pinned at
its default, **the temp-0.0 convergence positive control cannot be run on
gpt-5.5 either.** That limitation is now true of both frontier vendors rather
than being an Anthropic quirk.

Two failure modes are surfaced in ``provider_metadata`` rather than hidden,
because both would otherwise be indistinguishable from a content failure
downstream:

- ``finish_reason == "length"`` sets ``truncated``. A reasoning model can spend
  the whole ``max_completion_tokens`` budget thinking and return empty content,
  which would read as a JSON parse failure.
- a populated ``message.refusal`` sets ``refusal`` and the refusal text becomes
  ``raw_response``. That is a real behavioral observation, not a transport
  error, so ``ok`` stays True and the row is scored as a parse failure with the
  reason visible in the transcript.

Auth: ``openai.OpenAI()`` reads ``OPENAI_API_KEY`` from the env.
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

DEFAULT_MODEL = "gpt-5.5"

_STOP_MAP = {"tool_calls": "tool_use", "stop": "end_turn", "length": "max_tokens", "content_filter": "refusal"}


def _response_format(fmt: str | dict | None) -> dict | None:
    """Map this repo's ``generation.format`` onto OpenAI's ``response_format``.

    ``"json"`` -> free JSON mode (the analogue of Ollama's ``format: "json"``).
    A dict -> strict ``json_schema`` (the analogue of Ollama structured
    outputs), which is what ``generation.format: "schema"`` resolves to.
    """
    if not fmt:
        return None
    if fmt == "json":
        return {"type": "json_object"}
    if isinstance(fmt, dict):
        return {
            "type": "json_schema",
            "json_schema": {
                "name": fmt.get("title", "response").replace(" ", "_"),
                "schema": to_strict_schema(fmt),
                "strict": True,
            },
        }
    # An unrecognised string would silently disable the constraint if ignored.
    raise ValueError(f"unsupported generation.format for the openai provider: {fmt!r}")


def _drop_additional_properties(schema: dict) -> dict:
    """The strict transform's ``additionalProperties: false`` removed at every level. Used only
    when a subclass sets ``STRICT_TOOLS = False`` because its endpoint rejects the keyword."""
    if not isinstance(schema, dict):
        return schema
    out = {k: v for k, v in schema.items() if k != "additionalProperties"}
    if isinstance(out.get("properties"), dict):
        out["properties"] = {k: _drop_additional_properties(v) for k, v in out["properties"].items()}
    if isinstance(out.get("items"), dict):
        out["items"] = _drop_additional_properties(out["items"])
    return out


class OpenAIProvider(ProviderClient):
    name = "openai"
    #: Request-shape hooks. Subclasses for OpenAI-compatible endpoints (``google.py``) override
    #: these and nothing else; the parent's values are the PROBED gpt-5.5 shape pinned by
    #: tests/test_tool_adapters.py.
    TOKEN_BUDGET_KEY = "max_completion_tokens"
    STRICT_TOOLS = True
    default_model: str | None = DEFAULT_MODEL

    def _resolve_model(self, model: str) -> str:
        if model:
            return model
        if self.default_model:
            return self.default_model
        raise ValueError(f"provider {self.name!r} has no default model; the config must name one")

    def __init__(self):
        try:
            import openai
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise ImportError(
                "openai SDK not installed. Run: uv sync --extra frontier"
            ) from exc
        from ..utils.env import load_dotenv

        load_dotenv()  # safety net for non-CLI use; CLI also loads it at startup
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to a .env file in the project "
                "root (copy .env.example to .env), or export it in your shell:\n"
                '  $env:OPENAI_API_KEY = "sk-..."'
            )
        self._openai = openai
        self._client = openai.OpenAI()

    def _call(
        self, *, messages: list[dict], model: str, options: GenerationOptions
    ) -> ModelCallResult:
        openai = self._openai
        model = self._resolve_model(model)
        kwargs: dict = {
            "model": model,
            "messages": messages,
            # PROBED: `max_tokens` is a 400 on this model. This budget covers
            # reasoning tokens as well as visible output.
            self.TOKEN_BUDGET_KEY: options.max_tokens,
            "timeout": options.timeout_seconds,
        }
        # PROBED: temperature accepts only its default (1) and top_p is
        # rejected, so neither is sent. `options.temperature` / `.top_p` are
        # still recorded in run metadata for provenance.
        try:
            rf = _response_format(options.format)
        except ValueError as exc:
            return ModelCallResult(model=model, raw_response="", ok=False, error=str(exc))
        if rf:
            kwargs["response_format"] = rf

        start = time.perf_counter()
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except openai.APIStatusError as exc:
            return ModelCallResult(
                model=model, raw_response="", ok=False,
                latency_seconds=time.perf_counter() - start,
                error=f"http_{exc.status_code}: {str(getattr(exc, 'message', exc))[:300]}",
            )
        except openai.APIConnectionError as exc:
            return ModelCallResult(model=model, raw_response="", ok=False,
                                   error=f"connect_error: {exc}")
        except Exception as exc:  # noqa: BLE001 - never kill a batch on one bad call
            return ModelCallResult(
                model=model, raw_response="", ok=False,
                latency_seconds=time.perf_counter() - start,
                error=f"{type(exc).__name__}: {str(exc)[:300]}",
            )
        latency = time.perf_counter() - start

        choice = resp.choices[0]
        raw = choice.message.content or ""
        refusal = getattr(choice.message, "refusal", None)
        if refusal:
            # A behavioral observation, not a transport failure. Surfaced in the
            # transcript; the row lands as a parse failure with a visible reason.
            raw = refusal

        u = resp.usage
        details = getattr(u, "prompt_tokens_details", None)
        out_details = getattr(u, "completion_tokens_details", None)
        cached = (getattr(details, "cached_tokens", 0) or 0) if details else 0
        prompt_tokens = u.prompt_tokens or 0
        meta = {
            # `input_tokens` excludes the cached subset so the two are priced
            # separately without double-counting (OpenAI bills cached prompt
            # tokens at 0.1x, and does not bill cache writes at all).
            "input_tokens": max(prompt_tokens - cached, 0),
            "cached_input_tokens": cached,
            "prompt_tokens_total": prompt_tokens,
            "output_tokens": u.completion_tokens or 0,  # includes reasoning tokens
            "reasoning_tokens": (getattr(out_details, "reasoning_tokens", 0) or 0)
            if out_details
            else 0,
            "finish_reason": choice.finish_reason,
            "sampling_params_omitted": True,  # PROBED: temperature/top_p rejected
        }
        if choice.finish_reason == "length":
            meta["truncated"] = True
        if refusal:
            meta["refusal"] = True

        return ModelCallResult(
            model=model, raw_response=raw, ok=True, latency_seconds=latency,
            model_digest=resp.model, provider_metadata=meta,
        )

    def generate(
        self, *, system: str, prompt: str, model: str, options: GenerationOptions
    ) -> ModelCallResult:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self._call(messages=messages, model=model, options=options)

    def chat(
        self, *, messages: list[dict], model: str, options: GenerationOptions
    ) -> ModelCallResult:
        # Ollama-style message lists carry a leading system entry, which the
        # Chat Completions API accepts as-is (PROBED).
        return self._call(
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            model=model,
            options=options,
        )

    # -- native tool calling (Wave 3) --------------------------------------------- #

    supports_tools = True

    @classmethod
    def _declare_tool(cls, t: ToolSpec) -> dict:
        fn: dict = {"name": t.name, "description": t.description}
        if cls.STRICT_TOOLS:
            fn["parameters"] = to_strict_schema(t.parameters)
            fn["strict"] = True
        else:
            fn["parameters"] = _drop_additional_properties(to_strict_schema(t.parameters))
        return {"type": "function", "function": fn}

    @classmethod
    def _tools_request(
        cls, *, messages: list, tools: list[ToolSpec], model: str, options: GenerationOptions
    ) -> dict:
        """Pure: the exact kwargs for ``chat.completions.create``.

        Every ``tool_calls`` id in an assistant turn is answered by exactly one
        ``role: tool`` message before anything else (the API 400s otherwise); a text
        block accompanying the results becomes a following user message. Assistant
        turns are replayed from the stored message dict. Functions are declared
        ``strict`` with the shared strict-schema transform; arguments are still
        validated client-side because OpenAI documents that parallel calls may not
        honour strict schemas.
        """
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
                    msgs.append({"role": "tool", "tool_call_id": r.call_id, "content": r.content})
                if m.extra_text:
                    msgs.append({"role": "user", "content": m.extra_text})
        return {
            "model": model or (cls.default_model or DEFAULT_MODEL),
            "messages": msgs,
            cls.TOKEN_BUDGET_KEY: options.max_tokens,
            "timeout": options.timeout_seconds,
            "tools": [cls._declare_tool(t) for t in tools],
        }

    @staticmethod
    def _parse_tools_response(resp, *, model: str, latency: float) -> ToolCallResult:
        choice = resp.choices[0]
        msg = choice.message
        calls: list[ToolCall] = []
        replay_calls: list[dict] = []
        for tc in getattr(msg, "tool_calls", None) or []:
            fn = tc.function
            raw_args = fn.arguments if isinstance(fn.arguments, str) else json.dumps(fn.arguments or {})
            args, err = {}, None
            try:
                parsed = json.loads(raw_args) if raw_args else {}
                if isinstance(parsed, dict):
                    args = parsed
                else:
                    err = "arguments not a JSON object"
            except json.JSONDecodeError as exc:
                err = f"json: {exc.msg}"
            calls.append(ToolCall(id=tc.id, name=fn.name, arguments=args, raw_arguments=raw_args, arguments_error=err))
            replay_calls.append({"id": tc.id, "type": "function", "function": {"name": fn.name, "arguments": raw_args}})
        text = msg.content or ""
        refusal = getattr(msg, "refusal", None)
        replay: dict = {"role": "assistant", "content": text or None}
        if replay_calls:
            replay["tool_calls"] = replay_calls
        u = resp.usage
        details = getattr(u, "prompt_tokens_details", None)
        out_details = getattr(u, "completion_tokens_details", None)
        cached = (getattr(details, "cached_tokens", 0) or 0) if details else 0
        prompt_tokens = getattr(u, "prompt_tokens", 0) or 0
        meta = {
            "input_tokens": max(prompt_tokens - cached, 0),
            "cached_input_tokens": cached,
            "prompt_tokens_total": prompt_tokens,
            "output_tokens": getattr(u, "completion_tokens", 0) or 0,
            "reasoning_tokens": (getattr(out_details, "reasoning_tokens", 0) or 0) if out_details else 0,
            "finish_reason": choice.finish_reason,
            "sampling_params_omitted": True,
            "n_tool_calls": len(calls),
        }
        if choice.finish_reason == "length":
            meta["truncated"] = True
        if refusal:
            meta["refusal"] = True
            text = refusal
        raw = resp.model_dump_json() if hasattr(resp, "model_dump_json") else json.dumps(replay)
        return ToolCallResult(
            model=model, raw_response=raw, ok=True, latency_seconds=latency,
            model_digest=getattr(resp, "model", None), provider_metadata=meta,
            text=text, tool_calls=calls, replay=replay,
            stop=("refusal" if refusal else _STOP_MAP.get(choice.finish_reason, "other")),
        )

    def chat_tools(
        self, *, messages: list, tools: list[ToolSpec], model: str, options: GenerationOptions
    ) -> ToolCallResult:
        openai = self._openai
        model = self._resolve_model(model)
        kwargs = self._tools_request(messages=messages, tools=tools, model=model, options=options)
        start = time.perf_counter()
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except openai.APIStatusError as exc:
            return ToolCallResult(model=model, raw_response="", ok=False, latency_seconds=time.perf_counter() - start,
                                  error=f"http_{exc.status_code}: {str(getattr(exc, 'message', exc))[:300]}")
        except openai.APIConnectionError as exc:
            return ToolCallResult(model=model, raw_response="", ok=False, error=f"connect_error: {exc}")
        except Exception as exc:  # noqa: BLE001
            return ToolCallResult(model=model, raw_response="", ok=False, latency_seconds=time.perf_counter() - start,
                                  error=f"{type(exc).__name__}: {str(exc)[:300]}")
        return self._parse_tools_response(resp, model=model, latency=time.perf_counter() - start)
