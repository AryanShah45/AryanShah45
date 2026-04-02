"""Tests for LinkedIn content formatter."""

import pytest
import yaml
from pathlib import Path

from src.content.formatter import LinkedInFormatter

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
def formatter(settings, calendar):
    return LinkedInFormatter(settings, calendar)


class TestCleanContent:
    def test_removes_markdown_headers(self, formatter):
        text = "## Big Title\nSome content here."
        result = formatter._clean_content(text)
        assert "##" not in result
        assert "Big Title" in result

    def test_removes_bold_markdown(self, formatter):
        text = "This is **bold text** in a sentence."
        result = formatter._clean_content(text)
        assert "**" not in result
        assert "bold text" in result

    def test_removes_italic_markdown(self, formatter):
        text = "This is *italic text* here."
        result = formatter._clean_content(text)
        assert result == "This is italic text here."

    def test_removes_bullet_points(self, formatter):
        text = "Intro paragraph.\n\n- Point one\n- Point two\n* Point three"
        result = formatter._clean_content(text)
        assert "- " not in result
        assert "* " not in result
        assert "Point one" in result

    def test_removes_numbered_lists(self, formatter):
        text = "1. First item\n2. Second item\n3. Third item"
        result = formatter._clean_content(text)
        assert "1. " not in result
        assert "First item" in result

    def test_removes_urls(self, formatter):
        text = "Check this out https://example.com for more info."
        result = formatter._clean_content(text)
        assert "https://" not in result
        assert "Check this out" in result

    def test_collapses_excessive_newlines(self, formatter):
        text = "Para one.\n\n\n\n\nPara two."
        result = formatter._clean_content(text)
        assert "\n\n\n" not in result

    def test_strips_whitespace(self, formatter):
        text = "  \n  Some content  \n  "
        result = formatter._clean_content(text)
        assert result == "Some content"


class TestEnsureParagraphStyle:
    def test_splits_paragraphs(self, formatter):
        text = "First paragraph here with enough content to avoid merging by the formatter.\n\nSecond paragraph here also has enough content to stand on its own as a separate block."
        result = formatter._ensure_paragraph_style(text)
        assert len(result) == 2

    def test_splits_long_paragraphs(self, formatter):
        sentences = "Sentence one is fairly long. Sentence two is also long enough. Sentence three adds more. Sentence four continues the thought. Sentence five wraps things up nicely."
        result = formatter._ensure_paragraph_style(sentences)
        assert len(result) >= 2

    def test_merges_short_fragments(self, formatter):
        text = "Short.\n\nAlso short."
        result = formatter._ensure_paragraph_style(text)
        assert len(result) == 1
        assert "Short." in result[0]
        assert "Also short." in result[0]

    def test_removes_inline_newlines(self, formatter):
        text = "This is a line\nthat continues here."
        result = formatter._ensure_paragraph_style(text)
        assert "\n" not in result[0]

    def test_empty_input(self, formatter):
        result = formatter._ensure_paragraph_style("")
        assert result == []


class TestEnforceLength:
    def test_short_content_unchanged(self, formatter):
        text = "Short post content."
        result = formatter._enforce_length(text)
        assert result == text

    def test_trims_long_content(self, formatter):
        paragraphs = ["A" * 400 + "." for _ in range(5)]
        text = "\n\n".join(paragraphs)
        result = formatter._enforce_length(text)
        assert len(result) <= formatter.max_length

    def test_keeps_at_least_one_paragraph(self, formatter):
        text = "A" * 2000
        result = formatter._enforce_length(text)
        assert len(result) > 0


class TestSelectHashtags:
    def test_returns_correct_count(self, formatter):
        hashtags = formatter._select_hashtags("crude_oil_and_energy")
        assert len(hashtags) == formatter.hashtags_count

    def test_includes_topic_hashtags(self, formatter):
        hashtags = formatter._select_hashtags("crude_oil_and_energy")
        oil_tags = {"#CrudeOil", "#EnergyMarkets", "#OPEC", "#OilAndGas",
                    "#EnergyTransition", "#NaturalGas"}
        topic_matches = [h for h in hashtags if h in oil_tags]
        assert len(topic_matches) >= 1

    def test_unknown_topic_uses_universal(self, formatter):
        hashtags = formatter._select_hashtags("nonexistent_topic")
        assert len(hashtags) > 0

    def test_no_duplicates(self, formatter):
        hashtags = formatter._select_hashtags("metals_and_mining")
        assert len(hashtags) == len(set(hashtags))


class TestExtractLinks:
    def test_finds_http_links(self, formatter):
        text = "Visit http://example.com and https://test.org for info."
        links = formatter._extract_links(text)
        assert len(links) == 2

    def test_no_links(self, formatter):
        text = "No links in this text."
        links = formatter._extract_links(text)
        assert links == []


class TestFormatPost:
    def test_returns_complete_structure(self, formatter):
        raw = "This is a test post about commodity markets. It has important insights about oil prices."
        result = formatter.format_post(raw, "crude_oil_and_energy", "insight")
        assert "body" in result
        assert "hashtags" in result
        assert "first_comment" in result
        assert "metadata" in result
        assert result["metadata"]["topic"] == "crude_oil_and_energy"
        assert result["metadata"]["post_type"] == "insight"

    def test_body_contains_hashtags(self, formatter):
        raw = "Market analysis content here. This is a substantial paragraph about trends."
        result = formatter.format_post(raw, "crude_oil_and_energy", "analysis")
        assert "#" in result["body"]

    def test_links_moved_to_first_comment(self, formatter):
        raw = "Check https://reuters.com for more on oil prices. Great analysis here."
        result = formatter.format_post(raw, "crude_oil_and_energy", "insight")
        assert "https://" not in result["body"].split("\n\n")[0]
        assert result["first_comment"] is not None

    def test_no_links_means_no_first_comment(self, formatter):
        raw = "Pure text post about metals and mining trends in the global market."
        result = formatter.format_post(raw, "metals_and_mining", "insight")
        assert result["first_comment"] is None
