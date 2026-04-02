"""Performance tracker — collects LinkedIn post metrics over time."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from ..linkedin.analytics import LinkedInAnalytics

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
PUBLISHED_DIR = BASE_DIR / "posts" / "published"


class PerformanceTracker:
    """Tracks post performance metrics at scheduled intervals.

    Fetches metrics at 24h, 48h, and 7d after posting, storing
    everything in data/performance_log.json for the analyzer.
    """

    def __init__(self, analytics: LinkedInAnalytics, settings: dict):
        self.analytics = analytics
        self.intervals = settings.get("learning", {}).get(
            "track_intervals_hours", [24, 48, 168]
        )
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _load_log(self) -> dict:
        log_file = DATA_DIR / "performance_log.json"
        if log_file.exists():
            with open(log_file) as f:
                return json.load(f)
        return {"posts": []}

    def _save_log(self, log: dict):
        log_file = DATA_DIR / "performance_log.json"
        with open(log_file, "w") as f:
            json.dump(log, f, indent=2)

    def register_post(self, draft_data: dict, linkedin_post_id: str):
        """Register a newly published post for tracking.

        Args:
            draft_data: The draft data dict (from posts/published/).
            linkedin_post_id: The LinkedIn post URN/ID.
        """
        log = self._load_log()

        entry = {
            "id": draft_data.get("id", ""),
            "linkedin_post_id": linkedin_post_id,
            "published_at": datetime.utcnow().isoformat(),
            "topic": draft_data.get("topic", ""),
            "post_type": draft_data.get("post_type", ""),
            "hook_style": draft_data.get("hook_style", ""),
            "visual_type": draft_data.get("visual_type", "none"),
            "char_count": draft_data.get("post", {}).get("metadata", {}).get("char_count", 0),
            "metrics_24h": None,
            "metrics_48h": None,
            "metrics_7d": None,
            "engagement_rate": 0.0,
            "score": 0,
        }

        log["posts"].append(entry)
        self._save_log(log)
        logger.info(f"Post registered for tracking: {entry['id']}")

    async def update_metrics(self):
        """Check all tracked posts and fetch metrics at due intervals.

        Looks for posts that are past their tracking intervals
        and haven't been measured yet.
        """
        log = self._load_log()
        now = datetime.utcnow()
        updated = False

        for post in log["posts"]:
            published_at = datetime.fromisoformat(post["published_at"])
            linkedin_id = post.get("linkedin_post_id", "")

            if not linkedin_id:
                continue

            hours_since = (now - published_at).total_seconds() / 3600

            for interval in self.intervals:
                key = f"metrics_{interval}h" if interval < 100 else f"metrics_{interval // 24}d"
                if interval == 168:
                    key = "metrics_7d"
                elif interval == 48:
                    key = "metrics_48h"
                elif interval == 24:
                    key = "metrics_24h"

                if post.get(key) is None and hours_since >= interval:
                    try:
                        metrics = await self.analytics.get_post_metrics(linkedin_id)
                        post[key] = metrics
                        updated = True
                        logger.info(
                            f"Updated {key} for post {post['id']}: "
                            f"impressions={metrics.get('impressions', 0)}"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to fetch {key} for {post['id']}: {e}")

            # Update score if we have 7d metrics
            if post.get("metrics_7d"):
                post["engagement_rate"] = post["metrics_7d"].get("engagement_rate", 0)
                post["score"] = self._calculate_score(post)

        if updated:
            self._save_log(log)

    def _calculate_score(self, post: dict) -> int:
        """Calculate a 0-100 score for a post based on weighted metrics."""
        metrics = post.get("metrics_7d") or post.get("metrics_48h") or post.get("metrics_24h")
        if not metrics:
            return 0

        weights = {
            "impressions": 0.3,
            "reactions": 0.25,
            "comments": 0.25,
            "shares": 0.2,
        }

        benchmarks = {
            "impressions": 1000,
            "reactions": 50,
            "comments": 10,
            "shares": 5,
        }

        weighted_sum = 0
        for metric, weight in weights.items():
            value = metrics.get(metric, 0)
            benchmark = benchmarks[metric]
            normalized = min(value / benchmark, 2.0)
            weighted_sum += normalized * weight

        score = int(min(weighted_sum * 50, 100))
        return score

    def get_performance_summary(self) -> dict:
        """Get a summary of all tracked post performance."""
        log = self._load_log()
        posts = log.get("posts", [])

        if not posts:
            return {"total_posts": 0, "message": "No posts tracked yet."}

        scored_posts = [p for p in posts if p.get("score", 0) > 0]

        summary = {
            "total_posts": len(posts),
            "tracked_posts": len(scored_posts),
            "average_score": (
                round(sum(p["score"] for p in scored_posts) / len(scored_posts), 1)
                if scored_posts
                else 0
            ),
            "best_post": max(scored_posts, key=lambda p: p["score"]) if scored_posts else None,
            "worst_post": min(scored_posts, key=lambda p: p["score"]) if scored_posts else None,
            "average_engagement_rate": (
                round(
                    sum(p.get("engagement_rate", 0) for p in scored_posts)
                    / len(scored_posts),
                    2,
                )
                if scored_posts
                else 0
            ),
        }

        return summary
