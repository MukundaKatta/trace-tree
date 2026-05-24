"""Tree construction: session grouping vs parent chain."""

from __future__ import annotations

from trace_tree import Tree
from trace_tree.parser import Event


def _ev(**kw) -> Event:
    base = {"raw": {}, "kind": "event"}
    base.update(kw)
    return Event(**base)


def test_session_grouping_makes_one_root_per_session() -> None:
    events = [
        _ev(session_id="s1", kind="open"),
        _ev(session_id="s2", kind="open"),
        _ev(session_id="s1", kind="close"),
    ]
    t = Tree.from_events(events, session_key="session_id")
    assert [r.label for r in t.roots] == ["s1", "s2"]
    assert len(t.roots[0].children) == 2
    assert len(t.roots[1].children) == 1


def test_session_grouping_aggregates_usd_and_calls() -> None:
    events = [
        _ev(session_id="s1", kind="session_open"),
        _ev(session_id="s1", kind="tool_ok", tool="charge", usd=4.99, latency_ms=12),
        _ev(session_id="s1", kind="tool_ok", tool="charge", usd=1.0, latency_ms=8),
        _ev(session_id="s1", kind="session_close"),
    ]
    t = Tree.from_events(events, session_key="session_id")
    root = t.roots[0]
    assert round(root.agg_usd, 2) == 5.99
    assert root.agg_calls == 2
    assert root.agg_latency_ms == 20


def test_parent_key_mode_links_children_to_parents() -> None:
    events = [
        _ev(span_id="root", kind="run"),
        _ev(span_id="a", parent_id="root", kind="step_a", raw={"parent_span_id": "root"}),
        _ev(span_id="b", parent_id="a", kind="step_b", raw={"parent_span_id": "a"}),
    ]
    t = Tree.from_events(events, parent_key="parent_span_id")
    assert len(t.roots) == 1
    assert t.roots[0].event.kind == "run"
    assert len(t.roots[0].children) == 1
    assert t.roots[0].children[0].event.kind == "step_a"
    assert t.roots[0].children[0].children[0].event.kind == "step_b"


def test_parent_key_mode_orphans_become_roots() -> None:
    events = [
        _ev(span_id="a", kind="alpha", parent_id="missing", raw={"parent_span_id": "missing"}),
        _ev(span_id="b", kind="beta", raw={}),
    ]
    t = Tree.from_events(events, parent_key="parent_span_id")
    # both alpha and beta should be roots (alpha's parent does not exist)
    assert len(t.roots) == 2


def test_empty_session_id_uses_no_session_bucket() -> None:
    events = [_ev(kind="x")]
    t = Tree.from_events(events, session_key="session_id")
    assert t.roots[0].label == "(no session)"


def test_from_jsonl_uses_bundled_sample(tmp_path) -> None:
    p = tmp_path / "audit.jsonl"
    p.write_text(
        '{"session_id":"s","kind":"session_open"}\n'
        '{"session_id":"s","kind":"tool_ok","tool":"charge","usd":1.0,"extra":{"latency_ms":5}}\n'
        '{"session_id":"s","kind":"session_close"}\n'
    )
    t = Tree.from_jsonl(p)
    assert len(t.roots) == 1
    assert t.roots[0].agg_calls == 1
