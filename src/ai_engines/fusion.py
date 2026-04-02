"""Multi-AI fusion orchestrator — combines outputs from all engines."""

import asyncio
import logging
from typing import Optional

from .base import AIEngine, AIResponse

logger = logging.getLogger(__name__)


class FusionOrchestrator:
    """Orchestrates multi-AI content generation pipeline.

    Pipeline:
    1. Research phase (Perplexity + Grok in parallel) — gather latest info
    2. Analysis phase (Gemini) — extract data-driven insights
    3. Writing phase (Claude) — draft the primary content
    4. Enhancement phase (OpenAI GPT) — optimize hooks and engagement
    5. Fusion phase (Claude) — final rewrite combining best elements
    """

    def __init__(self, engines: dict[str, AIEngine]):
        self.engines = engines
        self.total_tokens = 0

    @classmethod
    def from_api_keys(
        cls,
        anthropic_key: str = None,
        openai_key: str = None,
        google_key: str = None,
        perplexity_key: str = None,
        xai_key: str = None,
    ) -> "FusionOrchestrator":
        """Create orchestrator from API keys, skipping engines without keys."""
        engines = {}

        if anthropic_key:
            from .claude_engine import ClaudeEngine
            engines["claude"] = ClaudeEngine(api_key=anthropic_key)
        if openai_key:
            from .openai_engine import OpenAIEngine
            engines["openai"] = OpenAIEngine(api_key=openai_key)
        if google_key:
            from .gemini_engine import GeminiEngine
            engines["gemini"] = GeminiEngine(api_key=google_key)
        if perplexity_key:
            from .perplexity_engine import PerplexityEngine
            engines["perplexity"] = PerplexityEngine(api_key=perplexity_key)
        if xai_key:
            from .grok_engine import GrokEngine
            engines["grok"] = GrokEngine(api_key=xai_key)

        if not engines:
            raise ValueError("At least one AI engine API key is required.")

        if "claude" not in engines:
            logger.warning(
                "Claude engine not configured. Claude is the primary writer "
                "and fusion engine — content quality may be reduced."
            )

        return cls(engines=engines)

    async def _safe_generate(
        self, engine_name: str, prompt: str, context: dict
    ) -> Optional[AIResponse]:
        """Call an engine safely, returning None on failure."""
        engine = self.engines.get(engine_name)
        if not engine:
            return None
        try:
            response = await engine.generate(prompt, context)
            self.total_tokens += response.tokens_used
            return response
        except Exception as e:
            logger.warning(f"Engine '{engine_name}' failed: {e}")
            return None

    async def research(self, topic: str, context: dict = None) -> dict:
        """Phase 1: Gather real-time research from Perplexity and Grok in parallel."""
        context = context or {}

        research_prompt = (
            f"Research the latest developments in: {topic}\n\n"
            f"Focus on events from the past 7 days. Include specific numbers, "
            f"price movements, policy changes, and expert forecasts. "
            f"This research will be used to write a LinkedIn post."
        )

        tasks = []
        research_engines = ["perplexity", "grok"]
        for engine_name in research_engines:
            tasks.append(self._safe_generate(engine_name, research_prompt, context))

        results = await asyncio.gather(*tasks)

        research_data = {}
        for engine_name, result in zip(research_engines, results):
            if result:
                research_data[engine_name] = result.content

        return research_data

    async def analyze(self, research_data: dict, context: dict = None) -> Optional[str]:
        """Phase 2: Analyze research data with Gemini for data-driven insights."""
        context = context or {}

        combined_research = "\n\n".join(
            f"[{source.upper()}]: {data}" for source, data in research_data.items()
        )

        analysis_prompt = (
            f"Analyze this commodity market research and extract the most compelling "
            f"data points, trends, and insights for a LinkedIn post:\n\n"
            f"{combined_research}\n\n"
            f"Identify the single most interesting angle, the strongest statistics, "
            f"and any surprising patterns. Write your analysis in paragraphs."
        )

        result = await self._safe_generate("gemini", analysis_prompt, context)
        return result.content if result else combined_research

    async def draft(self, analysis: str, context: dict = None) -> Optional[str]:
        """Phase 3: Write the primary draft with Claude."""
        context = context or {}

        draft_prompt = (
            f"Write a LinkedIn post about: {context.get('topic', 'commodity markets')}\n\n"
            f"Post type: {context.get('post_type', 'insight')}\n"
            f"Theme: {context.get('theme', '')}\n"
            f"Target length: {context.get('max_length', 1500)} characters\n\n"
            f"Research and analysis to base this on:\n{analysis}\n\n"
            f"Requirements:\n"
            f"Write in short paragraphs (2-3 sentences). Start with a hook that "
            f"stops the scroll. No dashes or bullet points. End with a question "
            f"that invites discussion. Professional but genuinely human tone."
        )

        result = await self._safe_generate("claude", draft_prompt, context)
        return result.content if result else None

    async def enhance(self, draft: str, context: dict = None) -> Optional[str]:
        """Phase 4: Enhance draft with OpenAI GPT for engagement optimization."""
        context = context or {}

        enhance_prompt = (
            f"Review this LinkedIn post draft and enhance it for maximum engagement:\n\n"
            f"{draft}\n\n"
            f"Provide:\n"
            f"1. Three alternative opening hooks (first 2 lines)\n"
            f"2. A contrarian or surprising angle on the same topic\n"
            f"3. A stronger call-to-action question for the ending\n"
            f"4. Any data points or insights that could strengthen the post\n\n"
            f"Write your enhanced version as a complete post in flowing paragraphs."
        )

        result = await self._safe_generate("openai", enhance_prompt, context)
        return result.content if result else None

    async def fuse(self, drafts: dict, context: dict = None) -> AIResponse:
        """Phase 5: Final fusion rewrite with Claude combining all perspectives."""
        claude = self.engines.get("claude")
        if not claude:
            best_draft = next(iter(drafts.values()), "")
            return AIResponse(content=best_draft, engine_name="fallback")

        return await claude.rewrite_fusion(drafts, context)

    async def generate_post(self, topic: str, context: dict = None) -> dict:
        """Run the full fusion pipeline to generate a LinkedIn post.

        Returns:
            Dict with keys: post, research, analysis, drafts, tokens_used
        """
        context = context or {}
        context["topic"] = topic
        self.total_tokens = 0

        logger.info(f"Starting fusion pipeline for topic: {topic}")

        # Phase 1: Research (parallel)
        logger.info("Phase 1: Research (Perplexity + Grok)")
        research_data = await self.research(topic, context)

        if not research_data:
            research_data = {"fallback": f"Write about current trends in {topic}."}

        # Phase 2: Analysis
        logger.info("Phase 2: Analysis (Gemini)")
        analysis = await self.analyze(research_data, context)

        # Phase 3: Draft (Claude)
        logger.info("Phase 3: Draft (Claude)")
        context["analysis"] = analysis
        claude_draft = await self.draft(analysis, context)

        # Phase 4: Enhance (OpenAI)
        logger.info("Phase 4: Enhance (OpenAI GPT)")
        enhanced_draft = None
        if claude_draft:
            enhanced_draft = await self.enhance(claude_draft, context)

        # Phase 5: Fusion (Claude final rewrite)
        logger.info("Phase 5: Fusion (Claude final rewrite)")
        drafts = {}
        if claude_draft:
            drafts["claude"] = claude_draft
        if enhanced_draft:
            drafts["openai"] = enhanced_draft
        if analysis:
            drafts["gemini_analysis"] = analysis

        if not drafts:
            raise RuntimeError("All AI engines failed. Cannot generate content.")

        if len(drafts) == 1:
            final = AIResponse(
                content=next(iter(drafts.values())),
                engine_name="single_source",
            )
        else:
            final = await self.fuse(drafts, context)

        logger.info(
            f"Fusion pipeline complete. Total tokens: {self.total_tokens}"
        )

        return {
            "post": final.content,
            "research": research_data,
            "analysis": analysis,
            "drafts": drafts,
            "tokens_used": self.total_tokens,
        }
