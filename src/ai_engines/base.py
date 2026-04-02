"""Abstract base class for all AI engines."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AIResponse:
    """Standardized response from any AI engine."""
    content: str
    engine_name: str
    tokens_used: int = 0
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AIEngine(ABC):
    """Base interface for all AI engines used in the fusion pipeline."""

    def __init__(self, api_key: str, model: str = None):
        self.api_key = api_key
        self.model = model
        self._available = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Engine identifier name."""
        ...

    @property
    @abstractmethod
    def role(self) -> str:
        """Role in the fusion pipeline (research, analysis, writer, enhancer)."""
        ...

    @abstractmethod
    async def generate(self, prompt: str, context: dict = None) -> AIResponse:
        """Generate content based on prompt and optional context.

        Args:
            prompt: The generation prompt.
            context: Additional context (topic, research data, learnings, etc.)

        Returns:
            AIResponse with generated content.
        """
        ...

    async def health_check(self) -> bool:
        """Check if this engine is available and responding."""
        try:
            response = await self.generate("Reply with OK.", context={})
            self._available = bool(response and response.content)
            return self._available
        except Exception:
            self._available = False
            return False

    @property
    def is_available(self) -> bool:
        """Whether the engine passed its last health check."""
        return self._available if self._available is not None else True

    def _build_system_prompt(self, role_context: str) -> str:
        """Build a system prompt tailored to this engine's role."""
        base = (
            "You are an expert content strategist specializing in commodity markets "
            "and supply chain topics. You create professional content with a natural "
            "human tone. You never use dashes or bullet points. You write in flowing "
            "paragraphs that feel like a knowledgeable colleague sharing insights."
        )
        return f"{base}\n\n{role_context}"
