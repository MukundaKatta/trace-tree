"""Render the bundled sample agentleash-style audit log.

Run::

    python examples/render_agentleash_audit.py
"""

from __future__ import annotations

from pathlib import Path

from trace_tree import render_file


def main() -> None:
    here = Path(__file__).parent
    sample = here / "sample_audit.jsonl"
    print(render_file(sample))


if __name__ == "__main__":
    main()
