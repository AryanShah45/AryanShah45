"""Tests for content generator scheduling and learning analyzer."""

import json
import tempfile
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch

from src.content.generator import ContentGenerator
from src.learning.analyzer import PerformanceAnalyzer

BASE_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def settings():
    with open(BASE_DIR / "config" / "settings.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def calendar():
    with open(BASE_DIR / "config" / "content_calendar.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def generator(settings, calendar):
    """Create a ContentGenerator with None dependencies (testing schedule logic only)."""
    return ContentGenerator(
        fusion=None,
        researcher=None,
        formatter=None,
        settings=settings,
        calendar=calendar,
    )


# --- ContentGenerator schedule & helper tests ---

class TestGetCurrentSchedule:
    def test_returns_valid_schedule(self, generator):
        schedule = generator._get_current_schedule()
        assert "topic" in schedule
        assert "post_type" in schedule
        assert schedule["topic"] in [
            "crude_oil_and_energy",
            "metals_and_mining",
            "agriculture_and_food",
            "shipping_and_logistics",
            "geopolitics_and_trade",
            "sustainability_and_esg",
        ]

    def test_returns_valid_post_type(self, generator):
        schedule = generator._get_current_schedule()
        valid_types = ["insight", "analysis", "story", "data_driven", "opinion", "current_event"]
        assert schedule["post_type"] in valid_types

    def test_has_visual_field(self, generator):
        schedule = generator._get_current_schedule()
        assert "visual" in schedule


class TestSelectHookStyle:
    def test_returns_valid_style(self, generator):
        style = generator._select_hook_style()
        valid_styles = [
            "surprising_stat", "provocative_question", "bold_claim",
            "personal_observation", "current_event_reference", "contrarian_take",
        ]
        assert style in valid_styles

    def test_randomness(self, generator):
        styles = {generator._select_hook_style() for _ in range(50)}
        assert len(styles) > 1


class TestLoadLearningInsights:
    def test_returns_empty_when_no_file(self, generator):
        result = generator._load_learning_insights()
        assert isinstance(result, str)

    def test_loads_valid_insights(self, generator, tmp_path):
        insights = {
            "top_performing_hooks": ["surprising_stat", "bold_claim"],
            "optimal_length": {"min": 900, "max": 1400},
            "best_topics": ["crude_oil_and_energy"],
            "engagement_tips": ["Carousel posts perform 2x better"],
        }
        insights_file = tmp_path / "learning_insights.json"
        with open(insights_file, "w") as f:
            json.dump(insights, f)

        with patch("src.content.generator.DATA_DIR", tmp_path):
            result = generator._load_learning_insights()

        assert "surprising_stat" in result
        assert "900" in result
        assert "crude_oil_and_energy" in result


# --- PerformanceAnalyzer tests ---

def make_post(topic, hook, score, visual="none", char_count=1200, published_at="2026-01-01"):
    return {
        "id": f"post_{score}",
        "topic": topic,
        "hook_style": hook,
        "post_type": "insight",
        "visual_type": visual,
        "char_count": char_count,
        "score": score,
        "published_at": published_at,
        "engagement_rate": score * 0.1,
    }


class TestAnalyzeDimension:
    def test_ranks_by_average_score(self, settings):
        analyzer = PerformanceAnalyzer(settings)
        posts = [
            make_post("oil", "bold_claim", 90),
            make_post("oil", "bold_claim", 80),
            make_post("metals", "question", 40),
            make_post("metals", "question", 30),
            make_post("agri", "stat", 60),
            make_post("agri", "stat", 50),
        ]
        result = analyzer._analyze_dimension(posts, "topic")
        assert result[0] == "oil"
        assert result[-1] == "metals"

    def test_handles_single_occurrence(self, settings):
        analyzer = PerformanceAnalyzer(settings)
        posts = [
            make_post("oil", "bold", 90),
            make_post("metals", "question", 50),
        ]
        result = analyzer._analyze_dimension(posts, "topic")
        assert "oil" in result


class TestAnalyzeLength:
    def test_finds_optimal_range(self, settings):
        analyzer = PerformanceAnalyzer(settings)
        posts = [
            make_post("oil", "h", 90, char_count=1200),
            make_post("oil", "h", 80, char_count=1300),
            make_post("oil", "h", 70, char_count=1100),
            make_post("oil", "h", 30, char_count=500),
            make_post("oil", "h", 20, char_count=2000),
        ]
        result = analyzer._analyze_length(posts)
        assert "min" in result
        assert "max" in result
        assert "sweet_spot" in result
        assert result["sweet_spot"] >= result["min"]
        assert result["sweet_spot"] <= result["max"]

    def test_empty_posts(self, settings):
        analyzer = PerformanceAnalyzer(settings)
        result = analyzer._analyze_length([])
        assert result == {"min": 800, "max": 1500}


class TestAnalyzeTrend:
    def test_improving_trend(self, settings):
        analyzer = PerformanceAnalyzer(settings)
        posts = [
            make_post("oil", "h", 30, published_at="2026-01-01"),
            make_post("oil", "h", 35, published_at="2026-01-02"),
            make_post("oil", "h", 70, published_at="2026-02-01"),
            make_post("oil", "h", 80, published_at="2026-02-02"),
        ]
        assert analyzer._analyze_trend(posts) == "improving"

    def test_declining_trend(self, settings):
        analyzer = PerformanceAnalyzer(settings)
        posts = [
            make_post("oil", "h", 80, published_at="2026-01-01"),
            make_post("oil", "h", 75, published_at="2026-01-02"),
            make_post("oil", "h", 30, published_at="2026-02-01"),
            make_post("oil", "h", 25, published_at="2026-02-02"),
        ]
        assert analyzer._analyze_trend(posts) == "declining"

    def test_stable_trend(self, settings):
        analyzer = PerformanceAnalyzer(settings)
        posts = [
            make_post("oil", "h", 50, published_at="2026-01-01"),
            make_post("oil", "h", 50, published_at="2026-01-02"),
            make_post("oil", "h", 50, published_at="2026-02-01"),
            make_post("oil", "h", 50, published_at="2026-02-02"),
        ]
        assert analyzer._analyze_trend(posts) == "stable"

    def test_insufficient_data(self, settings):
        analyzer = PerformanceAnalyzer(settings)
        posts = [make_post("oil", "h", 50)]
        assert analyzer._analyze_trend(posts) == "not_enough_data"


class TestAnalyze:
    def test_insufficient_data_response(self, settings):
        analyzer = PerformanceAnalyzer(settings)
        with patch.object(analyzer, "_load_log", return_value=[]):
            result = analyzer.analyze()
        assert result["status"] == "insufficient_data"

    def test_full_analysis(self, settings):
        analyzer = PerformanceAnalyzer(settings)
        posts = [
            make_post("oil", "bold_claim", 90, "carousel", 1200, "2026-01-01"),
            make_post("oil", "bold_claim", 85, "carousel", 1300, "2026-01-03"),
            make_post("metals", "question", 60, "image", 1100, "2026-01-05"),
            make_post("metals", "question", 55, "none", 900, "2026-01-07"),
            make_post("agri", "stat", 40, "none", 800, "2026-01-09"),
            make_post("agri", "stat", 35, "none", 700, "2026-02-01"),
        ]
        with patch.object(analyzer, "_load_log", return_value=posts):
            result = analyzer.analyze()

        assert result["status"] == "ready"
        assert result["posts_analyzed"] == 6
        assert result["average_score"] > 0
        assert len(result["top_performing_hooks"]) > 0
        assert len(result["best_topics"]) > 0
        assert "min" in result["optimal_length"]
        assert isinstance(result["engagement_tips"], list)
        assert result["trend"] in ["improving", "declining", "stable", "not_enough_data"]


class TestGenerateTips:
    def test_visual_vs_no_visual_tip(self, settings):
        analyzer = PerformanceAnalyzer(settings)
        posts = [
            make_post("oil", "h", 90, "carousel"),
            make_post("oil", "h", 85, "image"),
            make_post("oil", "h", 30, "none"),
            make_post("oil", "h", 25, "none"),
        ]
        tips = analyzer._generate_tips(posts)
        visual_tip = [t for t in tips if "visual" in t.lower()]
        assert len(visual_tip) > 0

    def test_underperforming_topic_tip(self, settings):
        analyzer = PerformanceAnalyzer(settings)
        posts = [
            make_post("oil", "h", 90),
            make_post("oil", "h", 85),
            make_post("bad_topic", "h", 10),
            make_post("bad_topic", "h", 15),
        ]
        tips = analyzer._generate_tips(posts)
        underperform = [t for t in tips if "underperform" in t.lower()]
        assert len(underperform) > 0
