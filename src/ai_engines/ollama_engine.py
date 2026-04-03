"""Ollama local model engine — free, private, runs on your machine."""

import httpx

from .base import AIEngine, AIResponse


class OllamaEngine(AIEngine):
    """Ollama local model — writer that runs entirely on your hardware.

    Supports any model available in Ollama (GLM-4, Llama, Mistral, etc.)
    via the OpenAI-compatible API at localhost:11434.
    """

    def __init__(self, api_key: str = "", model: str = None, base_url: str = None):
        super().__init__(api_key or "ollama", model or "glm4")
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")

    @property
    def name(self) -> str:
        return "ollama"

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

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 2000,
                },
            )
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]

        return AIResponse(
            content=choice["message"]["content"],
            engine_name=self.name,
            tokens_used=data.get("usage", {}).get("total_tokens", 0),
            metadata={"model": self.model, "local": True},
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                self._available = response.status_code == 200
                return self._available
        except Exception:
            self._available = False
            return False
