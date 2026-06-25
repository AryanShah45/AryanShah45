"""Seed the database from data/seed_*.json and ensure a default admin user exists.

Run with:  python -m backend.seed
Idempotent: skips a meeting that already exists for the same date.
"""
import json
import secrets
import sys
from datetime import date

from .auth import hash_password
from .config import ADMIN_PASSWORD, ADMIN_USERNAME, DATA_DIR
from .database import Base, SessionLocal, engine
from .models import Collection, Meeting, Quotation, Sales, SalesRep, User

# Map the JSON quotation stage names to our stored enum-ish strings.
SEED_FILES = ["seed_2025-06-24.json"]


def _ensure_admin(db) -> None:
    existing = db.query(User).filter(User.username == ADMIN_USERNAME).first()
    if existing:
        print(f"[seed] admin user '{ADMIN_USERNAME}' already exists — leaving as is.")
        return
    password = ADMIN_PASSWORD or secrets.token_urlsafe(9)
    db.add(
        User(
            username=ADMIN_USERNAME,
            hashed_password=hash_password(password),
            role="admin",
        )
    )
    db.commit()
    print("=" * 56)
    print("[seed] Created admin account:")
    print(f"        username: {ADMIN_USERNAME}")
    print(f"        password: {password}")
    if not ADMIN_PASSWORD:
        print("        (randomly generated — set ADMIN_PASSWORD in .env to fix one)")
    print("=" * 56)


def _seed_meeting(db, payload: dict) -> None:
    mdate = date.fromisoformat(payload["meeting_date"])
    if db.query(Meeting).filter(Meeting.meeting_date == mdate).first():
        print(f"[seed] meeting {mdate} already present — skipping.")
        return

    meeting = Meeting(
        meeting_date=mdate,
        period_start=date.fromisoformat(payload["period_start"]) if payload.get("period_start") else None,
        period_end=date.fromisoformat(payload["period_end"]) if payload.get("period_end") else None,
        source_file=payload.get("source_file"),
        created_by="seed",
    )
    db.add(meeting)
    db.flush()

    for c in payload.get("collections", []):
        b = c["buckets"]
        db.add(
            Collection(
                meeting_id=meeting.id,
                agent=c["agent"],
                d90_mbs=b["days_90"]["mbs"], d90_mcorp=b["days_90"]["mcorp"],
                d60_mbs=b["days_60"]["mbs"], d60_mcorp=b["days_60"]["mcorp"],
                d30_mbs=b["days_30"]["mbs"], d30_mcorp=b["days_30"]["mcorp"],
                other_mbs=b["other"]["mbs"], other_mcorp=b["other"]["mcorp"],
                collected_mbs=c["collected"]["mbs"], collected_mcorp=c["collected"]["mcorp"],
                coll_per_day=c.get("coll_per_day", 0),
                coll_pct=c.get("coll_pct", 0),
                new_target=c.get("new_target", 0),
                last_week_target=c.get("last_week_target", 0),
            )
        )

    for s in payload.get("sales", []):
        db.add(
            Sales(
                meeting_id=meeting.id,
                salesperson=s["salesperson"],
                branch=s.get("branch", "ALL"),
                purchase_mbs=s["purchase"]["mbs"], purchase_mcorp=s["purchase"]["mcorp"],
                sales_mbs=s["sales"]["mbs"], sales_mcorp=s["sales"]["mcorp"],
            )
        )

    for r in payload.get("sales_reps", []):
        db.add(SalesRep(meeting_id=meeting.id, **r))

    for q in payload.get("quotations", []):
        db.add(
            Quotation(
                meeting_id=meeting.id,
                stage=q["stage"],
                mbs=q.get("mbs", 0),
                mcorp=q.get("mcorp", 0),
                per_day=q.get("per_day", 0),
            )
        )

    db.commit()
    print(f"[seed] inserted meeting {mdate} with {len(payload.get('collections', []))} agents.")


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _ensure_admin(db)
        for fname in SEED_FILES:
            path = DATA_DIR / fname
            if not path.exists():
                print(f"[seed] {path} not found — skipping.", file=sys.stderr)
                continue
            with open(path) as f:
                _seed_meeting(db, json.load(f))
        print("[seed] done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
