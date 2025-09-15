from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

import anthropic
import google.generativeai as genai


def _load_env() -> None:
    # Load .env from project root (one level up from backend/)
    # Project root is the parent of backend/
    root_env = Path(__file__).resolve().parent.parent / ".env"
    if root_env.exists():
        load_dotenv(dotenv_path=root_env)
    else:
        load_dotenv()  # fallback to default search


class LLMHandler:
    """Unified interface for invoking Claude and Gemini models."""

    def __init__(self) -> None:
        _load_env()

        # Anthropic (Claude)
        self._anthropic_client: Optional[anthropic.Anthropic] = None
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_api_key:
            self._anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key)

        # Google (Gemini)
        self._gemini_model: Optional[genai.GenerativeModel] = None
        google_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if google_api_key:
            genai.configure(api_key=google_api_key)
            # Default to a strong, general-purpose model
            self._gemini_model = genai.GenerativeModel("gemini-1.5-pro")

        # Register available models
        self.available_models: Dict[str, Dict[str, str]] = {}
        if self._anthropic_client is not None:
            self.available_models["claude-3-5-sonnet-20240620"] = {
                "provider": "anthropic",
                "display_name": "Claude 3.5 Sonnet (2024-06-20)",
            }
            # Newer Claude model (keep existing too)
            self.available_models["claude-3-7-sonnet-latest"] = {
                "provider": "anthropic",
                "display_name": "Claude 3.7 Sonnet (latest)",
            }
        if self._gemini_model is not None:
            self.available_models["gemini-1.5-pro"] = {
                "provider": "google",
                "display_name": "Gemini 1.5 Pro",
            }
            # Newer Gemini model (keep existing too)
            self.available_models["gemini-2.5-flash"] = {
                "provider": "google",
                "display_name": "Gemini 2.5 Flash",
            }

    # ---- Public API ----
    def list_models(self) -> List[Dict[str, str]]:
        return [
            {"id": model_id, **info} for model_id, info in self.available_models.items()
        ]

    def generate(self, model_id: str, prompt: str, max_tokens: int = 1024) -> str:
        if model_id.startswith("claude"):
            return self._generate_claude(model_id=model_id, prompt=prompt, max_tokens=max_tokens)
        if model_id.startswith("gemini"):
            return self._generate_gemini(model_id=model_id, prompt=prompt)
        raise ValueError(f"Unknown model_id: {model_id}")

    # ---- Internal helpers ----
    def _generate_claude(self, model_id: str, prompt: str, max_tokens: int) -> str:
        if self._anthropic_client is None:
            return "Claude is not configured. Missing ANTHROPIC_API_KEY."
        try:
            message = self._anthropic_client.messages.create(
                model=model_id,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            # message.content is a list of content blocks; join the text blocks
            parts: List[str] = []
            for block in getattr(message, "content", []) or []:
                text = getattr(block, "text", None)
                if isinstance(text, str):
                    parts.append(text)
            return "\n\n".join(parts) or str(message)
        except Exception as exc:
            return f"Error from Claude API: {exc}"

    def _generate_gemini(self, model_id: str, prompt: str) -> str:
        if self._gemini_model is None:
            return "Gemini is not configured. Missing GOOGLE_API_KEY or GEMINI_API_KEY."
        # The GenerativeModel instance already encodes model choice; rebuild if ids differ
        model = self._gemini_model if getattr(self._gemini_model, "model_name", "") == model_id else self._build_gemini_model(model_id)
        try:
            response = model.generate_content(prompt)
            return getattr(response, "text", "") or str(response)
        except Exception as exc:
            return f"Error from Gemini API: {exc}"

    # ---- Streaming APIs ----
    def stream_generate(self, model_id: str, prompt: str, max_tokens: int = 1024):
        if model_id.startswith("claude"):
            yield from self._stream_claude(model_id=model_id, prompt=prompt, max_tokens=max_tokens)
            return
        if model_id.startswith("gemini"):
            yield from self._stream_gemini(model_id=model_id, prompt=prompt)
            return
        yield f"[Unknown model: {model_id}]"

    def _stream_claude(self, model_id: str, prompt: str, max_tokens: int):
        if self._anthropic_client is None:
            yield "Claude is not configured. Missing ANTHROPIC_API_KEY."
            return
        try:
            # Stream tokens from Claude
            with self._anthropic_client.messages.stream(
                model=model_id,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for text in stream.text_stream:
                    if text:
                        yield text
        except Exception as exc:
            yield f"[Claude error: {exc}]"

    def _stream_gemini(self, model_id: str, prompt: str):
        if self._gemini_model is None:
            yield "Gemini is not configured. Missing GOOGLE_API_KEY or GEMINI_API_KEY."
            return
        model = self._gemini_model if getattr(self._gemini_model, "model_name", "") == model_id else self._build_gemini_model(model_id)
        try:
            response = model.generate_content(prompt, stream=True)
            for chunk in response:
                text = getattr(chunk, "text", None)
                if text:
                    yield text
        except Exception as exc:
            yield f"[Gemini error: {exc}]"

    def _build_gemini_model(self, model_id: str) -> genai.GenerativeModel:
        # For 2.5 models, bias against verbose reasoning via system instruction
        if model_id.startswith("gemini-2.5"):
            return genai.GenerativeModel(model_id, system_instruction="Provide the final answer directly without showing reasoning steps.")
        return genai.GenerativeModel(model_id)


