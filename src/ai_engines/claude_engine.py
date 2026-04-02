"""Claude AI engine — primary content writer with best tone and structure."""

import anthropic

from .base import AIEngine, AIResponse


class ClaudeEngine(AIEngine):
    """Anthropic Claude — primary writer for LinkedIn content.

    Claude handles the core writing, final fusion rewrites, and knowledge briefings.
    Known for nuanced, professional writing with natural human tone.
    """

    def __init__(self, api_key: str, model: str = None):
        super().__init__(api_key, model or "claude-sonnet-4-20250514")
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    @property
    def name(self) -> str:
        return "claude"

    @property
    def role(self) -> str:
        return "writer"

    async def generate(self, prompt: str, context: dict = None) -> AIResponse:
        context = context or {}

        system_prompt = self._build_system_prompt(
            "You are the primary content writer. Your job is to craft LinkedIn posts "
            "that feel genuinely human, professionally insightful, and impossible to "
            "scroll past. Write in short paragraphs (2-3 sentences each) separated by "
            "blank lines. Never use dashes, bullet points, or lists. Every paragraph "
            "should flow naturally into the next, as if you're having a thoughtful "
            "conversation with a smart colleague.\n\n"
            "Start with a powerful hook in the first 2 lines that makes readers stop "
            "scrolling. End with a question that invites genuine discussion."
        )

        if context.get("learning_insights"):
            system_prompt += (
                f"\n\nPast performance insights to guide your writing:\n"
                f"{context['learning_insights']}"
            )

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        content = message.content[0].text
        tokens = message.usage.input_tokens + message.usage.output_tokens

        return AIResponse(
            content=content,
            engine_name=self.name,
            tokens_used=tokens,
            metadata={"model": self.model, "stop_reason": message.stop_reason},
        )

    async def rewrite_fusion(self, drafts: dict, context: dict = None) -> AIResponse:
        """Final fusion rewrite — combine best elements from all engines into one voice.

        Args:
            drafts: Dict of engine_name -> draft content from other engines.
            context: Topic context, research data, and learning insights.
        """
        context = context or {}

        parts = []
        for engine, draft in drafts.items():
            parts.append(f"[{engine.upper()} DRAFT]\n{draft}\n")

        prompt = (
            f"You have received multiple drafts about the same topic from different "
            f"AI perspectives. Your job is to fuse them into ONE exceptional LinkedIn "
            f"post that takes the best insights, hooks, and data points from each.\n\n"
            f"Topic: {context.get('topic', 'Commodity Markets')}\n"
            f"Post type: {context.get('post_type', 'insight')}\n"
            f"Target length: {context.get('max_length', 1500)} characters\n\n"
            f"DRAFTS TO FUSE:\n\n{''.join(parts)}\n\n"
            f"Write the final fused post. Keep the best hook, the strongest data "
            f"points, and the most thought-provoking angle. Write in flowing paragraphs "
            f"with a professional but human tone. No dashes or bullets."
        )

        return await self.generate(prompt, context)
