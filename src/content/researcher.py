"""News and market data research module — crawls RSS feeds and aggregates research."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import feedparser
import httpx

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """A single news article or data point."""
    title: str
    summary: str
    source: str
    url: str = ""
    published: str = ""
    relevance_score: float = 0.0


@dataclass
class ResearchBundle:
    """Aggregated research data for content generation."""
    topic: str
    news_items: list[NewsItem] = field(default_factory=list)
    market_data: dict = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_prompt_context(self) -> str:
        """Convert research bundle into a prompt-ready text block."""
        parts = [f"Research for topic: {self.topic}"]
        parts.append(f"Date: {self.timestamp[:10]}")
        parts.append("")

        if self.news_items:
            parts.append("RECENT NEWS AND DEVELOPMENTS:")
            for item in self.news_items[:10]:
                parts.append(f"{item.source}: {item.title}")
                if item.summary:
                    summary = item.summary[:300]
                    parts.append(f"  {summary}")
                parts.append("")

        if self.market_data:
            parts.append("MARKET DATA:")
            for key, value in self.market_data.items():
                parts.append(f"  {key}: {value}")

        return "\n".join(parts)


class NewsResearcher:
    """Crawls RSS feeds and aggregates commodity market news."""

    COMMODITY_KEYWORDS = {
        "crude_oil_and_energy": [
            "crude oil", "brent", "wti", "opec", "natural gas", "lng",
            "energy", "petroleum", "oil price", "refinery", "gasoline",
        ],
        "metals_and_mining": [
            "copper", "gold", "silver", "iron ore", "lithium", "nickel",
            "aluminum", "steel", "mining", "cobalt", "zinc", "platinum",
        ],
        "agriculture_and_food": [
            "wheat", "corn", "soybean", "rice", "sugar", "coffee", "cocoa",
            "palm oil", "agriculture", "crop", "harvest", "grain", "food price",
        ],
        "shipping_and_logistics": [
            "freight", "shipping", "container", "port", "logistics",
            "supply chain", "baltic dry", "vessel", "cargo", "trade route",
        ],
        "geopolitics_and_trade": [
            "tariff", "sanction", "trade war", "embargo", "export ban",
            "geopolitics", "trade policy", "import duty",
        ],
        "sustainability_and_esg": [
            "carbon", "esg", "green energy", "renewable", "climate",
            "emission", "sustainable", "carbon credit", "net zero",
        ],
    }

    def __init__(self, rss_feeds: list[dict]):
        """Initialize with RSS feed configs from settings.yaml."""
        self.rss_feeds = rss_feeds

    async def fetch_rss_feed(self, feed_config: dict) -> list[NewsItem]:
        """Fetch and parse a single RSS feed."""
        url = feed_config["url"]
        source = feed_config["name"]

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                feed = feedparser.parse(response.text)

            items = []
            cutoff = datetime.utcnow() - timedelta(days=7)

            for entry in feed.entries[:20]:
                published = entry.get("published", "")
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))

                if hasattr(summary, "__len__") and len(summary) > 500:
                    summary = summary[:500]

                items.append(
                    NewsItem(
                        title=title,
                        summary=summary,
                        source=source,
                        url=entry.get("link", ""),
                        published=published,
                    )
                )

            logger.info(f"Fetched {len(items)} items from {source}")
            return items

        except Exception as e:
            logger.warning(f"Failed to fetch RSS feed '{source}': {e}")
            return []

    def _score_relevance(self, item: NewsItem, topic: str) -> float:
        """Score how relevant a news item is to the target topic."""
        keywords = self.COMMODITY_KEYWORDS.get(topic, [])
        if not keywords:
            return 0.5

        text = f"{item.title} {item.summary}".lower()
        matches = sum(1 for kw in keywords if kw in text)
        return min(matches / max(len(keywords) * 0.3, 1), 1.0)

    async def research(self, topic: str) -> ResearchBundle:
        """Gather research for a specific commodity topic.

        Args:
            topic: One of the subtopic keys from settings.yaml

        Returns:
            ResearchBundle with relevant news and market data.
        """
        tasks = [self.fetch_rss_feed(feed) for feed in self.rss_feeds]
        all_results = await asyncio.gather(*tasks)

        all_items = []
        for items in all_results:
            all_items.extend(items)

        for item in all_items:
            item.relevance_score = self._score_relevance(item, topic)

        all_items.sort(key=lambda x: x.relevance_score, reverse=True)

        relevant_items = [item for item in all_items if item.relevance_score > 0.1]
        if not relevant_items:
            relevant_items = all_items[:5]

        bundle = ResearchBundle(
            topic=topic,
            news_items=relevant_items[:15],
        )

        logger.info(
            f"Research complete for '{topic}': {len(bundle.news_items)} relevant items"
        )

        return bundle
