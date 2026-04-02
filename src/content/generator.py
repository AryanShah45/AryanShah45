"""Content generation pipeline — orchestrates research, AI fusion, and formatting."""

import json
import logging
import random
from datetime import datetime
from pathlib import Path

import yaml

from ..ai_engines.fusion import FusionOrchestrator
from .researcher import NewsResearcher
from .formatter import LinkedInFormatter
from .templates import POST_STRUCTURES, HOOK_TEMPLATES, CTA_TEMPLATES

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
POSTS_DIR = BASE_DIR / "posts"
DATA_DIR = BASE_DIR / "data"


class ContentGenerator:
    """Full content generation pipeline from research to formatted post.

    Pipeline:
    1. Determine topic from content calendar
    2. Gather research (RSS feeds + AI research engines)
    3. Load learning insights from past performance
    4. Run AI fusion pipeline (research → analyze → draft → enhance → fuse)
    5. Format for LinkedIn (paragraphs, hashtags, CTA)
    6. Save draft for review
    """

    def __init__(
        self,
        fusion: FusionOrchestrator,
        researcher: NewsResearcher,
        formatter: LinkedInFormatter,
        settings: dict,
        calendar: dict,
    ):
        self.fusion = fusion
        self.researcher = researcher
        self.formatter = formatter
        self.settings = settings
        self.calendar = calendar

    def _get_current_schedule(self) -> dict:
        """Determine today's post topic and type from the content calendar."""
        now = datetime.now()
        day_name = now.strftime("%A").lower()

        weeks = self.calendar.get("weeks", {})
        week_keys = sorted(weeks.keys())

        if not week_keys:
            return {
                "topic": "crude_oil_and_energy",
                "post_type": "insight",
                "visual": "none",
                "theme": "Current trends in commodity markets",
            }

        week_number = (now.isocalendar()[1] - 1) % len(week_keys)
        current_week = weeks[week_keys[week_number]]

        schedule = current_week.get(day_name)
        if not schedule:
            posting_days = self.settings.get("linkedin", {}).get(
                "posting_days", ["monday", "wednesday", "friday"]
            )
            for fallback_day in posting_days:
                if fallback_day in current_week:
                    schedule = current_week[fallback_day]
                    break

        if not schedule:
            first_day = next(iter(current_week.values()), None)
            schedule = first_day or {
                "topic": "crude_oil_and_energy",
                "post_type": "insight",
                "visual": "none",
                "theme": "Current trends in commodity markets",
            }

        return schedule

    def _load_learning_insights(self) -> str:
        """Load accumulated learning insights to inform content generation."""
        insights_file = DATA_DIR / "learning_insights.json"
        if not insights_file.exists():
            return ""

        try:
            with open(insights_file) as f:
                insights = json.load(f)

            parts = []
            if insights.get("top_performing_hooks"):
                parts.append(
                    f"Top performing hook styles: {', '.join(insights['top_performing_hooks'])}"
                )
            if insights.get("optimal_length"):
                parts.append(
                    f"Optimal post length: {insights['optimal_length']['min']}-"
                    f"{insights['optimal_length']['max']} characters"
                )
            if insights.get("best_topics"):
                parts.append(
                    f"Best performing topics: {', '.join(insights['best_topics'])}"
                )
            if insights.get("best_post_types"):
                parts.append(
                    f"Best post types: {', '.join(insights['best_post_types'])}"
                )
            if insights.get("engagement_tips"):
                for tip in insights["engagement_tips"][:3]:
                    parts.append(f"Learning: {tip}")

            return "\n".join(parts) if parts else ""

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Could not load learning insights: {e}")
            return ""

    def _select_hook_style(self) -> str:
        """Select a hook style, weighted by past performance if available."""
        styles = self.calendar.get("hook_styles", list(HOOK_TEMPLATES.keys()))
        return random.choice(styles)

    def _build_generation_prompt(
        self, schedule: dict, research_context: str, hook_style: str
    ) -> str:
        """Build the master prompt for the AI fusion pipeline."""
        structure = POST_STRUCTURES.get(schedule["post_type"], POST_STRUCTURES["insight"])
        hook_examples = HOOK_TEMPLATES.get(hook_style, HOOK_TEMPLATES["surprising_stat"])
        cta_examples = random.sample(CTA_TEMPLATES, min(2, len(CTA_TEMPLATES)))

        topic_display = schedule["topic"].replace("_", " ").title()

        prompt = (
            f"Write a LinkedIn post about: {topic_display}\n"
            f"Theme: {schedule.get('theme', topic_display)}\n"
            f"Post style: {structure['description']}\n\n"
            f"POST STRUCTURE (follow this flow):\n"
        )
        for i, step in enumerate(structure["flow"], 1):
            prompt += f"  Paragraph {i}: {step}\n"

        prompt += (
            f"\nHOOK STYLE: {hook_style.replace('_', ' ').title()}\n"
            f"Example hooks for inspiration (adapt, don't copy):\n"
        )
        for example in hook_examples[:2]:
            prompt += f"  \"{example}\"\n"

        prompt += (
            f"\nCTA EXAMPLES (adapt for this topic):\n"
        )
        for cta in cta_examples:
            prompt += f"  \"{cta}\"\n"

        prompt += (
            f"\nRESEARCH DATA (use these facts and data points):\n"
            f"{research_context}\n\n"
            f"STRICT RULES:\n"
            f"1. Write in short paragraphs (2-3 sentences each)\n"
            f"2. Separate paragraphs with blank lines\n"
            f"3. NEVER use dashes, bullets, numbered lists, or any list formatting\n"
            f"4. Start with a powerful hook in the first 2 lines\n"
            f"5. End with an engaging question\n"
            f"6. Professional but human tone — like a smart colleague sharing insights\n"
            f"7. Include specific numbers and data points from the research\n"
            f"8. Keep total length between 800-1500 characters\n"
            f"9. Do not include any URLs in the post body\n"
            f"10. Use zero or at most one emoji in the entire post\n"
        )

        return prompt

    async def generate(
        self, topic_override: str = None, post_type_override: str = None
    ) -> dict:
        """Generate a complete LinkedIn post with visuals and briefing metadata.

        Args:
            topic_override: Override the content calendar topic.
            post_type_override: Override the post type.

        Returns:
            Dict with post content, metadata, and file paths.
        """
        schedule = self._get_current_schedule()
        if topic_override:
            schedule["topic"] = topic_override
        if post_type_override:
            schedule["post_type"] = post_type_override

        topic = schedule["topic"]
        post_type = schedule["post_type"]
        visual_type = schedule.get("visual", "none")
        theme = schedule.get("theme", "")

        logger.info(f"Generating post: topic={topic}, type={post_type}, visual={visual_type}")

        # Step 1: Gather RSS research
        research_bundle = await self.researcher.research(topic)
        research_context = research_bundle.to_prompt_context()

        # Step 2: Load learning insights
        learning_insights = self._load_learning_insights()

        # Step 3: Select hook style
        hook_style = self._select_hook_style()

        # Step 4: Build master prompt
        master_prompt = self._build_generation_prompt(schedule, research_context, hook_style)

        # Step 5: Run AI fusion pipeline
        fusion_context = {
            "topic": topic,
            "post_type": post_type,
            "theme": theme,
            "hook_style": hook_style,
            "max_length": self.settings.get("content", {}).get("max_length", 1500),
            "learning_insights": learning_insights,
        }

        fusion_result = await self.fusion.generate_post(master_prompt, fusion_context)

        # Step 6: Format for LinkedIn
        formatted = self.formatter.format_post(
            fusion_result["post"], topic, post_type
        )

        # Step 7: Save draft
        draft_id = self._save_draft(formatted, schedule, fusion_result, hook_style)

        return {
            "draft_id": draft_id,
            "formatted_post": formatted,
            "schedule": schedule,
            "hook_style": hook_style,
            "visual_type": visual_type,
            "research_summary": research_context[:500],
            "tokens_used": fusion_result.get("tokens_used", 0),
        }

    def _save_draft(
        self, formatted: dict, schedule: dict, fusion_result: dict, hook_style: str
    ) -> str:
        """Save the generated draft to posts/drafts/ for review."""
        drafts_dir = POSTS_DIR / "drafts"
        drafts_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        topic_short = schedule["topic"].replace("_and_", "_")[:20]
        draft_id = f"{timestamp}_{topic_short}"

        draft_data = {
            "id": draft_id,
            "created_at": datetime.now().isoformat(),
            "status": "draft",
            "topic": schedule["topic"],
            "post_type": schedule["post_type"],
            "visual_type": schedule.get("visual", "none"),
            "theme": schedule.get("theme", ""),
            "hook_style": hook_style,
            "post": formatted,
            "research_summary": fusion_result.get("analysis", "")[:1000],
            "tokens_used": fusion_result.get("tokens_used", 0),
        }

        draft_file = drafts_dir / f"{draft_id}.json"
        with open(draft_file, "w") as f:
            json.dump(draft_data, f, indent=2)

        logger.info(f"Draft saved: {draft_file}")
        return draft_id
