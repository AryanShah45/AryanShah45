"""FastAPI web dashboard for LinkedIn content automation."""

import asyncio
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv, set_key
from fastapi import BackgroundTasks, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .tasks import create_task, run_generation, run_publish, task_store

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
IS_VERCEL = bool(os.getenv("VERCEL"))

# Vercel filesystem is read-only except /tmp — use /tmp for writable dirs
WRITABLE_DIR = Path("/tmp/linkedin_automation") if IS_VERCEL else BASE_DIR
DRAFTS_DIR = WRITABLE_DIR / "posts" / "drafts"
APPROVED_DIR = WRITABLE_DIR / "posts" / "approved"
PUBLISHED_DIR = WRITABLE_DIR / "posts" / "published"
BRIEFINGS_DIR = WRITABLE_DIR / "posts" / "briefings"
DATA_DIR = WRITABLE_DIR / "data"

app = FastAPI(title="LinkedIn Content Dashboard")

# Mount static files and templates
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.on_event("startup")
async def startup():
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    for d in [DRAFTS_DIR, APPROVED_DIR, PUBLISHED_DIR, BRIEFINGS_DIR, DATA_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def load_config() -> tuple[dict, dict]:
    with open(BASE_DIR / "config" / "settings.yaml") as f:
        settings = yaml.safe_load(f)
    with open(BASE_DIR / "config" / "content_calendar.yaml") as f:
        calendar = yaml.safe_load(f)
    return settings, calendar


def load_drafts() -> list[dict]:
    drafts = []
    for f in sorted(DRAFTS_DIR.glob("*.json"), reverse=True):
        try:
            with open(f) as fp:
                data = json.load(fp)
            data["_file"] = str(f)
            drafts.append(data)
        except (json.JSONDecodeError, IOError):
            pass
    return drafts


def load_approved() -> list[dict]:
    posts = []
    for f in sorted(APPROVED_DIR.glob("*.json"), reverse=True):
        try:
            with open(f) as fp:
                posts.append(json.load(fp))
        except (json.JSONDecodeError, IOError):
            pass
    return posts


def load_published() -> list[dict]:
    posts = []
    for f in sorted(PUBLISHED_DIR.glob("*.json"), reverse=True):
        try:
            with open(f) as fp:
                posts.append(json.load(fp))
        except (json.JSONDecodeError, IOError):
            pass
    return posts


def load_performance_log() -> dict:
    log_file = DATA_DIR / "performance_log.json"
    if log_file.exists():
        with open(log_file) as f:
            return json.load(f)
    return {"posts": []}


# ─── Page Routes ────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    drafts = list(DRAFTS_DIR.glob("*.json"))
    approved = list(APPROVED_DIR.glob("*.json"))
    published = list(PUBLISHED_DIR.glob("*.json"))

    recent_drafts = []
    for f in sorted(drafts, reverse=True)[:5]:
        try:
            with open(f) as fp:
                recent_drafts.append(json.load(fp))
        except (json.JSONDecodeError, IOError):
            pass

    # Performance summary from cached data
    log = load_performance_log()
    posts = log.get("posts", [])
    scored = [p for p in posts if p.get("score", 0) > 0]
    summary = {
        "total_posts": len(posts),
        "average_score": round(sum(p["score"] for p in scored) / len(scored), 1) if scored else 0,
        "average_engagement_rate": round(
            sum(p.get("engagement_rate", 0) for p in scored) / len(scored), 2
        ) if scored else 0,
    }

    return templates.TemplateResponse(request, "dashboard.html", {
        "page": "dashboard",
        "draft_count": len(drafts),
        "approved_count": len(approved),
        "published_count": len(published),
        "recent_drafts": recent_drafts,
        "summary": summary,
    })


@app.get("/generate", response_class=HTMLResponse)
async def generate_page(request: Request):
    settings, _ = load_config()
    from src.content.templates import POST_STRUCTURES

    subtopics = settings.get("content", {}).get("subtopics", [])
    post_type_info = [
        {"key": k, "description": v["description"]}
        for k, v in POST_STRUCTURES.items()
    ]

    return templates.TemplateResponse(request, "generate.html", {
        "page": "generate",
        "subtopics": subtopics,
        "post_types": post_type_info,
    })


@app.get("/review", response_class=HTMLResponse)
async def review_page(request: Request):
    drafts = load_drafts()
    return templates.TemplateResponse(request, "review.html", {
        "page": "review",
        "drafts": drafts,
    })


@app.get("/review/{draft_id}", response_class=HTMLResponse)
async def review_detail_page(request: Request, draft_id: str):
    draft_file = DRAFTS_DIR / f"{draft_id}.json"
    if not draft_file.exists():
        return RedirectResponse("/review", status_code=303)

    with open(draft_file) as f:
        draft = json.load(f)

    briefing = ""
    briefing_file = BRIEFINGS_DIR / f"{draft_id}_briefing.md"
    if briefing_file.exists():
        with open(briefing_file) as f:
            briefing = f.read()

    return templates.TemplateResponse(request, "review_detail.html", {
        "page": "review",
        "draft": draft,
        "briefing": briefing,
    })


@app.get("/publish", response_class=HTMLResponse)
async def publish_page(request: Request):
    approved = load_approved()
    has_token = bool(os.getenv("LINKEDIN_ACCESS_TOKEN"))
    return templates.TemplateResponse(request, "publish.html", {
        "page": "publish",
        "approved": approved,
        "has_token": has_token,
    })


@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    log = load_performance_log()
    posts = log.get("posts", [])
    scored = [p for p in posts if p.get("score", 0) > 0]
    scored.sort(key=lambda p: p.get("published_at", ""), reverse=True)

    summary = {
        "total_posts": len(posts),
        "tracked_posts": len(scored),
        "average_score": round(sum(p["score"] for p in scored) / len(scored), 1) if scored else 0,
        "average_engagement_rate": round(
            sum(p.get("engagement_rate", 0) for p in scored) / len(scored), 2
        ) if scored else 0,
        "best_post": max(scored, key=lambda p: p["score"]) if scored else None,
        "worst_post": min(scored, key=lambda p: p["score"]) if scored else None,
    }

    return templates.TemplateResponse(request, "analytics.html", {
        "page": "analytics",
        "posts": scored,
        "summary": summary,
    })


@app.get("/learning", response_class=HTMLResponse)
async def learning_page(request: Request):
    settings, _ = load_config()
    from src.learning.analyzer import PerformanceAnalyzer
    from src.learning.optimizer import ContentOptimizer

    analyzer = PerformanceAnalyzer(settings)
    optimizer = ContentOptimizer(analyzer, settings)

    insights = analyzer.analyze()
    gen_context = optimizer.get_generation_context()

    return templates.TemplateResponse(request, "learning.html", {
        "page": "learning",
        "insights": insights,
        "gen_context": gen_context,
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    settings, _ = load_config()

    # Engine status: which keys/configs are set
    engine_status = {
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "google": bool(os.getenv("GOOGLE_API_KEY")),
        "perplexity": bool(os.getenv("PERPLEXITY_API_KEY")),
        "xai": bool(os.getenv("XAI_API_KEY")),
        "qwen": bool(os.getenv("QWEN_API_KEY")),
        "ollama": bool(os.getenv("OLLAMA_MODEL")),
    }
    active_count = sum(engine_status.values())

    # LinkedIn status
    linkedin_status = {
        "has_credentials": bool(os.getenv("LINKEDIN_CLIENT_ID") and os.getenv("LINKEDIN_CLIENT_SECRET")),
        "has_token": bool(os.getenv("LINKEDIN_ACCESS_TOKEN")),
    }

    return templates.TemplateResponse(request, "settings.html", {
        "page": "settings",
        "settings": settings,
        "engine_status": engine_status,
        "active_engines": active_count,
        "linkedin_status": linkedin_status,
    })


# ─── API Routes ─────────────────────────────────────────────────


@app.post("/api/generate")
async def api_generate(background_tasks: BackgroundTasks, request: Request):
    form = await request.form()

    # Multi-select: collect all checked topics and post_types
    topics = form.getlist("topics")
    custom_topic = form.get("custom_topic", "").strip()
    post_types = form.getlist("post_types")

    # Combine into comma-separated strings for the generator
    topic = ", ".join(t.replace("_", " ") for t in topics) if topics else None
    if custom_topic:
        topic = f"{topic}, {custom_topic}" if topic else custom_topic

    post_type = ", ".join(post_types) if post_types else None

    task_id = create_task()
    background_tasks.add_task(run_generation, task_id, topic or None, post_type or None)
    return JSONResponse({"task_id": task_id, "status": "running"})


@app.get("/api/tasks/{task_id}")
async def api_task_status(task_id: str):
    task = task_store.get(task_id)
    if not task:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    return JSONResponse(task)


@app.post("/api/review/{draft_id}/approve")
async def api_approve(draft_id: str):
    draft_file = DRAFTS_DIR / f"{draft_id}.json"
    if not draft_file.exists():
        return JSONResponse({"error": "Draft not found"}, status_code=404)

    with open(draft_file) as f:
        draft = json.load(f)

    draft["status"] = "approved"
    draft["approved_at"] = datetime.now().isoformat()

    approved_file = APPROVED_DIR / f"{draft_id}.json"
    with open(approved_file, "w") as f:
        json.dump(draft, f, indent=2)

    # Move visual files
    for ext in ["_carousel.pdf", "_image.png"]:
        src = DRAFTS_DIR / f"{draft_id}{ext}"
        if src.exists():
            shutil.move(str(src), str(APPROVED_DIR / f"{draft_id}{ext}"))

    draft_file.unlink()
    return JSONResponse({"status": "approved", "draft_id": draft_id})


@app.post("/api/review/{draft_id}/reject")
async def api_reject(draft_id: str):
    draft_file = DRAFTS_DIR / f"{draft_id}.json"
    if not draft_file.exists():
        return JSONResponse({"error": "Draft not found"}, status_code=404)

    draft_file.unlink()
    for ext in ["_carousel.pdf", "_image.png"]:
        visual = DRAFTS_DIR / f"{draft_id}{ext}"
        if visual.exists():
            visual.unlink()

    return JSONResponse({"status": "rejected", "draft_id": draft_id})


@app.post("/api/review/{draft_id}/edit")
async def api_edit(draft_id: str, body: str = Form(...)):
    draft_file = DRAFTS_DIR / f"{draft_id}.json"
    if not draft_file.exists():
        return JSONResponse({"error": "Draft not found"}, status_code=404)

    with open(draft_file) as f:
        draft = json.load(f)

    draft["post"]["body"] = body
    draft["post"]["metadata"]["char_count"] = len(body)
    draft["post"]["metadata"]["edited"] = True

    with open(draft_file, "w") as f:
        json.dump(draft, f, indent=2)

    return JSONResponse({"status": "updated", "draft_id": draft_id})


@app.post("/api/publish/{draft_id}")
async def api_publish(draft_id: str, background_tasks: BackgroundTasks):
    approved_file = APPROVED_DIR / f"{draft_id}.json"
    if not approved_file.exists():
        return JSONResponse({"error": "Approved post not found"}, status_code=404)

    task_id = create_task()
    background_tasks.add_task(run_publish, task_id, draft_id)
    return JSONResponse({"task_id": task_id, "status": "running"})


@app.post("/api/publish/all")
async def api_publish_all(background_tasks: BackgroundTasks):
    approved = list(APPROVED_DIR.glob("*.json"))
    if not approved:
        return JSONResponse({"error": "No approved posts"}, status_code=404)

    task_ids = []
    for f in approved:
        draft_id = f.stem
        task_id = create_task()
        background_tasks.add_task(run_publish, task_id, draft_id)
        task_ids.append(task_id)

    return JSONResponse({"task_ids": task_ids, "status": "running"})


@app.post("/api/analytics/refresh")
async def api_refresh_analytics():
    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    if not access_token:
        return JSONResponse({"error": "No LinkedIn token configured"}, status_code=400)

    try:
        from src.linkedin.analytics import LinkedInAnalytics
        from src.learning.tracker import PerformanceTracker

        settings, _ = load_config()
        analytics = LinkedInAnalytics(access_token)
        tracker = PerformanceTracker(analytics, settings)
        await tracker.update_metrics()
        return JSONResponse({"status": "refreshed"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/learning/optimize")
async def api_optimize():
    try:
        settings, _ = load_config()
        from src.learning.analyzer import PerformanceAnalyzer
        from src.learning.optimizer import ContentOptimizer

        analyzer = PerformanceAnalyzer(settings)
        optimizer = ContentOptimizer(analyzer, settings)
        report = optimizer.format_report()
        return JSONResponse({"status": "ok", "report": report})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/keys")
async def api_save_keys(request: Request):
    """Save AI engine API keys and Ollama model to .env and update os.environ."""
    try:
        form = await request.form()
        env_path = str(BASE_DIR / ".env")

        if not (BASE_DIR / ".env").exists():
            (BASE_DIR / ".env").touch()

        key_map = {
            "anthropic_key": "ANTHROPIC_API_KEY",
            "openai_key": "OPENAI_API_KEY",
            "google_key": "GOOGLE_API_KEY",
            "perplexity_key": "PERPLEXITY_API_KEY",
            "xai_key": "XAI_API_KEY",
            "qwen_key": "QWEN_API_KEY",
            "ollama_model": "OLLAMA_MODEL",
        }

        for form_field, env_var in key_map.items():
            value = form.get(form_field, "").strip()
            if value:
                if not IS_VERCEL:
                    set_key(env_path, env_var, value)
                os.environ[env_var] = value
            elif not value and os.getenv(env_var):
                if not IS_VERCEL:
                    set_key(env_path, env_var, "")
                os.environ.pop(env_var, None)

        return RedirectResponse("/settings?saved=keys", status_code=303)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/linkedin/credentials")
async def api_save_linkedin_credentials(request: Request):
    """Save LinkedIn OAuth credentials to .env."""
    try:
        form = await request.form()
        env_path = str(BASE_DIR / ".env")

        if not (BASE_DIR / ".env").exists():
            (BASE_DIR / ".env").touch()

        client_id = form.get("client_id", "").strip()
        client_secret = form.get("client_secret", "").strip()

        if client_id:
            if not IS_VERCEL:
                set_key(env_path, "LINKEDIN_CLIENT_ID", client_id)
            os.environ["LINKEDIN_CLIENT_ID"] = client_id
        if client_secret:
            if not IS_VERCEL:
                set_key(env_path, "LINKEDIN_CLIENT_SECRET", client_secret)
            os.environ["LINKEDIN_CLIENT_SECRET"] = client_secret

        return RedirectResponse("/settings?saved=linkedin", status_code=303)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/auth/linkedin")
async def auth_linkedin_start():
    """Start LinkedIn OAuth flow — redirects to LinkedIn authorization page."""
    from src.linkedin.auth import LinkedInAuth

    auth = LinkedInAuth()
    if not auth.is_configured:
        return RedirectResponse("/settings?error=linkedin_not_configured", status_code=303)

    # Use the dashboard callback URL instead of CLI's localhost:8080
    auth_url = auth.get_authorization_url()
    return RedirectResponse(auth_url, status_code=303)


@app.get("/auth/linkedin/callback")
async def auth_linkedin_callback(request: Request, code: str = None, error: str = None):
    """Handle LinkedIn OAuth callback — exchange code for tokens."""
    if error or not code:
        return RedirectResponse(f"/settings?error=linkedin_auth_failed", status_code=303)

    try:
        from src.linkedin.auth import LinkedInAuth

        auth = LinkedInAuth()
        await auth.exchange_code(code)
        os.environ["LINKEDIN_ACCESS_TOKEN"] = auth.access_token
        return RedirectResponse("/settings?saved=linkedin_connected", status_code=303)
    except Exception as e:
        logger.exception("LinkedIn OAuth callback failed")
        return RedirectResponse(f"/settings?error=linkedin_token_failed", status_code=303)


@app.post("/api/settings")
async def api_save_settings(request: Request):
    try:
        form = await request.form()
        settings, _ = load_config()

        # Update LinkedIn settings
        settings["linkedin"]["posting_days"] = form.getlist("posting_days") or settings["linkedin"]["posting_days"]
        settings["linkedin"]["posting_time"] = form.get("posting_time", settings["linkedin"]["posting_time"])
        settings["linkedin"]["timezone"] = form.get("timezone", settings["linkedin"]["timezone"])

        # Update content settings
        settings["content"]["max_length"] = int(form.get("max_length", settings["content"]["max_length"]))
        settings["content"]["min_length"] = int(form.get("min_length", settings["content"]["min_length"]))
        settings["content"]["hashtags_count"] = int(form.get("hashtags_count", settings["content"]["hashtags_count"]))

        # Update visuals
        colors = settings.get("visuals", {}).get("brand_colors", {})
        colors["primary"] = form.get("color_primary", colors.get("primary", "#1B365D"))
        colors["secondary"] = form.get("color_secondary", colors.get("secondary", "#C5A572"))

        if not IS_VERCEL:
            settings_path = BASE_DIR / "config" / "settings.yaml"
            with open(settings_path, "w") as f:
                yaml.safe_dump(settings, f, default_flow_style=False, sort_keys=False)

        return RedirectResponse("/settings?saved=1", status_code=303)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
