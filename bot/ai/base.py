"""AI provider interface (master §8.1). The rest of the bot never imports a vendor SDK."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """A function the model may call: name, description and a plain JSON-schema (no $ref)."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolCall:
    name: str
    args: dict[str, Any]  # from the model: UNTRUSTED
    # Answers the user tapped on buttons (customer id, section, debt...). Set only by our own code from
    # server-side state — the model cannot set it (an `_fix` key in `args` is ignored).
    fix: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AudioInput:
    data: bytes
    mime_type: str = "audio/ogg"  # Telegram voice notes are OGG/Opus


@dataclass(frozen=True, slots=True)
class Turn:
    """One earlier exchange, kept so short answers like "yuz ming" make sense."""

    user: str
    assistant: str


@dataclass(slots=True)
class Usage:
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(slots=True)
class AIResult:
    calls: list[ToolCall] = field(default_factory=list)
    text: str | None = None  # model said something without calling a tool
    usage: Usage = field(default_factory=Usage)


class AIUnavailableError(Exception):
    """Provider is down, not configured, rate limited or returned garbage."""


class AIProvider(Protocol):
    provider_name: str
    model: str

    async def decide(
        self,
        *,
        system: str,
        text: str | None,
        audio: AudioInput | None,
        history: Sequence[Turn],
        tools: Sequence[ToolSpec],
    ) -> AIResult: ...
