"""FastAPI application: auth, meeting CRUD, analytics, insights, trends, users."""
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import analytics as analytics_mod
from . import schemas
from .ai import generate_insights
from .auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)
from .config import FRONTEND_DIR
from .database import Base, engine, get_db
from .models import Collection, Insight, Meeting, Quotation, Sales, SalesRep, User

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Meeting Insights Platform", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- Auth
@app.post("/api/auth/login", response_model=schemas.TokenResponse)
def login(body: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(user.username, user.role)
    return schemas.TokenResponse(access_token=token, username=user.username, role=user.role)


@app.get("/api/auth/me", response_model=schemas.UserOut)
def me(user: User = Depends(get_current_user)):
    return user


# ---------------------------------------------------------------- Users (admin)
@app.get("/api/users", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_role("admin"))):
    return db.query(User).order_by(User.username).all()


@app.post("/api/users", response_model=schemas.UserOut, status_code=201)
def create_user(
    body: schemas.UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    if body.role not in ("viewer", "editor", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role")
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=409, detail="Username already exists")
    user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.delete("/api/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_role("admin")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == actor.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    db.delete(user)
    db.commit()


# ---------------------------------------------------------------- Meetings
def _persist_meeting(db: Session, body: schemas.MeetingCreate, created_by: str) -> Meeting:
    meeting = Meeting(
        meeting_date=body.meeting_date,
        period_start=body.period_start,
        period_end=body.period_end,
        source_file=body.source_file,
        created_by=created_by,
    )
    db.add(meeting)
    db.flush()
    for c in body.collections:
        db.add(Collection(meeting_id=meeting.id, **c.model_dump()))
    for srow in body.sales:
        db.add(Sales(meeting_id=meeting.id, **srow.model_dump()))
    for r in body.sales_reps:
        db.add(SalesRep(meeting_id=meeting.id, **r.model_dump()))
    for q in body.quotations:
        db.add(Quotation(meeting_id=meeting.id, **q.model_dump()))
    db.commit()
    db.refresh(meeting)
    return meeting


@app.get("/api/meetings", response_model=list[schemas.MeetingSummary])
def list_meetings(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Meeting).order_by(Meeting.meeting_date.desc()).all()


@app.post("/api/meetings", status_code=201)
def create_meeting(
    body: schemas.MeetingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("editor")),
):
    meeting = _persist_meeting(db, body, user.username)
    return {"id": meeting.id}


def _get_meeting_or_404(db: Session, meeting_id: int) -> Meeting:
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@app.get("/api/meetings/{meeting_id}/analytics")
def meeting_analytics(
    meeting_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    return analytics_mod.meeting_analytics(_get_meeting_or_404(db, meeting_id))


@app.delete("/api/meetings/{meeting_id}", status_code=204)
def delete_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("editor")),
):
    db.delete(_get_meeting_or_404(db, meeting_id))
    db.commit()


@app.get("/api/meetings/{meeting_id}/insights")
def meeting_insights(
    meeting_id: int,
    refresh: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    meeting = _get_meeting_or_404(db, meeting_id)
    cached = (
        db.query(Insight)
        .filter(Insight.meeting_id == meeting_id)
        .order_by(Insight.created_at.desc())
        .first()
    )
    if cached and not refresh:
        return {"body": cached.body, "source": cached.source, "cached": True}

    bundle = analytics_mod.meeting_analytics(meeting)
    body, source = generate_insights(bundle)
    db.add(Insight(meeting_id=meeting_id, body=body, source=source))
    db.commit()
    return {"body": body, "source": source, "cached": False}


# ---------------------------------------------------------------- Dashboard & trends
@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    meeting = db.query(Meeting).order_by(Meeting.meeting_date.desc()).first()
    if not meeting:
        return {"empty": True}
    return analytics_mod.meeting_analytics(meeting)


@app.get("/api/trends")
def trends(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    meetings = db.query(Meeting).all()
    return analytics_mod.trends(meetings)


# ---------------------------------------------------------------- Static frontend
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
