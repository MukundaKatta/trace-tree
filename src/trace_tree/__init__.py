"""trace-tree: render an agent JSONL audit log as an ASCII tree.

Quick use::

    from trace_tree import render_file, render_lines, Tree

    print(render_file("runs/audit.jsonl"))

Composable::

    tree = Tree.from_jsonl("runs/audit.jsonl", session_key="session_id")
    print(tree.render(max_depth=10, show_timing=True, show_args=False))
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .parser import Event, parse_file, parse_lines
from .tree import Node, Tree

__all__ = [
    "Event",
    "Node",
    "Tree",
    "parse_file",
    "parse_lines",
    "render_file",
    "render_lines",
    "__version__",
]

__version__ = "0.1.0"


def render_file(
    path: str | Path,
    session_key: str | None = "session_id",
    parent_key: str | None = None,
    max_depth: int = 100,
    show_timing: bool = True,
    show_args: bool = False,
    ascii_only: bool = False,
) -> str:
    """Read a JSONL file and return the rendered tree."""
    tree = Tree.from_jsonl(path, session_key=session_key, parent_key=parent_key)
    return tree.render(
        max_depth=max_depth,
        show_timing=show_timing,
        show_args=show_args,
        ascii_only=ascii_only,
    )


def render_lines(
    lines: Iterable[str],
    session_key: str | None = "session_id",
    parent_key: str | None = None,
    max_depth: int = 100,
    show_timing: bool = True,
    show_args: bool = False,
    ascii_only: bool = False,
) -> str:
    """Same as render_file but for any iterable of JSONL lines (or one big string)."""
    if isinstance(lines, str):
        lines = lines.splitlines()
    tree = Tree.from_lines(lines, session_key=session_key, parent_key=parent_key)
    return tree.render(
        max_depth=max_depth,
        show_timing=show_timing,
        show_args=show_args,
        ascii_only=ascii_only,
    )
