"""Pure analytics functions.

Everything here derives metrics from ORM rows. No persistence, no side effects — so the same
functions power the API responses, the computed-insights fallback, and the trends endpoint.
"""
from __future__ import annotations

from .models import Collection, Meeting


def _round(x: float, n: int = 2) -> float:
    return round(float(x or 0), n)


def collection_metrics(c: Collection) -> dict:
    """Per-agent collection metrics, including derived outstanding totals."""
    buckets = {
        "d90": {"mbs": c.d90_mbs, "mcorp": c.d90_mcorp},
        "d60": {"mbs": c.d60_mbs, "mcorp": c.d60_mcorp},
        "d30": {"mbs": c.d30_mbs, "mcorp": c.d30_mcorp},
        "other": {"mbs": c.other_mbs, "mcorp": c.other_mcorp},
    }
    os_mbs = c.d90_mbs + c.d60_mbs + c.d30_mbs + c.other_mbs
    os_mcorp = c.d90_mcorp + c.d60_mcorp + c.d30_mcorp + c.other_mcorp
    outstanding = os_mbs + os_mcorp
    collected = c.collected_mbs + c.collected_mcorp

    bucket_totals = {k: v["mbs"] + v["mcorp"] for k, v in buckets.items()}
    overdue = bucket_totals["d90"] + bucket_totals["d60"]  # 60+ days = real risk

    return {
        "agent": c.agent,
        "buckets": buckets,
        "bucket_totals": {k: _round(v) for k, v in bucket_totals.items()},
        "outstanding_mbs": _round(os_mbs),
        "outstanding_mcorp": _round(os_mcorp),
        "outstanding": _round(outstanding),
        "collected_mbs": _round(c.collected_mbs),
        "collected_mcorp": _round(c.collected_mcorp),
        "collected": _round(collected),
        "coll_per_day": _round(c.coll_per_day),
        # Coll % as reported, plus a derived efficiency we can always recompute.
        "coll_pct": _round(c.coll_pct),
        "collected_vs_outstanding_pct": _round(100 * collected / outstanding) if outstanding else 0,
        "overdue_90_60": _round(overdue),
        "overdue_pct": _round(100 * overdue / outstanding) if outstanding else 0,
        "new_target": _round(c.new_target),
        "last_week_target": _round(c.last_week_target),
        "target_change_pct": (
            _round(100 * (c.new_target - c.last_week_target) / c.last_week_target)
            if c.last_week_target
            else 0
        ),
    }


