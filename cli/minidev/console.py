from __future__ import annotations

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

NAVY = "#0A1128"
BLUE = "#1E90FF"
YELLOW = "#FFD166"
WHITE = "#F5F5F5"
GREEN = "#7CFC00"
RED = "#FF6B6B"

theme = Theme(
    {
        "bg": f"on {NAVY}",
        "mini.text": WHITE,
        "mini.blue": BLUE,
        "mini.yellow": YELLOW,
        "mini.ok": GREEN,
        "mini.warn": YELLOW,
        "mini.err": RED,
        "mini.dim": "#8EA4B8",
        "mini.box": YELLOW,
    }
)

console = Console(theme=theme)


def title_panel(text: str) -> Panel:
    return Panel(
        f"[mini.yellow]{text}[/]",
        title="[mini.yellow]MiniDev[/]",
        subtitle="[mini.blue]offline coding agent setup[/]",
        border_style="mini.box",
        style="bg",
        box=box.ROUNDED,
        padding=(1, 2),
    )


def status_table(title: str) -> Table:
    table = Table(
        title=f"[mini.yellow]{title}[/]",
        title_justify="left",
        box=box.SIMPLE_HEAVY,
        border_style="mini.box",
        style="bg",
        show_header=False,
        pad_edge=False,
    )
    table.add_column("step", style="mini.text", no_wrap=True)
    table.add_column("status", justify="right", no_wrap=True)
    return table


def ok(label: str) -> str:
    return f"[mini.blue]✓[/] {label}"


def warn(label: str) -> str:
    return f"[mini.yellow]![/] {label}"


def fail(label: str) -> str:
    return f"[mini.err]x[/] {label}"


def badge(text: str, style: str = "mini.ok") -> str:
    return f"[{style}][ {text} ][/]"
