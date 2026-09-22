"""Google Gemini through the OpenAI-compatible endpoint (third frontier vendor, 12 Sep 2026).

Why a subclass of ``OpenAIProvider`` rather than a native ``google-genai`` client: Google
exposes a Chat Completions-compatible surface at ``GEMINI_OPENAI_BASE_URL`` that accepts the
same wire shapes this repo already sends to OpenAI (messages, ``tools`` as function
declarations, ``tool_calls`` replayed verbatim, ``role: tool`` results). Reusing the parent
means the usage metadata comes out under the keys ``usage_from_metadata`` already prices
(``input_tokens`` / ``cached_input_tokens`` / ``output_tokens``), so a Gemini call is costed and
capped by the same guard as a gpt-5.5 call with no new normaliser. It also means the provider
carries **no scenario-aware or vendor-tuned behaviour**: everything that could differ from the
OpenAI path is one of the class attributes below, and ``tests/test_google_provider.py`` asserts
that the set of names this class adds is exactly that set (the reviewer's "do not tune the
scenario for the third model" rule, in code form).

Key: ``GOOGLE_API_KEY`` or ``GEMINI_API_KEY`` from the environment (``.env`` is loaded by the
CLI and, as a safety net, here). The key is passed to the SDK constructor and nowhere else --
never logged, never placed in metadata, never echoed by ``list_models``.

Base URL: scoped to this class. Setting ``OPENAI_BASE_URL`` in the process environment would
redirect every gpt-5.5 config to Google as well, which is why it is not used.

Two request-shape hooks inherited from the parent may need flipping for the compat layer,
and only a live probe can say (``PREREG_THIRD_VENDOR_GEMINI.md`` fixes the rule): if the
endpoint returns ``http_400`` on ``max_completion_tokens`` set ``TOKEN_BUDGET_KEY = "max_tokens"``;
if it rejects ``strict`` function declarations or ``additionalProperties: false`` set
``STRICT_TOOLS = False``. Both default to the OpenAI values, so until a probe says otherwise
the Gemini request is byte-identical in shape to the OpenAI one.
"""

from __future__ import annotations

import os

from ..utils.env import load_dotenv
from .base import GenerationOptions, ModelCallResult, ToolCallResult, ToolSpec
from .openai import OpenAIProvider

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
KEY_ENV_VARS: tuple[str, ...] = ("GOOGLE_API_KEY", "GEMINI_API_KEY")


def _key_from_env() -> str | None:
    for name in KEY_ENV_VARS:
        value = os.environ.get(name)
        if value:
            return value
    return None


class GoogleProvider(OpenAIProvider):
    name = "google"
    #: No silent fall-through to the parent's ``gpt-5.5``: a Gemini config must name its model.
    default_model = None

    def __init__(self, base_url: str = GEMINI_OPENAI_BASE_URL):
        try:
            import openai
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise ImportError("openai SDK not installed. Run: uv sync --extra frontier") from exc
        load_dotenv()  # safety net for non-CLI use; CLI also loads it at startup
        key = _key_from_env()
        if not key:
            raise RuntimeError(
                "Neither GOOGLE_API_KEY nor GEMINI_API_KEY is set. Add one to the project .env "
                "or export it in your shell."
            )
        self._openai = openai
        self._client = openai.OpenAI(api_key=key, base_url=base_url)

    def list_models(self) -> list[str]:
        """Model ids the endpoint exposes, sorted. Free; used by ``ombs list-models``."""
        page = self._client.models.list()
        ids = [getattr(m, "id", None) or (m.get("id") if isinstance(m, dict) else None) for m in page]
        return sorted(i for i in ids if i)

    # The parent builds provider_metadata without a "model" key, so `model_resolved` on the
    # sandbox record is None for OpenAI. For a new vendor the resolved id is worth keeping.
    def _call(self, *, messages: list[dict], model: str, options: GenerationOptions) -> ModelCallResult:
        result = super()._call(messages=messages, model=model, options=options)
        if result.ok and result.provider_metadata is not None:
            result.provider_metadata["model"] = result.model_digest
        return result

    def chat_tools(
        self, *, messages: list, tools: list[ToolSpec], model: str, options: GenerationOptions
    ) -> ToolCallResult:
        result = super().chat_tools(messages=messages, tools=tools, model=model, options=options)
        if result.ok and result.provider_metadata is not None:
            result.provider_metadata["model"] = result.model_digest
        return result
