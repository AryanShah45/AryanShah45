"""Background task manager for async content generation and publishing."""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# In-memory task store (single-user tool, no persistence needed)
task_store: dict[str, dict] = {}


def create_task() -> str:
    """Create a new task entry and return its ID."""
    task_id = str(uuid.uuid4())[:8]
    task_store[task_id] = {
        "status": "running",
        "created_at": datetime.utcnow().isoformat(),
        "result": None,
        "error": None,
    }
    return task_id


async def run_generation(task_id: str, topic: Optional[str], post_type: Optional[str]):
    """Background task: run the full content generation pipeline."""
    import yaml
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")

    try:
        from src.ai_engines.fusion import FusionOrchestrator
        from src.content.researcher import NewsResearcher
        from src.content.formatter import LinkedInFormatter
        from src.content.generator import ContentGenerator

        # Load config
        with open(BASE_DIR / "config" / "settings.yaml") as f:
            settings = yaml.safe_load(f)
        with open(BASE_DIR / "config" / "content_calendar.yaml") as f:
            calendar = yaml.safe_load(f)

        fusion = FusionOrchestrator.from_api_keys(
            anthropic_key=os.getenv("ANTHROPIC_API_KEY"),
            openai_key=os.getenv("OPENAI_API_KEY"),
            google_key=os.getenv("GOOGLE_API_KEY"),
            perplexity_key=os.getenv("PERPLEXITY_API_KEY"),
            xai_key=os.getenv("XAI_API_KEY"),
        )

        researcher = NewsResearcher(settings.get("rss_feeds", []))
        formatter = LinkedInFormatter(settings, calendar)
        generator = ContentGenerator(fusion, researcher, formatter, settings, calendar)

        result = await generator.generate(
            topic_override=topic,
            post_type_override=post_type,
        )

        # Generate visuals if needed
        visual_type = result["visual_type"]
        if visual_type != "none":
            draft_file = BASE_DIR / "posts" / "drafts" / f"{result['draft_id']}.json"
            with open(draft_file) as f:
                draft_data = json.load(f)

            if visual_type == "carousel":
                from src.visuals.carousel_maker import CarouselMaker
                maker = CarouselMaker(settings.get("visuals", {}))
                maker.generate(draft_data)
            elif visual_type == "image":
                from src.visuals.image_maker import ImageMaker
                maker = ImageMaker(settings.get("visuals", {}))
                maker.generate_post_image(draft_data)

        # Generate knowledge briefing
        claude_engine = fusion.engines.get("claude")
        if claude_engine:
            from src.knowledge.briefing import BriefingGenerator
            briefer = BriefingGenerator(claude_engine)
            post_body = result["formatted_post"]["body"]
            await briefer.generate_and_save(
                result["draft_id"],
                post_body,
                result["schedule"]["topic"],
                result.get("research_summary", ""),
            )

        task_store[task_id]["status"] = "complete"
        task_store[task_id]["result"] = {
            "draft_id": result["draft_id"],
            "topic": result["schedule"]["topic"],
            "post_type": result["schedule"]["post_type"],
            "visual_type": result["visual_type"],
            "tokens_used": result["tokens_used"],
        }

    except Exception as e:
        logger.exception(f"Generation task {task_id} failed")
        task_store[task_id]["status"] = "failed"
        task_store[task_id]["error"] = str(e)


async def run_publish(task_id: str, draft_id: str):
    """Background task: publish a single approved post to LinkedIn."""
    import yaml
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")

    try:
        approved_dir = BASE_DIR / "posts" / "approved"
        published_dir = BASE_DIR / "posts" / "published"
        published_dir.mkdir(parents=True, exist_ok=True)

        draft_file = approved_dir / f"{draft_id}.json"
        if not draft_file.exists():
            raise FileNotFoundError(f"Approved post {draft_id} not found")

        with open(draft_file) as f:
            draft = json.load(f)

        access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
        if not access_token:
            raise ValueError("LINKEDIN_ACCESS_TOKEN not set")

        from src.linkedin.poster import LinkedInPoster
        from src.linkedin.analytics import LinkedInAnalytics
        from src.learning.tracker import PerformanceTracker

        with open(BASE_DIR / "config" / "settings.yaml") as f:
            settings = yaml.safe_load(f)

        poster = LinkedInPoster(access_token)
        analytics = LinkedInAnalytics(access_token)
        tracker = PerformanceTracker(analytics, settings)

        post_body = draft.get("post", {}).get("body", "")
        visual_type = draft.get("visual_type", "none")

        if visual_type == "carousel":
            pdf_path = approved_dir / f"{draft_id}_carousel.pdf"
            if pdf_path.exists():
                result = await poster.post_with_document(
                    post_body, str(pdf_path), draft.get("theme", "")
                )
            else:
                result = await poster.post_text(post_body)
        elif visual_type == "image":
            img_path = approved_dir / f"{draft_id}_image.png"
            if img_path.exists():
                result = await poster.post_with_image(post_body, str(img_path))
            else:
                result = await poster.post_text(post_body)
        else:
            result = await poster.post_text(post_body)

        post_id = result.get("id", "")

        # Post first comment if available
        first_comment = draft.get("post", {}).get("first_comment")
        if first_comment and post_id:
            await poster.post_comment(post_id, first_comment)

        # Register for tracking
        tracker.register_post(draft, post_id)

        # Move to published
        draft["status"] = "published"
        draft["linkedin_post_id"] = post_id
        pub_file = published_dir / f"{draft_id}.json"
        with open(pub_file, "w") as f:
            json.dump(draft, f, indent=2)

        # Clean up
        draft_file.unlink()
        for ext in ["_carousel.pdf", "_image.png"]:
            visual_file = approved_dir / f"{draft_id}{ext}"
            if visual_file.exists():
                visual_file.unlink()

        task_store[task_id]["status"] = "complete"
        task_store[task_id]["result"] = {
            "draft_id": draft_id,
            "linkedin_post_id": post_id,
        }

    except Exception as e:
        logger.exception(f"Publish task {task_id} failed")
        task_store[task_id]["status"] = "failed"
        task_store[task_id]["error"] = str(e)
