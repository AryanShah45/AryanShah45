"""Qwen engine — Alibaba Cloud's large language model via OpenAI-compatible API."""

import openai

from .base import AIEngine, AIResponse


class QwenEngine(AIEngine):
    """Qwen — writer using Alibaba's Qwen model via DashScope API.

    Uses the OpenAI-compatible endpoint at DashScope, making it easy
    to swap models and leverage Qwen's strong multilingual capabilities.
    """

    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def __init__(self, api_key: str, model: str = None):
        super().__init__(api_key, model or "qwen-plus")
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=self.BASE_URL,
        )

    @property
    def name(self) -> str:
        return "qwen"

    @property
    def role(self) -> str:
        return "writer"

    async def generate(self, prompt: str, context: dict = None) -> AIResponse:
        context = context or {}

        system_prompt = self._build_system_prompt(
            "You are a commodity markets content writer. Your job is to create "
            "professional, insightful LinkedIn posts about commodity markets, "
            "supply chains, and global trade. Write in flowing paragraphs with "
            "a natural human tone. No dashes or bullet points."
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
