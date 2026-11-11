#!/usr/bin/env python3
"""Measure how well the real model understands the phrases in tests/eval/phrases.yaml (Stage 3 acceptance).

    .venv/bin/python scripts/run_eval.py            # all phrases
    .venv/bin/python scripts/run_eval.py --limit 10 # quick smoke run
    .venv/bin/python scripts/run_eval.py --audio    # also run tests/eval/audio/*.ogg (see audio/README)

Needs GEMINI_API_KEY and GEMINI_MODEL in .env and a dev database (for the product synonyms).
Uses ONLY fake phrases. Acceptance: write-tool accuracy >= 90%. Exit code 1 if below.
A phrase passes only if tools, customer words, amounts (read by OUR parser), products and due dates all match.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.ai import build_provider
from bot.ai.base import ToolCall
from bot.ai.dispatcher import load_hints, resolve_category
from bot.ai.prompts import build_system_prompt
from bot.ai.tools import tool_specs
from bot.config import get_settings
from bot.db.session import make_engine, make_sessionmaker, read_session
from bot.utils.dates import TASHKENT, parse_due_text
from bot.utils.money import AmountParseError, parse_amount
from bot.utils.translit import search_key

ROOT = Path(__file__).resolve().parents[1]
WRITE_TOOLS = {
    "add_payment",
    "add_debt",
    "write_off",
    "create_customer",
    "delete_customer",
    "cancel_last_entry",
}


def _amount(text: str | None) -> int | None:
    try:
        return parse_amount(text or "").value
    except AmountParseError:
        return None


async def check(
    call: ToolCall, want: dict[str, Any], session: Any, today: Any, last_customer: str | None = None
) -> list[str]:
    errs: list[str] = []
    a = call.args
    if want["tool"] == "ask" and call.name != "ask":
        # the dispatcher asks "who?" / "how much?" itself when a required field is missing
        incomplete = not (a.get("customer_query") or a.get("name") or a.get("query")) or not (
            a.get("amount_text") or a.get("items") or a.get("all")
        )
        return (
            []
            if (call.name in WRITE_TOOLS | {"get_customer_debt"}) and incomplete
            else [f"tool {call.name} != ask"]
        )
    if call.name != want["tool"]:
        return [f"tool {call.name} != {want['tool']}"]
    if "customer" in want:
        words = search_key(str(a.get("customer_query") or a.get("name") or a.get("query") or ""))
        if last_customer and words in {"", "u", "unga", "uning", "shu odam"}:
            words = search_key(
                last_customer
            )  # the code maps pronouns / empty to the remembered customer
        if not set(search_key(want["customer"]).split()) <= set(words.split()):  # whole words
            errs.append(f"customer '{words}' lacks '{want['customer']}'")
    if "amount" in want and _amount(a.get("amount_text")) != want["amount"]:
        errs.append(
            f"amount {a.get('amount_text')!r} -> {_amount(a.get('amount_text'))} != {want['amount']}"
        )
    if "section" in want and a.get("section") != want["section"]:
        # "ichki kiyim qarziga" may come as item="ichki kiyim": the code derives the section from it
        cat = await resolve_category(session, str(a.get("item") or ""))
        if not (cat and cat.section_code == want["section"]):
            errs.append(f"section {a.get('section')} != {want['section']}")
    if want.get("all") and not a.get("all"):
        errs.append("all=true missing")
    if "item" in want:
        cat = await resolve_category(session, str(a.get("item") or ""))
        if cat is None or cat.name != want["item"]:
            errs.append(f"item {a.get('item')!r} -> {cat.name if cat else None} != {want['item']}")
    for i, wi in enumerate(want.get("items", [])):
        got = a.get("items") or []
        if i >= len(got):
            errs.append(f"item #{i} missing")
            continue
        cat = await resolve_category(session, str(got[i].get("item") or ""))
        if cat is None or cat.name != wi["cat"]:
            errs.append(
                f"item#{i} {got[i].get('item')!r} -> {cat.name if cat else None} != {wi['cat']}"
            )
        if int(got[i].get("quantity") or 1) != wi["qty"]:
            errs.append(f"item#{i} qty {got[i].get('quantity')} != {wi['qty']}")
        if _amount(got[i].get("unit_price_text")) != wi["price"]:
            errs.append(f"item#{i} price {got[i].get('unit_price_text')!r} != {wi['price']}")
    if "due" in want:
        raw = a.get("due_text")
        if want["due"] == "unset":
            if raw:
                errs.append(f"due should be empty, got {raw!r}")
        else:
            ok, due = parse_due_text(str(raw or ""), today)
            if not ok or (want["due"] == "none") != (due is None):
                errs.append(f"due {raw!r} wrong for {want['due']}")
    return errs


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--audio", action="store_true")
    args = ap.parse_args()

    settings = get_settings()
    ai = build_provider(settings)
    if ai is None:
        print("GEMINI_API_KEY / GEMINI_MODEL .env da yo'q — baholash mumkin emas.")
        return 2
    phrases = yaml.safe_load((ROOT / "tests/eval/phrases.yaml").read_text(encoding="utf-8"))
    if args.limit:
        phrases = phrases[: args.limit]

    sm = make_sessionmaker(make_engine(settings.app_database_url))
    async with read_session(sm) as s:
        hints = await load_hints(s)
        now = datetime.now(TASHKENT)
        system = build_system_prompt(
            now=now, staff_name="Nodira opa", categories=hints, last_customer=None
        )
        passed: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        failures: list[str] = []
        tokens = 0
        for n, ph in enumerate(phrases, 1):
            t0 = time.monotonic()
            system = build_system_prompt(
                now=now,
                staff_name="Nodira opa",
                categories=hints,
                last_customer=ph.get("last_customer"),
            )
            res = None
            err_name = ""
            for attempt in range(
                4
            ):  # free tier: 429 / slow replies -> wait and retry (not a wrong answer)
                try:
                    res = await ai.decide(
                        system=system, text=ph["say"], audio=None, history=[], tools=tool_specs()
                    )
                    break
                except Exception as exc:
                    err_name = f"{type(exc).__name__}: {exc}"[:80]
                    await asyncio.sleep(4 * (attempt + 1))
            if res is None:
                failures.append(f"#{n} {ph['say']!r}: provider error after retries ({err_name})")
                for w in ph["expect"]:
                    passed[w["tool"]][1] += 1
                continue
            tokens += res.usage.total_tokens or 0
            wants = ph["expect"]
            errs: list[str] = []
            if len(res.calls) != len(wants):
                errs.append(
                    f"{len(res.calls)} calls != {len(wants)}: {[c.name for c in res.calls]}"
                )
            for call, want in zip(res.calls, wants, strict=False):
                errs += await check(call, want, s, now.date(), ph.get("last_customer"))
            ok = not errs
            for w in wants:
                passed[w["tool"]][1] += 1
                passed[w["tool"]][0] += int(ok)
            if not ok:
                failures.append(f"#{n} {ph['say']!r}: " + "; ".join(errs))
            print(
                f"{'✅' if ok else '❌'} #{n:02d} {time.monotonic() - t0:4.1f}s  {ph['say'][:70]}"
            )
    print("\n" + "=" * 60)
    for tool, (n_ok, total) in sorted(passed.items()):
        print(f"{tool:20s} {n_ok}/{total}  {100 * n_ok / total:5.1f}%")
    w_ok = sum(v[0] for k, v in passed.items() if k in WRITE_TOOLS)
    w_total = sum(v[1] for k, v in passed.items() if k in WRITE_TOOLS)
    all_ok = sum(v[0] for v in passed.values())
    all_total = sum(v[1] for v in passed.values())
    print(
        f"\nYOZISH tool'lari:  {w_ok}/{w_total} = {100 * w_ok / max(w_total, 1):.1f}%   (talab: >= 90%)"
    )
    print(
        f"Hammasi:           {all_ok}/{all_total} = {100 * all_ok / max(all_total, 1):.1f}%   | tokenlar: {tokens}"
    )
    if failures:
        print("\nXatolar:")
        print("\n".join(f"  {f}" for f in failures))
    return 0 if w_total and 100 * w_ok / w_total >= 90 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
