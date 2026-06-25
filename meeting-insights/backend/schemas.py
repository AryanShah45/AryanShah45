"""Pydantic request/response models."""
from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# --- Auth ---
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class UserCreate(BaseModel):
    username: str
    password: str = Field(min_length=4)
    role: str = "viewer"  # viewer | editor | admin


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: str


# --- Collections ---
class CollectionIn(BaseModel):
    agent: str
    d90_mbs: float = 0
    d90_mcorp: float = 0
    d60_mbs: float = 0
    d60_mcorp: float = 0
    d30_mbs: float = 0
    d30_mcorp: float = 0
    other_mbs: float = 0
    other_mcorp: float = 0
    collected_mbs: float = 0
    collected_mcorp: float = 0
    coll_per_day: float = 0
    coll_pct: float = 0
    new_target: float = 0
    last_week_target: float = 0


class SalesIn(BaseModel):
    salesperson: str
    branch: str = "ALL"
    purchase_mbs: float = 0
    purchase_mcorp: float = 0
    sales_mbs: float = 0
    sales_mcorp: float = 0


class SalesRepIn(BaseModel):
    salesperson: str
    target_tons: float = 0
    achieve_pct_tons: float = 0
    target_party: float = 0
    achieve_pct_party: float = 0
    total_visit: int = 0
    total_inquiry: int = 0
    inquiry_confirm: int = 0
    order_loss: int = 0


class QuotationIn(BaseModel):
    stage: str
    mbs: float = 0
    mcorp: float = 0
    per_day: float = 0


class MeetingCreate(BaseModel):
    meeting_date: date
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    source_file: Optional[str] = None
    collections: list[CollectionIn] = []
    sales: list[SalesIn] = []
    sales_reps: list[SalesRepIn] = []
    quotations: list[QuotationIn] = []


class MeetingSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    meeting_date: date
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    source_file: Optional[str] = None
