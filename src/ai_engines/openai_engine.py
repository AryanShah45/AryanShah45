"""OpenAI GPT engine — engagement hooks and alternative perspectives."""

import openai

from .base import AIEngine, AIResponse


class OpenAIEngine(AIEngine):
    """OpenAI GPT-4 — enhancer that optimizes for engagement.

    GPT focuses on crafting irresistible hooks, contrarian angles,
    and engagement-optimized CTAs.
    """

    def __init__(self, api_key: str, model: str = None):
        super().__init__(api_key, model or "gpt-4o")
        self.client = openai.AsyncOpenAI(api_key=api_key)

    @property
    def name(self) -> str:
        return "openai"

    @property
    def role(self) -> str:
        return "enhancer"

    async def generate(self, prompt: str, context: dict = None) -> AIResponse:
        context = context or {}

        system_prompt = self._build_system_prompt(
            "You are a LinkedIn engagement specialist. Your primary job is to take "
            "commodity market content and make it impossible to ignore. Focus on:\n\n"
            "1. Crafting 3 alternative hooks (first 2 lines) that stop the scroll\n"
            "2. Finding a contrarian or surprising angle on the topic\n"
            "3. Suggesting a call-to-action question that drives comments\n"
            "4. Adding a human, relatable element to technical market content\n\n"
            "Write in flowing paragraphs. No dashes or bullet points."
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )

        choice = response.choices[0]
        tokens = response.usage.total_tokens if response.usage else 0

        return AIResponse(
            content=choice.message.content,
            engine_name=self.name,
            tokens_used=tokens,
            metadata={"model": self.model, "finish_reason": choice.finish_reason},
        )
