#!/usr/bin/env python3
"""DownloadPilot console/UI helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Tuple

from rich.box import ROUNDED
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

TOOL_NAME = "DownloadPilot"
TOOL_SUBTITLE = "Advanced File Downloader"

BANNER_ART = r"""    ____                      __                ______  _ __      __
   / __ \____ _      ______  / /___  ____ _____/ / __ \(_) /___  / /_
  / / / / __ \ | /| / / __ \/ / __ \/ __ `/ __  / /_/ / / / __ \/ __/
 / /_/ / /_/ / |/ |/ / / / / / /_/ / /_/ / /_/ / ____/ / / /_/ / /_
/_____/\____/|__/|__/_/ /_/_/\____/\__,_/\__,_/_/   /_/_/\____/\__/"""

CUSTOM_THEME = Theme({
    "info": "cyan",
    "warning": "bold yellow",
    "error": "bold red",
    "success": "bold green",
    "title": "bold bright_cyan",
    "subtitle": "italic bright_white",
    "accent": "bold magenta",
    "muted": "dim white",
})

console = Console(theme=CUSTOM_THEME)


def print_tool_header(name: Optional[str] = None, subtitle: Optional[str] = None, icon: str = "◆") -> None:
    """Display a professional ASCII banner with subtitle and version."""
    from .config import load_defaults

    cfg = load_defaults()
    title = name or TOOL_NAME
    sub = subtitle or TOOL_SUBTITLE
    version = str(cfg.get("version", "1.0.0"))
    author = str(cfg.get("author", "MrHacker-X"))

    console.print()
    # Full FIGlet wordmark - this is the banner, not a 2-line label.
    console.print(Text(BANNER_ART, style="bold bright_cyan"))
    meta_line = Text.assemble(
        ("  ", ""),
        (sub, "italic bright_white"),
        ("\n  ", ""),
        (f"v{version}", "bold magenta"),
        ("  ·  ", "dim"),
        (author, "dim"),
    )
    console.print(meta_line)
    width = max((len(ln) for ln in BANNER_ART.splitlines()), default=40)
    console.print(f"  [dim cyan]{'─' * min(width, max(40, console.width - 4))}[/dim cyan]")


def print_success(message: str) -> None:
    console.print("[success]\u2713[/success] " + str(message))


def print_warning(message: str) -> None:
    console.print("[warning]\u26a0[/warning] " + str(message))


def print_error(message: str) -> None:
    console.print("[error]\u2717[/error] " + str(message))


def print_info(message: str) -> None:
    console.print("[info]\u2139[/info] " + str(message))


def handle_keyboard_interrupt() -> int:
    """Clean Ctrl+C / Ctrl+D exit: no traceback, return shell code 130."""
    console.print()
    console.print("[dim]Interrupted - exited safely. (Ctrl+C / Ctrl+D)[/dim]")
    return 130

def format_bytes(size: float) -> str:
    """Format a byte count into a human-readable string."""
    if size < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = 0
    val = float(size)
    while val >= 1024.0 and idx < len(units) - 1:
        val /= 1024.0
        idx += 1
    if idx == 0:
        return f"{int(val)} {units[idx]}"
    return f"{val:.2f} {units[idx]}"


def make_table(
    title: Optional[str],
    columns: Sequence[Tuple[str, str]],
    rows: Optional[Iterable[Sequence[Any]]] = None,
    caption: Optional[str] = None,
) -> Table:
    """Create a styled Rich table. Cell strings may contain Rich markup."""
    table = Table(
        title=title,
        box=ROUNDED,
        header_style="bold bright_cyan",
        border_style="bright_blue",
        caption=caption,
        show_lines=False,
        expand=False,
        pad_edge=False,
    )
    for col_name, col_style in columns:
        table.add_column(col_name, style=col_style, overflow="fold")
    if rows:
        for row in rows:
            table.add_row(*[str(c) if c is not None else "" for c in row])
    return table


def prompt_menu(
    title: str,
    options: Sequence[Tuple[str, str]],
    allow_back: bool = True,
    back_label: str = "Quit",
) -> str:
    """Render a compact numbered menu with short professional labels."""
    console.print()
    console.print(f"  [bold bright_cyan]{title}[/bold bright_cyan]")
    console.print(f"  [dim]{'─' * max(22, len(title))}[/dim]")

    valid_keys: List[str] = []
    for key, desc in options:
        key_s = str(key)
        console.print(
            f"  [bold magenta]\\[{key_s}][/bold magenta]"
            f"  [bright_white]{desc}[/bright_white]"
        )
        valid_keys.append(key_s)

    if allow_back:
        console.print(f"  [dim]\\[0]  {back_label}[/dim]")
        valid_keys.append("0")

    console.print()
    # No default: empty Enter must not auto-select. Validate without dumping [1/2/3...] on the line.
    choice = Prompt.ask(
        "  [bold cyan]Select[/bold cyan]",
        choices=valid_keys,
        show_choices=False,
        show_default=False,
    )
    return choice


def prompt_text(label: str, default: Optional[str] = None, required: bool = True) -> str:
    """Prompt the user for text input (loop until a required value is given)."""
    while True:
        if default is not None:
            val = Prompt.ask(f"[bold cyan]{label}[/bold cyan]", default=default)
        else:
            val = Prompt.ask(f"[bold cyan]{label}[/bold cyan]")
        val = val.strip()
        if val or not required:
            return val


def prompt_confirm(label: str, default: bool = True) -> bool:
    """Prompt the user for a Yes/No confirmation."""
    return Confirm.ask(f"[bold cyan]{label}[/bold cyan]", default=default)


def safe_filename(name: str, default: str = "file") -> str:
    """Sanitize a string into a safe cross-platform filename."""
    cleaned = "".join(c if c.isalnum() or c in "._- " else "_" for c in name).strip()
    cleaned = cleaned.strip(".")
    return cleaned or default


def unique_path(dest: Path) -> Path:
    """Return a non-conflicting path by appending _1, _2 ... numerics if dest exists."""
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    parent = dest.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def show_about_panel() -> None:
    """Premium About screen (box-free): identity, overview, key features, contacts."""
    import textwrap
    from .config import load_defaults

    cfg = load_defaults()
    name = str(cfg.get("name", TOOL_NAME))
    subtitle = str(cfg.get("subtitle", TOOL_SUBTITLE))
    version = str(cfg.get("version", "1.0.0"))
    overview = str(cfg.get("about_overview", ""))
    features = list(cfg.get("about_features", []) or [])
    author = str(cfg.get("author", ""))
    email = str(cfg.get("email", ""))
    website = str(cfg.get("website", ""))
    network = str(cfg.get("network", ""))
    repo = str(cfg.get("homepage", ""))

    console.print()
    console.print(Text.assemble(
        ("  ◆ ", "bold magenta"),
        ("ABOUT", "bold magenta"),
    ))
    console.print(Text.assemble(
        ("  ", ""),
        (name, "bold bright_cyan"),
        ("  \u2014  ", "dim"),
        (subtitle, "italic bright_white"),
        ("  \u2014  ", "dim"),
        (f"v{version}", "bold magenta"),
    ))

    if overview:
        console.print()
        console.print("  [bold bright_cyan]OVERVIEW[/bold bright_cyan]")
        width = max(40, min(88, console.width - 4))
        for line in textwrap.wrap(overview, width=width):
            console.print(f"  [bright_white]{line}[/bright_white]")

    console.print()
    console.print("  [bold bright_cyan]IDENTITY & CONTACTS[/bold bright_cyan]")
    for key, value in (
        ("Version", f"[bold magenta]{version}[/bold magenta]"),
        ("Author", f"[bold]{author}[/bold]"),
        ("GitHub", f"[link={repo}]{repo}[/link]" if repo else repo),
        ("Email", f"[link=mailto:{email}]{email}[/link]" if email else email),
        ("Website", f"[link={website}]{website}[/link]" if website else website),
        ("Network", f"[link={network}]{network}[/link]" if network else network),
    ):
        console.print(f"  [bold bright_white]{key:<9}[/bold bright_white] {value}")

    if features:
        console.print()
        console.print("  [bold bright_cyan]KEY FEATURES[/bold bright_cyan]")
        for i, feature in enumerate(features, 1):
            console.print(f"  [bold magenta]{i}.[/bold magenta] [bright_white]{feature}[/bright_white]")

    console.print()
    console.print(Text(f"  Built & maintained by {author}", "dim italic"))
    console.print()
