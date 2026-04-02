"""Carousel PDF generator — creates multi-slide LinkedIn carousels."""

import json
import logging
import textwrap
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class CarouselMaker:
    """Generates branded PDF carousels for LinkedIn document posts.

    Creates professional, slide-based PDFs with consistent branding:
    - Slide 1: Title slide with hook
    - Slides 2-N: Content slides with key points
    - Final slide: CTA and author info
    """

    SLIDE_WIDTH = 1080
    SLIDE_HEIGHT = 1080
    MARGIN = 80

    def __init__(self, brand_config: dict):
        self.colors = brand_config.get("brand_colors", {})
        self.primary = HexColor(self.colors.get("primary", "#1B365D"))
        self.secondary = HexColor(self.colors.get("secondary", "#C5A572"))
        self.background = HexColor(self.colors.get("background", "#FFFFFF"))
        self.text_color = HexColor(self.colors.get("text", "#2D2D2D"))
        self.num_slides = brand_config.get("carousel_slides", 6)

    def _create_title_style(self) -> ParagraphStyle:
        return ParagraphStyle(
            "Title",
            fontSize=42,
            leading=50,
            textColor=self.background,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        )

    def _create_body_style(self) -> ParagraphStyle:
        return ParagraphStyle(
            "Body",
            fontSize=28,
            leading=38,
            textColor=self.text_color,
            alignment=TA_LEFT,
            fontName="Helvetica",
        )

    def _create_subtitle_style(self) -> ParagraphStyle:
        return ParagraphStyle(
            "Subtitle",
            fontSize=22,
            leading=30,
            textColor=self.secondary,
            alignment=TA_CENTER,
            fontName="Helvetica",
        )

    def _draw_background(self, c: canvas.Canvas, slide_type: str = "content"):
        """Draw the slide background."""
        if slide_type == "title":
            c.setFillColor(self.primary)
            c.rect(0, 0, self.SLIDE_WIDTH, self.SLIDE_HEIGHT, fill=True, stroke=False)
            c.setFillColor(self.secondary)
            c.rect(0, 0, self.SLIDE_WIDTH, 8, fill=True, stroke=False)
            c.rect(0, self.SLIDE_HEIGHT - 8, self.SLIDE_WIDTH, 8, fill=True, stroke=False)
        elif slide_type == "cta":
            c.setFillColor(self.primary)
            c.rect(0, 0, self.SLIDE_WIDTH, self.SLIDE_HEIGHT, fill=True, stroke=False)
            c.setFillColor(self.secondary)
            c.rect(self.MARGIN, self.SLIDE_HEIGHT // 2 - 2, self.SLIDE_WIDTH - 2 * self.MARGIN, 4, fill=True, stroke=False)
        else:
            c.setFillColor(self.background)
            c.rect(0, 0, self.SLIDE_WIDTH, self.SLIDE_HEIGHT, fill=True, stroke=False)
            c.setFillColor(self.primary)
            c.rect(0, 0, 8, self.SLIDE_HEIGHT, fill=True, stroke=False)
            c.setFillColor(self.secondary)
            c.rect(0, self.SLIDE_HEIGHT - 4, self.SLIDE_WIDTH, 4, fill=True, stroke=False)

    def _draw_slide_number(self, c: canvas.Canvas, number: int, total: int):
        """Draw slide number indicator."""
        c.setFillColor(HexColor("#999999"))
        c.setFont("Helvetica", 16)
        c.drawRightString(
            self.SLIDE_WIDTH - self.MARGIN,
            self.MARGIN - 30,
            f"{number}/{total}",
        )

    def _wrap_text_to_lines(self, text: str, max_chars: int = 40) -> list[str]:
        """Wrap text to fit slide width."""
        return textwrap.wrap(text, width=max_chars)

    def generate(self, post_data: dict, output_path: str = None) -> str:
        """Generate a carousel PDF from post data.

        Args:
            post_data: Dict with keys 'topic', 'theme', 'post' (containing 'body'),
                       and optionally 'slides' (list of slide content dicts).
            output_path: Optional output file path.

        Returns:
            Path to the generated PDF file.
        """
        if not output_path:
            drafts_dir = BASE_DIR / "posts" / "drafts"
            drafts_dir.mkdir(parents=True, exist_ok=True)
            draft_id = post_data.get("id", "carousel")
            output_path = str(drafts_dir / f"{draft_id}_carousel.pdf")

        slides = self._extract_slides(post_data)

        c = canvas.Canvas(output_path, pagesize=(self.SLIDE_WIDTH, self.SLIDE_HEIGHT))

        # Slide 1: Title
        self._draw_title_slide(c, slides[0] if slides else post_data, len(slides) + 2)
        c.showPage()

        # Content slides
        for i, slide in enumerate(slides[1:], start=2):
            self._draw_content_slide(c, slide, i, len(slides) + 2)
            c.showPage()

        # CTA slide
        self._draw_cta_slide(c, post_data, len(slides) + 2)
        c.showPage()

        c.save()
        logger.info(f"Carousel PDF generated: {output_path}")
        return output_path

    def _extract_slides(self, post_data: dict) -> list[dict]:
        """Extract slide content from post data."""
        if "slides" in post_data:
            return post_data["slides"]

        body = post_data.get("post", {}).get("body", "")
        if not body:
            body = post_data.get("theme", "Commodity Markets Insight")

        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        paragraphs = [p for p in paragraphs if not p.startswith("#")]

        slides = []
        topic = post_data.get("topic", "").replace("_", " ").title()
        theme = post_data.get("theme", topic)

        slides.append({"title": theme, "subtitle": topic})

        for para in paragraphs[:self.num_slides - 2]:
            if len(para) > 200:
                para = para[:197] + "..."
            slides.append({"content": para})

        return slides

    def _draw_title_slide(self, c: canvas.Canvas, slide: dict, total: int):
        """Draw the title slide."""
        self._draw_background(c, "title")

        title = slide.get("title", "Commodity Markets")
        subtitle = slide.get("subtitle", "")

        lines = self._wrap_text_to_lines(title, 25)
        y_start = self.SLIDE_HEIGHT // 2 + (len(lines) * 25)

        c.setFillColor(self.background)
        c.setFont("Helvetica-Bold", 42)
        for i, line in enumerate(lines):
            c.drawCentredString(
                self.SLIDE_WIDTH // 2,
                y_start - i * 55,
                line,
            )

        if subtitle:
            c.setFillColor(self.secondary)
            c.setFont("Helvetica", 22)
            c.drawCentredString(
                self.SLIDE_WIDTH // 2,
                y_start - len(lines) * 55 - 30,
                subtitle,
            )

        self._draw_slide_number(c, 1, total)

    def _draw_content_slide(self, c: canvas.Canvas, slide: dict, number: int, total: int):
        """Draw a content slide."""
        self._draw_background(c, "content")

        content = slide.get("content", "")
        heading = slide.get("heading", "")

        y = self.SLIDE_HEIGHT - self.MARGIN - 60

        if heading:
            c.setFillColor(self.primary)
            c.setFont("Helvetica-Bold", 32)
            for line in self._wrap_text_to_lines(heading, 30):
                c.drawString(self.MARGIN + 20, y, line)
                y -= 42
            y -= 20

        c.setFillColor(self.text_color)
        c.setFont("Helvetica", 26)
        lines = self._wrap_text_to_lines(content, 38)
        for line in lines:
            if y < self.MARGIN + 40:
                break
            c.drawString(self.MARGIN + 20, y, line)
            y -= 36

        self._draw_slide_number(c, number, total)

    def _draw_cta_slide(self, c: canvas.Canvas, post_data: dict, total: int):
        """Draw the call-to-action final slide."""
        self._draw_background(c, "cta")

        c.setFillColor(self.background)
        c.setFont("Helvetica-Bold", 36)
        c.drawCentredString(
            self.SLIDE_WIDTH // 2,
            self.SLIDE_HEIGHT // 2 + 80,
            "What do you think?",
        )

        c.setFillColor(self.secondary)
        c.setFont("Helvetica", 24)
        c.drawCentredString(
            self.SLIDE_WIDTH // 2,
            self.SLIDE_HEIGHT // 2 - 60,
            "Share your perspective in the comments",
        )

        c.setFillColor(HexColor("#AAAAAA"))
        c.setFont("Helvetica", 18)
        c.drawCentredString(
            self.SLIDE_WIDTH // 2,
            self.MARGIN + 40,
            "Follow for more commodity market insights",
        )

        self._draw_slide_number(c, total, total)
