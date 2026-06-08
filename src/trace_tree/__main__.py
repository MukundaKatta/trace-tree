"""CLI entry: ``python -m trace_tree path/to/audit.jsonl``.

Flags are kept small. The library exposes the rest of the knobs.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__, render_file


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="trace-tree",
        description="Render an agent JSONL audit log as an ASCII tree.",
    )
    p.add_argument("path", help="Path to a .jsonl audit log file.")
    p.add_argument(
        "--parent-key",
        default=None,
        help="Build a parent-id chain using this field name (e.g. parent_span_id).",
    )
    p.add_argument(
        "--session-key",
        default="session_id",
        help="Group flat events by this field (default: session_id).",
    )
    p.add_argument(
        "--max-depth", type=int, default=100, help="Cap tree depth (default: 100)."
    )
    p.add_argument("--no-timing", action="store_true", help="Hide latency_ms columns.")
    p.add_argument(
        "--show-args",
        action="store_true",
        help="Show inline args (or hang long ones below the node).",
    )
    p.add_argument(
        "--ascii",
        action="store_true",
        help="Use ASCII-only box characters (no unicode).",
    )
    p.add_argument("--version", action="version", version=f"trace-tree {__version__}")
    args = p.parse_args(argv)

    try:
        out = render_file(
            args.path,
            session_key=args.session_key,
            parent_key=args.parent_key,
            max_depth=args.max_depth,
            show_timing=not args.no_timing,
            show_args=args.show_args,
            ascii_only=args.ascii,
        )
    except FileNotFoundError:
        print(f"trace-tree: no such file: {args.path}", file=sys.stderr)
        return 2
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
