"""AI layer: provider-neutral interface (`base`), tool schemas, prompt, dispatcher; Gemini adapter."""

from __future__ import annotations

from bot.ai.base import AIProvider
from bot.config import AIProviderName, Settings


def build_provider(settings: Settings) -> AIProvider | None:
    """None = AI not configured (no key or model) — staff then use the buttons."""
    if settings.ai_provider == AIProviderName.GEMINI:
        if settings.gemini_api_key is None or not settings.gemini_model:
            return None
        from bot.ai.gemini import GeminiProvider

        return GeminiProvider(settings.gemini_api_key.get_secret_value(), settings.gemini_model)
    return None  # Claude adapter: later (needs separate speech-to-text for voice)
