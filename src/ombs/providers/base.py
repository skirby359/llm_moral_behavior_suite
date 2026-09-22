"""Provider interface shared by local and frontier backends.

Designed for frontier providers from day one (brief §2) even though only Ollama
is implemented: the harness depends on ``ProviderClient.generate`` returning a
``ModelCallResult``, never on a concrete backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GenerationOptions:
    temperature: float = 0.2
    top_p: float = 0.9
    max_tokens: int = 800
    seed: int | None = 42
    timeout_seconds: int = 90
    think: bool = False
    # "json" -> Ollama free JSON mode; a dict -> a JSON schema for structured
    # output (forces enum/type compliance); None -> unconstrained.
    format: str | dict | None = None
    # Native tool calling only: ask Anthropic to cache the system block and the latest
    # tool results. Invisible to the model; costs money if it fails, never correctness.
    prompt_caching: bool = False


@dataclass
class ModelCallResult:
    """Outcome of a single ``generate`` call.

    ``ok`` is about transport (did we get a response), not about content quality.
    JSON-parse success and scoring happen downstream.
    """

    model: str
    raw_response: str
    ok: bool
    latency_seconds: float | None = None
    error: str | None = None
    model_digest: str | None = None
    provider_metadata: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Native tool calling (Wave 3). A provider-neutral message model; each provider's
# ``chat_tools`` adapter maps it onto its own wire shape and stores the vendor's
# assistant turn verbatim in ``AssistantMsg.replay`` so the conversation is never
# reconstructed (thinking blocks, call ids and argument strings round-trip intact).
# --------------------------------------------------------------------------- #


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON schema; adapters make it strict where the vendor requires


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict = field(default_factory=dict)
    raw_arguments: str | None = None  # the vendor's argument string, when it sends one
    arguments_error: str | None = None  # set when the argument JSON did not decode


@dataclass
class ToolResult:
    call_id: str
    name: str
    content: str
    is_error: bool = False


@dataclass
class SystemMsg:
    text: str


@dataclass
class UserMsg:
    text: str


@dataclass
class AssistantMsg:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    replay: Any = None  # provider-shaped object appended verbatim on the next request


@dataclass
class ToolResultsMsg:
    results: list[ToolResult]
    extra_text: str | None = None  # e.g. the workspace listing or a workspace notice


ToolMessage = SystemMsg | UserMsg | AssistantMsg | ToolResultsMsg


@dataclass
class ToolCallResult(ModelCallResult):
    """Outcome of one ``chat_tools`` call: text plus zero or more tool calls."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    replay: Any = None
    stop: str = "other"  # tool_use | end_turn | max_tokens | refusal | other


class ProviderClient(ABC):
    name: str = "base"

    @abstractmethod
    def generate(
        self,
        *,
        system: str,
        prompt: str,
        model: str,
        options: GenerationOptions,
    ) -> ModelCallResult:
        """Run one generation. Must not raise on model/transport errors —
        return a ``ModelCallResult`` with ``ok=False`` and ``error`` set."""
        raise NotImplementedError

    def chat_tools(
        self,
        *,
        messages: list[ToolMessage],
        tools: list[ToolSpec],
        model: str,
        options: GenerationOptions,
    ) -> ToolCallResult:
        """Native tool calling. Providers that implement it override this; the
        sandbox runner checks ``supports_tools`` before choosing the transport."""
        return ToolCallResult(
            model=model, raw_response="", ok=False,
            error=f"tools_unsupported: provider {self.name!r} has no native tool calling",
        )

    supports_tools: bool = False
