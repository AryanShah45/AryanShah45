"""CLI review interface — approve, edit, or reject pending drafts."""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich.text import Text
from rich.rule import Rule

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DRAFTS_DIR = BASE_DIR / "posts" / "drafts"
APPROVED_DIR = BASE_DIR / "posts" / "approved"
BRIEFINGS_DIR = BASE_DIR / "posts" / "briefings"

console = Console()


class DraftReviewer:
    """Interactive CLI for reviewing and approving content drafts.

    Displays formatted post content, knowledge briefing, and visual
    attachments, then lets the user approve, edit, or reject.
    """

    def __init__(self):
        DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
        APPROVED_DIR.mkdir(parents=True, exist_ok=True)

    def list_drafts(self) -> list[dict]:
        """List all pending drafts."""
        drafts = []
        for draft_file in sorted(DRAFTS_DIR.glob("*.json")):
            try:
                with open(draft_file) as f:
                    data = json.load(f)
                data["_file"] = str(draft_file)
                drafts.append(data)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Skipping invalid draft {draft_file}: {e}")
        return drafts

    def display_draft(self, draft: dict):
        """Display a single draft with rich formatting."""
        console.print()
        console.print(Rule(f"[bold]Draft: {draft.get('id', 'unknown')}[/bold]"))

        # Metadata table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="bold cyan")
        table.add_column()
        table.add_row("Topic", draft.get("topic", "").replace("_", " ").title())
        table.add_row("Post Type", draft.get("post_type", "").replace("_", " ").title())
        table.add_row("Hook Style", draft.get("hook_style", "").replace("_", " ").title())
        table.add_row("Visual", draft.get("visual_type", "none").title())
        table.add_row("Created", draft.get("created_at", "")[:19])

        post = draft.get("post", {})
        metadata = post.get("metadata", {})
        table.add_row("Characters", str(metadata.get("char_count", "N/A")))
        table.add_row("Paragraphs", str(metadata.get("paragraph_count", "N/A")))
        console.print(table)
        console.print()

        # Post body
        body = post.get("body", "No content available.")
        console.print(Panel(
            body,
            title="[bold green]LinkedIn Post[/bold green]",
            border_style="green",
            padding=(1, 2),
        ))

        # Hashtags
        hashtags = post.get("hashtags", [])
        if hashtags:
            console.print(f"  [bold]Hashtags:[/bold] {' '.join(hashtags)}")

        # First comment
        first_comment = post.get("first_comment")
        if first_comment:
            console.print(Panel(
                first_comment,
                title="[bold blue]First Comment (links)[/bold blue]",
                border_style="blue",
                padding=(1, 2),
            ))

        # Visual attachment info
        visual_type = draft.get("visual_type", "none")
        if visual_type != "none":
            draft_id = draft.get("id", "")
            if visual_type == "carousel":
                visual_file = DRAFTS_DIR / f"{draft_id}_carousel.pdf"
            else:
                visual_file = DRAFTS_DIR / f"{draft_id}_image.png"

            if visual_file.exists():
                console.print(f"  [bold]Visual:[/bold] {visual_file}")
            else:
                console.print(f"  [bold yellow]Visual ({visual_type}) not yet generated[/bold yellow]")

        # Briefing
        briefing_file = BRIEFINGS_DIR / f"{draft.get('id', '')}_briefing.md"
        if briefing_file.exists():
            with open(briefing_file) as f:
                briefing_text = f.read()
            console.print(Panel(
                briefing_text,
                title="[bold magenta]Knowledge Briefing[/bold magenta]",
                border_style="magenta",
                padding=(1, 2),
            ))

        # Research summary
        research = draft.get("research_summary", "")
        if research:
            console.print(Panel(
                research[:500],
                title="[bold yellow]Research Summary[/bold yellow]",
                border_style="yellow",
                padding=(1, 2),
            ))

    def review_all(self):
        """Interactive review of all pending drafts."""
        drafts = self.list_drafts()

        if not drafts:
            console.print("[yellow]No pending drafts to review.[/yellow]")
            return

        console.print(f"\n[bold]Found {len(drafts)} pending draft(s)[/bold]\n")

        for i, draft in enumerate(drafts, 1):
            console.print(f"[bold cyan]--- Draft {i} of {len(drafts)} ---[/bold cyan]")
            self.display_draft(draft)
            console.print()

            action = Prompt.ask(
                "[bold]Action[/bold]",
                choices=["approve", "edit", "reject", "skip", "quit"],
                default="skip",
            )

            if action == "approve":
                self._approve_draft(draft)
                console.print("[bold green]Draft approved and moved to approved/[/bold green]")
            elif action == "edit":
                self._edit_draft(draft)
            elif action == "reject":
                self._reject_draft(draft)
                console.print("[bold red]Draft rejected and removed.[/bold red]")
            elif action == "quit":
                console.print("[yellow]Review session ended.[/yellow]")
                break
            else:
                console.print("[dim]Skipped.[/dim]")

    def _approve_draft(self, draft: dict):
        """Move draft to approved directory."""
        draft["status"] = "approved"
        draft["approved_at"] = datetime.now().isoformat()

        approved_file = APPROVED_DIR / f"{draft['id']}.json"
        with open(approved_file, "w") as f:
            json.dump(draft, f, indent=2)

        # Move visual files too
        draft_id = draft.get("id", "")
        for ext in ["_carousel.pdf", "_image.png"]:
            src = DRAFTS_DIR / f"{draft_id}{ext}"
            if src.exists():
                dst = APPROVED_DIR / f"{draft_id}{ext}"
                shutil.move(str(src), str(dst))

        # Remove original draft
        draft_file = Path(draft.get("_file", ""))
        if draft_file.exists():
            draft_file.unlink()

    def _edit_draft(self, draft: dict):
        """Allow user to edit the post body inline."""
        console.print("\n[bold]Enter your edited post body below.[/bold]")
        console.print("[dim]Type your full post, then enter an empty line to finish.[/dim]\n")

        lines = []
        while True:
            try:
                line = input()
                if line == "" and lines and lines[-1] == "":
                    lines.pop()
                    break
                lines.append(line)
            except EOFError:
                break

        if lines:
            new_body = "\n".join(lines)
            draft["post"]["body"] = new_body
            draft["post"]["metadata"]["char_count"] = len(new_body)
            draft["post"]["metadata"]["edited"] = True

            # Save back to draft
            draft_file = Path(draft.get("_file", ""))
            if draft_file.exists():
                with open(draft_file, "w") as f:
                    clean_draft = {k: v for k, v in draft.items() if k != "_file"}
                    json.dump(clean_draft, f, indent=2)

            console.print("[bold green]Draft updated. Review again to approve.[/bold green]")
        else:
            console.print("[yellow]No changes made.[/yellow]")

    def _reject_draft(self, draft: dict):
        """Remove a rejected draft."""
        draft_file = Path(draft.get("_file", ""))
        if draft_file.exists():
            draft_file.unlink()

        # Remove associated visual files
        draft_id = draft.get("id", "")
        for ext in ["_carousel.pdf", "_image.png"]:
            visual_file = DRAFTS_DIR / f"{draft_id}{ext}"
            if visual_file.exists():
                visual_file.unlink()
