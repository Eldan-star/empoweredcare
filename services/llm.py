"""
Language-model provider interface.

Every text agent talks to an `LLMProvider` instead of a specific vendor SDK, so
the model can be changed with configuration (LLM_PROVIDER) without touching
agent logic. Vision/OCR calls still go through GeminiService directly.

    LLM_PROVIDER=gemini   (default) uses the existing GeminiService
    LLM_PROVIDER=claude   uses the Anthropic Messages API (needs `pip install anthropic`
                          and ANTHROPIC_API_KEY or an `ant auth login` profile)
"""

from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class LLMJSONError(ValueError):
    """The model's reply could not be parsed as JSON."""


def strip_code_fences(text: str) -> str:
    """Return the content of the first ``` fenced block, or the text itself."""
    m = _FENCE.search(text)
    return (m.group(1) if m else text).strip()


class LLMProvider(ABC):
    name: str = "llm"

    @abstractmethod
    def generate_text(self, prompt: str) -> str:
        """Return the model's text reply, with any surrounding code fence removed."""

    def generate_json(self, prompt: str) -> Any:
        """Ask for JSON and parse it. Raises LLMJSONError when the reply is not valid JSON."""
        instruction = "\n\nRespond with valid JSON only. Do not add commentary or code fences."
        raw = self.generate_text(prompt + instruction)
        try:
            return json.loads(strip_code_fences(raw))
        except json.JSONDecodeError as e:
            raise LLMJSONError(f"{self.name} returned non-JSON output: {raw[:200]!r}") from e


class GeminiProvider(LLMProvider):
    """Adapter over the existing GeminiService (keeps its model fallback and retries)."""

    name = "gemini"

    def __init__(self, gemini_service):
        self._gemini = gemini_service

    def generate_text(self, prompt: str) -> str:
        return strip_code_fences(self._gemini.generate_text(prompt))


class ClaudeProvider(LLMProvider):
    """Anthropic Messages API provider."""

    name = "claude"

    def __init__(self, model: str | None = None, effort: str | None = None, max_tokens: int = 16000):
        import anthropic  # optional dependency; imported only when this provider is selected

        self._anthropic = anthropic
        self._client = anthropic.Anthropic()
        self.model = model or os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
        # Claude Opus 5.5 defaults to "medium" effort; set it explicitly so behaviour is predictable.
        self.effort = effort or os.getenv("CLAUDE_EFFORT", "medium")
        self.max_tokens = max_tokens

    def generate_text(self, prompt: str) -> str:
        # Server-side fallback: if the model declines on a safety category, the API
        # re-runs the request on a suitable fallback model within the same call.
        response = self._client.beta.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            output_config={"effort": self.effort},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
        )
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise RuntimeError(f"Claude declined the request (category: {category})")
        if response.stop_reason == "max_tokens":
            logger.warning("Claude reply hit max_tokens (%s); output may be truncated", self.max_tokens)
        text = "".join(block.text for block in response.content if block.type == "text")
        return strip_code_fences(text)


def get_llm(gemini_service=None) -> LLMProvider:
    """Build the provider selected by LLM_PROVIDER (default: gemini)."""
    choice = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    if choice == "claude":
        logger.info("LLM provider: Claude (%s)", os.getenv("CLAUDE_MODEL", "claude-opus-5-5"))
        return ClaudeProvider()
    if choice != "gemini":
        raise ValueError(f"Unknown LLM_PROVIDER {choice!r}; use 'gemini' or 'claude'")
    if gemini_service is None:
        from services.gemini_service import GeminiService

        gemini_service = GeminiService()
    logger.info("LLM provider: Gemini")
    return GeminiProvider(gemini_service)
