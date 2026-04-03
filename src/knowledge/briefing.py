"""Knowledge briefing generator — creates topic briefs for the user."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from ..ai_engines.base import AIEngine

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
IS_VERCEL = bool(os.getenv("VERCEL"))
WRITABLE_DIR = Path("/tmp/linkedin_automation") if IS_VERCEL else BASE_DIR
BRIEFINGS_DIR = WRITABLE_DIR / "posts" / "briefings"


class BriefingGenerator:
    """Generates knowledge briefings so the user learns alongside their audience.

    For each post, creates a brief covering:
    - Topic background and context
    - Key data points and their sources
    - Talking points for responding to comments
    - Related trends and what to watch next
    """

    def __init__(self, writer_engine: AIEngine):
        """Initialize with an AI engine for generating briefings.

        Args:
            writer_engine: Typically the Claude engine for high-quality writing.
        """
        self.engine = writer_engine
        BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)

    async def generate_briefing(
        self, post_content: str, topic: str, research_context: str = ""
    ) -> str:
        """Generate a knowledge briefing for a specific post.

        Args:
            post_content: The LinkedIn post text that was generated.
            topic: The commodity market subtopic.
            research_context: The research data used to generate the post.

        Returns:
            Briefing text as a formatted string.
        """
        topic_display = topic.replace("_", " ").title()

        prompt = (
            f"I just wrote a LinkedIn post about {topic_display}. I want to deeply "
            f"understand this topic so I can confidently respond to any comments and "
            f"build genuine expertise. Create a comprehensive knowledge briefing.\n\n"
            f"THE POST I WROTE:\n{post_content}\n\n"
        )

        if research_context:
            prompt += f"RESEARCH USED:\n{research_context}\n\n"

        prompt += (
            f"Create a briefing with these sections:\n\n"
            f"TOPIC BACKGROUND\n"
            f"Explain the broader context of this topic. What's the history? "
            f"Why does it matter? What are the key dynamics at play?\n\n"
            f"KEY DATA POINTS\n"
            f"List the most important numbers, statistics, and facts I should know. "
            f"Where do these numbers come from? How reliable are they?\n\n"
            f"COMMENT RESPONSE GUIDE\n"
            f"What questions might people ask in the comments? Prepare me with "
            f"thoughtful responses. What if someone challenges the main argument?\n\n"
            f"WHAT TO WATCH NEXT\n"
            f"What related developments should I track? What could change the "
            f"narrative? What's the next logical topic to post about?\n\n"
            f"Write in clear, educational paragraphs. This is for my personal "
            f"learning, so be thorough and honest about uncertainties."
        )

        response = await self.engine.generate(prompt, context={"role": "briefing"})
        briefing_text = response.content
        return briefing_text

    async def generate_and_save(
        self,
        draft_id: str,
        post_content: str,
        topic: str,
        research_context: str = "",
    ) -> str:
        """Generate a briefing and save it to the briefings directory.

        Args:
            draft_id: The draft identifier (for file naming).
            post_content: The LinkedIn post text.
            topic: The commodity market subtopic.
            research_context: Research data used for the post.

        Returns:
            Path to the saved briefing file.
        """
        briefing_text = await self.generate_briefing(
            post_content, topic, research_context
        )

        briefing_file = BRIEFINGS_DIR / f"{draft_id}_briefing.md"
        topic_display = topic.replace("_", " ").title()

        with open(briefing_file, "w") as f:
            f.write(f"# Knowledge Briefing: {topic_display}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"Draft: {draft_id}\n\n")
            f.write(briefing_text)

        logger.info(f"Briefing saved: {briefing_file}")
        return str(briefing_file)
