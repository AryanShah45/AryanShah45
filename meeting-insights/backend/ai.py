"""Insight generation: Claude when a key is configured, deterministic fallback otherwise."""
from __future__ import annotations

import json

from .config import AI_MODEL, ANTHROPIC_API_KEY


def _fmt_inr(x: float) -> str:
    """Format a rupee amount in lakh/crore, the way Indian businesses read it."""
    x = float(x or 0)
    if abs(x) >= 1e7:
        return f"₹{x / 1e7:.2f} Cr"
    if abs(x) >= 1e5:
        return f"₹{x / 1e5:.2f} L"
    return f"₹{x:,.0f}"


def computed_insights(a: dict) -> str:
    """Deterministic narrative built straight from the analytics bundle.

    Always available — no API key required.
    """
    t = a["totals"]
    ageing = a["ageing"]
    lines: list[str] = []

    lines.append(
        f"**Collection overview** — Total outstanding stands at {_fmt_inr(t['outstanding'])} "
        f"(MBS {_fmt_inr(t['outstanding_mbs'])}, MCORP {_fmt_inr(t['outstanding_mcorp'])}). "
        f"This week the team recovered {_fmt_inr(t['collected'])}, an overall collection "
        f"efficiency of {t['collection_efficiency_pct']}%."
    )

    lines.append(
        f"**Ageing risk** — {ageing['pct']['d90']}% of the book is in the 90-day bucket "
        f"({_fmt_inr(ageing['amounts']['d90'])}) and {ageing['pct']['d60']}% in 60-day "
        f"({_fmt_inr(ageing['amounts']['d60'])}). Combined 60+ days overdue is "
        f"{_fmt_inr(ageing['overdue_total'])} ({ageing['overdue_pct']}% of total) — this is the "
        f"money most at risk and should drive the call list."
    )

    lb = a["leaderboard"]
    if lb:
        best = lb[0]
        worst = lb[-1]
        lines.append(
            f"**Agent performance** — Best collector this week is {best['agent']} at "
            f"{best['coll_pct']}% (recovered {_fmt_inr(best['collected'])}). Lowest is "
            f"{worst['agent']} at {worst['coll_pct']}% on a book of "
            f"{_fmt_inr(worst['outstanding'])} — a priority for follow-up."
        )
        # Largest 90-day holder.
        by90 = max(a["agents"], key=lambda x: x["bucket_totals"]["d90"])
        lines.append(
            f"**Oldest receivables** — {by90['agent']} carries the largest 90-day balance at "
            f"{_fmt_inr(by90['bucket_totals']['d90'])}, the single biggest pocket of stale debt."
        )

    s = a["sales"]["totals"]
    lines.append(
        f"**Sales & purchase (tons)** — Sales {s['sales_total']} t "
        f"(MBS {s['sales_mbs']} / MCORP {s['sales_mcorp']}), purchase {s['purchase_total']} t. "
    )

    q = a["quotation"]
    lines.append(
        f"**Quotation funnel** — {q['prepared']:.0f} prepared → {q['confirmed']:.0f} confirmed, "
        f"a {q['conversion_pct']}% conversion rate."
    )

    return "\n\n".join(lines)


def _claude_insights(a: dict) -> str:
    """Ask Claude for an executive narrative. Raises on any failure so caller can fall back."""
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = (
        "You are a financial analyst preparing the weekly collections & sales review for a "
        "commodities trading company with two business units, MBS and MCORP. Amounts are in INR; "
        "tonnage is in metric tons. Using ONLY the JSON analytics below, write a concise executive "
        "brief (~150-220 words) in markdown with short bold-led paragraphs covering: collection "
        "ageing risk (90/60/30), collection efficiency and which agents lead/lag, sales & purchase "
        "performance, and quotation conversion. Call out the single biggest risk and one concrete "
        "action. Use lakh/crore notation for rupee figures. Do not invent numbers.\n\n"
        f"ANALYTICS JSON:\n{json.dumps(a, default=str)}"
    )
    msg = client.messages.create(
        model=AI_MODEL,
        max_tokens=900,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in msg.content if getattr(block, "type", "") == "text").strip()


def generate_insights(a: dict) -> tuple[str, str]:
    """Return (body, source) where source is 'ai' or 'computed'."""
    if ANTHROPIC_API_KEY:
        try:
            text = _claude_insights(a)
            if text:
                return text, "ai"
        except Exception:
            # Any AI failure (no quota, network, bad key) → deterministic fallback.
            pass
    return computed_insights(a), "computed"
