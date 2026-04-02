"""Main CLI entry point — orchestrates the LinkedIn content automation pipeline."""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import click
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler

BASE_DIR = Path(__file__).resolve().parent.parent
console = Console()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, show_path=False)],
)
logger = logging.getLogger("linkedin_automation")


def load_config() -> tuple[dict, dict]:
    """Load settings and content calendar from config files."""
    settings_path = BASE_DIR / "config" / "settings.yaml"
    calendar_path = BASE_DIR / "config" / "content_calendar.yaml"

    with open(settings_path) as f:
        settings = yaml.safe_load(f)
    with open(calendar_path) as f:
        calendar = yaml.safe_load(f)

    return settings, calendar


def create_fusion_orchestrator():
    """Create the multi-AI fusion orchestrator from env vars."""
    from src.ai_engines.fusion import FusionOrchestrator

    return FusionOrchestrator.from_api_keys(
        anthropic_key=os.getenv("ANTHROPIC_API_KEY"),
        openai_key=os.getenv("OPENAI_API_KEY"),
        google_key=os.getenv("GOOGLE_API_KEY"),
        perplexity_key=os.getenv("PERPLEXITY_API_KEY"),
        xai_key=os.getenv("XAI_API_KEY"),
    )


@click.group()
def cli():
    """LinkedIn Commodity Markets Content Automation Tool.

    Generate, review, and publish professional LinkedIn content
    about commodity markets and supply chains.
    """
    load_dotenv(BASE_DIR / ".env")


@cli.command()
@click.option("--topic", default=None, help="Override topic (e.g., crude_oil_and_energy)")
@click.option("--post-type", default=None, help="Override post type (e.g., insight, analysis)")
@click.option("--dry-run", is_flag=True, help="Generate without posting, save to drafts/")
def generate(topic, post_type, dry_run):
    """Generate a new LinkedIn post based on the content calendar."""
    console.print("[bold]Starting content generation pipeline...[/bold]\n")

    settings, calendar = load_config()
    fusion = create_fusion_orchestrator()

    from src.content.researcher import NewsResearcher
    from src.content.formatter import LinkedInFormatter
    from src.content.generator import ContentGenerator

    researcher = NewsResearcher(settings.get("rss_feeds", []))
    formatter = LinkedInFormatter(settings, calendar)
    generator = ContentGenerator(fusion, researcher, formatter, settings, calendar)

    async def run():
        result = await generator.generate(
            topic_override=topic,
            post_type_override=post_type,
        )

        console.print(f"\n[bold green]Draft generated successfully![/bold green]")
        console.print(f"  Draft ID: {result['draft_id']}")
        console.print(f"  Topic: {result['schedule']['topic'].replace('_', ' ').title()}")
        console.print(f"  Type: {result['schedule']['post_type'].replace('_', ' ').title()}")
        console.print(f"  Hook: {result['hook_style'].replace('_', ' ').title()}")
        console.print(f"  Visual: {result['visual_type'].title()}")
        console.print(f"  Tokens used: {result['tokens_used']}")

        # Generate visuals if needed
        visual_type = result["visual_type"]
        if visual_type != "none":
            draft_file = BASE_DIR / "posts" / "drafts" / f"{result['draft_id']}.json"
            with open(draft_file) as f:
                draft_data = json.load(f)

            if visual_type == "carousel":
                from src.visuals.carousel_maker import CarouselMaker
                maker = CarouselMaker(settings.get("visuals", {}))
                pdf_path = maker.generate(draft_data)
                console.print(f"  Carousel: {pdf_path}")
            elif visual_type == "image":
                from src.visuals.image_maker import ImageMaker
                maker = ImageMaker(settings.get("visuals", {}))
                img_path = maker.generate_post_image(draft_data)
                console.print(f"  Image: {img_path}")

        # Generate knowledge briefing
        claude_engine = fusion.engines.get("claude")
        if claude_engine:
            from src.knowledge.briefing import BriefingGenerator
            briefer = BriefingGenerator(claude_engine)
            post_body = result["formatted_post"]["body"]
            briefing_path = await briefer.generate_and_save(
                result["draft_id"],
                post_body,
                result["schedule"]["topic"],
                result.get("research_summary", ""),
            )
            console.print(f"  Briefing: {briefing_path}")

        console.print(f"\n[bold]Run 'python -m src.main review' to approve this post.[/bold]")

    asyncio.run(run())


@cli.command()
def review():
    """Review and approve pending draft posts."""
    from src.cli.review import DraftReviewer

    reviewer = DraftReviewer()
    reviewer.review_all()


