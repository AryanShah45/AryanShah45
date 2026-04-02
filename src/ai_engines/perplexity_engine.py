"""Perplexity engine — real-time research with source citations."""

import httpx

from .base import AIEngine, AIResponse


class PerplexityEngine(AIEngine):
    """Perplexity AI — real-time researcher with grounded, cited information.

    Perplexity searches the web for the latest commodity news, price data,
    and market developments, returning cited and verified information.
    """

    API_URL = "https://api.perplexity.ai/chat/completions"

    def __init__(self, api_key: str, model: str = None):
        super().__init__(api_key, model or "sonar-pro")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @property
    def name(self) -> str:
        return "perplexity"

    @property
    def role(self) -> str:
        return "researcher"

    async def generate(self, prompt: str, context: dict = None) -> AIResponse:
        context = context or {}

        system_prompt = self._build_system_prompt(
            "You are a commodity markets research analyst. Search for the latest "
            "news, price movements, and developments in commodity markets and "
            "supply chains. Always cite your sources. Focus on:\n\n"
            "1. Breaking news and recent events (last 7 days)\n"
            "2. Price movements with specific numbers\n"
            "3. Supply chain disruptions or shifts\n"
            "4. Policy changes, tariffs, sanctions affecting commodities\n"
            "5. Expert opinions and forecasts from major institutions\n\n"
            "Present findings as a research brief in flowing paragraphs."
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
        citations = data.get("citations", [])

        return AIResponse(
            content=content,
            engine_name=self.name,
            tokens_used=data.get("usage", {}).get("total_tokens", 0),
            metadata={"model": self.model, "citations": citations},
        )
