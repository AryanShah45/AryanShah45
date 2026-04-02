"""Gemini engine — data analysis and market insight extraction."""

import google.generativeai as genai

from .base import AIEngine, AIResponse


class GeminiEngine(AIEngine):
    """Google Gemini — data analyst that extracts patterns and insights.

    Gemini processes market data, price movements, and supply chain metrics
    to generate data-driven insights for content.
    """

    def __init__(self, api_key: str, model: str = None):
        super().__init__(api_key, model or "gemini-2.0-flash")
        genai.configure(api_key=api_key)
        self.genai_model = genai.GenerativeModel(self.model)

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def role(self) -> str:
        return "analyst"

    async def generate(self, prompt: str, context: dict = None) -> AIResponse:
        context = context or {}

        system_context = self._build_system_prompt(
            "You are a commodity market data analyst. Your job is to analyze market "
            "data, price trends, supply-demand dynamics, and trade flows. Extract "
            "the most compelling statistics and patterns that would make strong "
            "talking points in a LinkedIn post.\n\n"
            "Focus on:\n"
            "1. Key numbers and percentages that tell a story\n"
            "2. Trend analysis (what's changing and why)\n"
            "3. Supply-demand imbalances or disruptions\n"
            "4. Comparisons that provide perspective (year-over-year, vs peers)\n\n"
            "Present your analysis in flowing paragraphs, not lists."
        )

        full_prompt = f"{system_context}\n\n{prompt}"

        response = await self.genai_model.generate_content_async(full_prompt)

        return AIResponse(
            content=response.text,
            engine_name=self.name,
            tokens_used=0,
            metadata={"model": self.model},
        )
