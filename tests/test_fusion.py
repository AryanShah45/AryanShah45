"""Tests for AI engine base classes and fusion orchestrator."""

import asyncio
import pytest

from src.ai_engines.base import AIEngine, AIResponse
from src.ai_engines.fusion import FusionOrchestrator


# --- Mock Engine ---

class MockEngine(AIEngine):
    """A mock AI engine for testing."""

    def __init__(self, name_val="mock", role_val="writer", response_text="Mock output", should_fail=False):
        super().__init__(api_key="test-key", model="mock-model")
        self._name = name_val
        self._role = role_val
        self._response_text = response_text
        self._should_fail = should_fail

    @property
    def name(self) -> str:
        return self._name

    @property
    def role(self) -> str:
        return self._role

    async def generate(self, prompt: str, context: dict = None) -> AIResponse:
        if self._should_fail:
            raise RuntimeError("Engine failure")
        return AIResponse(
            content=self._response_text,
            engine_name=self._name,
            tokens_used=10,
        )

    async def rewrite_fusion(self, drafts: dict, context: dict = None) -> AIResponse:
        combined = " | ".join(drafts.values())
        return AIResponse(
            content=f"Fused: {combined[:200]}",
            engine_name=self._name,
            tokens_used=15,
        )


class TestAIResponse:
    def test_basic_creation(self):
        resp = AIResponse(content="Hello", engine_name="test")
        assert resp.content == "Hello"
        assert resp.engine_name == "test"
        assert resp.tokens_used == 0
        assert resp.metadata == {}

    def test_metadata_defaults_to_dict(self):
        resp = AIResponse(content="X", engine_name="Y", metadata=None)
        assert resp.metadata == {}

    def test_custom_metadata(self):
        resp = AIResponse(content="X", engine_name="Y", metadata={"model": "gpt-4"})
        assert resp.metadata["model"] == "gpt-4"


class TestAIEngine:
    def test_build_system_prompt(self):
        engine = MockEngine()
        prompt = engine._build_system_prompt("You are a researcher.")
        assert "commodity markets" in prompt
        assert "You are a researcher." in prompt

    def test_is_available_default(self):
        engine = MockEngine()
        assert engine.is_available is True

    def test_health_check_success(self):
        engine = MockEngine()
        result = asyncio.get_event_loop().run_until_complete(engine.health_check())
        assert result is True
        assert engine.is_available is True

    def test_health_check_failure(self):
        engine = MockEngine(should_fail=True)
        result = asyncio.get_event_loop().run_until_complete(engine.health_check())
        assert result is False
        assert engine.is_available is False


class TestFusionOrchestrator:
    def test_from_api_keys_no_keys_raises(self):
        with pytest.raises(ValueError, match="At least one"):
            FusionOrchestrator.from_api_keys()

    def test_from_api_keys_creates_engines(self):
        orchestrator = FusionOrchestrator.from_api_keys(
            anthropic_key="test-key",
            openai_key="test-key",
        )
        assert "claude" in orchestrator.engines
        assert "openai" in orchestrator.engines
        assert "gemini" not in orchestrator.engines

    def test_from_api_keys_skips_none(self):
        orchestrator = FusionOrchestrator.from_api_keys(
            anthropic_key="test",
            openai_key=None,
        )
        assert "claude" in orchestrator.engines
        assert "openai" not in orchestrator.engines

    def test_safe_generate_returns_none_on_missing_engine(self):
        orchestrator = FusionOrchestrator(engines={})
        result = asyncio.get_event_loop().run_until_complete(
            orchestrator._safe_generate("nonexistent", "test", {})
        )
        assert result is None

    def test_safe_generate_returns_none_on_failure(self):
        failing_engine = MockEngine(name_val="fail", should_fail=True)
        orchestrator = FusionOrchestrator(engines={"fail": failing_engine})
        result = asyncio.get_event_loop().run_until_complete(
            orchestrator._safe_generate("fail", "test", {})
        )
        assert result is None

    def test_safe_generate_success(self):
        engine = MockEngine(name_val="good", response_text="Great output")
        orchestrator = FusionOrchestrator(engines={"good": engine})
        result = asyncio.get_event_loop().run_until_complete(
            orchestrator._safe_generate("good", "test prompt", {})
        )
        assert result is not None
        assert result.content == "Great output"
        assert orchestrator.total_tokens == 10

    def test_generate_post_with_mock_engines(self):
        """Test the full pipeline with mock engines."""
        engines = {
            "perplexity": MockEngine(name_val="perplexity", role_val="researcher",
                                      response_text="Oil prices rose 5% this week."),
            "grok": MockEngine(name_val="grok", role_val="researcher",
                                response_text="Trending: copper supply concerns."),
            "gemini": MockEngine(name_val="gemini", role_val="analyst",
                                  response_text="Analysis: supply deficit of 200kt."),
            "claude": MockEngine(name_val="claude", role_val="writer",
                                  response_text="The commodity market is telling us something important right now."),
            "openai": MockEngine(name_val="openai", role_val="enhancer",
                                  response_text="What if everything you know about oil is wrong?"),
        }
        orchestrator = FusionOrchestrator(engines=engines)

        result = asyncio.get_event_loop().run_until_complete(
            orchestrator.generate_post("crude oil prices", {"max_length": 1500})
        )

        assert "post" in result
        assert "research" in result
        assert "analysis" in result
        assert "drafts" in result
        assert "tokens_used" in result
        assert result["tokens_used"] > 0
        assert len(result["post"]) > 0

    def test_generate_post_with_only_claude(self):
        """Pipeline should work even with just Claude."""
        engines = {
            "claude": MockEngine(name_val="claude", role_val="writer",
                                  response_text="A single-engine post about commodities."),
        }
        orchestrator = FusionOrchestrator(engines=engines)

        result = asyncio.get_event_loop().run_until_complete(
            orchestrator.generate_post("metals market", {})
        )

        assert "post" in result
        assert len(result["post"]) > 0
