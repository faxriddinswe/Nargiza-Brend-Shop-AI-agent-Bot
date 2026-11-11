"""Gemini adapter: the request we send and how we read the reply — no network (SDK call is stubbed)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from google.genai import errors, types

from bot.ai import build_provider
from bot.ai.base import AIUnavailableError, AudioInput, Turn
from bot.ai.gemini import GeminiProvider
from bot.ai.prompts import CategoryHint, build_system_prompt
from bot.ai.tools import REGISTRY, tool_specs, validate
from bot.config import Settings
from bot.utils.dates import TASHKENT


def _response(
    parts: list[types.Part], prompt: int = 120, out: int = 15
) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=parts))],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=prompt, candidates_token_count=out, total_token_count=prompt + out
        ),
    )


def _provider(reply: Any, captured: dict[str, Any]) -> GeminiProvider:
    p = GeminiProvider("fake-key-not-real", "gemini-test-model")

    async def fake(*, model: str, contents: Any, config: Any) -> Any:
        captured.update(model=model, contents=contents, config=config)
        if isinstance(reply, Exception):
            raise reply
        return reply

    p._client.aio.models.generate_content = fake  # type: ignore[method-assign,assignment]
    return p


async def test_request_shape_voice_and_tools() -> None:
    cap: dict[str, Any] = {}
    reply = _response(
        [
            types.Part.from_function_call(
                name="add_payment", args={"customer_query": "Umida", "amount_text": "100 ming"}
            )
        ]
    )
    p = _provider(reply, cap)
    res = await p.decide(
        system="SYS", text=None, audio=AudioInput(b"OggS-fake", "audio/ogg"),
        history=[Turn("Umida 100", "Qancha?")], tools=tool_specs(),
    )  # fmt: skip
    assert cap["model"] == "gemini-test-model"  # from config, never hard-coded
    cfg: types.GenerateContentConfig = cap["config"]
    assert cfg.system_instruction == "SYS" and cfg.temperature == 0.0
    assert (
        cfg.automatic_function_calling is not None
        and cfg.automatic_function_calling.disable is True
    )
    assert cfg.tool_config is not None and cfg.tool_config.function_calling_config is not None
    assert cfg.tool_config.function_calling_config.mode == types.FunctionCallingConfigMode.ANY
    tool = cfg.tools[0] if cfg.tools else None
    assert isinstance(tool, types.Tool) and tool.function_declarations is not None
    assert {f.name for f in tool.function_declarations} == set(REGISTRY)
    contents = cap["contents"]
    assert [c.role for c in contents] == ["user", "model", "user"]  # history, then the new message
    audio_part = next(pt for pt in contents[-1].parts if pt.inline_data)
    assert (
        audio_part.inline_data.mime_type == "audio/ogg"
        and audio_part.inline_data.data == b"OggS-fake"
    )
    assert [(c.name, c.args["amount_text"]) for c in res.calls] == [("add_payment", "100 ming")]
    assert (res.usage.prompt_tokens, res.usage.output_tokens, res.usage.total_tokens) == (
        120,
        15,
        135,
    )


async def test_parallel_calls_and_plain_text() -> None:
    cap: dict[str, Any] = {}
    reply = _response([
        types.Part.from_function_call(name="add_payment", args={"amount_text": "50 ming"}),
        types.Part.from_function_call(name="add_debt", args={"items": []}),
    ])  # fmt: skip
    res = await _provider(reply, cap).decide(
        system="s", text="x", audio=None, history=[], tools=tool_specs()
    )
    assert [c.name for c in res.calls] == ["add_payment", "add_debt"]
    res = await _provider(_response([types.Part.from_text(text="salom")]), cap).decide(
        system="s", text="x", audio=None, history=[], tools=tool_specs()
    )
    assert res.calls == [] and res.text == "salom"


@pytest.mark.parametrize(
    "exc", [errors.APIError(429, {"error": {"message": "quota"}}), TimeoutError()]
)
async def test_vendor_errors_become_unavailable(exc: Exception) -> None:
    with pytest.raises(AIUnavailableError):
        await _provider(exc, {}).decide(
            system="s", text="x", audio=None, history=[], tools=tool_specs()
        )


async def test_empty_request_rejected() -> None:
    with pytest.raises(AIUnavailableError):
        await _provider(_response([]), {}).decide(
            system="s", text=None, audio=None, history=[], tools=[]
        )


def test_tool_schemas_are_plain_json_schema() -> None:
    """No $ref/$defs/anyOf/title — works with any vendor."""
    import json

    for spec in tool_specs():
        blob = json.dumps(spec.parameters)
        for bad in ("$ref", "$defs", "anyOf", '"title"'):
            assert bad not in blob, (spec.name, bad)
        assert spec.parameters["type"] == "object"


def test_validation_is_done_by_us() -> None:
    assert validate("add_payment", {"amount_text": "100 ming", "evil": 1}).amount_text == "100 ming"  # type: ignore[attr-defined]
    with pytest.raises(Exception):  # noqa: B017
        validate("add_payment", {"amount_text": ""})


def test_provider_only_built_when_configured() -> None:
    base: dict[str, Any] = {
        "bot_token": "1:x",
        "postgres_password": "p",
        "postgres_app_password": "p" * 16,
    }
    assert build_provider(Settings(_env_file=None, **base)) is None
    assert (
        build_provider(Settings(_env_file=None, gemini_api_key="k", **base)) is None
    )  # model missing
    p = build_provider(Settings(_env_file=None, gemini_api_key="k", gemini_model="m", **base))
    assert p is not None and p.model == "m"


def test_system_prompt_has_rules_and_no_secrets() -> None:
    text = build_system_prompt(
        now=datetime(2026, 11, 11, 14, 30, tzinfo=TASHKENT), staff_name="Nodira opa",
        categories=[CategoryHint("ko'ylak", "shop", ("platye",))], last_customer="Umida opa",
    )  # fmt: skip
    assert "chorshanba" in text and "11-noyabr 2026" in text and "14:30" in text
    assert "taxmin qilma" in text and "ko'ylak" in text and "Umida opa" in text
