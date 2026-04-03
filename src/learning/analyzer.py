"""Performance analyzer — detects patterns in post performance."""

import json
import logging
import os
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

_BASE = Path(__file__).resolve().parent.parent.parent
DATA_DIR = (Path("/tmp/linkedin_automation") if os.getenv("VERCEL") else _BASE) / "data"


class PerformanceAnalyzer:
    """Analyzes historical post performance to find winning patterns.

    Detects which topics, hooks, post types, lengths, and visual formats
    drive the most engagement, then generates actionable insights.
    """

    def __init__(self, settings: dict):
        self.min_posts = settings.get("learning", {}).get("min_posts_for_insights", 5)
        self.score_weights = settings.get("learning", {}).get(
            "score_weights",
            {"impressions": 0.3, "reactions": 0.25, "comments": 0.25, "shares": 0.2},
        )

    def _load_log(self) -> list:
        log_file = DATA_DIR / "performance_log.json"
        if not log_file.exists():
            return []
        with open(log_file) as f:
            data = json.load(f)
        return [p for p in data.get("posts", []) if p.get("score", 0) > 0]

    def analyze(self) -> dict:
        """Run full analysis and return insights dict.

        Returns:
            Dict of insights (top hooks, best topics, optimal lengths, etc.)
        """
        posts = self._load_log()

        if len(posts) < self.min_posts:
            return {
                "status": "insufficient_data",
                "posts_tracked": len(posts),
                "min_required": self.min_posts,
                "message": (
                    f"Need at least {self.min_posts} tracked posts for insights. "
                    f"Currently have {len(posts)}."
                ),
            }

        insights = {
            "status": "ready",
            "posts_analyzed": len(posts),
            "average_score": round(sum(p["score"] for p in posts) / len(posts), 1),
            "top_performing_hooks": self._analyze_dimension(posts, "hook_style"),
            "best_topics": self._analyze_dimension(posts, "topic"),
            "best_post_types": self._analyze_dimension(posts, "post_type"),
            "best_visual_types": self._analyze_dimension(posts, "visual_type"),
            "optimal_length": self._analyze_length(posts),
            "engagement_tips": self._generate_tips(posts),
            "trend": self._analyze_trend(posts),
        }

        return insights

    def _analyze_dimension(self, posts: list, dimension: str) -> list[str]:
        """Analyze which values of a dimension perform best."""
        scores_by_value = defaultdict(list)

        for post in posts:
            value = post.get(dimension, "unknown")
            scores_by_value[value].append(post["score"])

        averages = {
            val: sum(scores) / len(scores)
            for val, scores in scores_by_value.items()
            if len(scores) >= 2
        }

        if not averages:
            averages = {
                val: sum(scores) / len(scores)
                for val, scores in scores_by_value.items()
            }

        sorted_values = sorted(averages, key=averages.get, reverse=True)
        return sorted_values[:3]

    def _analyze_length(self, posts: list) -> dict:
        """Find the optimal post length range."""
        scored = [(p.get("char_count", 0), p["score"]) for p in posts if p.get("char_count")]

        if not scored:
            return {"min": 800, "max": 1500}

        scored.sort(key=lambda x: x[1], reverse=True)
        top_half = scored[: len(scored) // 2] if len(scored) > 2 else scored

        lengths = [s[0] for s in top_half]
        return {
            "min": min(lengths),
            "max": max(lengths),
            "sweet_spot": round(sum(lengths) / len(lengths)),
        }

    def _generate_tips(self, posts: list) -> list[str]:
        """Generate human-readable engagement tips from the data."""
        tips = []

        # Compare visual vs no-visual
        visual_posts = [p for p in posts if p.get("visual_type", "none") != "none"]
        no_visual = [p for p in posts if p.get("visual_type", "none") == "none"]

        if visual_posts and no_visual:
            avg_visual = sum(p["score"] for p in visual_posts) / len(visual_posts)
            avg_no_visual = sum(p["score"] for p in no_visual) / len(no_visual)
            ratio = avg_visual / max(avg_no_visual, 1)
            if ratio > 1.1:
                tips.append(
                    f"Posts with visuals score {ratio:.1f}x higher than text-only posts"
                )
            elif ratio < 0.9:
                tips.append("Text-only posts are outperforming posts with visuals")

        # Compare carousel vs image
        carousels = [p for p in posts if p.get("visual_type") == "carousel"]
        images = [p for p in posts if p.get("visual_type") == "image"]

        if carousels and images:
            avg_carousel = sum(p["score"] for p in carousels) / len(carousels)
            avg_image = sum(p["score"] for p in images) / len(images)
            if avg_carousel > avg_image * 1.1:
                tips.append("Carousel posts consistently outperform image posts")
            elif avg_image > avg_carousel * 1.1:
                tips.append("Single image posts are getting better engagement than carousels")

        # Topic engagement patterns
        topic_scores = defaultdict(list)
        for p in posts:
            topic_scores[p.get("topic", "")].append(p["score"])

        for topic, scores in topic_scores.items():
            avg = sum(scores) / len(scores)
            overall_avg = sum(p["score"] for p in posts) / len(posts)
            if avg < overall_avg * 0.7 and len(scores) >= 2:
                display = topic.replace("_", " ").title()
                tips.append(
                    f"{display} posts consistently underperform. Consider reducing frequency."
                )

        if not tips:
            tips.append("Keep posting consistently. More data needed for deeper insights.")

        return tips

    def _analyze_trend(self, posts: list) -> str:
        """Analyze whether engagement is trending up or down."""
        if len(posts) < 4:
            return "not_enough_data"

        sorted_posts = sorted(posts, key=lambda p: p.get("published_at", ""))
        mid = len(sorted_posts) // 2
        first_half = sorted_posts[:mid]
        second_half = sorted_posts[mid:]

        avg_first = sum(p["score"] for p in first_half) / len(first_half)
        avg_second = sum(p["score"] for p in second_half) / len(second_half)

        if avg_second > avg_first * 1.1:
            return "improving"
        elif avg_second < avg_first * 0.9:
            return "declining"
        else:
            return "stable"

    def save_insights(self, insights: dict):
        """Save insights to data/learning_insights.json."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        insights_file = DATA_DIR / "learning_insights.json"
        with open(insights_file, "w") as f:
            json.dump(insights, f, indent=2)
        logger.info(f"Learning insights saved to {insights_file}")
