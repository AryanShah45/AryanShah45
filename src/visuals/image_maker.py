"""Branded image generator — creates post images for LinkedIn."""

import logging
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class ImageMaker:
    """Generates branded images for LinkedIn posts.

    Creates professional quote cards and stat highlights with
    consistent branding (navy/gold commodity theme).
    """

    DEFAULT_WIDTH = 1200
    DEFAULT_HEIGHT = 628
    MARGIN = 60

    def __init__(self, brand_config: dict):
        self.colors = brand_config.get("brand_colors", {})
        self.primary = self.colors.get("primary", "#1B365D")
        self.secondary = self.colors.get("secondary", "#C5A572")
        self.background = self.colors.get("background", "#FFFFFF")
        self.text_color = self.colors.get("text", "#2D2D2D")
        self.width = brand_config.get("image_width", self.DEFAULT_WIDTH)
        self.height = brand_config.get("image_height", self.DEFAULT_HEIGHT)

    def _get_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        """Get a font, falling back to default if custom fonts unavailable."""
        try:
            font_name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
            return ImageFont.truetype(font_name, size)
        except (OSError, IOError):
            try:
                font_name = "arial.ttf" if not bold else "arialbd.ttf"
                return ImageFont.truetype(font_name, size)
            except (OSError, IOError):
                return ImageFont.load_default()

    def _hex_to_rgb(self, hex_color: str) -> tuple:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def generate_quote_card(
        self, quote: str, attribution: str = "", output_path: str = None
    ) -> str:
        """Generate a branded quote card image.

        Args:
            quote: The main quote or insight text.
            attribution: Optional attribution line.
            output_path: Optional output file path.

        Returns:
            Path to the generated image.
        """
        img = Image.new("RGB", (self.width, self.height), self._hex_to_rgb(self.primary))
        draw = ImageDraw.Draw(img)

        # Accent bar at top
        draw.rectangle(
            [0, 0, self.width, 6],
            fill=self._hex_to_rgb(self.secondary),
        )

        # Accent bar at bottom
        draw.rectangle(
            [0, self.height - 6, self.width, self.height],
            fill=self._hex_to_rgb(self.secondary),
        )

        # Quote marks
        quote_font = self._get_font(120, bold=True)
        draw.text(
            (self.MARGIN, self.MARGIN - 20),
            "\u201C",
            fill=self._hex_to_rgb(self.secondary),
            font=quote_font,
        )

        # Main quote text
        text_font = self._get_font(36, bold=True)
        wrapped = textwrap.fill(quote, width=40)
        lines = wrapped.split("\n")

        y_start = 140
        line_height = 48
        max_lines = (self.height - y_start - 120) // line_height

        for i, line in enumerate(lines[:max_lines]):
            draw.text(
                (self.MARGIN + 20, y_start + i * line_height),
                line,
                fill=self._hex_to_rgb("#FFFFFF"),
                font=text_font,
            )

        # Attribution
        if attribution:
            attr_font = self._get_font(22)
            draw.text(
                (self.MARGIN + 20, self.height - 80),
                attribution,
                fill=self._hex_to_rgb(self.secondary),
                font=attr_font,
            )

        if not output_path:
            drafts_dir = BASE_DIR / "posts" / "drafts"
            drafts_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(drafts_dir / "quote_card.png")

        img.save(output_path, "PNG", quality=95)
        logger.info(f"Quote card generated: {output_path}")
        return output_path

    def generate_stat_highlight(
        self,
        stat: str,
        description: str,
        context: str = "",
        output_path: str = None,
    ) -> str:
        """Generate a stat highlight image with a big number/stat.

        Args:
            stat: The key statistic (e.g., "+42%", "$85/bbl").
            description: Brief description of what the stat means.
            context: Additional context line.
            output_path: Optional output file path.

        Returns:
            Path to the generated image.
        """
        img = Image.new("RGB", (self.width, self.height), self._hex_to_rgb(self.background))
        draw = ImageDraw.Draw(img)

        # Left accent bar
        draw.rectangle(
            [0, 0, 8, self.height],
            fill=self._hex_to_rgb(self.primary),
        )

        # Bottom accent bar
        draw.rectangle(
            [0, self.height - 4, self.width, self.height],
            fill=self._hex_to_rgb(self.secondary),
        )

        # Big stat number
        stat_font = self._get_font(96, bold=True)
        draw.text(
            (self.MARGIN + 20, self.height // 2 - 120),
            stat,
            fill=self._hex_to_rgb(self.primary),
            font=stat_font,
        )

        # Description
        desc_font = self._get_font(32, bold=True)
        wrapped = textwrap.fill(description, width=35)
        y = self.height // 2 + 20
        for line in wrapped.split("\n")[:3]:
            draw.text(
                (self.MARGIN + 20, y),
                line,
                fill=self._hex_to_rgb(self.text_color),
                font=desc_font,
            )
            y += 42

        # Context
        if context:
            ctx_font = self._get_font(20)
            draw.text(
                (self.MARGIN + 20, self.height - 70),
                context,
                fill=self._hex_to_rgb("#888888"),
                font=ctx_font,
            )

        if not output_path:
            drafts_dir = BASE_DIR / "posts" / "drafts"
            drafts_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(drafts_dir / "stat_highlight.png")

        img.save(output_path, "PNG", quality=95)
        logger.info(f"Stat highlight generated: {output_path}")
        return output_path

    def generate_post_image(self, post_data: dict, output_path: str = None) -> str:
        """Auto-generate the best image type based on post content.

        Args:
            post_data: Dict with post content and metadata.
            output_path: Optional output file path.

        Returns:
            Path to the generated image.
        """
        body = post_data.get("post", {}).get("body", "")
        theme = post_data.get("theme", "")
        topic = post_data.get("topic", "").replace("_", " ").title()

        if not output_path:
            drafts_dir = BASE_DIR / "posts" / "drafts"
            drafts_dir.mkdir(parents=True, exist_ok=True)
            draft_id = post_data.get("id", "image")
            output_path = str(drafts_dir / f"{draft_id}_image.png")

        # Extract the hook (first paragraph) for the quote card
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        hook = paragraphs[0] if paragraphs else theme

        if len(hook) > 150:
            hook = hook[:147] + "..."

        return self.generate_quote_card(
            quote=hook,
            attribution=f"Insights on {topic}",
            output_path=output_path,
        )
