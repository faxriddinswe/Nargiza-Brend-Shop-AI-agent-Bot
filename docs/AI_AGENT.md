# AI agent

> Status: skeleton. To be filled in during Stage 3 (the google-genai SDK documentation will be checked at that time).

## Provider
- `AI_PROVIDER=gemini`; the model is set via `GEMINI_MODEL` (never hard-coded).
- `ai/base.py` defines the `AIProvider` interface; `ai/gemini.py` is the implementation; `ai/claude.py` will follow later (with separate STT for voice).

## Strict rules
- The AI never does calculations and never decides permissions.
- Ambiguous amount, customer or department → ask a question instead of calling a tool.
- Arguments are validated with Pydantic; the department is re-determined in code.
- Write tools always go through a confirmation card.
- Every call is logged to `ai_calls` (tokens, cost, latency) without any personal data.
- If the AI is unavailable, the staff member gets a clear message plus the button menu, and the admin is notified.

## Tools
_To be finalised in Stage 3 together with `architect` (master prompt, section 8.3)._

## System prompt
_Stage 3._

## Eval
- `tests/eval/phrases.yaml` — at least 60 phrases; `scripts/run_eval.py`.
- Acceptance: ≥ 90% accuracy on write tools.
- Real voice recordings live in `tests/eval/audio/` and are never committed to git.