def meeting_analytics(meeting: Meeting) -> dict:
    """Full analytics bundle for one meeting."""
    agents = [collection_metrics(c) for c in meeting.collections]

    # Derived grand totals (single source of truth).
    def s(key: str) -> float:
        return sum(a[key] for a in agents)

    totals = {
        "outstanding": _round(s("outstanding")),
        "outstanding_mbs": _round(s("outstanding_mbs")),
        "outstanding_mcorp": _round(s("outstanding_mcorp")),
        "collected": _round(s("collected")),
        "collected_mbs": _round(s("collected_mbs")),
        "collected_mcorp": _round(s("collected_mcorp")),
    }
    totals["collection_efficiency_pct"] = (
        _round(100 * totals["collected"] / totals["outstanding"]) if totals["outstanding"] else 0
    )

    # Ageing concentration across all agents.
    ageing = {"d90": 0.0, "d60": 0.0, "d30": 0.0, "other": 0.0}
    ageing_mbs = {"d90": 0.0, "d60": 0.0, "d30": 0.0, "other": 0.0}
    ageing_mcorp = {"d90": 0.0, "d60": 0.0, "d30": 0.0, "other": 0.0}
    for a in agents:
        for k in ageing:
            ageing[k] += a["bucket_totals"][k]
            ageing_mbs[k] += a["buckets"][k]["mbs"]
            ageing_mcorp[k] += a["buckets"][k]["mcorp"]
    ageing = {k: _round(v) for k, v in ageing.items()}
    ageing_pct = {
        k: _round(100 * v / totals["outstanding"]) if totals["outstanding"] else 0
        for k, v in ageing.items()
    }
    overdue_total = ageing["d90"] + ageing["d60"]

    # Leaderboard: best collectors first (by reported coll %).
    leaderboard = sorted(agents, key=lambda a: a["coll_pct"], reverse=True)

    # Sales / purchase tonnage.
    sales_total = {"purchase_mbs": 0.0, "purchase_mcorp": 0.0, "sales_mbs": 0.0, "sales_mcorp": 0.0}
    by_branch: dict[str, dict] = {}
    for srow in meeting.sales:
        for k in sales_total:
            sales_total[k] += getattr(srow, k)
        b = by_branch.setdefault(
            srow.branch, {"branch": srow.branch, "purchase": 0.0, "sales": 0.0}
        )
        b["purchase"] += srow.purchase_mbs + srow.purchase_mcorp
        b["sales"] += srow.sales_mbs + srow.sales_mcorp
    sales_total = {k: _round(v) for k, v in sales_total.items()}
    sales_total["purchase_total"] = _round(sales_total["purchase_mbs"] + sales_total["purchase_mcorp"])
    sales_total["sales_total"] = _round(sales_total["sales_mbs"] + sales_total["sales_mcorp"])
    branches = [
        {"branch": b["branch"], "purchase": _round(b["purchase"]), "sales": _round(b["sales"])}
        for b in by_branch.values()
    ]

    # Quotation funnel + conversion.
    quotes = {q.stage: {"mbs": q.mbs, "mcorp": q.mcorp, "total": q.mbs + q.mcorp} for q in meeting.quotations}
    prepared = quotes.get("PREPARED", {}).get("total", 0)
    confirmed = quotes.get("CONFIRMED", {}).get("total", 0)
    conversion_pct = _round(100 * confirmed / prepared) if prepared else 0
    quotation = {
        "stages": [
            {"stage": q.stage, "mbs": _round(q.mbs), "mcorp": _round(q.mcorp), "total": _round(q.mbs + q.mcorp)}
            for q in meeting.quotations
        ],
        "prepared": _round(prepared),
        "confirmed": _round(confirmed),
        "conversion_pct": conversion_pct,
    }

    sales_reps = [
        {
            "salesperson": r.salesperson,
            "target_tons": r.target_tons,
            "achieve_pct_tons": r.achieve_pct_tons,
            "target_party": r.target_party,
            "achieve_pct_party": r.achieve_pct_party,
            "total_visit": r.total_visit,
            "total_inquiry": r.total_inquiry,
            "inquiry_confirm": r.inquiry_confirm,
            "order_loss": r.order_loss,
        }
        for r in meeting.sales_reps
    ]

    return {
        "meeting": {
            "id": meeting.id,
            "meeting_date": meeting.meeting_date.isoformat(),
            "period_start": meeting.period_start.isoformat() if meeting.period_start else None,
            "period_end": meeting.period_end.isoformat() if meeting.period_end else None,
            "source_file": meeting.source_file,
        },
        "totals": totals,
        "ageing": {
            "amounts": ageing,
            "pct": ageing_pct,
            "mbs": {k: _round(v) for k, v in ageing_mbs.items()},
            "mcorp": {k: _round(v) for k, v in ageing_mcorp.items()},
            "overdue_total": _round(overdue_total),
            "overdue_pct": _round(100 * overdue_total / totals["outstanding"]) if totals["outstanding"] else 0,
        },
        "agents": agents,
        "leaderboard": leaderboard,
        "sales": {"totals": sales_total, "branches": branches},
        "sales_reps": sales_reps,
        "quotation": quotation,
    }


def trends(meetings: list[Meeting]) -> list[dict]:
    """Week-over-week series, oldest first."""
    series = []
    for m in sorted(meetings, key=lambda x: x.meeting_date):
        a = meeting_analytics(m)
        series.append(
            {
                "meeting_id": m.id,
                "date": m.meeting_date.isoformat(),
                "outstanding": a["totals"]["outstanding"],
                "collected": a["totals"]["collected"],
                "collection_efficiency_pct": a["totals"]["collection_efficiency_pct"],
                "overdue_pct": a["ageing"]["overdue_pct"],
                "sales_total": a["sales"]["totals"]["sales_total"],
                "purchase_total": a["sales"]["totals"]["purchase_total"],
                "quotation_conversion_pct": a["quotation"]["conversion_pct"],
            }
        )
    return series
