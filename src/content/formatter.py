"""LinkedIn content formatter — optimizes posts for the LinkedIn algorithm."""

import re
import random
import logging
import yaml

logger = logging.getLogger(__name__)


class LinkedInFormatter:
    """Formats content according to LinkedIn best practices for maximum reach.

    Key rules:
    - Hook in first 2 lines (before "see more" fold)
    - Short paragraphs (2-3 sentences), separated by blank lines
    - No dashes, bullets, or lists — flowing narrative only
    - 3-5 hashtags at the end
    - Engaging CTA question at the end
    - No external links in body (links go in first comment)
    - Minimal emojis (0-2 per post)
    - Optimal length: 1100-1500 characters
    """

    def __init__(self, settings: dict, calendar: dict):
        self.settings = settings
        self.calendar = calendar
        self.content_config = settings.get("content", {})
        self.max_length = self.content_config.get("max_length", 1500)
        self.min_length = self.content_config.get("min_length", 800)
        self.hashtags_count = self.content_config.get("hashtags_count", 4)

    def format_post(self, raw_content: str, topic: str, post_type: str) -> dict:
        """Format raw AI-generated content into LinkedIn-optimized post.

        Args:
            raw_content: Raw text from the AI fusion pipeline.
            topic: Subtopic key (e.g., 'crude_oil_and_energy').
            post_type: Post structure type (e.g., 'insight', 'analysis').

        Returns:
            Dict with 'body' (formatted post), 'hashtags', 'first_comment', 'metadata'.
        """
        cleaned = self._clean_content(raw_content)
        paragraphs = self._ensure_paragraph_style(cleaned)
        formatted = self._apply_spacing(paragraphs)
        trimmed = self._enforce_length(formatted)
        hashtags = self._select_hashtags(topic)
        final_body = f"{trimmed}\n\n{' '.join(hashtags)}"

        links = self._extract_links(raw_content)
        first_comment = None
        if links:
            first_comment = "Sources and further reading:\n" + "\n".join(links)

        return {
            "body": final_body,
            "hashtags": hashtags,
            "first_comment": first_comment,
            "metadata": {
                "char_count": len(final_body),
                "paragraph_count": len(paragraphs),
                "topic": topic,
                "post_type": post_type,
            },
        }

    def _clean_content(self, text: str) -> str:
        """Remove unwanted formatting artifacts from AI output."""
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'^[\-\*\u2022]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()
        return text

    def _ensure_paragraph_style(self, text: str) -> list[str]:
        """Split text into clean paragraphs, merging short fragments."""
        raw_paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        paragraphs = []

        for para in raw_paragraphs:
            para = para.replace('\n', ' ')
            para = re.sub(r'\s+', ' ', para).strip()

            if not para:
                continue

            sentences = re.split(r'(?<=[.!?])\s+', para)
            if len(sentences) > 4:
                mid = len(sentences) // 2
                paragraphs.append(' '.join(sentences[:mid]))
                paragraphs.append(' '.join(sentences[mid:]))
            else:
                paragraphs.append(para)

        merged = []
        for para in paragraphs:
            if merged and len(merged[-1]) < 80 and len(para) < 80:
                merged[-1] = f"{merged[-1]} {para}"
            else:
                merged.append(para)

        return merged

    def _apply_spacing(self, paragraphs: list[str]) -> str:
        """Join paragraphs with blank lines for LinkedIn readability."""
        return '\n\n'.join(paragraphs)

    def _enforce_length(self, text: str) -> str:
        """Trim or flag content that's too long or too short."""
        if len(text) <= self.max_length:
            return text

        paragraphs = text.split('\n\n')
        result = []
        current_length = 0

        for para in paragraphs:
            if current_length + len(para) + 2 > self.max_length:
                if not result:
                    result.append(para[:self.max_length])
                break
            result.append(para)
            current_length += len(para) + 2

        trimmed = '\n\n'.join(result)

        if len(trimmed) < self.min_length:
            logger.warning(
                f"Post is short ({len(trimmed)} chars, min {self.min_length}). "
                f"Consider regenerating."
            )

        return trimmed

    def _select_hashtags(self, topic: str) -> list[str]:
        """Select optimal hashtags from the calendar's hashtag pools."""
        hashtag_pools = self.calendar.get("hashtags", {})
        topic_tags = hashtag_pools.get(topic, [])
        universal_tags = hashtag_pools.get("universal", [])

        selected = []

        if topic_tags:
            n_topic = min(self.hashtags_count - 1, len(topic_tags))
            selected.extend(random.sample(topic_tags, n_topic))

        remaining = self.hashtags_count - len(selected)
        if universal_tags and remaining > 0:
            available = [t for t in universal_tags if t not in selected]
            selected.extend(random.sample(available, min(remaining, len(available))))

        return selected[:self.hashtags_count]

    def _extract_links(self, text: str) -> list[str]:
        """Extract any URLs from the original content for first comment."""
        return re.findall(r'https?://\S+', text)
