"""Grok engine — trending topics and real-time news from xAI."""

import httpx

from .base import AIEngine, AIResponse


class GrokEngine(AIEngine):
    """xAI Grok — real-time trending news and social sentiment.

    Grok taps into real-time data to identify trending commodity topics,
    market sentiment, and breaking developments.
    """

    API_URL = "https://api.x.ai/v1/chat/completions"

    def __init__(self, api_key: str, model: str = None):
        super().__init__(api_key, model or "grok-3")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @property
    def name(self) -> str:
        return "grok"

    @property
    def role(self) -> str:
        return "researcher"

    async def generate(self, prompt: str, context: dict = None) -> AIResponse:
        context = context or {}

        system_prompt = self._build_system_prompt(
            "You are a real-time commodity markets trend spotter. Identify what is "
            "trending right now in commodity markets, supply chains, and global trade. "
            "Focus on:\n\n"
            "1. What commodity topics are people talking about today\n"
            "2. Breaking developments in energy, metals, agriculture\n"
            "3. Social and market sentiment around key commodities\n"
            "4. Viral or highly-discussed supply chain events\n"
            "5. Emerging narratives that could gain traction on LinkedIn\n\n"
            "Present your findings as a concise trend report in flowing paragraphs."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 2000,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                self.API_URL, json=payload, headers=self.headers
            )
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]
        content = choice["message"]["content"]

        return AIResponse(
            content=content,
            engine_name=self.name,
            tokens_used=data.get("usage", {}).get("total_tokens", 0),
            metadata={"model": self.model},
        )
