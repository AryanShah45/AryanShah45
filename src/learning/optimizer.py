"""Content strategy optimizer — auto-adjusts strategy based on performance data."""

import json
import logging
import os
from pathlib import Path

from .analyzer import PerformanceAnalyzer

logger = logging.getLogger(__name__)

_BASE = Path(__file__).resolve().parent.parent.parent
DATA_DIR = (Path("/tmp/linkedin_automation") if os.getenv("VERCEL") else _BASE) / "data"


class ContentOptimizer:
    """Automatically adjusts content strategy based on performance analysis.

    Takes insights from the analyzer and translates them into
    actionable adjustments for the content generation pipeline.
    """

    def __init__(self, analyzer: PerformanceAnalyzer, settings: dict):
        self.analyzer = analyzer
        self.settings = settings

    def optimize(self) -> dict:
        """Run analysis and generate optimization recommendations.

        Returns:
            Dict with adjustments to content strategy.
        """
        insights = self.analyzer.analyze()

        if insights.get("status") != "ready":
            return {
                "status": "skipped",
                "reason": insights.get("message", "Insufficient data"),
                "insights": insights,
            }

        recommendations = {
            "status": "optimized",
            "insights": insights,
            "adjustments": {},
            "summary": [],
        }

        # Adjust topic weights
        if insights.get("best_topics"):
            best = insights["best_topics"]
            recommendations["adjustments"]["preferred_topics"] = best
            recommendations["summary"].append(
                f"Prioritize these topics: {', '.join(t.replace('_', ' ').title() for t in best[:3])}"
            )

        # Adjust hook styles
        if insights.get("top_performing_hooks"):
            best_hooks = insights["top_performing_hooks"]
            recommendations["adjustments"]["preferred_hooks"] = best_hooks
            recommendations["summary"].append(
                f"Use these hook styles more: {', '.join(h.replace('_', ' ').title() for h in best_hooks[:2])}"
            )

        # Adjust post length
        if insights.get("optimal_length"):
            length = insights["optimal_length"]
            recommendations["adjustments"]["target_length"] = length
            if length.get("sweet_spot"):
                recommendations["summary"].append(
                    f"Aim for ~{length['sweet_spot']} characters per post"
                )

        # Adjust visual strategy
        if insights.get("best_visual_types"):
            best_visuals = insights["best_visual_types"]
            recommendations["adjustments"]["preferred_visuals"] = best_visuals
            if best_visuals:
                recommendations["summary"].append(
                    f"Best visual format: {best_visuals[0].replace('_', ' ').title()}"
                )

        # Engagement trend feedback
        trend = insights.get("trend", "stable")
        if trend == "improving":
            recommendations["summary"].append(
                "Your engagement is trending upward. Keep the current strategy going."
            )
        elif trend == "declining":
            recommendations["summary"].append(
                "Engagement is trending down. Consider experimenting with new topics or hook styles."
            )

        # Add tips
        tips = insights.get("engagement_tips", [])
        for tip in tips:
            recommendations["summary"].append(tip)

        # Save optimization results
        self._save_optimization(recommendations)
        self.analyzer.save_insights(insights)

        return recommendations

    def get_generation_context(self) -> dict:
        """Get optimization context to inject into content generation prompts.

        Returns:
            Dict with keys the generator can use to improve content.
        """
        insights_file = DATA_DIR / "learning_insights.json"
        if not insights_file.exists():
            return {}

        try:
            with open(insights_file) as f:
                insights = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

        if insights.get("status") != "ready":
            return {}

        context = {
            "preferred_hooks": insights.get("top_performing_hooks", []),
            "best_topics": insights.get("best_topics", []),
            "optimal_length": insights.get("optimal_length", {}),
            "tips": insights.get("engagement_tips", []),
            "trend": insights.get("trend", "unknown"),
            "average_score": insights.get("average_score", 0),
        }

        return context

    def format_report(self) -> str:
        """Generate a human-readable optimization report."""
        result = self.optimize()

        lines = ["=" * 60]
        lines.append("CONTENT STRATEGY OPTIMIZATION REPORT")
        lines.append("=" * 60)

        if result["status"] == "skipped":
            lines.append(f"\nStatus: {result['reason']}")
            return "\n".join(lines)

        insights = result.get("insights", {})
        lines.append(f"\nPosts Analyzed: {insights.get('posts_analyzed', 0)}")
        lines.append(f"Average Score: {insights.get('average_score', 0)}/100")
        lines.append(f"Engagement Trend: {insights.get('trend', 'unknown').title()}")

        lines.append("\n--- RECOMMENDATIONS ---")
        for i, summary in enumerate(result.get("summary", []), 1):
            lines.append(f"\n{i}. {summary}")

        if insights.get("top_performing_hooks"):
            lines.append(f"\nTop Hook Styles: {', '.join(insights['top_performing_hooks'])}")
        if insights.get("best_topics"):
            topics = [t.replace('_', ' ').title() for t in insights['best_topics']]
            lines.append(f"Best Topics: {', '.join(topics)}")
        if insights.get("optimal_length", {}).get("sweet_spot"):
            lines.append(f"Optimal Length: ~{insights['optimal_length']['sweet_spot']} chars")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def _save_optimization(self, recommendations: dict):
        """Save optimization results to file."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        opt_file = DATA_DIR / "latest_optimization.json"
        with open(opt_file, "w") as f:
            json.dump(recommendations, f, indent=2)
