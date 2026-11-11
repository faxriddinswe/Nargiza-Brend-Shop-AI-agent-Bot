"""Gemini implementation of AIProvider (google-genai SDK).

API shapes verified against the installed SDK (google-genai 3.x): `client.aio.models.generate_content`,
`types.Part.from_bytes`, `types.FunctionDeclaration(parameters_json_schema=...)`,
`AutomaticFunctionCallingConfig(disable=True)` (we validate and run tools ourselves) and
`FunctionCallingConfigMode.ANY` (the model must answer with a tool call — `ask`/`say` cover chit-chat).
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from google import genai
from google.genai import errors, types

from bot.ai.base import (
    AIResult,
    AIUnavailableError,
    AudioInput,
    ToolCall,
    ToolSpec,
    Turn,
    Usage,
)

TIMEOUT_SECONDS = 45


class GeminiProvider:
    provider_name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self._client = genai.Client(api_key=api_key)

    async def decide(
        self,
        *,
        system: str,
        text: str | None,
        audio: AudioInput | None,
        history: Sequence[Turn],
        tools: Sequence[ToolSpec],
    ) -> AIResult:
        contents: list[types.Content] = []
        for turn in history:
            contents.append(
                types.Content(role="user", parts=[types.Part.from_text(text=turn.user)])
            )
            contents.append(
                types.Content(role="model", parts=[types.Part.from_text(text=turn.assistant)])
            )
        parts: list[types.Part] = []
        if audio is not None:
            parts.append(types.Part.from_text(text="Xodim ovozli xabar yubordi:"))
            parts.append(types.Part.from_bytes(data=audio.data, mime_type=audio.mime_type))
        if text:
            parts.append(types.Part.from_text(text=text))
        if not parts:
            raise AIUnavailableError("empty request")
        contents.append(types.Content(role="user", parts=parts))

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.0,
            max_output_tokens=1024,  # a tool call is short; caps the cost if the model rambles
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=t.name,
                            description=t.description,
                            parameters_json_schema=t.parameters,
                        )
                        for t in tools
                    ]
                )
            ],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode=types.FunctionCallingConfigMode.ANY
                )
            ),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        try:
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=self.model, contents=contents, config=config
                ),
                timeout=TIMEOUT_SECONDS,
            )
        except (errors.APIError, TimeoutError) as exc:
            raise AIUnavailableError(type(exc).__name__) from exc

        calls: list[ToolCall] = []
        said: list[str] = []
        for cand in response.candidates or []:
            for part in cand.content.parts if cand.content and cand.content.parts else []:
                if part.function_call and part.function_call.name:
                    calls.append(
                        ToolCall(part.function_call.name, dict(part.function_call.args or {}))
                    )
                elif part.text:
                    said.append(part.text)
            break  # first candidate only
        meta = response.usage_metadata
        usage = Usage(
            prompt_tokens=meta.prompt_token_count if meta else None,
            output_tokens=(meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0)
            if meta
            else None,
            total_tokens=meta.total_token_count if meta else None,
        )
        return AIResult(calls=calls, text=" ".join(said) or None, usage=usage)
