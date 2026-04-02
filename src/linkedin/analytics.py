"""LinkedIn analytics — fetches post performance metrics."""

import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


class LinkedInAnalytics:
    """Fetches and processes LinkedIn post performance metrics.

    Collects impressions, reactions, comments, and shares for
    the self-learning feedback loop.
    """

    API_BASE = "https://api.linkedin.com/v2"

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202401",
        }

    async def get_post_metrics(self, post_urn: str) -> dict:
        """Fetch engagement metrics for a specific post.

        Args:
            post_urn: The URN identifier of the LinkedIn post.

        Returns:
            Dict with impressions, reactions, comments, shares.
        """
        metrics = {
            "impressions": 0,
            "reactions": 0,
            "comments": 0,
            "shares": 0,
            "clicks": 0,
            "engagement_rate": 0.0,
            "fetched_at": datetime.utcnow().isoformat(),
        }

        try:
            social_metrics = await self._get_social_actions(post_urn)
            metrics.update(social_metrics)

            if metrics["impressions"] > 0:
                total_engagement = (
                    metrics["reactions"]
                    + metrics["comments"]
                    + metrics["shares"]
                    + metrics["clicks"]
                )
                metrics["engagement_rate"] = round(
                    (total_engagement / metrics["impressions"]) * 100, 2
                )

        except Exception as e:
            logger.warning(f"Failed to fetch metrics for {post_urn}: {e}")

        return metrics

    async def _get_social_actions(self, post_urn: str) -> dict:
        """Fetch social action counts (likes, comments, shares)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE}/socialActions/{post_urn}",
                headers=self.headers,
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "reactions": data.get("likesSummary", {}).get("totalLikes", 0),
                    "comments": data.get("commentsSummary", {}).get("totalFirstLevelComments", 0),
                }

            logger.warning(f"Social actions API returned {response.status_code}")
            return {}

    async def get_share_statistics(self, post_urn: str) -> dict:
        """Fetch share statistics including impressions."""
        async with httpx.AsyncClient() as client:
            params = {
                "q": "organizationalEntity",
                "shares[0]": post_urn,
            }
            response = await client.get(
                f"{self.API_BASE}/organizationalEntityShareStatistics",
                headers=self.headers,
                params=params,
            )

            if response.status_code == 200:
                data = response.json()
                elements = data.get("elements", [])
                if elements:
                    stats = elements[0].get("totalShareStatistics", {})
                    return {
                        "impressions": stats.get("impressionCount", 0),
                        "clicks": stats.get("clickCount", 0),
                        "shares": stats.get("shareCount", 0),
                        "engagement": stats.get("engagement", 0),
                    }

            return {}

    async def get_recent_posts(self, person_urn: str, count: int = 10) -> list:
        """Fetch recent posts for the authenticated user.

        Args:
            person_urn: The person URN of the user.
            count: Number of recent posts to fetch.

        Returns:
            List of post data dicts.
        """
        async with httpx.AsyncClient() as client:
            params = {
                "q": "authors",
                "authors": f"List(urn:li:person:{person_urn})",
                "count": count,
                "sortBy": "LAST_MODIFIED",
            }
            response = await client.get(
                f"{self.API_BASE}/ugcPosts",
                headers=self.headers,
                params=params,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("elements", [])

            logger.warning(f"Failed to fetch recent posts: {response.status_code}")
            return []