@cli.command()
def publish():
    """Publish all approved posts to LinkedIn."""
    console.print("[bold]Publishing approved posts...[/bold]\n")

    approved_dir = BASE_DIR / "posts" / "approved"
    published_dir = BASE_DIR / "posts" / "published"
    published_dir.mkdir(parents=True, exist_ok=True)

    approved_files = list(approved_dir.glob("*.json"))
    if not approved_files:
        console.print("[yellow]No approved posts to publish.[/yellow]")
        return

    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    if not access_token:
        console.print("[red]LINKEDIN_ACCESS_TOKEN not set. Run auth setup first.[/red]")
        return

    from src.linkedin.poster import LinkedInPoster
    from src.linkedin.analytics import LinkedInAnalytics
    from src.learning.tracker import PerformanceTracker

    poster = LinkedInPoster(access_token)
    settings, _ = load_config()
    analytics = LinkedInAnalytics(access_token)
    tracker = PerformanceTracker(analytics, settings)

    async def run():
        for approved_file in approved_files:
            with open(approved_file) as f:
                draft = json.load(f)

            post_body = draft.get("post", {}).get("body", "")
            visual_type = draft.get("visual_type", "none")
            draft_id = draft.get("id", "")

            try:
                if visual_type == "carousel":
                    pdf_path = approved_dir / f"{draft_id}_carousel.pdf"
                    if pdf_path.exists():
                        result = await poster.post_with_document(
                            post_body, str(pdf_path), draft.get("theme", "")
                        )
                    else:
                        result = await poster.post_text(post_body)
                elif visual_type == "image":
                    img_path = approved_dir / f"{draft_id}_image.png"
                    if img_path.exists():
                        result = await poster.post_with_image(post_body, str(img_path))
                    else:
                        result = await poster.post_text(post_body)
                else:
                    result = await poster.post_text(post_body)

                post_id = result.get("id", "")
                console.print(f"[green]Published: {draft_id} -> {post_id}[/green]")

                # Post first comment if available
                first_comment = draft.get("post", {}).get("first_comment")
                if first_comment and post_id:
                    await poster.post_comment(post_id, first_comment)
                    console.print(f"  [dim]First comment posted.[/dim]")

                # Register for tracking
                tracker.register_post(draft, post_id)

                # Move to published
                draft["status"] = "published"
                draft["linkedin_post_id"] = post_id
                pub_file = published_dir / f"{draft_id}.json"
                with open(pub_file, "w") as f:
                    json.dump(draft, f, indent=2)

                # Clean up approved files
                approved_file.unlink()
                for ext in ["_carousel.pdf", "_image.png"]:
                    visual_file = approved_dir / f"{draft_id}{ext}"
                    if visual_file.exists():
                        visual_file.unlink()

            except Exception as e:
                console.print(f"[red]Failed to publish {draft_id}: {e}[/red]")

    asyncio.run(run())


@cli.command()
def analytics():
    """View post performance analytics."""
    from src.learning.tracker import PerformanceTracker
    from src.linkedin.analytics import LinkedInAnalytics

    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    settings, _ = load_config()

    if access_token:
        li_analytics = LinkedInAnalytics(access_token)
        tracker = PerformanceTracker(li_analytics, settings)

        # Update metrics first
        console.print("[dim]Updating metrics...[/dim]")
        asyncio.run(tracker.update_metrics())

        summary = tracker.get_performance_summary()
    else:
        console.print("[yellow]No LinkedIn token. Showing cached data only.[/yellow]")
        from src.learning.tracker import PerformanceTracker, LinkedInAnalytics

        class DummyAnalytics:
            pass

        tracker = PerformanceTracker.__new__(PerformanceTracker)
        tracker.analytics = None
        tracker.intervals = settings.get("learning", {}).get("track_intervals_hours", [24, 48, 168])
        summary = tracker.get_performance_summary()

    console.print(f"\n[bold]Post Performance Summary[/bold]")
    console.print(f"  Total posts tracked: {summary.get('total_posts', 0)}")
    console.print(f"  Average score: {summary.get('average_score', 0)}/100")
    console.print(f"  Average engagement rate: {summary.get('average_engagement_rate', 0)}%")

    best = summary.get("best_post")
    if best:
        console.print(f"\n  [green]Best post:[/green] {best.get('id', '')} (score: {best.get('score', 0)})")

    worst = summary.get("worst_post")
    if worst:
        console.print(f"  [red]Worst post:[/red] {worst.get('id', '')} (score: {worst.get('score', 0)})")


@cli.command()
@click.option("--report", is_flag=True, help="Show learning insights report")
@click.option("--optimize", is_flag=True, help="Run strategy optimization")
def learn(report, optimize):
    """View learning insights and optimize content strategy."""
    from src.learning.analyzer import PerformanceAnalyzer
    from src.learning.optimizer import ContentOptimizer

    settings, _ = load_config()
    analyzer = PerformanceAnalyzer(settings)
    optimizer = ContentOptimizer(analyzer, settings)

    if optimize:
        console.print("[bold]Running content strategy optimization...[/bold]\n")
        report_text = optimizer.format_report()
        console.print(report_text)
    elif report:
        insights = analyzer.analyze()
        if insights.get("status") == "ready":
            console.print(f"\n[bold]Learning Insights[/bold]")
            console.print(f"  Posts analyzed: {insights['posts_analyzed']}")
            console.print(f"  Average score: {insights['average_score']}/100")
            console.print(f"  Trend: {insights['trend'].title()}")
            console.print(f"\n  [bold]Top hooks:[/bold] {', '.join(insights.get('top_performing_hooks', []))}")
            console.print(f"  [bold]Best topics:[/bold] {', '.join(insights.get('best_topics', []))}")
            console.print(f"  [bold]Best formats:[/bold] {', '.join(insights.get('best_visual_types', []))}")

            tips = insights.get("engagement_tips", [])
            if tips:
                console.print(f"\n  [bold]Tips:[/bold]")
                for tip in tips:
                    console.print(f"    {tip}")
        else:
            console.print(f"[yellow]{insights.get('message', 'No insights available yet.')}[/yellow]")
    else:
        console.print("Use --report to view insights or --optimize to run optimization.")


@cli.command()
def setup():
    """Set up LinkedIn OAuth authentication."""
    from src.linkedin.auth import LinkedInAuth

    auth = LinkedInAuth()
    auth.setup_interactive()


if __name__ == "__main__":
    cli()
