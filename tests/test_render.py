"""Render output shape. We assert structure, not exact strings, where the
labels could legitimately change. The branch markers are stable enough to
assert literally.
"""

from __future__ import annotations

from pathlib import Path

from trace_tree import Tree, render_file, render_lines
from trace_tree.parser import Event
from trace_tree.render import fmt_ms, fmt_usd, prefix


def _ev(**kw) -> Event:
    base = {"raw": {}, "kind": "event"}
    base.update(kw)
    return Event(**base)


def test_unicode_box_chars_used_by_default() -> None:
    out = render_lines(
        [
            '{"session_id":"s","kind":"session_open"}',
            '{"session_id":"s","kind":"tool_ok","tool":"charge","usd":1.0}',
            '{"session_id":"s","kind":"session_close"}',
        ]
    )
    assert "├─" in out or "└─" in out


def test_ascii_only_mode_emits_no_unicode_branches() -> None:
    out = render_lines(
        [
            '{"session_id":"s","kind":"open"}',
            '{"session_id":"s","kind":"close"}',
        ],
        ascii_only=True,
    )
    assert "├" not in out
    assert "└" not in out
    assert "+-" in out or "|-" in out


def test_session_root_shows_aggregated_stats_in_brackets() -> None:
    events = [
        _ev(session_id="run1", kind="session_open"),
        _ev(session_id="run1", kind="tool_ok", tool="charge", usd=4.99, latency_ms=850),
    ]
    out = Tree.from_events(events).render()
    assert "run1" in out.splitlines()[0]
    assert "4.99 USD" in out
    assert "1 call" in out
    assert "850 ms" in out


def test_error_renders_as_quoted_child_line() -> None:
    events = [
        _ev(session_id="s", kind="session_open"),
        _ev(session_id="s", kind="egress_denied", url="https://evil/exfil", error="host not in allowlist"),
    ]
    out = Tree.from_events(events).render()
    assert 'error="host not in allowlist"' in out
    assert "url=https://evil/exfil" in out


def test_args_hash_renders_as_child_line() -> None:
    events = [
        _ev(session_id="s", kind="tool_ok", tool="charge", usd=4.99, args_hash="aeff9a9e"),
    ]
    out = Tree.from_events(events).render()
    assert "args_hash=aeff9a9e" in out


def test_render_file_renders_bundled_example() -> None:
    here = Path(__file__).resolve().parents[1] / "examples" / "sample_audit.jsonl"
    out = render_file(here)
    assert "session-abc12" in out
    # last child of session_close should use the branch marker, not a tee.
    assert "└─" in out


def test_max_depth_cuts_off_children() -> None:
    events = [
        _ev(span_id="r", kind="root"),
        _ev(span_id="a", parent_id="r", kind="a", raw={"parent_span_id": "r"}),
        _ev(span_id="b", parent_id="a", kind="b", raw={"parent_span_id": "a"}),
        _ev(span_id="c", parent_id="b", kind="c", raw={"parent_span_id": "b"}),
    ]
    t = Tree.from_events(events, parent_key="parent_span_id")
    # depth 1 shows root + its immediate children
    out_shallow = t.render(max_depth=1, ascii_only=True)
    assert "root" in out_shallow
    assert "c" not in out_shallow
    out_deep = t.render(max_depth=10, ascii_only=True)
    assert "c" in out_deep


def test_fmt_usd_picks_decimals_by_magnitude() -> None:
    assert fmt_usd(0) == "0 USD"
    assert fmt_usd(4.99) == "4.99 USD"
    assert fmt_usd(0.0001) == "0.0001 USD"


def test_fmt_ms_swaps_to_seconds_for_long_durations() -> None:
    assert fmt_ms(None) is None
    assert fmt_ms(12) == "12 ms"
    assert fmt_ms(1500) == "1.50 s"


def test_prefix_uses_blank_under_last_ancestor() -> None:
    # second-level node whose grandparent was a last child should have a
    # blank gutter on the left, not a pipe.
    p = prefix([True], is_last=False, ascii_only=True)
    assert p.startswith("   ")
    p2 = prefix([False], is_last=True, ascii_only=True)
    assert p2.startswith("|")


def test_show_args_inlines_short_args_and_hangs_long_ones() -> None:
    short = [_ev(session_id="s", kind="tool_call", tool="t", args={"x": 1})]
    out_short = Tree.from_events(short).render(show_args=True)
    assert 'args={"x":1}' in out_short

    long_args = {"data": "x" * 200}
    long_events = [_ev(session_id="s", kind="tool_call", tool="t", args=long_args)]
    out_long = Tree.from_events(long_events).render(show_args=True)
    # long args should NOT be inlined on the header line. They should appear
    # on a child line.
    header = out_long.splitlines()[1]
    assert "args=" not in header
    assert "args=" in out_long
