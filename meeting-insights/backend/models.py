"""ORM models.

Design note: meeting-level totals (outstanding / collection / sales / purchase) are NOT stored.
They are derived from the child rows in `analytics.py` so there is a single source of truth and no
risk of stored totals drifting out of sync with the line items.
"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="viewer")  # viewer | editor | admin
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_date: Mapped[date] = mapped_column(Date, index=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_file: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    collections: Mapped[list["Collection"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )
    sales: Mapped[list["Sales"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )
    sales_reps: Mapped[list["SalesRep"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )
    quotations: Mapped[list["Quotation"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )
    insights: Mapped[list["Insight"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )


class Collection(Base):
    """One collection agent's receivables book + this week's recovery."""

    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"))
    agent: Mapped[str] = mapped_column(String(80))

    # Ageing buckets, split by unit (MBS / MCORP).
    d90_mbs: Mapped[float] = mapped_column(Float, default=0)
    d90_mcorp: Mapped[float] = mapped_column(Float, default=0)
    d60_mbs: Mapped[float] = mapped_column(Float, default=0)
    d60_mcorp: Mapped[float] = mapped_column(Float, default=0)
    d30_mbs: Mapped[float] = mapped_column(Float, default=0)
    d30_mcorp: Mapped[float] = mapped_column(Float, default=0)
    other_mbs: Mapped[float] = mapped_column(Float, default=0)
    other_mcorp: Mapped[float] = mapped_column(Float, default=0)

    # Recovered this week.
    collected_mbs: Mapped[float] = mapped_column(Float, default=0)
    collected_mcorp: Mapped[float] = mapped_column(Float, default=0)

    coll_per_day: Mapped[float] = mapped_column(Float, default=0)
    coll_pct: Mapped[float] = mapped_column(Float, default=0)
    new_target: Mapped[float] = mapped_column(Float, default=0)
    last_week_target: Mapped[float] = mapped_column(Float, default=0)

    meeting: Mapped["Meeting"] = relationship(back_populates="collections")


class Sales(Base):
    """Purchase / sales tonnage for a salesperson at a branch."""

    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"))
    salesperson: Mapped[str] = mapped_column(String(80))
    branch: Mapped[str] = mapped_column(String(80), default="ALL")
    purchase_mbs: Mapped[float] = mapped_column(Float, default=0)
    purchase_mcorp: Mapped[float] = mapped_column(Float, default=0)
    sales_mbs: Mapped[float] = mapped_column(Float, default=0)
    sales_mcorp: Mapped[float] = mapped_column(Float, default=0)

    meeting: Mapped["Meeting"] = relationship(back_populates="sales")


class SalesRep(Base):
    """Per-salesperson targets and activity (visits / inquiries)."""

    __tablename__ = "sales_reps"

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"))
    salesperson: Mapped[str] = mapped_column(String(80))
    target_tons: Mapped[float] = mapped_column(Float, default=0)
    achieve_pct_tons: Mapped[float] = mapped_column(Float, default=0)
    target_party: Mapped[float] = mapped_column(Float, default=0)
    achieve_pct_party: Mapped[float] = mapped_column(Float, default=0)
    total_visit: Mapped[int] = mapped_column(Integer, default=0)
    total_inquiry: Mapped[int] = mapped_column(Integer, default=0)
    inquiry_confirm: Mapped[int] = mapped_column(Integer, default=0)
    order_loss: Mapped[int] = mapped_column(Integer, default=0)

    meeting: Mapped["Meeting"] = relationship(back_populates="sales_reps")


class Quotation(Base):
    """One stage of the quotation funnel."""

    __tablename__ = "quotations"

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"))
    stage: Mapped[str] = mapped_column(String(40))  # PREPARED | CONFIRMED | PENDING | ...
    mbs: Mapped[float] = mapped_column(Float, default=0)
    mcorp: Mapped[float] = mapped_column(Float, default=0)
    per_day: Mapped[float] = mapped_column(Float, default=0)

    meeting: Mapped["Meeting"] = relationship(back_populates="quotations")


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String(20), default="computed")  # ai | computed
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    meeting: Mapped["Meeting"] = relationship(back_populates="insights")
